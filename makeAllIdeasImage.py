# make_all_ideas_image.py
# pip install pillow moviepy

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
from typing import List, Dict, Tuple
import numpy as np
from moviepy import ImageSequenceClip, AudioClip
import math
from getTTS import getTTS
from getAudioLength import getAudioLength
from overlayAudioVideo import overlayAudioVideo

# ---------------------- constants ----------------------
MAX_IDEA_SIZE = 300  # Maximum diameter for each idea circle
# Label rendering constraints
LABEL_MAX_LINES = 2
LABEL_MARGIN_X = 12  # inner horizontal padding inside the label area
LABEL_MARGIN_Y = 6   # inner vertical padding inside the label area
MAX_FONT_SIZE = 48   # Maximum font size for labels

# ---------------------- helpers ----------------------

def _cover_fit(bg: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Resize+crop a background to cover target_size (like CSS background-size: cover)."""
    tw, th = target_size
    bw, bh = bg.size
    scale = max(tw / bw, th / bh)
    new_size = (int(bw * scale), int(bh * scale))
    bg = bg.resize(new_size, Image.LANCZOS)
    # center crop
    left = (bg.width - tw) // 2
    top = (bg.height - th) // 2
    return bg.crop((left, top, left + tw, top + th))

def _load_font(preferred: str, size: int, font_path: str = "font.ttf") -> ImageFont.FreeTypeFont:
    """Try a few common fonts; fall back gracefully."""
    candidates = [
        preferred,
        font_path,
        "DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_px: int, font_path: str = "font.ttf") -> ImageFont.FreeTypeFont:
    """Shrink font so text fits within max_width."""
    size = min(start_px, MAX_FONT_SIZE)
    while size > 8:
        font = _load_font("", size, font_path)
        w, _ = draw.textbbox((0, 0), text, font=font)[2:]
        if w <= max_width:
            return font
        size -= 1
    return _load_font("", 8, font_path)

def _wrap_text_to_width(draw: ImageDraw.ImageDraw,
                        text: str,
                        font: ImageFont.FreeTypeFont,
                        max_width: int,
                        max_lines: int = 3) -> Tuple[List[str], int, int]:
    """Greedy wrap text into lines that fit max_width. Returns (lines, block_w, block_h).

    - Splits on spaces; if a single token is too wide, it is hard-wrapped by characters.
    - Up to max_lines lines are produced; callers should shrink font if more would be needed.
    """
    if not text:
        return [""], 0, 0

    words = text.split()
    lines: List[str] = []
    current = ""

    def text_size(s: str) -> Tuple[int, int]:
        box = draw.textbbox((0, 0), s, font=font)
        return box[2] - box[0], box[3] - box[1]

    i = 0
    while i < len(words):
        word = words[i]
        # If a single word is wider than the box, hard-wrap it by characters
        w_word, _ = text_size(word)
        if w_word > max_width and len(word) > 1:
            # Flush current line first
            if current:
                lines.append(current)
                current = ""
                if len(lines) >= max_lines:
                    break
            # Hard-wrap this long token
            start = 0
            while start < len(word):
                # Fit as many characters as possible on this line
                end = start + 1
                last_good = start + 1
                while end <= len(word):
                    segment = word[start:end]
                    seg_w, _ = text_size(segment)
                    if seg_w <= max_width:
                        last_good = end
                        end += 1
                    else:
                        break
                segment = word[start:last_good]
                lines.append(segment)
                start = last_good
                if len(lines) >= max_lines:
                    break
            i += 1
            continue

        # Try to place word on current line
        trial = word if not current else current + " " + word
        if text_size(trial)[0] <= max_width:
            current = trial
            i += 1
        else:
            lines.append(current or word)
            current = "" if current else ""
            if not current:
                # If we placed the word as its own line, move to next
                if trial == word:
                    i += 1
            if len(lines) >= max_lines:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    # Measure block size
    max_w = 0
    line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
    spacing = max(4, int(line_h * 0.15))
    for ln in lines:
        lw = draw.textbbox((0, 0), ln, font=font)[2]
        if lw > max_w:
            max_w = lw
    block_h = len(lines) * line_h + max(0, len(lines) - 1) * spacing
    return lines, max_w, block_h

def _fit_wrapped_text(draw: ImageDraw.ImageDraw,
                      text: str,
                      max_width: int,
                      max_height: int,
                      start_px: int,
                      max_lines: int = 3,
                      font_path: str = "font.ttf") -> Tuple[ImageFont.FreeTypeFont, List[str], int, int, int]:
    """Find the largest font size so the wrapped text fits within (max_width, max_height).

    Returns: (font, lines, block_w, block_h, line_height)
    """
    size = min(start_px, MAX_FONT_SIZE)
    while size > 8:
        font = _load_font("", size, font_path)
        lines, block_w, block_h = _wrap_text_to_width(draw, text, font, max_width, max_lines=max_lines)
        line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
        if block_w <= max_width and block_h <= max_height and len(lines) <= max_lines:
            return font, lines, block_w, block_h, line_h
        size -= 1
    # Fallback tiny font
    font = _load_font("", 8, font_path)
    lines, block_w, block_h = _wrap_text_to_width(draw, text, font, max_width, max_lines=max_lines)
    line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
    return font, lines, block_w, block_h, line_h

def _find_uniform_font_size(draw: ImageDraw.ImageDraw,
                            labels: List[str],
                            max_width: int,
                            max_height: int,
                            start_px: int,
                            max_lines: int,
                            font_path: str = "font.ttf") -> ImageFont.FreeTypeFont:
    """Find one font size that allows all labels to fit (wrapped) in the box.

    Chooses the largest size that satisfies constraints for every label.
    """
    size = min(start_px, MAX_FONT_SIZE)
    while size > 8:
        font = _load_font("", size, font_path)
        ok = True
        for label in labels:
            lines, block_w, block_h = _wrap_text_to_width(draw, label, font, max_width, max_lines)
            if block_w > max_width or block_h > max_height or len(lines) > max_lines:
                ok = False
                break
        if ok:
            return font
        size -= 1
    return _load_font("", 8, font_path)

def _circle_thumb(img_path: str, diameter: int) -> Image.Image:
    """Open an image, center-crop to square, resize, and mask to a circle with border."""
    # Robust open with fallback
    try:
        img = Image.open(img_path).convert("RGB")
    except Exception:
        # fallback placeholder
        img = Image.new("RGB", (diameter, diameter), (40, 40, 40))
    # center-crop to square
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((diameter, diameter), Image.LANCZOS)

    # circular mask
    mask = Image.new("L", (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill=255)

    # simplified without vignette

    img = Image.composite(img, Image.new("RGB", (diameter, diameter), (20, 20, 20)), mask)
    mimg = Image.merge("RGBA", (*img.split(), mask))
    # high-quality anti-aliased border ring
    scale = 4  # render at 4x for anti-aliasing
    ring_size = diameter * scale
    ring = Image.new("RGBA", (ring_size, ring_size), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    border = max(8, (diameter * scale) // 60)  # scale border thickness too
    rd.ellipse((0, 0, ring_size - 1, ring_size - 1),
               outline=(0, 0, 0, 255), width=border)
    # scale back down with high-quality resampling for smooth edges
    ring = ring.resize((diameter, diameter), Image.LANCZOS)

    composed = Image.alpha_composite(mimg, ring)
    return composed



def _balanced_layout(n: int, W: int, H: int, pad: int) -> Tuple[int, List[int], int, int]:
    """
    Choose row count and per-row column counts that maximize circle diameter.
    Returns: rows, cols_per_row, cell_w, cell_h (approx for largest-row calc).
    """
    inner_w, inner_h = W - 2 * pad, H - 2 * pad
    best = None

    for rows in range(1, n + 1):
        # gutters proportional to canvas
        gutter_x = max(20, min(inner_w // 40, 60))     # ~2.5% width
        gutter_y = max(24, min(inner_h // 25, 70))     # ~4% height

        base = n // rows
        rem = n % rows
        cols_per_row = [(base + 1 if i < rem else base) for i in range(rows)]
        c_max = max(cols_per_row)

        cell_w = (inner_w - (c_max - 1) * gutter_x) // c_max
        cell_h = (inner_h - (rows - 1) * gutter_y) // rows

        # reserve space ~28% for label; circle diam limited by both w and h
        label_frac = 0.28
        diameter = min(cell_w, int(cell_h * (1 - label_frac)))
        # Apply maximum size constraint
        diameter = min(diameter, MAX_IDEA_SIZE)

        if diameter <= 0:
            continue
        score = diameter  # maximize circle diameter
        if best is None or score > best[0]:
            best = (score, rows, cols_per_row, cell_w, cell_h, gutter_x, gutter_y)

    if best is None:
        # degenerate fallback
        return 1, [n], inner_w, inner_h
    _, rows, cols_per_row, cell_w, cell_h, gx, gy = best
    return rows, cols_per_row, cell_w, cell_h

# ---------------------- main function ----------------------

def makeAllIdeasImage(items: List[Dict[str, str]],
                      output_path: str = "all_ideas.png",
                      size: Tuple[int, int] = (1920, 1080),
                      background_path: str = "background.png",
                      font_path: str = "font.ttf") -> Image.Image:
    """
    Render a polished 16:9 collage.
    items: [{'subject': str, 'image': str}, ...]
    Returns the PIL image and also saves to output_path.
    """
    W, H = size

    # Background
    if os.path.exists(background_path):
        bg = Image.open(background_path).convert("RGB")
        canvas = _cover_fit(bg, (W, H)).convert("RGBA")
    else:
        # tasteful fallback gradient
        grad = Image.new("L", (1, H), color=0)
        for y in range(H):
            grad.putpixel((0, y), int(30 + 70 * y / H))
        grad = grad.resize((W, H))
        canvas = Image.merge("RGBA",
                             (Image.new("L", (W, H), 18),
                              Image.new("L", (W, H), 18),
                              Image.new("L", (W, H), 22),
                              grad))

    draw = ImageDraw.Draw(canvas)

    # Layout
    pad = max(40, min(W, H) // 16)  # ~6% edge padding
    rows, cols_per_row, cell_w, cell_h = _balanced_layout(len(items), W, H, pad)
    inner_w, inner_h = W - 2 * pad, H - 2 * pad
    gutter_x = max(20, min(inner_w // 40, 60))
    gutter_y = max(24, min(inner_h // 25, 70))
    label_frac = 0.28
    diameter = min(cell_w, int(cell_h * (1 - label_frac)))
    # Apply maximum size constraint
    diameter = min(diameter, MAX_IDEA_SIZE)
    label_area = max(24, cell_h - diameter)

    # Fonts
    tmp_font = _load_font("", max(24, diameter // 3), font_path)
    # Compute a single uniform font size for all labels (with wrapping)
    labels_all = [str(it.get("subject", "")).strip() for it in items]
    avail_w = max(10, int(cell_w * 0.95) - 2 * LABEL_MARGIN_X)
    avail_h = max(8, label_area - 2 * LABEL_MARGIN_Y)
    start_px = max(24, avail_h)
    uniform_font = _find_uniform_font_size(draw, labels_all, avail_w, avail_h, start_px, LABEL_MAX_LINES, font_path)
    uniform_line_h = draw.textbbox((0, 0), "Ag", font=uniform_font)[3]
    uniform_spacing = max(4, int(uniform_line_h * 0.15))

    # Calculate total grid height for vertical centering
    total_grid_height = rows * cell_h + (rows - 1) * gutter_y
    
    # Center the grid vertically
    grid_start_y = pad + (inner_h - total_grid_height) // 2
    
    # Prepare list to capture exact circle centers for later zooming
    circle_centers: List[Tuple[int, int]] = []
    layout_info: List[Dict[str, int]] = []

    # Render rows
    idx = 0
    y_cursor = grid_start_y
    for r in range(rows):
        cols = cols_per_row[r]
        row_w = cols * cell_w + (cols - 1) * gutter_x
        x_start = pad + (inner_w - row_w) // 2  # center the shorter rows

        for c in range(cols):
            if idx >= len(items):
                break
            item = items[idx]
            idx += 1

            # positions inside this cell
            cell_x = x_start + c * (cell_w + gutter_x)
            cell_y = y_cursor
            circle_x = cell_x + (cell_w - diameter) // 2

            # label text using a uniform font size and wrapping for consistency
            label = str(item.get("subject", "")).strip()
            lines, block_w, block_h = _wrap_text_to_width(
                draw, label, uniform_font, avail_w, max_lines=LABEL_MAX_LINES
            )

            # vertically center the circle + label as a group within the cell
            text_gap = max(8, int(diameter * 0.08))
            group_h = diameter + text_gap + block_h
            base_y = cell_y + max(0, (cell_h - group_h) // 2)
            circle_y = base_y
            label_y = base_y + diameter + text_gap

            # draw circle
            circ = _circle_thumb(item.get("image", ""), diameter)
            canvas.alpha_composite(circ, (circle_x, circle_y))

            # store exact metadata for zoom
            circle_center_x = circle_x + diameter // 2
            circle_center_y = circle_y + diameter // 2
            circle_centers.append((circle_center_x, circle_center_y))
            group_center_y = base_y + group_h // 2
            cell_center_x = cell_x + cell_w // 2
            layout_info.append({
                "circle_cx": circle_center_x,
                "circle_cy": circle_center_y,
                "group_cy": group_center_y,
                "circle_d": diameter,
                "cell_cx": cell_center_x,
                "cell_y": cell_y,
                "cell_h": cell_h
            })

            # draw label (centered, multi-line) with inner margins
            tx = cell_x + (cell_w - min(block_w, avail_w)) // 2
            cy = label_y + LABEL_MARGIN_Y
            for ln in lines:
                lw = draw.textbbox((0, 0), ln, font=uniform_font)[2]
                lx = cell_x + (cell_w - lw) // 2
                draw.text((lx, cy), ln, font=uniform_font, fill=(0, 0, 0, 255))
                cy += uniform_line_h + uniform_spacing

        y_cursor += cell_h + gutter_y

    
    canvas.save(output_path)
    # attach centers and layout info to the image for consumers (non-breaking API)
    try:
        setattr(canvas, "_circle_centers", circle_centers)
        setattr(canvas, "_layout_info", layout_info)
    except Exception:
        pass
    return canvas

# ---------------------- zoom video function ----------------------

# Animation constants
ZOOM_DURATION = 2.0  # seconds (minimum animation length baseline)
ZOOM_FPS = 30
ZOOM_SPEED = 2.0  # zoom factor per second
FINAL_SCALE = 2.0  # how much to zoom into the final item (reduced to keep full item visible)
PAUSE_START = 0.5  # seconds to pause at start (set to 0 to keep base at 2s)
PAUSE_END = 0.0  # seconds to pause at end (set to 0 to keep base at 2s)

def zoomintoidea(items: List[Dict[str, str]], 
                 index: int,
                 output_path: str = "zoom_video.mp4",
                 size: Tuple[int, int] = (1920, 1080),
                 background_path: str = "background.png",
                 font_path: str = "font.ttf") -> str:
    """
    Create a video that zooms into a specific item from the grid.
    
    Args:
        items: List of items with 'subject' and 'image' keys
        index: Index of the item to zoom into
        output_path: Path for output video file
        size: Video resolution
        background_path: Background image path
        
    Returns:
        Path to the created video file
    """
    if index < 0 or index >= len(items):
        raise ValueError(f"Index {index} out of range for {len(items)} items")
    
    W, H = size
    total_frames = int((ZOOM_DURATION + PAUSE_START + PAUSE_END) * ZOOM_FPS)
    pause_start_frames = int(PAUSE_START * ZOOM_FPS)
    pause_end_frames = int(PAUSE_END * ZOOM_FPS)
    zoom_frames = total_frames - pause_start_frames - pause_end_frames
    
    frames = []
    
    # Generate TTS for the idea name and measure duration
    idea_label = str(items[index].get("subject", f"item_{index}")).strip() or f"item_{index}"
    tts_path = getTTS(idea_label)
    audio_len = getAudioLength(tts_path)
    end_linger = 0.35  # slight delay to avoid a rushed cut when audio runs long

    # Create the full grid image first
    full_image = makeAllIdeasImage(items, "temp_grid.png", size, background_path, font_path)

    # If the image carries exact circle centers, use them directly
    circle_centers = getattr(full_image, "_circle_centers", None)
    if isinstance(circle_centers, list) and 0 <= index < len(circle_centers):
        target_x, target_y = circle_centers[index]
        # Also try to get full layout info for precise fallback calculations later if needed
        layout_info = getattr(full_image, "_layout_info", None)
    else:
        target_x = target_y = None
    
    # Calculate the target item position (fallback if centers not available)
    pad = max(40, min(W, H) // 16)
    rows, cols_per_row, cell_w, cell_h = _balanced_layout(len(items), W, H, pad)
    inner_w, inner_h = W - 2 * pad, H - 2 * pad
    gutter_x = max(20, min(inner_w // 40, 60))
    gutter_y = max(24, min(inner_h // 25, 70))
    
    # Calculate total grid height for vertical centering (same as main function)
    total_grid_height = rows * cell_h + (rows - 1) * gutter_y
    grid_start_y = pad + (inner_h - total_grid_height) // 2
    
    # Find the target item's position (center of entire cell including text)
    idx = 0
    y_cursor = grid_start_y
    if target_x is None or target_y is None:
        target_x = target_y = 0
    
    for r in range(rows):
        cols = cols_per_row[r]
        row_w = cols * cell_w + (cols - 1) * gutter_x
        x_start = pad + (inner_w - row_w) // 2
        
        for c in range(cols):
            if idx == index and (circle_centers is None):
                # Compute the exact circle center using the same sizing rules as rendering
                label_frac = 0.28
                diameter = min(cell_w, int(cell_h * (1 - label_frac)))
                diameter = min(diameter, MAX_IDEA_SIZE)
                label_w_max = int(cell_w * 0.95)
                font_start_px = max(24, cell_h - diameter)
                measure_draw = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
                label = str(items[idx].get("subject", "")).strip()
                # Use same uniform rules as renderer to compute group height
                avail_w = max(10, int(cell_w * 0.95) - 2 * LABEL_MARGIN_X)
                avail_h = max(24, cell_h - diameter - 2 * LABEL_MARGIN_Y)
                # Estimate with a conservative font size similar to the renderer
                est_font = _find_uniform_font_size(measure_draw, [label], avail_w, avail_h, font_start_px, LABEL_MAX_LINES, font_path)
                lines, block_w, block_h = _wrap_text_to_width(measure_draw, label, est_font, avail_w, max_lines=LABEL_MAX_LINES)
                text_gap = max(8, int(diameter * 0.08))
                group_h = diameter + text_gap + block_h + 2 * LABEL_MARGIN_Y
                base_y = y_cursor + max(0, (cell_h - group_h) // 2)

                target_x = x_start + c * (cell_w + gutter_x) + cell_w // 2
                # Focus on the circle center, not the group center
                target_y = base_y + diameter // 2
                break
            idx += 1
            if idx >= len(items):
                break
        if idx == index:
            break
        y_cursor += cell_h + gutter_y
    
    # Generate frames
    for frame_num in range(total_frames):
        if frame_num < pause_start_frames:
            # Pause at start - show full grid
            scale = 1.0
            center_x, center_y = W // 2, H // 2
        elif frame_num >= total_frames - pause_end_frames:
            # Pause at end - show zoomed view
            scale = FINAL_SCALE
            center_x, center_y = target_x, target_y
        else:
            # Zoom animation - direct linear interpolation
            progress = (frame_num - pause_start_frames) / zoom_frames
            # Simple smooth easing - less dramatic than cubic
            progress = progress * progress * (3 - 2 * progress)  # smoothstep
            
            scale = 1.0 + (FINAL_SCALE - 1.0) * progress
            center_x = W // 2 + (target_x - W // 2) * progress
            center_y = H // 2 + (target_y - H // 2) * progress
        
        # Create frame by cropping and scaling
        frame = full_image.copy()
        
        # Calculate crop region
        crop_w = W / scale
        crop_h = H / scale
        
        # Calculate initial crop bounds
        left = center_x - crop_w / 2
        top = center_y - crop_h / 2
        right = left + crop_w
        bottom = top + crop_h
        
        # Adjust if we hit boundaries
        if left < 0:
            right = right - left
            left = 0
        if top < 0:
            bottom = bottom - top
            top = 0
        if right > W:
            left = left - (right - W)
            right = W
        if bottom > H:
            top = top - (bottom - H)
            bottom = H
            
        # Ensure we don't go negative after adjustments
        left = max(0, left)
        top = max(0, top)
        right = min(W, right)
        bottom = min(H, bottom)
        
        # Ensure valid crop coordinates
        if right <= left:
            left = 0
            right = W
        if bottom <= top:
            top = 0
            bottom = H
        
        # Crop and resize
        cropped = frame.crop((int(left), int(top), int(right), int(bottom)))
        frame_resized = cropped.resize((W, H), Image.LANCZOS)
        
        # Convert to RGB for video
        frame_rgb = frame_resized.convert('RGB')
        frames.append(np.array(frame_rgb))
    
    # If audio is longer than animation, hold the last frame until audio completes (+ small linger)
    base_duration = len(frames) / ZOOM_FPS
    target_min_duration = audio_len + end_linger
    if target_min_duration > base_duration and frames:
        extra_seconds = target_min_duration - base_duration
        extra_frames = int(math.ceil(extra_seconds * ZOOM_FPS))
        if extra_frames > 0:
            frames.extend([frames[-1]] * extra_frames)

    # Create video with silent audio to ensure consistent concat later
    clip = ImageSequenceClip(frames, fps=ZOOM_FPS)
    # Use 48kHz silent audio to match the pipeline and avoid resample artifacts later
    silent_audio = AudioClip(lambda t: 0.0, duration=clip.duration, fps=48000)
    clip = clip.with_audio(silent_audio)
    clip.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        audio=True,
        fps=ZOOM_FPS,
        bitrate=None,
        audio_bitrate='192k',
        temp_audiofile=None,
        logger=None
    )

    # Overlay the TTS audio on the zoom video (video already extended to cover audio)
    overlayAudioVideo(output_path, tts_path, trim_to_shortest=False)
    
    # Clean up temp file
    if os.path.exists("temp_grid.png"):
        os.remove("temp_grid.png")
    
    return output_path

# ---------------------- example usage ----------------------
if __name__ == "__main__":
    sample = [
        {'subject': 'DEFCON 5', 'image': r'images\DEFCON+5+military+normal+operations+photo+peacetime+-logo+-meme+-clipart+-infographic+-diagram+-text\5.jpg'},
        {'subject': 'DEFCON 4', 'image': r'images\DEFCON+4+military+intelligence+gathering+operations+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\8.jpg'},
        {'subject': 'DEFCON 3', 'image': r'images\DEFCON+3+military+heightened+readiness+alert+state+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\9.jpg'},
        {'subject': 'DEFCON 2', 'image': r'images\DEFCON+2+military+urgent+readiness+preparation+imminent+threat+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\5.jpg'},
        {'subject': 'DEFCON 1', 'image': r'images\DEFCON+1+military+maximum+readiness+active+combat+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\9.jpg'},
    {'subject': 'DEFCON 9', 'image': r'images\DEFCON+5+military+normal+operations+photo+peacetime+-logo+-meme+-clipart+-infographic+-diagram+-text\5.jpg'},
        {'subject': 'DEFCON 4', 'image': r'images\DEFCON+4+military+intelligence+gathering+operations+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\8.jpg'},
        {'subject': 'DEFCON 3', 'image': r'images\DEFCON+3+military+heightened+readiness+alert+state+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\9.jpg'},
        {'subject': 'DEFCON 2', 'image': r'images\DEFCON+2+military+urgent+readiness+preparation+imminent+threat+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\5.jpg'},
        {'subject': 'DEFCON 1', 'image': r'images\DEFCON+1+military+maximum+readiness+active+combat+photo+-logo+-meme+-clipart+-infographic+-diagram+-text\9.jpg'},
    
    ]
    # makeAllIdeasImage(sample, output_path="all_ideas.png", size=(1920, 1080), background_path="background.png")
    
    # Example: Create zoom video for DEFCON 1 (index 4)
    zoomintoidea(sample, 5, "defcon1_zoom.mp4", size=(1920, 1080), background_path="background.png", font_path="font.ttf")
