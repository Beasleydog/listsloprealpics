import subprocess
import os

def overlayAudioVideo(video_path: str, audio_path: str, trim_to_shortest: bool = True) -> str:
    """Overlay audio directly on video using ffmpeg, overwriting the original video file.
    
    Args:
        video_path: Path to the input video file (will be overwritten)
        audio_path: Path to the input audio file
        trim_to_shortest: If True, output stops at the end of the shorter stream. If False,
            output continues to the longest stream (commonly the video), leaving silence after audio ends.
        
    Returns:
        Path to the video file (same as input)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    # Normalize paths for cross-platform compatibility
    video_path = os.path.normpath(video_path)
    audio_path = os.path.normpath(audio_path)
    
    # Create temporary output file with proper mp4 extension
    temp_output = video_path.replace('.mp4', '_temp.mp4')
    
    try:
        # Overlay TTS audio on the shot video. Resample with timestamp correction
        # to avoid any speed/pitch issues, and make mappings explicit.
        cmd = [
            'ffmpeg',
            '-hide_banner', '-loglevel', 'error',
            '-i', video_path,
            '-i', audio_path,
            '-map', '0:v:0?',          # first input video
            '-map', '1:a:0?',          # second input audio
            '-c:v', 'copy',            # keep video as-is
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',            # standard video sample rate
            '-ac', '2',
            '-af', 'aresample=async=1:first_pts=0',  # fix timestamps & resample
        ]

        if trim_to_shortest:
            cmd.append('-shortest')

        cmd += [
            '-movflags', '+faststart',
            '-f', 'mp4',
            '-y',                      # overwrite
            temp_output
        ]
        
        print(f"Running ffmpeg command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Print ffmpeg output for debugging
        if result.stdout:
            print(f"FFmpeg stdout: {result.stdout}")
        if result.stderr:
            print(f"FFmpeg stderr: {result.stderr}")
        
        # Replace original file with the new one
        os.replace(temp_output, video_path)
        
        return video_path
    except subprocess.CalledProcessError as e:
        # Clean up temp file if it exists
        if os.path.exists(temp_output):
            os.remove(temp_output)
        
        # Print detailed error information
        print(f"FFmpeg command failed with exit code: {e.returncode}")
        if e.stdout:
            print(f"FFmpeg stdout: {e.stdout}")
        if e.stderr:
            print(f"FFmpeg stderr: {e.stderr}")
        
        raise RuntimeError(f"Failed to overlay audio on video. Exit code: {e.returncode}, stderr: {e.stderr}")
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(temp_output):
            os.remove(temp_output)
        raise


