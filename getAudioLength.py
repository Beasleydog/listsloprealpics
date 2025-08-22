import subprocess
import json

def getAudioLength(audio_path: str) -> float:
    """Get the length of an audio file in seconds using ffmpeg.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Duration in seconds as a float
    """
    try:
        result = subprocess.run([
            'ffprobe', 
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            audio_path
        ], capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        raise RuntimeError(f"Failed to get audio length for {audio_path}: {e}")
