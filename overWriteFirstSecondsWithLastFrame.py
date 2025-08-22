# import subprocess
# import os

# def overWriteFirstSecondsWithLastFrame(modify_path, source_path, duration):
#     """Overwrite the first duration seconds of modify_path video with the last frame of source_path video.
#     Preserves the original audio from modify_path.
    
#     Args:
#         modify_path: Path to the video file to modify (will be overwritten)
#         source_path: Path to the source video to extract last frame from
#         duration: Duration in seconds to overwrite at the beginning
        
#     Returns:
#         Path to the modified video file (same as modify_path)
#     """
#     if not os.path.exists(modify_path):
#         raise FileNotFoundError(f"Modify video file not found: {modify_path}")
#     if not os.path.exists(source_path):
#         raise FileNotFoundError(f"Source video file not found: {source_path}")
    
#     # Duration bounds checking to prevent timing issues
#     if duration <= 0:
#         print(f"Warning: Duration {duration} is <= 0, skipping overwrite")
#         return modify_path
#     if duration < 0.1:
#         print(f"Warning: Duration {duration} is very small, setting to minimum 0.1s")
#         duration = 0.1
    
#     # Normalize paths
#     modify_path = os.path.normpath(modify_path)
#     source_path = os.path.normpath(source_path)
    
#     # Create temporary output file
#     temp_output = modify_path.replace('.mp4', '_temp.mp4')
    
#     try:
#         # Use ffmpeg to:
#         # 1. Extract the last frame from source video and loop it for duration seconds
#         # 2. Take the rest of the modify video after duration seconds  
#         # 3. Concatenate them together
#         # 4. Keep original audio from modify video
#         cmd = [
#             'ffmpeg',
#             '-sseof', '-1',           # Start from 1 second before end
#             '-i', source_path,        # Source video (for last frame)
#             '-i', modify_path,        # Modify video (for audio and remaining video)
#             '-filter_complex',
#             # Reset PTS on both parts to ensure exact alignment and prevent drift
#             f'[0:v]scale=1920:1080,loop=loop=-1:size=1:start=0,trim=duration={duration},setpts=PTS-STARTPTS[firstpart];'
#             f'[1:v]trim=start={duration},setpts=PTS-STARTPTS[secondpart];'
#             f'[firstpart][secondpart]concat=n=2:v=1:a=0,setpts=PTS-STARTPTS[outv];'
#             f'[1:a]asetpts=PTS-STARTPTS[aout]',
#             '-map', '[outv]',         # Use concatenated video
#             '-map', '[aout]',         # Use original audio with reset PTS
#             '-c:v', 'libx264',        # Video codec
#             '-c:a', 'aac',            # Re-encode audio to apply filter
#             '-avoid_negative_ts', 'make_zero',  # Handle timing precision issues
#             '-y',                     # Overwrite output file
#             temp_output
#         ]
        
#         print(f"Running ffmpeg command: {' '.join(cmd)}")
        
#         result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
#         # Print ffmpeg output for debugging
#         if result.stdout:
#             print(f"FFmpeg stdout: {result.stdout}")
#         if result.stderr:
#             print(f"FFmpeg stderr: {result.stderr}")
        
#         # Verify the temp output was created successfully
#         if not os.path.exists(temp_output):
#             raise RuntimeError(f"FFmpeg failed to create output file: {temp_output}")
        
#         # Replace original file with the new one
#         os.replace(temp_output, modify_path)
        
#         print(f"Successfully overwrote first {duration}s of {modify_path} with last frame from {source_path}")
#         return modify_path
        
#     except subprocess.CalledProcessError as e:
#         # Clean up temp file if it exists
#         if os.path.exists(temp_output):
#             os.remove(temp_output)
        
#         print(f"FFmpeg command failed with exit code: {e.returncode}")
#         if e.stdout:
#             print(f"FFmpeg stdout: {e.stdout}")
#         if e.stderr:
#             print(f"FFmpeg stderr: {e.stderr}")
        
#         raise RuntimeError(f"Failed to overwrite video. Exit code: {e.returncode}, stderr: {e.stderr}")
#     except Exception as e:
#         # Clean up temp file if it exists
#         if os.path.exists(temp_output):
#             os.remove(temp_output)
#         raise

import subprocess
import os
from typing import Optional
import cv2  # type: ignore
from getLastFrame import getLastFrame

