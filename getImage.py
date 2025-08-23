from dotenv import load_dotenv
import os
import requests
import json
from urllib.parse import quote_plus
from pathlib import Path

load_dotenv()

gemini_prompt="""What number image is best for the following criteria
{description}

1. Shouldn't be edited, like it ideally shouldnt be a collage or have text overlay
2. Should be high quality 
3. MUST NOT HAVE ANY BRANDING, LIKE A NEWS COMPANY OR A STOCK IMAGE COMPANY OR ANYTHING SIMILAR UNLESS IT IS A PART OF THE IMAGE OBJECT ITSELF.
    - ABSOLUTELY NO STOCK IMAGE WATERMARKS LIKE "ALAMY", "GETTY", "PEXELS", "STOCK", etc

Output your response in this json:
{{
"analysis": string,  # reasoning here, look at all the images, compare, etc
"finalSelection": int
}}

Your analysis value must be a simple string that must follow this pattern:
For each image, do the following:
1. See if it follows the theme
2. See if it follows EACH individual criteria
Then, only after looking at and rating all the images, do the following:
Explain which one is the best fit for the criteria and why.

Remember, JUST A JSON BLOCK WITH THE JSON OBJECT, NO OTHER TEXT.
"""

# ------------------ Internal helpers ------------------


def _download_images(search_query: str, num_images: int = 10) -> list[str]:
    """Search Serper for *search_query*, download up to *num_images* images, and
    return a list of local file paths."""

    safe_query = quote_plus(search_query)
    folder = Path("images") / safe_query
    
    # Check if folder already exists and has images
    if folder.exists():
        existing_images = list(folder.glob("*"))
        if existing_images:
            return [str(path) for path in existing_images]
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY environment variable not set.")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    search_query = f"{search_query} -filetype:gif"
    response = requests.post(
        "https://google.serper.dev/images",
        headers=headers,
        json={"q": search_query,"num": num_images, 
        # "tbs": "isz:lt,islt:xga",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    results = data.get("images") or data.get("results") or data.get("items") or []

    folder.mkdir(parents=True, exist_ok=True)

    image_paths: list[str] = []

    for idx, item in enumerate(results[:num_images], start=1):
        url = (
            item.get("imageUrl")
            or item.get("url")
            or item.get("thumbnailUrl")
        )
        if not url:
            continue

        try:
            img_resp = requests.get(url, timeout=20)
            if img_resp.status_code != 200:
                continue

            ext = ".png" if url.lower().endswith(".png") else ".jpg"
            file_path = folder / f"{idx}{ext}"
            with open(file_path, "wb") as f:
                f.write(img_resp.content)
            image_paths.append(str(file_path))
        except Exception:
            continue

    if not image_paths:
        raise RuntimeError("Failed to download any images.")

    return image_paths

# ------------------ Public API ------------------


def getImage(searchQuery: str, description: str) -> str:
    """Search for images of *searchQuery*, ask Gemini which one is best given
    *description*, and return the selected image's local path."""

    from gemini import ask_gemini_with_images  # Local import to avoid circular deps

    # --- Helper to validate images ---
    import imghdr

    def _filter_valid_images(paths: list[str]) -> list[str]:
        """Return only those image *paths* that are valid and ensure the
        folder contains a contiguous sequence of image filenames (1.jpg,
        2.jpg, 3.png, ...).

        Validation strategy:
        1. Skip zero-byte files.
        2. Use the stdlib *imghdr* module to identify common image formats.
           If *imghdr.what* returns *None* the file is considered invalid or
           corrupted and will be deleted from disk.
        After validation, any gaps in numbering caused by deletions are
        fixed by renaming the remaining images in ascending order so that
        the filenames are sequential with no jumps.
        """
        valid: list[str] = []
        for p in paths:
            try:
                remove_file = False
                if os.path.getsize(p) == 0:
                    remove_file = True
                elif imghdr.what(p) is None:
                    remove_file = True
                else:
                    # Additional validation: try to actually load the image data
                    try:
                        from PIL import Image
                        with Image.open(p) as img:
                            # Try to load the image data completely to catch corruption
                            img.load()
                            # Verify image has reasonable dimensions
                            if img.width < 10 or img.height < 10:
                                remove_file = True
                    except Exception as img_error:
                        print(f"Image validation failed for {p}: {img_error}")
                        remove_file = True

                if remove_file:
                    # Delete corrupted/invalid file so it doesn't linger on disk
                    try:
                        os.remove(p)
                        print(f"Removed corrupted/invalid image: {p}")
                    except OSError:
                        pass  # Ignore inability to delete
                    continue  # Skip to next path

                valid.append(p)
            except Exception:
                # Any unexpected error counts as invalid – attempt deletion
                try:
                    os.remove(p)
                except OSError:
                    pass
                continue

        # ---------- Renumber remaining valid images ----------
        from pathlib import Path as _Path

        # Sort paths by the numeric value in their stem ("3" in "3.jpg").
        def _numeric_stem(path: str) -> int:
            try:
                return int(_Path(path).stem)
            except ValueError:
                # Non-numeric stems are sorted to the end
                return 10**9

        valid_sorted = sorted(valid, key=_numeric_stem)
        renumbered_paths: list[str] = []

        for new_idx, old_path in enumerate(valid_sorted, start=1):
            old_p = _Path(old_path)
            new_name = f"{new_idx}{old_p.suffix}"
            new_p = old_p.with_name(new_name)

            # If the current name already matches the desired one, skip renaming
            if old_p == new_p:
                renumbered_paths.append(str(old_p))
                continue

            # Handle potential name collision by first renaming the target (rare)
            if new_p.exists() and new_p != old_p:
                temp_p = new_p.with_name(f"tmp_{new_idx}{old_p.suffix}")
                new_p.rename(temp_p)

            old_p.rename(new_p)
            renumbered_paths.append(str(new_p))

        return renumbered_paths

    # 1. Fetch and store images
    image_paths = _download_images(searchQuery)

    # 1b. Filter out any corrupted / invalid images before sending to Gemini
    image_paths = _filter_valid_images(image_paths)

    # 1c. If no valid images, try downloading again with different search terms
    if not image_paths:
        print(f"No valid images found for '{searchQuery}', retrying with modified search...")
        # Try a few fallback searches
        fallback_searches = [
            f"{searchQuery} high quality",
            f"{searchQuery} stock photo", 
            searchQuery.split()[0] if ' ' in searchQuery else f"{searchQuery} image"
        ]
        
        for fallback_query in fallback_searches:
            try:
                print(f"Trying fallback search: '{fallback_query}'")
                image_paths = _download_images(fallback_query)
                image_paths = _filter_valid_images(image_paths)
                if image_paths:
                    break
            except Exception as e:
                print(f"Fallback search failed for '{fallback_query}': {e}")
                continue
    
    if not image_paths:
        raise RuntimeError(f"No valid images were downloaded for '{searchQuery}' or any fallback searches.")

    # 2. Build the prompt
    prompt = gemini_prompt.format(description=description)

    # 3. Ask Gemini for the best image
    response = ask_gemini_with_images(image_paths, prompt)

    # 4. Parse Gemini's response to determine the chosen index
    import re

    def _extract_final_selection(resp: str) -> int | None:
        """Try to robustly pull the integer value of `finalSelection` from *resp*.

        The Gemini response is often wrapped in a markdown fenced code block like:

        ```json
        { "analysis": "...", "finalSelection": 7 }
        ```

        It may also appear as a raw JSON string or with escaped new-lines/quotes.
        This helper makes a best-effort attempt to locate the JSON object and
        load it with *json.loads*.  If that fails we fall back to a regex that
        looks for the key/value pair.
        """
        # 1. Try to locate a fenced JSON block first
        fenced = re.search(r"```json\s*(\{.*?\})\s*```", resp, re.DOTALL | re.IGNORECASE)
        json_str: str | None = None
        if fenced:
            json_str = fenced.group(1)
        else:
            # 2. Otherwise grab the first {...} occurrence which is likely the JSON
            braces = re.search(r"\{.*\}", resp, re.DOTALL)
            if braces:
                json_str = braces.group(0)
        if json_str:
            try:
                return json.loads(json_str).get("finalSelection")
            except Exception:
                pass  # fallthrough to regex below
        # 3. Last resort – regex for a standalone number after the key
        m = re.search(r'"finalSelection"\s*[:=]\s*(\d+)', resp)
        return int(m.group(1)) if m else None
    print(response)
    selection = _extract_final_selection(response)
    print(selection)
    print(type(selection))
    if not isinstance(selection, int) or selection < 1:
        selection = 1  # default on parse failure

    # 5. Map the selection number to the correct file regardless of list order
    #    by matching the filename (without extension) with the chosen number.
    from pathlib import Path as _Path

    matched_paths = [p for p in image_paths if _Path(p).stem == str(selection)]
    print([_Path(p).stem for p in image_paths])
    chosen_path = matched_paths[0] if matched_paths else image_paths[0]

    return chosen_path