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

Output just a single standalone paragraph, don't use continuing language like "next up".
Explain plainly without overly verbose word choice, but make it interesting. Use examples to help the viewer understand.
This will just be a subsection of the larger video, so don't explain the larger video idea but rather explain JUST the concept.

NEVER EVER START A SENTENCE WITH A ACRONYM"""

MAKE_MEDIA="""Break the VO into an array of shot objects. Output JSON ONLY (no prose, no markdown): an array of shots.

Each shot object MUST be:
{
  "vo": "the EXACT portion of the full VO aligned with this shot",
  "media": [ media objects ]
}

Media object types:
- Text:
  { "text": "just the text", "appearAt": "EXACT substring from the shot's VO that triggers the text" }
- Image:
  { "imageSearch": "query for Google Images", "goal": "what the image should convey", "appearAt": "EXACT substring from the shot's VO", "caption": "optional" }

Rules:
- Every media object MUST include a non-empty "appearAt".
- Do NOT include graphs or charts.
- Return compact, valid JSON array ONLY.

Full VO to be broken down into shots:
{vo}"""


# Parse the response flexibly - look for JSON in markdown blocks or plain text
def parse_json_response(response):
    # 1) Try direct parse
    try:
        obj = json.loads(response)
        normalized = _normalize_media_plan_container(obj)
        if normalized is not None:
            return normalized
    except Exception:
        pass

    # 2) Try code-fenced blocks (prefer the largest)
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if blocks:
        blocks.sort(key=len, reverse=True)
        for blk in blocks:
            try:
                obj = json.loads(blk)
                normalized = _normalize_media_plan_container(obj)
                if normalized is not None:
                    return normalized
            except Exception:
                continue

    # 3) Extract top-level JSON arrays by bracket-depth scanning
    for candidate in _extract_json_arrays(response):
        try:
            obj = json.loads(candidate)
            normalized = _normalize_media_plan_container(obj)
            if normalized is not None:
                return normalized
        except Exception:
            continue

    # If no JSON found, raise an error with trimmed preview
    preview = response[:2000]
    raise ValueError(f"Could not parse JSON from response (preview): {preview}")

def _normalize_media_plan_container(obj):
    # If already a list, accept
    if isinstance(obj, list):
        return obj
    # If dict with a shots-like array, extract
    if isinstance(obj, dict):
        for key in ("shots", "data", "result", "plan", "media_plan"):
            val = obj.get(key)
            if isinstance(val, list):
                return val
        # Single-shot dict fallback
        if _is_non_empty_string(obj.get("vo")) and isinstance(obj.get("media"), list):
            return [obj]
    return None

def _extract_json_arrays(text: str):
    arrays = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == '[':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ']':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        arrays.append(text[start:i+1])
                        start = -1
    return arrays

def _is_non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""

def _validate_media_item(item):
    if not isinstance(item, dict):
        return False
    if "text" in item:
        return _is_non_empty_string(item.get("text")) and _is_non_empty_string(item.get("appearAt"))
    return (
        _is_non_empty_string(item.get("imageSearch"))
        and _is_non_empty_string(item.get("goal"))
        and _is_non_empty_string(item.get("appearAt"))
    )

def validate_media_plan(media_plan):
    if not isinstance(media_plan, list) or not media_plan:
        return False
    for shot in media_plan:
        if not isinstance(shot, dict):
            return False
        if not _is_non_empty_string(shot.get("vo")):
            return False
        media = shot.get("media")
        if not isinstance(media, list):
            return False
        for m in media:
            if not _validate_media_item(m):
                return False
    return True

def get_valid_media_plan(vo_script, max_attempts: int = 3):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        # Vary prompt slightly on retries to bypass cache
        print(f"vo_script for attempt {attempt}: {repr(vo_script[:200])}")
        prompt = MAKE_MEDIA.format(vo=vo_script)
        if attempt > 1:
            prompt += f"\n\n# Retry attempt {attempt}: Ensure all media objects have non-empty appearAt fields."
        
        print(f"Sending prompt attempt {attempt}:")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("-" * 50)
        
        response = ask_gemini(prompt, model="gemini-2.5-pro")
        print(f"Raw response attempt {attempt}:")
        print(repr(response))
        print("=" * 50)
        
        plan = parse_json_response(response)
        if validate_media_plan(plan):
            return plan
        print(f"Media plan validation failed on attempt {attempt}—retrying...")
    # raise ValueError(f"Failed to obtain a valid media plan after {max_attempts} attempts")
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
    
    media_plan = get_valid_media_plan(vo_script, max_attempts=3)

    
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