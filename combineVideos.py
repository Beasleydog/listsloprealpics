import subprocess
import os
import json
from typing import List


def _has_audio_stream(path: str) -> bool:
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', path
        ], capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        for s in info.get('streams', []):
            if s.get('codec_type') == 'audio':
                return True
        return False
    except Exception:
        # If probe fails, assume it has audio to avoid attempting to synthesize incorrectly
        return True


def combineVideos(video_paths: List[str], output_path: str) -> str:
    """Combine multiple videos into a single video using ffmpeg.
    
    Args:
        video_paths: List of paths to input video files
        output_path: Path where the combined video will be saved
        
    Returns:
        Path to the combined video file
    """
    if not video_paths:
        raise ValueError("video_paths cannot be empty")
    
    # Verify all input files exist
    for path in video_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Video file not found: {path}")
    
    # Normalize paths for cross-platform compatibility
    video_paths = [os.path.normpath(path) for path in video_paths]
    output_path = os.path.normpath(output_path)
    
    # Normalize all inputs to consistent params (video: 1920x1080 30fps yuv420p h264; audio: AAC LC 48kHz stereo)
    # Use absolute path for normalization directory to avoid relative path duplication in concat list
    norm_dir = os.path.abspath(os.path.join(os.path.dirname(output_path) or '.', '__concat_norm__'))
    os.makedirs(norm_dir, exist_ok=True)
    normalized_paths: List[str] = []

    for i, in_path in enumerate(video_paths):
        norm_path = os.path.join(norm_dir, f"{i:04d}.mp4")
        has_audio = _has_audio_stream(in_path)

        if has_audio:
            cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', in_path,
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                '-vsync', 'cfr',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',               # resample to 48k for concat stability
                '-ac', '2',
                '-af', 'aresample=async=1:first_pts=0',
                '-movflags', '+faststart',
                '-y', norm_path
            ]
        else:
            # Add a silent stereo track if missing
            cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', in_path,
                '-f', 'lavfi', '-t', '1', '-i', 'anullsrc=r=48000:cl=stereo',
                '-shortest',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                '-vsync', 'cfr',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',
                '-ac', '2',
                '-movflags', '+faststart',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-y', norm_path
            ]

        print(f"Running ffmpeg command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        normalized_paths.append(norm_path)

    # Create temporary concat file for ffmpeg (absolute path ensures ffmpeg resolves correctly)
    concat_file = os.path.abspath(output_path).replace('.mp4', '_concat.txt')
    
    try:
        # Write concat file with absolute, forward-slashed paths per ffmpeg concat demuxer best practices
        with open(concat_file, 'w') as f:
            for path in normalized_paths:
                abs_path = os.path.abspath(path)
                # ffmpeg on Windows is happier with forward slashes
                abs_path = abs_path.replace('\\', '/')
                f.write(f"file '{abs_path}'\n")
        
        # Concatenate normalized videos; re-encode audio to avoid timestamp gaps
        cmd = [
            'ffmpeg',
            '-hide_banner', '-loglevel', 'error',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',
            '-ac', '2',
            '-af', 'aresample=async=1:first_pts=0',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        print(f"Running ffmpeg command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Print ffmpeg output for debugging
        if result.stdout:
            print(f"FFmpeg stdout: {result.stdout}")
        if result.stderr:
            print(f"FFmpeg stderr: {result.stderr}")
        
        return output_path
        
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg command failed with exit code: {e.returncode}")
        if e.stdout:
            print(f"FFmpeg stdout: {e.stdout}")
        if e.stderr:
            print(f"FFmpeg stderr: {e.stderr}")
        
        raise RuntimeError(f"Failed to combine videos. Exit code: {e.returncode}, stderr: {e.stderr}")
    except Exception as e:
        raise
    finally:
        # Clean up temporary concat file
        if os.path.exists(concat_file):
            os.remove(concat_file)
        # Clean up normalized files
        try:
            for p in normalized_paths:
                if os.path.exists(p):
                    os.remove(p)
            if os.path.isdir(norm_dir) and not os.listdir(norm_dir):
                os.rmdir(norm_dir)
        except Exception:
            pass
