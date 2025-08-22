

from buildShot import buildShot
from getTTS import getTTS
from getTimestamps import get_phrase_timestamps
from getImage import getImage
from getAudioLength import getAudioLength
from overlayAudioVideo import overlayAudioVideo
from overWriteFirstSecondsWithLastFrame import overWriteFirstSecondsWithLastFrame
from combineVideos import combineVideos
from getLastFrame import getLastFrame
from getSubideas import getSubideas
from makeWholeShot import makeWholeShot
from makeAllIdeasImage import zoomintoidea, makeAllIdeasImage
from getMetadata import getMetadata
from upload_video import publish_simple
from makeAndUploadShort import makeAndUploadShort
from image_utils import resize_thumbnail_for_youtube
import os
import re
import requests

def runit(assetspath):
    def check_ideas_and_notify():
        """Check if next_ideas.txt has fewer than 5 ideas and send Discord webhook if needed."""
        next_ideas_file = os.path.join(assetspath, "next_ideas.txt")
        webhook_url = os.getenv('DISCORD_WEBHOOK')
        
        if not webhook_url:
            return  # No webhook configured, skip notification
            
        if os.path.exists(next_ideas_file):
            with open(next_ideas_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if len(lines) < 5:
                try:
                    payload = {
                        "content": f"⚠️ **Low Ideas Alert!** Only {len(lines)} ideas remaining in next_ideas.txt for {assetspath}. Please add more ideas!"
                    }
                    response = requests.post(webhook_url, json=payload)
                    response.raise_for_status()
                    print(f"Discord notification sent: {len(lines)} ideas remaining")
                except Exception as e:
                    print(f"Failed to send Discord notification: {e}")

    def update_default_title():
        next_ideas_file = os.path.join(assetspath, "next_ideas.txt")
        done_ideas_file = os.path.join(assetspath, "done_ideas.txt")
        
        if os.path.exists(next_ideas_file):
            with open(next_ideas_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if lines:
                # Get first line and strip whitespace
                first_line = lines[0].strip()
                
                # Write remaining lines back to next_ideas.txt
                with open(next_ideas_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[1:])
                
                # Append first line to done_ideas.txt
                with open(done_ideas_file, 'a', encoding='utf-8') as f:
                    f.write(first_line + '\n')
                
                return first_line
            else:
                raise Exception("No ideas available in next_ideas.txt")
        else:
            raise Exception("next_ideas.txt file not found")

    video_idea = update_default_title()
    check_ideas_and_notify()

    subideas = getSubideas(video_idea)
    makeAllIdeasImage(subideas, output_path=os.path.join(assetspath, "thumbnail.png"), size=(1920, 1080), background_path=os.path.join(assetspath, "background.png"), font_path=os.path.join(assetspath, "font.ttf"))

    # Resize thumbnail to meet YouTube's requirements
    thumbnail_path = os.path.join(assetspath, "thumbnail.png")
    youtube_thumbnail_path = os.path.join(assetspath, "youtube_thumbnail.jpg")

    if os.path.exists(thumbnail_path):
        try:
            print("Resizing thumbnail for YouTube compliance...")
            resized_thumb_path = resize_thumbnail_for_youtube(
                thumbnail_path,
                youtube_thumbnail_path,
                max_file_size_bytes=2000000,  # 2MB YouTube limit
                target_dimensions=(1280, 720)  # YouTube recommended size
            )
            print(f"Thumbnail resized successfully: {resized_thumb_path}")
            # Use the resized thumbnail for uploading
            thumb_path = resized_thumb_path
        except Exception as e:
            print(f"Failed to resize thumbnail: {e}")
            print("Using original thumbnail...")
            thumb_path = thumbnail_path
    else:
        thumb_path = None

    # Ensure zoom cache directory exists
    zoom_dir = os.path.join("cache", "zooms")
    os.makedirs(zoom_dir, exist_ok=True)

    def _slugify(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")

    # Build sequence: [zoom_to_0, whole_0, zoom_to_1, whole_1, ...]
    segments = []
    for idx, sub in enumerate(subideas):
        subject = sub.get("subject", f"item_{idx}")
        zoom_out = os.path.join(zoom_dir, f"{idx:02d}_{_slugify(subject)}.mp4")
        # Build zoom transition into this subidea from the grid of all items
        zoom_path = zoomintoidea(subideas, idx, zoom_out, size=(1920, 1080), background_path=os.path.join(assetspath, "background.png"), font_path=os.path.join(assetspath, "font.ttf"))
        segments.append(zoom_path)

        # Build the subidea's full shot
        whole_path = makeWholeShot(subject, video_idea, assetspath)
        segments.append(whole_path)

    # Stitch full program
    final_output = os.path.join(assetspath, "final.mp4")
    combineVideos(segments, final_output)


    # --- Generate AI description and keywords, then upload ---
    description, keywords_csv = getMetadata(video_idea, subideas)

    # thumb_path is already set above during thumbnail resizing

    try:
        watch_url = publish_simple(
            title=video_idea,
            file_path=final_output,
            description=description,
            assetspath=assetspath,
            thumbnail_path=thumb_path,
            category="27",  # Education
            keywords=keywords_csv
        )
        print(f"Uploaded: {watch_url}")
    except Exception as e:
        print(f"Upload failed: {e}")

    for i in range(0, min(8, len(segments)), 2):
        makeAndUploadShort(segments[i+1], video_idea, subideas[i//2], assetspath)  