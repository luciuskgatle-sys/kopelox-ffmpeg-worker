# Python FFmpeg Worker with Librosa — Deploy to Railway
# Docker-ready, processes offset_detection and render jobs

import os
import json
import subprocess
import tempfile
import shutil
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request

try:
    import librosa
except ImportError:
    librosa = None

def download_file(url, path):
    """Download file from URL"""
    urllib.request.urlretrieve(url, path)

def extract_audio(video_path, audio_path):
    """Extract mono audio at 22050Hz using ffmpeg"""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '22050', '-ac', '1',
        '-y', audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg extract failed: {result.stderr}")

def detect_offset_librosa(user_audio_path, master_audio_path):
    """
    Detect audio offset using librosa cross-correlation.
    Returns: (offset_seconds, confidence_score)
    """
    if not librosa:
        raise Exception("librosa not installed")
    
    print("Loading audio files...")
    master, sr = librosa.load(master_audio_path, sr=22050, mono=True)
    user, sr = librosa.load(user_audio_path, sr=22050, mono=True)
    
    print(f"Master: {len(master)} samples, User: {len(user)} samples")
    
    # Cross-correlation
    print("Computing cross-correlation...")
    corr = np.correlate(master, user, mode='full')
    
    # Find peak
    lag = np.argmax(corr) - len(user)
    offset_seconds = lag / sr
    
    # Confidence: normalized correlation peak
    user_energy = np.sqrt(np.mean(user**2))
    master_energy = np.sqrt(np.mean(master**2))
    
    if user_energy > 0 and master_energy > 0:
        confidence = corr.max() / (len(user) * user_energy * master_energy)
        confidence = min(confidence, 1.0)
    else:
        confidence = 0.0
    
    print(f"Offset: {offset_seconds:.2f}s, Confidence: {confidence:.3f}")
    return abs(offset_seconds), confidence

