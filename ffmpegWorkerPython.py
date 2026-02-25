# Python FFmpeg Worker - Production Implementation
# Handles offset detection + choir video rendering

from fastapi import FastAPI, HTTPException
import uvicorn
import os
import subprocess
import requests
import tempfile
import shutil
from pathlib import Path
import cloudinary
import cloudinary.uploader
import math

app = FastAPI()

# Cloudinary configuration from environment
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {"status": "worker running", "service": "ffmpeg-worker-production"}

@app.post("/worker/offset")
async def offset_job(payload: dict):
    """Offset detection endpoint - TEMP dummy response for pipeline validation"""
    print("[WORKER] Received offset job:", payload.get('job_id', 'unknown'))
    
    # TEMP: dummy return to confirm pipeline works
    # No actual processing yet - infrastructure validation only
    return {
        "status": "success",
        "job_id": payload.get('job_id'),
        "contribution_id": payload.get('contribution_id'),
        "offset_seconds": 0.0,
        "confidence_score": 1.0,
        "algorithm": "PIPELINE_TEST"
    }

@app.post("/")
async def choir_render_job(payload: dict):
    """Choir video rendering endpoint - creates synchronized grid video"""
    job_id = payload.get('job_id', 'unknown')
    job_type = payload.get('job_type')
    
    print(f"[WORKER] Received {job_type} job: {job_id}")
    
    if job_type != 'choir_render':
        return {"status": "error", "message": f"Unknown job_type: {job_type}"}
    
    work_dir = None
    
    try:
        # Create temporary working directory
        work_dir = tempfile.mkdtemp(prefix=f"choir_{job_id}_")
        print(f"[WORKER] Working directory: {work_dir}")
        
        # Extract job parameters
        auto_clips = payload.get('auto_layer', {}).get('clips', [])
        layout = payload.get('layout', {})
        output_config = payload.get('output', {})
        
        if len(auto_clips) == 0:
            raise ValueError("No clips provided for rendering")
        
        print(f"[WORKER] Rendering {len(auto_clips)} clips")
        
        # Download videos
        video_files = []
        for idx, clip in enumerate(auto_clips):
            video_url = clip['video_url']
            offset = clip.get('offset_seconds', 0)
            
            print(f"[WORKER] Downloading clip {idx+1}/{len(auto_clips)}...")
            
            video_path = os.path.join(work_dir, f"input_{idx}.mp4")
            
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            video_files.append({
                'path': video_path,
                'offset': offset,
                'index': idx
            })
        
        # Calculate grid dimensions
        num_videos = len(video_files)
        grid_cols = math.ceil(math.sqrt(num_videos))
        grid_rows = math.ceil(num_videos / grid_cols)
        
        print(f"[WORKER] Grid layout: {grid_rows}x{grid_cols}")
        
        # Build FFmpeg filter for grid layout
        filter_parts = []
        
        # Use smaller resolution to reduce memory usage on Render free tier
        # Ensure dimensions are even (required by libx264)
        tile_width = (640 // grid_cols) & ~1  # Round down to nearest even number
        tile_height = (360 // grid_rows) & ~1  # Round down to nearest even number
        
        print(f"[WORKER] Using tile dimensions: {tile_width}x{tile_height}")
        
        for idx, video in enumerate(video_files):
            print(f"[DEBUG] Processing video {idx}")
            offset = video['offset']
            # Scale with aspect ratio preservation, then force even dimensions
            filter_parts.append(
                f"[{idx}:v]trim=start={offset},setpts=PTS-STARTPTS,"
                f"fps=30,"
                f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=decrease,"
                f"scale=trunc(iw/2)*2:trunc(ih/2)*2[v{idx}]"
            )
            # Extract and trim audio
            filter_parts.append(
                f"[{idx}:a]atrim=start={offset},asetpts=PTS-STARTPTS[a{idx}]"
            )
        
        # Create grid using xstack
        input_labels = ''.join([f"[v{i}]" for i in range(num_videos)])
        
        # Build xstack layout
        xstack_layout = ''
        for row in range(grid_rows):
            for col in range(grid_cols):
                idx = row * grid_cols + col
                if idx < num_videos:
                    x_pos = col * tile_width
                    y_pos = row * tile_height
                    if xstack_layout:
                        xstack_layout += '|'
                    xstack_layout += f"{x_pos}_{y_pos}"
        
        filter_parts.append(
            f"{input_labels}xstack=inputs={num_videos}:layout={xstack_layout}[outv]"
        )
        
        # Combine audio (mix all prepared tracks)
        audio_inputs = ''.join([f"[a{i}]" for i in range(num_videos)])
        audio_filter = f"{audio_inputs}amix=inputs={num_videos}:duration=longest[outa]"
        
        filter_complex = ';'.join(filter_parts) + ';' + audio_filter
        
        # DEBUG: Print the actual filter_complex being sent to FFmpeg
        print(f"[WORKER] ===== FILTER_COMPLEX =====")
        print(filter_complex)
        print(f"[WORKER] ===== END FILTER_COMPLEX =====")
        
        # Output file
        output_path = os.path.join(work_dir, 'output_grid.mp4')
        
        # Build FFmpeg command
        ffmpeg_cmd = ['ffmpeg', '-y']
        
        # Add all input files
        for video in video_files:
            ffmpeg_cmd.extend(['-i', video['path']])
        
        # Add filters with memory-efficient encoding
        ffmpeg_cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',  # Fastest encoding to reduce memory
            '-crf', '28',  # Lower quality but much faster
            '-maxrate', '2M',
            '-bufsize', '4M',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-t', '60',  # Limit to 60 seconds
            '-threads', '2',  # Limit CPU threads
            output_path
        ])
        
        print(f"[WORKER] Running FFmpeg...")
        
        # Run FFmpeg
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            print(f"[WORKER] FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
        
        print(f"[WORKER] Video rendered successfully")
        
        # Upload to Cloudinary
        print(f"[WORKER] Uploading to Cloudinary...")
        
        upload_result = cloudinary.uploader.upload(
            output_path,
            resource_type="video",
            folder="choir_contributions",
            timeout=180
        )
        
        video_url = upload_result['secure_url']
        
        print(f"[WORKER] Upload complete: {video_url}")
        
        return {
            "status": "success",
            "job_id": job_id,
            "output_video_url": video_url,
            "video_url": video_url,
            "clip_count": num_videos,
            "grid_layout": f"{grid_rows}x{grid_cols}"
        }
        
    except Exception as e:
        print(f"[WORKER] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e)
        }
    
    finally:
        # Cleanup
        if work_dir and os.path.exists(work_dir):
            print(f"[WORKER] Cleaning up {work_dir}")
            shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    print("=" * 60)
    print("FFmpeg Worker - Production")
    print("=" * 60)
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting FastAPI server on port {port}...")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)
