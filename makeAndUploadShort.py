from combineVideos import combineVideos
from create9x16Video import create9x16Video
from captions import add_tiktok_captions
from getTTS import getTTS
from upload_video import publish_short

import os
import re
import subprocess

def createEndClip(image_path: str, tts_text: str, output_path: str, voice: str = "Liam") -> str:
    """
    Create a video clip from a 9:16 image with TTS audio.
    
    Args:
        image_path: Path to the 9:16 image (shortend.png)
        tts_text: Text to convert to speech
        output_path: Path for the output video clip
        voice: Voice to use for TTS
    
    Returns:
        Path to the created video clip
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Generate TTS audio
    print(f"Generating TTS for: '{tts_text}'")
    audio_path = getTTS(tts_text, voice=voice)
    
    # Get audio duration to match video length
    duration_cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
    ]
    
    try:
        result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
        audio_duration = float(result.stdout.strip())
    except Exception as e:
        print(f"Could not get audio duration, using default 3 seconds: {e}")
        audio_duration = 3.0
    
    # Create output directory if needed
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Create video from image + audio
    cmd = [
        'ffmpeg',
        '-hide_banner', '-loglevel', 'error',
        '-loop', '1',
        '-i', image_path,
        '-i', audio_path,
        '-c:v', 'libx264',
        '-t', str(audio_duration),
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-shortest',
        '-y',
        output_path
    ]
    
    print(f"Creating end clip: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stderr:
            print(f"FFmpeg stderr: {result.stderr}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"End clip creation failed: {e.returncode}, stderr: {e.stderr}")
        raise RuntimeError(f"Failed to create end clip: {e.stderr}")

def speedUpVideo(input_path: str, output_path: str, speed_multiplier: float = 1.2) -> str:
    """
    Speed up a video by the given multiplier while preserving audio pitch.
    
    Args:
        input_path: Path to input video
        output_path: Path for output video
        speed_multiplier: Speed factor (e.g., 1.2 = 20% faster, 1.5 = 50% faster)
    
    Returns:
        Path to the sped-up video
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")
    
    # Create output directory if needed
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # ffmpeg command to speed up video and audio while preserving pitch
    cmd = [
        'ffmpeg',
        '-hide_banner', '-loglevel', 'error',
        '-i', input_path,
        '-filter_complex',
        f'[0:v]setpts=PTS/{speed_multiplier}[v];[0:a]atempo={speed_multiplier}[a]',
        '-map', '[v]',
        '-map', '[a]',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-y',
        output_path
    ]
    
    print(f"Speeding up video by {speed_multiplier}x: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stderr:
            print(f"FFmpeg stderr: {result.stderr}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Speed adjustment failed: {e.returncode}, stderr: {e.stderr}")
        raise RuntimeError(f"Failed to speed up video: {e.stderr}")

def makeAndUploadShort(segment, video_idea, subidea, assetspath, speed_multiplier: float = 2):
    print(f"Processing segment: {segment} (speed: {speed_multiplier}x)")
    
    # Create 9:16 format video with blurred background
    segment_id = os.path.splitext(os.path.basename(segment))[0]
    temp_9x16_filename = f"temp_9x16_{segment_id}.mp4"
    temp_9x16_path = os.path.join("cache", "shorts", temp_9x16_filename)
    
    # Ensure shorts directory exists
    os.makedirs(os.path.dirname(temp_9x16_path), exist_ok=True)
    
    # Step 1: Convert to 9:16 format
    nine_sixteen_video = create9x16Video(segment, temp_9x16_path)
    print(f"Created 9:16 video: {nine_sixteen_video}")
    
    # Step 2: Create end clip with shortend.png + TTS
    segment_id = os.path.splitext(os.path.basename(segment))[0]
    end_clip_filename = f"temp_endclip_{segment_id}.mp4"
    end_clip_path = os.path.join("cache", "shorts", end_clip_filename)
    
    end_clip = createEndClip(os.path.join(assetspath, "shortend.png"), "check out the full video on our channel now", end_clip_path)
    print(f"Created end clip: {end_clip}")
    
    # Step 3: Combine main video with end clip
    combined_filename = f"temp_combined_{segment_id}.mp4"
    combined_path = os.path.join("cache", "shorts", combined_filename)
    
    combined_video = combineVideos([nine_sixteen_video, end_clip], combined_path)
    print(f"Combined main video with end clip: {combined_video}")

    # Step 4: Add TikTok-style captions
    temp_captioned_filename = f"temp_captions_{segment_id}.mp4"
    temp_captioned_path = os.path.join("cache", "shorts", temp_captioned_filename)
    
    captioned_video = add_tiktok_captions(combined_video, temp_captioned_path, font_path=os.path.join(assetspath, "font.ttf"))
    print(f"Added captions to video: {captioned_video}")
    
    # Step 5: Speed up the final video
    final_filename = f"short_9x16_captions_speed{speed_multiplier}x_{segment_id}.mp4"
    final_output_path = os.path.join("cache", "shorts", final_filename)
    
    final_video = speedUpVideo(captioned_video, final_output_path, speed_multiplier)
    print(f"Sped up video by {speed_multiplier}x: {final_video}")
    
    # Clean up temporary files
    temp_files = [temp_9x16_path, end_clip_path, combined_path, temp_captioned_path]
    for temp_file in temp_files:
        if os.path.exists(temp_file) and temp_file != final_video:
            os.remove(temp_file)
            print(f"Cleaned up temporary file: {temp_file}")
    
    # Build a safe, concise YouTube title (<= 100 chars, non-empty)
    def _sanitize(text: str) -> str:
        # Collapse whitespace and remove control chars
        text = re.sub(r"\s+", " ", text or "").strip()
        text = re.sub(r"[\x00-\x1F\x7F]", "", text)
        return text

    def _truncate(text: str, max_len: int = 100) -> str:
        if len(text) <= max_len:
            return text
        # leave room for ellipsis
        cut = max_len - 1
        return text[:cut].rstrip() + "…"

    title_subject = subidea.get("subject", str(subidea)) if isinstance(subidea, dict) else str(subidea)
    raw_title = f"{_sanitize(str(video_idea))} - { _sanitize(str(title_subject)) }"
    safe_title = _truncate(_sanitize(raw_title), 100)
    if not safe_title:
        safe_title = "Cool Short"

    publish_short(
        title=safe_title,
        file_path=final_video,
        assetspath=assetspath,
        base_description="Check out the full video on our channel now!"
    )