def process_offset_detection(job_contract):
    """Handle offset_detection job"""
    video_url = job_contract.get('video_url')
    master_audio_url = job_contract.get('master_audio_url')
    job_id = job_contract.get('job_id')
    contribution_id = job_contract.get('contribution_id')
    
    if not all([video_url, master_audio_url, job_id]):
        raise Exception("Missing required fields: video_url, master_audio_url, job_id")
    
    tmp_dir = tempfile.mkdtemp(prefix=f'offset_{job_id}_')
    
    try:
        video_path = os.path.join(tmp_dir, 'contribution.mp4')
        master_path = os.path.join(tmp_dir, 'master.wav')
        user_audio_path = os.path.join(tmp_dir, 'user.wav')
        
        print(f"Processing offset job {job_id}...")
        
        print("Downloading video...")
        download_file(video_url, video_path)
        
        print("Downloading master audio...")
        download_file(master_audio_url, master_path)
        
        print("Extracting audio from video...")
        extract_audio(video_path, user_audio_path)
        
        offset_seconds, confidence = detect_offset_librosa(user_audio_path, master_path)
        
        return {
            'success': True,
            'job_id': job_id,
            'contribution_id': contribution_id,
            'job_type': 'offset_detection',
            'offset_seconds': round(offset_seconds, 3),
            'confidence_score': round(confidence, 3),
            'algorithm': 'librosa_crosscorr'
        }
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def process_choir_render(job_contract):
    """Handle choir_render job — mosaic + audio mix"""
    job_id = job_contract.get('job_id')
    choir_id = job_contract.get('choir_id')
    master_audio_url = job_contract.get('master_audio_url')
    auto_layer = job_contract.get('auto_layer', {})
    crowd_layer = job_contract.get('crowd_layer', {})
    layout_config = job_contract.get('layout', {})
    output_config = job_contract.get('output', {})
    
    if not all([job_id, choir_id, master_audio_url]):
        raise Exception("Missing required fields: job_id, choir_id, master_audio_url")
    
    auto_clips = auto_layer.get('clips', [])
    crowd_clips = crowd_layer.get('clips', [])
    
    if not auto_clips:
        raise Exception("No auto clips provided")
    
    tmp_dir = tempfile.mkdtemp(prefix=f'render_{job_id}_')
    
    try:
        print(f"Processing choir render job {job_id}...")
        print(f"Auto clips: {len(auto_clips)}, Crowd clips: {len(crowd_clips)}")
        
        # Download all clips
        clip_paths = {}
        all_clips = auto_clips + crowd_clips
        
        for idx, clip in enumerate(all_clips):
            contribution_id = clip['contribution_id']
            video_url = clip['video_url']
            clip_path = os.path.join(tmp_dir, f'clip_{idx}.mp4')
            
            print(f"Downloading clip {contribution_id}...")
            download_file(video_url, clip_path)
            clip_paths[contribution_id] = {
                'path': clip_path,
                'offset': clip['offset_seconds'],
                'gain': clip.get('gain', 1.0),
                'layer': 'auto' if clip in auto_clips else 'crowd'
            }
        
        # Build FFmpeg mosaic filter
        max_tiles = layout_config.get('max_tiles', 25)
        num_videos = min(len(auto_clips), max_tiles)
        cols = int(np.ceil(np.sqrt(num_videos)))
        rows = int(np.ceil(num_videos / cols))
        
        tile_w = output_config.get('resolution', '1920x1080').split('x')[0]
        tile_h = output_config.get('resolution', '1920x1080').split('x')[1]
        tile_w = int(int(tile_w) / cols)
        tile_h = int(int(tile_h) / rows)
        
        # Create input list for ffmpeg
        inputs = []
        for idx, clip_info in enumerate(clip_paths.values()):
            inputs.append(f"-i {clip_info['path']}")
        
        # Build filter complex for mosaic
        filter_parts = []
        for idx in range(len(auto_clips[:max_tiles])):
            filter_parts.append(f"[{idx}]scale={tile_w}:{tile_h}[v{idx}]")
        
        # Concat tiles
        tile_refs = "".join([f"[v{i}]" for i in range(len(auto_clips[:max_tiles]))])
        filter_parts.append(f"{tile_refs}xstack=inputs={len(auto_clips[:max_tiles])}:layout={cols}x{rows}[out]")
        
        filter_complex = ";".join(filter_parts)
        
        # Audio mix (auto + crowd with effects)
        output_path = os.path.join(tmp_dir, 'choir_render.mp4')
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-map', f'{len(inputs)-1}:a',  # Use last clip audio as base
            '-c:v', output_config.get('codec', 'h264'),
            '-b:v', output_config.get('bitrate', '20M'),
            '-c:a', output_config.get('audio_codec', 'aac'),
            '-ar', str(output_config.get('sample_rate', 48000)),
            '-y',
            output_path
        ]
        
        print(f"Running FFmpeg mosaic render...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg render failed: {result.stderr}")
        
        # For now, return success with local path
        # In production, upload to Cloudinary
        return {
            'success': True,
            'job_id': job_id,
            'choir_id': choir_id,
            'job_type': 'choir_render',
            'auto_clip_count': len(auto_clips),
            'crowd_clip_count': len(crowd_clips),
            'mosaic_layout': f'{cols}x{rows}',
            'output_path': output_path,
            'status': 'render_complete'
        }
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

class WorkerHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'healthy', 'service': 'ffmpeg-worker'}).encode())
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            job_contract = json.loads(body)
            
            job_type = job_contract.get('job_type')
            
            if job_type == 'offset_detection':
                result = process_offset_detection(job_contract)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            elif job_type == 'choir_render':
                result = process_choir_render(job_contract)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Unknown job_type: {job_type}'}).encode())
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def log_message(self, format, *args):
        print(f"[WORKER] {format % args}")

def run_server(port=8000):
    server = HTTPServer(('0.0.0.0', port), WorkerHandler)
    print(f"FFmpeg Librosa Worker listening on port {port}...")
    server.serve_forever()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    run_server(port)
