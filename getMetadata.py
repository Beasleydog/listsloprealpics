from gemini import ask_gemini
import json
import re


def getMetadata(video_title: str, subideas: list[dict]) -> tuple[str, str]:
    """
    Generate YouTube description and keywords for a video using AI.
    
    Args:
        video_title: The main title of the video
        subideas: List of dictionaries with 'subject' keys representing topics covered
        
    Returns:
        Tuple of (description, keywords_csv)
    """
    subjects = [str(item.get("subject", "")).strip() for item in subideas if isinstance(item, dict)]
    subjects = [s for s in subjects if s]

    prompt = f"""
You are an assistant that writes YouTube metadata for educational videos.

Input:
- Title: {video_title}
- Topics covered (ordered): {', '.join(subjects)}

Task:
- Write a clear, engaging educational description (2-5 sentences) that explains what viewers will learn. Avoid clickbait. Keep it concise and factual. Mention key themes naturally.
- Propose 8-15 short, generic keywords (no hashtags, no duplicates). Keywords should be single words or short phrases relevant to the content and audience discovery.

Output strictly as JSON only, no markdown, using this shape:
{{
  "description": "...",
  "keywords": ["word1", "word2", "word3"]
}}
"""

    def _parse_json_block(text: str) -> dict:
        """Extract JSON from AI response, handling markdown fences."""
        # Try fenced JSON
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # Fallback: first { ... }
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {}

    try:
        response = ask_gemini(prompt, model="gemini-2.5-pro")
    except Exception as e:
        print(f"Warning: Failed to generate metadata with AI: {e}")
        response = "{}"

    data = _parse_json_block(response) if isinstance(response, str) else {}
    description = str(data.get("description") or "").strip()
    raw_keywords = data.get("keywords") or []
    
    if isinstance(raw_keywords, str):
        # Split on commas if model returned a string
        raw_keywords = [k.strip() for k in raw_keywords.split(",")]

    # Sanitize keywords: lower noise, dedupe, drop empties
    seen = set()
    keywords: list[str] = []
    for k in raw_keywords:
        if not isinstance(k, str):
            continue
        token = k.strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(token)

    # Fallbacks if AI generation failed
    if not description:
        description = f"An educational overview of '{video_title}', covering: " + ", ".join(subjects[:8]) + "."
    if not keywords:
        keywords = [video_title, "education", "explainer"] + subjects[:7]

    keywords_csv = ", ".join(keywords)
    return description, keywords_csv