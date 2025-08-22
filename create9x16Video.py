import subprocess
import os

def create9x16Video(input_video_path: str, output_path: str) -> str:
    """
    Convert a video to 9:16 aspect ratio with the original video centered
    and a blurred version as the background.
    
    Args:
        input_video_path: Path to the input video file
        output_path: Path where the 9:16 video will be saved
        
    Returns:
        Path to the output 9:16 video file
    """
    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"Input video file not found: {input_video_path}")
    
    # Normalize paths
    input_video_path = os.path.normpath(input_video_path)
    output_path = os.path.normpath(output_path)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # ffmpeg command to create 9:16 video with blurred background
    cmd = [
        'ffmpeg',
        '-hide_banner', '-loglevel', 'error',
        '-i', input_video_path,  # Input video
        '-filter_complex', 
        # Create blurred background that fills 9:16 (1080x1920)
        '[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=50[bg];'
        # Scale original video to fit width while maintaining aspect ratio
        '[0:v]scale=1080:-1[fg];'
        # Overlay the original video centered on the blurred background
        '[bg][fg]overlay=(W-w)/2:(H-h)/2[v]',
        '-map', '[v]',
        '-map', '0:a?',  # Map audio if it exists
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-r', '30',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-ar', '48000',
        '-ac', '2',
        '-movflags', '+faststart',
        '-y',
        output_path
    ]
    
    print(f"Creating 9:16 video: {' '.join(cmd)}")
    
    try:
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
        
        raise RuntimeError(f"Failed to create 9:16 video. Exit code: {e.returncode}, stderr: {e.stderr}")