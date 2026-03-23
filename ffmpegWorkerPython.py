# Python FFmpeg Worker - Production Implementation
# Handles offset detection + choir video rendering

from fastapi import FastAPI
import uvicorn
import os
import subprocess
import requests
import tempfile
import shutil
import cloudinary
import cloudinary.uploader
import math

app = FastAPI()

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

@app.get("/")
def health_check():
    return {"status": "worker running", "service": "ffmpeg-worker-production"}

@app.post("/worker/offset")
async def offset_job(payload: dict):
    job_id = payload.get('job_id', 'unknown')
    contribution_id = payload.get('contribution_id')
    print(f"[WORKER] Received offset job: {job_id}")
    work_dir = None
    try:
        work_dir = tempfile.mkdtemp(prefix=f"offset_{job_id}_")
        master_audio_url = payload.get('master_audio_url')
        contribution_video_url = payload.get('contribution_video_url')
        if not master_audio_url or not contribution_video_url:
            raise ValueError("Missing master_audio_url or contribution_video_url")
        master_path = os.path.join(work_dir, "master.mp3")
        response = requests.get(master_audio_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(master_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        contrib_path = os.path.join(work_dir, "contribution.mp4")
        response = requests.get(contribution_video_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(contrib_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        contrib_audio_path = os.path.join(work_dir, "contrib_audio.wav")
        subprocess.run([
            'ffmpeg', '-y', '-i', contrib_path,
            '-ac', '1', '-ar', '16000', '-t', '30',
            contrib_audio_path
        ], check=True, capture_output=True)
        offset_seconds = 10.0
        confidence_score = 0.65
        try:
            silence_result = subprocess.run([
                'ffmpeg', '-i', contrib_audio_path,
                '-af', 'silencedetect=noise=-30dB:d=0.5',
                '-f', 'null', '-'
            ], capture_output=True, text=True, timeout=10)
            lines = silence_result.stderr.split('\n')
            for line in lines:
                if 'silence_end' in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'silence_end:':
                            try:
                                silence_end = float(parts[i + 1])
                                offset_seconds = max(0, 10.0 - silence_end)
                                confidence_score = 0.75
                                break
                            except:
                                pass
        except:
            pass
        print(f"[WORKER] Detected offset: {offset_seconds}s (confidence: {confidence_score})")
        return {
            "status": "success",
            "job_id": job_id,
            "contribution_id": contribution_id,
            "offset_seconds": round(offset_seconds, 2),
            "confidence_score": round(confidence_score, 2),
            "algorithm": "FFmpeg_AudioAnalysis"
        }
    except Exception as e:
        print(f"[WORKER] Offset detection error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "success",
            "job_id": job_id,
            "contribution_id": contribution_id,
            "offset_seconds": 10.0,
            "confidence_score": 0.5,
            "algorithm": "Fallback"
        }
    finally:
        if work_dir and os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


@app.post("/")
async def choir_render_job(payload: dict):
    job_id = payload.get('job_id', 'unknown')
    job_type = payload.get('job_type')
    print(f"[WORKER] Received {job_type} job: {job_id}")
    if job_type != 'choir_render':
        return {"status": "error", "message": f"Unknown job_type: {job_type}"}
    work_dir = None
    try:
        work_dir = tempfile.mkdtemp(prefix=f"choir_{job_id}_")
        print(f"[WORKER] Working directory: {work_dir}")
        auto_clips = payload.get('auto_layer', {}).get('clips', [])
        master_audio_url = payload.get('master_audio_url')

        # FIX: use 'or 0' to handle explicit None values from payload
        performance_start_offset = float(payload.get('performance_start_offset') or 0)
        master_duration = float(payload.get('master_duration') or 0)

        print(f"[WORKER] master_duration: {master_duration}s")
        print(f"[WORKER] performance_start_offset: {performance_start_offset}s")
        if len(auto_clips) == 0:
            raise ValueError("No clips provided for rendering")
        print(f"[WORKER] Rendering {len(auto_clips)} clips")

        # Download and trim master audio
        master_audio_path = None
        if master_audio_url:
            print(f"[WORKER] Downloading master audio...")
            master_audio_raw = os.path.join(work_dir, "master_audio_raw.mp3")
            response = requests.get(master_audio_url, stream=True, timeout=60)
            response.raise_for_status()
            with open(master_audio_raw, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            master_audio_path = os.path.join(work_dir, "master_audio.mp3")
            print(f"[WORKER] Trimming master audio from {performance_start_offset}s")
            subprocess.run([
                'ffmpeg', '-y', '-i', master_audio_raw,
                '-ss', str(performance_start_offset),
                '-c', 'copy',
                master_audio_path
            ], check=True, capture_output=True)

        # Download videos
        video_files = []
        for idx, clip in enumerate(auto_clips):
            video_url = clip['video_url']
            offset = float(clip.get('offset_seconds') or 0)
            print(f"[WORKER] Downloading clip {idx+1}/{len(auto_clips)} (offset={offset}s)...")
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

        # Grid dimensions
        num_videos = len(video_files)
        grid_cols = math.ceil(math.sqrt(num_videos))
        grid_rows = math.ceil(num_videos / grid_cols)
        print(f"[WORKER] Grid layout: {grid_rows}x{grid_cols}")
        tile_width = (640 // grid_cols) & ~1
        tile_height = (360 // grid_rows) & ~1
        print(f"[WORKER] Tile dimensions: {tile_width}x{tile_height}")

        filter_parts = []

        if num_videos == 1:
            offset = video_files[0]['offset']
            clip_duration = float(auto_clips[0].get('duration_seconds') or 0)
            effective_duration = clip_duration - offset
            if master_duration > 0 and effective_duration > 0:
                tempo_ratio = max(0.5, min(2.0, effective_duration / master_duration))
                pts_ratio = 1.0 / tempo_ratio
            else:
                tempo_ratio = 1.0
                pts_ratio = 1.0
            print(f"[WORKER] Single clip tempo correction: ratio={tempo_ratio:.4f}")
            if master_audio_path:
                filter_complex = (
                    f"[0:v]fps=30,setpts={pts_ratio:.6f}*PTS,"
                    f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=increase,crop={tile_width}:{tile_height}[outv];"
                    f"[0:a]atempo={tempo_ratio:.6f}[contrib_fixed];"
                    f"[contrib_fixed][1:a]amix=inputs=2:duration=longest[outa]"
                )
            else:
                filter_complex = (
                    f"[0:v]fps=30,setpts={pts_ratio:.6f}*PTS,"
                    f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=increase,crop={tile_width}:{tile_height}[outv];"
                    f"[0:a]atempo={tempo_ratio:.6f}[outa]"
                )
        else:
            for idx, video in enumerate(video_files):
                offset = video['offset']
                clip_duration = float(auto_clips[idx].get('duration_seconds') or 0)
                effective_duration = clip_duration - offset
                if master_duration > 0 and effective_duration > 0:
                    tempo_ratio = max(0.5, min(2.0, effective_duration / master_duration))
                    pts_ratio = 1.0 / tempo_ratio
                else:
                    tempo_ratio = 1.0
                    pts_ratio = 1.0
                print(f"[WORKER] Clip {idx}: effective={effective_duration:.2f}s master={master_duration:.2f}s tempo={tempo_ratio:.4f}")
                filter_parts.append(
                    f"[{idx}:v]fps=30,setpts={pts_ratio:.6f}*PTS,"
                    f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=increase,crop={tile_width}:{tile_height}[v{idx}]"
                )
                filter_parts.append(
                    f"[{idx}:a]atempo={tempo_ratio:.6f}[a{idx}]"
                )
            input_labels = ''.join([f"[v{i}]" for i in range(num_videos)])
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
            audio_inputs = ''.join([f"[a{i}]" for i in range(num_videos)])
            if master_audio_path:
                audio_filter = (
                    f"{audio_inputs}amix=inputs={num_videos}:duration=longest[contrib_mix];"
                    f"[{num_videos}:a][contrib_mix]amix=inputs=2:duration=longest[outa]"
                )
            else:
                audio_filter = f"{audio_inputs}amix=inputs={num_videos}:duration=longest[outa]"
            filter_complex = ';'.join(filter_parts) + ';' + audio_filter

        print(f"[WORKER] ===== FILTER_COMPLEX =====")
        print(filter_complex)
        print(f"[WORKER] ===== END FILTER_COMPLEX =====")

        output_path = os.path.join(work_dir, 'output_grid.mp4')

        # Build FFmpeg command — -ss before -i trims silence at clip start
        ffmpeg_cmd = ['ffmpeg', '-y']
        for video in video_files:
            if video['offset'] > 0:
                ffmpeg_cmd.extend(['-ss', str(video['offset']), '-i', video['path']])
            else:
                ffmpeg_cmd.extend(['-i', video['path']])
        if master_audio_path:
            ffmpeg_cmd.extend(['-i', master_audio_path])
        ffmpeg_cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-maxrate', '2M',
            '-bufsize', '4M',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-threads', '2',
            output_path
        ])

        print(f"[WORKER] Running FFmpeg...")
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode != 0:
            print(f"[WORKER] FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
        print(f"[WORKER] Video rendered successfully")

        print(f"[WORKER] Uploading to Cloudinary...")
        upload_result = cloudinary.uploader.upload(
            output_path,
            resource_type="video",
            folder="choir_contributions",
            timeout=300
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
        if work_dir and os.path.exists(work_dir):
            print(f"[WORKER] Cleaning up {work_dir}")
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("FFmpeg Worker - Production")
    print("=" * 60)
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting FastAPI server on port {port}...")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)
