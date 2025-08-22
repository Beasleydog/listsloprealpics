# import os
# import hashlib
# import requests
# import urllib.parse

# CACHE_DIR = "cache/openai_tts"
# os.makedirs(CACHE_DIR, exist_ok=True)

# def _cache_path(text, voice="ash", prompt="british, youtube commentary style, expressive, uses pauses effectively"):
#     key_src = f"{voice}|{prompt}|{text}".encode("utf-8")
#     # Use .mp3 since the service returns MP3 content; extension mismatch can confuse probes
#     return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp3")

# def getTTS(text, voice="ash", prompt="british, youtube commentary style, expressive, uses pauses effectively"):
#     text = text.strip()
#     if not text:
#         raise ValueError("getOpenAiTTS: text is empty.")

#     print(f"OpenAI TTS: Processing text: {text[:80]!r}...")  # trim for logs

#     cache_path = _cache_path(text, voice=voice, prompt=prompt)
    
#     if os.path.exists(cache_path):
#         return cache_path

#     # Backward-compat: migrate old .wav caches that actually contain MP3
#     legacy_path = cache_path[:-4] + '.wav'
#     if os.path.exists(legacy_path):
#         try:
#             os.replace(legacy_path, cache_path)
#             return cache_path
#         except Exception:
#             pass

#     # URL encode the parameters
#     encoded_text = urllib.parse.quote_plus(text)
#     encoded_prompt = urllib.parse.quote_plus(prompt)
#     encoded_voice = urllib.parse.quote_plus(voice)
    
#     url = f"https://www.openai.fm/api/generate?input={encoded_text}&prompt={encoded_prompt}&voice={encoded_voice}"
    
#     try:
#         response = requests.get(url, stream=True)
#         response.raise_for_status()
        
#         with open(cache_path, "wb") as f:
#             for chunk in response.iter_content(chunk_size=8192):
#                 f.write(chunk)
                
#     except Exception as e:
#         raise RuntimeError(f"OpenAI TTS request failed: {e}") from e

#     return cache_path
# import os, hashlib
# # from gradio_client import Client

# # CACHE_DIR = "cache/tts"
# # os.makedirs(CACHE_DIR, exist_ok=True)

# # def _cache_path(text, voice="en-GB-RyanNeural - en-GB (Male)", rate=0, pitch=0):
# #     key_src = f"{voice}|{rate}|{pitch}|{text}".encode("utf-8")
# #     return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".wav")

# # def getTTS(text, voice="en-GB-RyanNeural - en-GB (Male)", rate=0, pitch=0):
# #     text = text.strip()
# #     if not text:
# #         raise ValueError("getTTS: text is empty.")

# #     print(f"TTS: Processing text: {text[:80]!r}...")  # trim for logs

# #     cache_path = _cache_path(text, voice=voice, rate=rate, pitch=pitch)
    
# #     if os.path.exists(cache_path):
# #         return cache_path

# #     # call gradio client
# #     try:
# #         client = Client("keshav6936/GENAI-TTS-Text-to-Speech")
# #         result = client.predict(
# #             text=text,
# #             voice=voice,
# #             rate=rate,
# #             pitch=pitch,
# #             api_name="/predict"
# #         )
# #     except Exception as e:
# #         raise RuntimeError(f"TTS request failed: {e}") from e

# #     if not result or len(result) < 2:
# #         raise RuntimeError(f"Unexpected TTS result: {result}")

# #     audio_file_path, status = result
    
# #     if not audio_file_path:
# #         raise RuntimeError(f"TTS generation failed: {status}")

# #     # copy to cache
# #     import shutil
# #     shutil.copy2(audio_file_path, cache_path)

# #     return cache_path

import os, hashlib
from gradio_client import Client

CACHE_DIR = "cache/tts"
os.makedirs(CACHE_DIR, exist_ok=True)

def _append_log(message: str) -> None:
    """Append a timestamped log line to log.txt in project root."""
    from datetime import datetime
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        # Avoid raising in logging path; best effort only
        pass


def getTTS(text, voice="Liam", previous_text=None):
    import requests
    import json
    import time
    from dotenv import load_dotenv
    
    load_dotenv()
    
    text = text.strip()
    if not text:
        raise ValueError("getTTS: text is empty.")

    print(f"TTS: Processing text: {text[:80]!r}...")

    # Update cache path for new parameters
    key_src = f"{voice}|{previous_text or ''}|{text}".encode("utf-8")
    cache_path = os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp3")
    
    if os.path.exists(cache_path):
        print(f"TTS: Using cached audio: {cache_path}")
        return cache_path

    # Primary (and only): ElevenLabs via FAL with retries (3)
    api_key = os.getenv('FAL_KEY')
    if not api_key:
        _append_log("TTS: FAL_KEY not set; cannot proceed")
        import sys
        sys.exit(1)

    url = "https://fal.run/fal-ai/elevenlabs/tts/turbo-v2.5"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "voice": voice,
        "stability": 1,
    }
    if previous_text:
        payload["previous_text"] = previous_text

    max_retries = 3
    last_error_msg = None
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            status = response.status_code
            if status >= 400:
                # Log body on errors for visibility
                body = None
                try:
                    body = response.text[:1000]
                except Exception:
                    body = "<failed to read body>"
                last_error_msg = f"HTTP {status} from FAL; body: {body}"
                _append_log(f"TTS: attempt {attempt+1}/{max_retries} failed — {last_error_msg}")
                # Do not raise_for_status yet; continue retry loop
            else:
                result = response.json()
                audio_url = result.get("audio", {}).get("url")
                if not audio_url:
                    last_error_msg = "No audio URL returned from API"
                    _append_log(f"TTS: attempt {attempt+1}/{max_retries} failed — {last_error_msg}")
                else:
                    # Download audio with timeout
                    audio_response = requests.get(audio_url, timeout=60)
                    audio_response.raise_for_status()
                    with open(cache_path, "wb") as f:
                        f.write(audio_response.content)
                    return cache_path
        except Exception as e:
            last_error_msg = str(e)
            _append_log(f"TTS: attempt {attempt+1}/{max_retries} exception — {last_error_msg}")
        # Small delay between attempts
        time.sleep(2)

    # All retries failed — log context and exit program
    snippet = text[:200].replace("\n", " ")
    _append_log(f"TTS: all retries failed; voice={voice}, prev_len={(len(previous_text) if previous_text else 0)}, text_len={len(text)}, text_snippet={snippet!r}, error={last_error_msg}")
    import sys
    sys.exit(1)
