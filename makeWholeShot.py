import json
import re
import os
import hashlib
import shutil
from gemini import ask_gemini  # Assuming this exists based on context
from buildShot import buildShot
from getTTS import getTTS
from getTimestamps import get_phrase_timestamps
from getImage import getImage
from getAudioLength import getAudioLength
from overlayAudioVideo import overlayAudioVideo
from overWriteFirstSecondsWithLastFrame import overWriteFirstSecondsWithLastFrame
from combineVideos import combineVideos
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = "cache/wholeshot"
os.makedirs(CACHE_DIR, exist_ok=True)

# Extra silence to append to the very end of the whole shot (seconds)
WHOLE_SHOT_END_SILENCE_SECONDS = 0.5

def _cache_path(concept, larger_video):
    key_src = f"{concept}|{larger_video}".encode("utf-8")
    return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp4")

VO_PLAN="""Write a one minute long VO script for the following concept in the context of the larger video.
Concept: {concept}
Larger Video: {larger_video}

Output just a single standalone paragraph, don't use continueing language like "next up".
Explain plainly without overly verbose word choice, but make it interesting. Use examples to help the viewer understand.
This will just be a subsection of the larger video, so don't explain the larger video idea but rather explain JUST the concept.

NEVER EVER START A SENTENCE WITH A ACRONYM"""

MAKE_MEDIA="""Break this script down into shots and build the media for each shot.
You should return an array of shot objects.
Shot objects should be the following:
{{
vo:"the EXACT portion of the full vo that should be aligned with this shot",
media:[
an array of media objects
]
}}
Use media objects to represent all the key concepts in each shot.
Media objects can either be text or images.
Text objects should be the following
{{
text:"just the text",
appearAt:"the EXACT text from the shot's VO that should trigger the text to show"
}}
Image objects should be the following
{{
imageSearch"a search that could be put into google images to find the desired images",
goal:"the goal of the image, what it should convey (to help the editor search and pick the best image)",
caption:"an optional param, a text snippet that will be directly below the image",
appearAt:"the EXACT text from the shot's VO that should trigger the image to show"
}}
Never use graphs or charts for an image.

Full VO to be broken down into shots:
{vo}"""


# Parse the response flexibly - look for JSON in markdown blocks or plain text
def parse_json_response(response):
    # First try to find JSON in markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON array in the response without markdown
    json_match = re.search(r'(\[.*?\])', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # If no JSON found, raise an error
    raise ValueError(f"Could not parse JSON from response: {response}")

def makeWholeShot(concept, larger_video, assetspath: str = "."):
    concept = concept.strip()
    larger_video = larger_video.strip()
    if not concept or not larger_video:
        raise ValueError("makeWholeShot: concept and larger_video cannot be empty.")

    print(f"WholeShot: Processing concept: {concept[:80]!r}...")  # trim for logs

    cache_path = _cache_path(concept, larger_video)
    
    if os.path.exists(cache_path):
        return cache_path

    vo_plan = VO_PLAN.format(concept=concept, larger_video=larger_video)
    vo_script = ask_gemini(vo_plan,model="gemini-2.5-pro")
    
    make_media = MAKE_MEDIA.format(vo=vo_script)
    make_media_response = ask_gemini(make_media,model="gemini-2.5-pro")
    media_plan = parse_json_response(make_media_response)

    
    # Pre-cache all images up front and in parallel so later calls are fast
    # Build unique list of (imageSearch, goal) pairs
    image_jobs = []
    for shot in media_plan:
        for media in shot.get("media", []):
            if "text" in media:
                continue
            search = media.get("imageSearch")
            goal = media.get("goal")
            if not search or not goal:
                continue
            image_jobs.append((search, goal))

    # Deduplicate while preserving order
    unique_image_jobs = list(dict.fromkeys(image_jobs))

    pre_cached_images = {}
    if unique_image_jobs:
        max_workers = min(8, len(unique_image_jobs))

        def _cache_one(job):
            s, g = job
            try:
                path = getImage(s, g)
                return job, path
            except Exception as e:
                print(f"Pre-cache getImage failed for {s!r}: {e}")
                return job, None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_cache_one, job) for job in unique_image_jobs]
            for fut in as_completed(futures):
                job, path = fut.result()
                if path:
                    pre_cached_images[job] = path
    SHOT_SWITCH_TIME_PADDING = 0.5

    shot_paths= []

    

    for i in range(len(media_plan)):
        vo_tts = getTTS(media_plan[i]["vo"], voice="Liam", previous_text=media_plan[i-1]["vo"] if i>0 else None)
        media_timestamps_map = get_phrase_timestamps([x["appearAt"] for x in media_plan[i]["media"]], vo_tts)

        clean_media=[]
        for media in media_plan[i]["media"]:
            if "text" in media:
                clean_media.append({
                    "text": media["text"],
                    "appearAt": media_timestamps_map[media["appearAt"]],
                })
            else:
                key = (media.get("imageSearch"), media.get("goal"))
                img_path = pre_cached_images.get(key)
                if not img_path:
                    img_path = getImage(media["imageSearch"], media["goal"])  # fallback (cache miss)
                clean_media.append({
                    "path": img_path,
                    "appearAt": media_timestamps_map[media["appearAt"]],
                })

        # Base duration equals the TTS audio length plus the original 1s hold; add extra end silence only for the final shot
        duration_seconds = getAudioLength(vo_tts) + 1
        if i == len(media_plan) - 1:
            duration_seconds += WHOLE_SHOT_END_SILENCE_SECONDS
        shot_path = buildShot(clean_media, duration_seconds, 
                             font_path=os.path.join(assetspath, "font.ttf"),
                             background_path=os.path.join(assetspath, "background.png"))
        if i == len(media_plan) - 1:
            overlayAudioVideo(shot_path, vo_tts, trim_to_shortest=False)
        else:
            overlayAudioVideo(shot_path, vo_tts)

        if i>0: 
            firstMediaTimestamp = min(media_timestamps_map.values())
            overWriteFirstSecondsWithLastFrame(shot_path, shot_paths[-1], firstMediaTimestamp-SHOT_SWITCH_TIME_PADDING)
        shot_paths.append(shot_path)

    # Generate temporary output path
    temp_output = "temp_output.mp4"
    combineVideos(shot_paths, temp_output)
    
    # Copy to cache
    shutil.copy2(temp_output, cache_path)
    
    # Clean up temporary file
    os.remove(temp_output)

    return cache_path