def overWriteFirstSecondsWithLastFrame(modify_path: str, source_path: str, duration: float, fps: Optional[float] = None) -> str:
    """Overwrite the first N frames (duration * fps) of `modify_path` with the last
    frame of `source_path`, using OpenCV for video, while keeping the original
    audio stream untouched (bitstream-copied).

    Args:
        modify_path: Path to the video we will modify in-place.
        source_path: Path to the source video from which we take the last frame.
        duration: Seconds of the start to overwrite.
        fps: Optional override for FPS to compute how many frames to overwrite.

    Returns:
        The same `modify_path` after modification.
    """
    if not os.path.exists(modify_path):
        raise FileNotFoundError(f"Modify video file not found: {modify_path}")
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source video file not found: {source_path}")

    if duration <= 0:
        return modify_path

    modify_path = os.path.normpath(modify_path)
    source_path = os.path.normpath(source_path)

    # Prepare paths
    root, ext = os.path.splitext(modify_path)
    temp_video_noaudio = f"{root}.__temp_noaudio__{ext or '.mp4'}"
    temp_output = f"{root}.__temp__{ext or '.mp4'}"

    last_frame_png: Optional[str] = None
    cap = None
    writer = None
    try:
        # Open the video to modify to read metadata and frames
        cap = cv2.VideoCapture(modify_path)
        if not cap.isOpened():
            raise RuntimeError("cv2.VideoCapture failed to open modify_path")

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if not video_fps or video_fps <= 0:
            # Fall back to provided fps or a safe default
            video_fps = fps if fps and fps > 0 else 30.0

        total_frames_float = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        total_frames = int(total_frames_float) if total_frames_float and total_frames_float > 0 else None
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            raise RuntimeError("Could not determine video dimensions from modify_path")

        # How many frames to overwrite at the start
        frames_to_overwrite = int(round(duration * float(video_fps)))
        if total_frames is not None:
            frames_to_overwrite = max(0, min(frames_to_overwrite, total_frames))
        if frames_to_overwrite <= 0:
            # Nothing to do
            return modify_path

        # Load the last frame from the source video
        last_frame_png = getLastFrame(source_path)
        hold_img = cv2.imread(last_frame_png, cv2.IMREAD_COLOR)
        if hold_img is None:
            raise RuntimeError("cv2.imread failed to load the last frame PNG")
        if hold_img.shape[1] != width or hold_img.shape[0] != height:
            hold_img = cv2.resize(hold_img, (width, height), interpolation=cv2.INTER_AREA)

        # Write a new temporary video (no audio) using OpenCV
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(temp_video_noaudio, fourcc, video_fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError("cv2.VideoWriter failed to open temp video path")

        # 1) Write the held last-frame for the required number of frames
        for _ in range(frames_to_overwrite):
            writer.write(hold_img)

        # 2) Skip the first N frames in the original video and write the rest
        # Try seeking; if it fails, fall back to reading-and-discarding
        seek_ok = cap.set(cv2.CAP_PROP_POS_FRAMES, frames_to_overwrite)
        if not seek_ok:
            # Fallback: read and discard frames_to_overwrite frames
            dropped = 0
            while dropped < frames_to_overwrite:
                ret, _ = cap.read()
                if not ret:
                    break
                dropped += 1

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame is None:
                break
            # Ensure frame matches output size (just in case)
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            writer.write(frame)

        # Close writer to flush file
        writer.release()
        writer = None
        cap.release()
        cap = None

        # Now mux original audio (untouched) with the new video, re-encoding
        # the video to H.264 to keep codec compatibility across shots.
        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-y",
            "-i", temp_video_noaudio,
            "-i", modify_path,
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", f"{video_fps}",
            "-vsync", "cfr",
            "-preset", "medium",
            "-movflags", "+faststart",
            "-c:a", "copy",
            temp_output,
        ]
        subprocess.run(cmd, check=True, text=True, capture_output=True)
        if not os.path.exists(temp_output):
            raise RuntimeError("FFmpeg did not create the expected output.")

        # Replace original with the muxed output
        os.replace(temp_output, modify_path)

        # Clean up temp video-without-audio
        if os.path.exists(temp_video_noaudio):
            try:
                os.remove(temp_video_noaudio)
            except OSError:
                pass

        return modify_path

    except subprocess.CalledProcessError as e:
        # Clean temp files on failure
        for p in (temp_output, temp_video_noaudio):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise RuntimeError(
            f"FFmpeg failed (exit {e.returncode}).\nSTDERR:\n{e.stderr or ''}"
        )
    finally:
        # Release OpenCV resources if still open
        if writer is not None:
            try:
                writer.release()
            except Exception:
                pass
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        # Clean PNG last frame
        if last_frame_png and os.path.exists(last_frame_png):
            try:
                os.remove(last_frame_png)
            except OSError:
                pass
