import os
import hashlib
import json

CACHE_DIR = "cache/whisper"
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(tts_path):
    """Generate cache path for whisper results based on audio file path."""
    key_src = f"{tts_path}".encode("utf-8")
    return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".json")

def _load_whisper_cache(cache_path):
    """Load cached whisper results if available."""
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["words"]
    except Exception as e:
        print(f"Warning: failed to read whisper cache {cache_path}: {e}")
        return None

def _save_whisper_cache(cache_path, words):
    """Save whisper results to cache."""
    try:
        # Convert Word objects to serializable format
        words_data = []
        for word in words:
            words_data.append({
                "word": word.word,
                "start": word.start,
                "end": word.end
            })
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"words": words_data}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: failed to write whisper cache {cache_path}: {e}")

def getMediaTimestamps(media, tts_path):
    """Given the media plan (list of dicts) and an audio file path, return the same
    list but with `startTimestamp` and `endTimestamp` (seconds) filled in for each
    entry.

    The audio is transcribed at *word* level using the *small* faster-whisper
    model. For every object we look for an approximate match (fuzzy) of
    `triggerPhrase` and `endPhrase` in the transcript and record the timestamps
    at the beginning of the first matched word and at the end of the last matched
    word respectively.
    """
    from pathlib import Path
    import re, difflib, math

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ImportError(
            "faster_whisper is required for getMediaTimestamps. Install with 'pip install faster-whisper'"
        ) from e

    audio_path = Path(tts_path).resolve()  # Use absolute path
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Check cache first
    cache_path = _cache_path(str(audio_path))
    cached_words = _load_whisper_cache(cache_path)
    
    if cached_words:
        print(f"Whisper: Using cached results for {audio_path.name}")
        # Convert cached data back to objects with attributes
        class Word:
            def __init__(self, word, start, end):
                self.word = word
                self.start = start
                self.end = end
        
        words = [Word(w["word"], w["start"], w["end"]) for w in cached_words]
    else:
        print(f"Whisper: Processing audio file: {audio_path.name}")
        
        # Load model (small is ~500MB and reasonably fast)
        model = WhisperModel("small", device="cpu", compute_type="int8")

        # Transcribe and collect words across segments
        words = []  # list of Word objects each having .word, .start, .end

        # faster-whisper's transcribe returns (segments_generator, info)
        segments, _ = model.transcribe(str(audio_path), word_timestamps=True)

        for segment in segments:
            # Each segment has a .words attribute which is a list of Word objects
            if not segment.words:
                continue
            words.extend(segment.words)

        if not words:
            raise RuntimeError("No words were produced by the speech recogniser.")
        
        # Save to cache
        _save_whisper_cache(cache_path, words)

    # Normalisation helpers -------------------------------------------------
    _punct = re.compile(r"[^a-z0-9 ]", re.IGNORECASE)

    def _norm(s: str) -> str:
        s = s.lower()
        s = _punct.sub(" ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # Prepare transcript word list once for quick lookups
    norm_transcript_words = [_norm(w.word) for w in words]

    # Build helper for fuzzy matching ---------------------------------------
    def _best_window_match(phrase_words: list[str], start_idx: int = 0):
        """Return (best_start_index, score) for best fuzzy match of phrase_words
        in transcript starting from start_idx.
        """
        target_str = " ".join(phrase_words)
        best_score = 0.0
        best_i = None
        pl = len(phrase_words)
        # Allow window length ±2 to account for extra/missing words
        for win_len in range(max(1, pl - 2), pl + 3):
            for i in range(start_idx, len(norm_transcript_words) - win_len + 1):
                window = norm_transcript_words[i : i + win_len]
                cand_str = " ".join(window)
                score = difflib.SequenceMatcher(None, target_str, cand_str).ratio()
                if score > best_score:
                    best_score = score
                    best_i = (i, win_len)
                # Early exit if perfect match
                if best_score == 1.0:
                    return best_i[0], best_i[1], best_score
        if best_i is None:
            return None, None, 0.0
        return best_i[0], best_i[1], best_score

    # Iterate media objects and fill timestamps -----------------------------
    for item in media:
        trig_words = _norm(item["triggerPhrase"]).split()
        end_words = _norm(item["endPhrase"]).split()

        trig_start, trig_len, trig_score = _best_window_match(trig_words)
        if trig_start is None:
            # Could not find; skip
            item["startTimestamp"] = None
            item["endTimestamp"] = None
            continue

        # End search begins after trigger start to ensure order
        end_search_start = trig_start + trig_len
        end_start, end_len, end_score = _best_window_match(end_words, start_idx=end_search_start)

        # Compute timestamps
        start_ts = words[trig_start].start  # type: ignore[attr-defined]
        if end_start is not None:
            end_ts = words[end_start + end_len - 1].end  # type: ignore[attr-defined]
        else:
            end_ts = None

        item["startTimestamp"] = round(start_ts, 3) if start_ts is not None else None
        item["endTimestamp"] = round(end_ts, 3) if end_ts is not None else None
        # Optionally store scores for debugging
        item["_matchScores"] = {"trigger": round(trig_score, 3), "end": round(end_score, 3)}

    return media


def get_phrase_timestamps(phrases: list[str], tts_path: str) -> dict[str, float]:
    """
    Convenience wrapper around getMediaTimestamps for a simpler use-case:
    Given a list of phrases and the path to the corresponding audio, return a
    mapping {phrase: start_timestamp_seconds}.
    """
    if not phrases:
        return {}

    # Re-use the existing implementation by constructing a minimal media plan
    media_plan = [{"triggerPhrase": p, "endPhrase": ""} for p in phrases]
    results = getMediaTimestamps(media_plan, tts_path)
    return {item["triggerPhrase"]: item.get("startTimestamp") for item in results}