# # from typing import List, Dict, Any, Tuple
# # from moviepy import ImageClip, CompositeVideoClip, TextClip, VideoClip, vfx
# # import numpy as np
# # import os
# # import hashlib
# # import json

# # # ===== Constants =====
# # VIDEO_WIDTH = 1920
# # VIDEO_HEIGHT = 1080
# # FPS = 30
# # BACKGROUND_COLOR = (10, 10, 10)  # RGB

# # # Cache settings
# # CACHE_DIR = "cache/buildshot"
# # os.makedirs(CACHE_DIR, exist_ok=True)

# # PADDING_LEFT = 120
# # PADDING_RIGHT = 120
# # PADDING_TOP = 120
# # PADDING_BOTTOM = 120

# # TEXT_COLOR = (255, 255, 255)
# # TEXT_FONT_SIZE = 80

# # POST_HOLD_SECONDS = 3

# # # Animation settings
# # ANIMATION_DURATION = 0.4  # seconds for smooth repositioning/resize
# # ANIMATION_EASING = "ease_out"  # easing type
# # ENTRANCE_DURATION = 0.45  # seconds for fade-in and translate-in
# # ENTRANCE_TRANSLATE_OFFSET = 28  # pixels to slide in from

# # # Max allowed absolute image upscaling relative to its original/native resolution
# # # This prevents noticeable pixelation when a single/small image would otherwise be blown up
# # MAX_IMAGE_UPSCALE_ABS = 1.5


# # def ease_out_cubic(t: float) -> float:
# #     """Ease-out cubic easing function for smooth animations."""
# #     return 1 - pow(1 - t, 3)


# # def ease_in_out_cubic(t: float) -> float:
# #     """Ease-in-out cubic easing function."""
# #     return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


# # def apply_easing(t: float, easing_type: str = "ease_out") -> float:
# #     """Apply easing function to time value t (0 to 1)."""
# #     t = max(0.0, min(1.0, t))  # clamp to [0, 1]
# #     if easing_type == "ease_out":
# #         return ease_out_cubic(t)
# #     elif easing_type == "ease_in_out":
# #         return ease_in_out_cubic(t)
# #     else:
# #         return t  # linear


# # def _cache_path(media_plan: List[Dict[str, Any]], duration: float) -> str:
# #     """Generate cache path based on media_plan and duration."""
# #     # Create a deterministic hash from the parameters
# #     media_plan_str = json.dumps(media_plan, sort_keys=True, separators=(',', ':'))
# #     key_src = f"{duration}|{media_plan_str}".encode("utf-8")
# #     return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp4")


# # def buildShot(media_plan: List[Dict[str, Any]], duration: float) -> str:
# #     """
# #     Layout + animation engine with dynamic, uniform scaling:
# #       • When few items are visible, they render large.
# #       • As new items appear, all visible items scale down together to fit.
# #       • Position and scale transitions are eased for smooth reflows.
    
# #     Returns:
# #         str: Path to the cached video file
# #     """
# #     if not isinstance(media_plan, list):
# #         raise ValueError("media_plan must be a list")
    
# #     print(f"BuildShot: Processing media_plan with {len(media_plan)} items, duration: {duration}s...")
    
# #     # Check cache first
# #     cache_path = _cache_path(media_plan, duration)
# #     if os.path.exists(cache_path):
# #         print(f"BuildShot: Using cached video: {cache_path}")
# #         return cache_path

# #     # --- Layout bounds ---
# #     available_width = max(1, VIDEO_WIDTH - PADDING_LEFT - PADDING_RIGHT)
# #     available_height = max(1, VIDEO_HEIGHT - PADDING_TOP - PADDING_BOTTOM)

# #     # --- Tunables for layout feel ---
# #     GAP_MIN = 64                # desired minimum horizontal gap between items
# #     MIN_SCALE = 0.35            # never shrink below this
# #     MAX_BASE_W = 2048           # cap initial raster size to avoid huge frames (but allow clean upscales)
# #     MAX_BASE_H = 1536

# #     # Keep only items that actually render
# #     render_items = [
# #         it for it in media_plan
# #         if ("path" in it and it.get("path")) or ("text" in it and it.get("text") is not None)
# #     ]
# #     if not render_items:
# #         # Create empty video if no items to render
# #         from moviepy import ColorClip
# #         empty_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=BACKGROUND_COLOR, duration=max(0.1, duration))
# #         empty_clip.write_videofile(
# #             cache_path,
# #             fps=FPS,
# #             codec="libx264",
# #             audio=False,
# #             preset="medium",
# #         )
# #         return cache_path

# #     # Build base clips (no time-dependent transforms yet)
# #     # We cap initial size to keep memory sane; dynamic scaling can further scale, but capped.
# #     # Tuple: (clip, appear_at, base_w, base_h, is_image, orig_w, orig_h)
# #     base_clips: List[Tuple[VideoClip, float, int, int, bool, int, int]] = []

# #     for item in render_items:
# #         appear_at = float(item.get("appearAt", 0) or 0)

# #         is_image = bool("path" in item and item.get("path"))

# #         if is_image:
# #             clip = ImageClip(item["path"])
# #         else:
# #             # Text as a clip; start with a generous font size, we'll scale visually over time.
# #             text_color_hex = f"#{TEXT_COLOR[0]:02x}{TEXT_COLOR[1]:02x}{TEXT_COLOR[2]:02x}"
# #             clip = TextClip(
# #                 text=str(item.get("text", "")),
# #                 font_size=TEXT_FONT_SIZE,   # large base; will be dynamically scaled
# #                 color=text_color_hex,
# #                 size=(None, available_height),
# #                 # prevent baseline clipping in MoviePy v2
# #             )

# #         # Constrain the *base* raster size (no upscaling)
# #         orig_w, orig_h = max(1, clip.w), max(1, clip.h)
# #         scale_w = min(1.0, MAX_BASE_W / orig_w)
# #         scale_h = min(1.0, MAX_BASE_H / orig_h)
# #         s = min(scale_w, scale_h)
# #         if s < 1.0:
# #             clip = clip.resized(s)

# #         base_clips.append((clip, appear_at, clip.w, clip.h, is_image, orig_w, orig_h))

# #     # Timeline end: show for given duration or last appear + hold
# #     last_appear = max(a for _, a, _, _, _, _, _ in base_clips) if base_clips else 0.0
# #     final_duration = float(max(duration, last_appear + POST_HOLD_SECONDS))

# #     # Pre-extract arrays for speed
# #     appear_times = [a for _, a, _, _, _, _, _ in base_clips]
# #     widths = [w for _, _, w, _, _, _, _ in base_clips]
# #     heights = [h for _, _, _, h, _, _, _ in base_clips]
# #     is_image_flags = [img for _, _, _, _, img, _, _ in base_clips]
# #     original_widths = [ow for _, _, _, _, _, ow, _ in base_clips]
# #     original_heights = [oh for _, _, _, _, _, _, oh in base_clips]

# #     # --- Shared animation state across all callbacks ---
# #     # Now supports per-item scales so mixed media can share equal widths.
# #     animation_state = {
# #         "last_visible_set": None,          # tuple of indices
# #         "last_positions": {},              # idx -> (x, y) from previous layout
# #         "target_positions": {},            # idx -> (x, y) for current layout
# #         "last_scales": {},                 # idx -> scale for previous layout
# #         "target_scales": {},               # idx -> scale for current layout
# #         "animation_start_time": None,      # global t when layout changed
# #     }

# #     def compute_target_layout(visible: List[int]):
# #         """
# #         Compute per-item scales and positions.
# #         - If one item: scale it up to fill the available area (respecting padding) and center it.
# #         - If multiple items: enforce equal target widths across all items, while respecting height.
# #         Returns: (positions: dict[idx]->(x,y), scales: dict[idx]->float)
# #         """
# #         if not visible:
# #             return {}, {}

# #         n = len(visible)

# #         # Helper: per-item max allowed dynamic scale relative to base raster
# #         # Ensures final display size <= MAX_IMAGE_UPSCALE_ABS * original resolution
# #         def allowed_scale_limit(idx: int) -> float:
# #             if not is_image_flags[idx]:
# #                 return float("inf")  # no hard cap for text
# #             base_w = max(1.0, widths[idx])
# #             base_h = max(1.0, heights[idx])
# #             o_w = max(1.0, original_widths[idx])
# #             o_h = max(1.0, original_heights[idx])
# #             # Aspect ratio preserved; width ratio == height ratio == (final/base)
# #             limit_w = MAX_IMAGE_UPSCALE_ABS * (o_w / base_w)
# #             limit_h = MAX_IMAGE_UPSCALE_ABS * (o_h / base_h)
# #             return max(MIN_SCALE, min(limit_w, limit_h))

# #         # Single item: maximize within available rect (allow upscaling but capped for images)
# #         if n == 1:
# #             idx = visible[0]
# #             s_fill_w = available_width / max(1, widths[idx])
# #             s_fill_h = available_height / max(1, heights[idx])
# #             s = max(MIN_SCALE, min(s_fill_w, s_fill_h))
# #             # Cap image upscaling to avoid pixelation
# #             s = min(s, allowed_scale_limit(idx))

# #             scaled_w = widths[idx] * s
# #             scaled_h = heights[idx] * s
# #             x_left = int(PADDING_LEFT + (available_width - scaled_w) / 2)
# #             y_top = int(PADDING_TOP + (available_height - scaled_h) / 2)
# #             return {idx: (x_left, y_top)}, {idx: s}

# #         # Multiple items: equal width for all, with adaptive gaps
# #         content_width_budget = max(1.0, available_width - GAP_MIN * (n + 1))
# #         equal_target_width = content_width_budget / n

# #         # Also respect image caps: equal target width cannot exceed any item's allowed max width
# #         max_width_per_item = []
# #         for i in visible:
# #             cap_scale = allowed_scale_limit(i)
# #             max_width_per_item.append(widths[i] * cap_scale)
# #         if max_width_per_item:
# #             equal_target_width = min(equal_target_width, min(max_width_per_item))

# #         # Initial per-item scales to reach equal width
# #         raw_scales = {i: equal_target_width / max(1.0, widths[i]) for i in visible}
# #         # Ensure we never go below MIN_SCALE and never exceed per-item cap
# #         for i in visible:
# #             raw_scales[i] = max(MIN_SCALE, min(raw_scales[i], allowed_scale_limit(i)))

# #         # If heights overflow, shrink all uniformly
# #         scaled_heights = [heights[i] * raw_scales[i] for i in visible]
# #         max_scaled_h = max(scaled_heights) if scaled_heights else 0.0
# #         if max_scaled_h > available_height:
# #             height_scale = available_height / max_scaled_h
# #             for i in visible:
# #                 raw_scales[i] *= height_scale

# #         # With resulting scales, compute actual free width to distribute as gaps
# #         scaled_sum_w = sum(widths[i] * raw_scales[i] for i in visible)
# #         free_w = max(0.0, available_width - scaled_sum_w)
# #         gap = free_w / (n + 1)

# #         # Positions: horizontally spaced with equal gaps, vertically centered per item height
# #         positions = {}
# #         x_cursor = PADDING_LEFT + gap
# #         for i in visible:
# #             scaled_h = heights[i] * raw_scales[i]
# #             y_top = int(PADDING_TOP + (available_height - scaled_h) / 2)
# #             positions[i] = (int(x_cursor), y_top)
# #             x_cursor += widths[i] * raw_scales[i] + gap

# #         return positions, raw_scales

# #     def ensure_layout_for_time(global_t: float):
# #         """
# #         Update target layout if the set of visible clips has changed.
# #         Start a new reflow animation window when it does.
# #         """
# #         visible = [i for i, a in enumerate(appear_times) if a <= global_t]
# #         visible_set = tuple(sorted(visible))

# #         if animation_state["last_visible_set"] != visible_set:
# #             new_positions, new_scales = compute_target_layout(visible)
# #             animation_state["target_positions"] = new_positions
# #             animation_state["target_scales"] = new_scales

# #             # Initialize or carry previous layout for smooth interpolation
# #             if animation_state["last_visible_set"] is None:
# #                 animation_state["last_positions"] = new_positions.copy()
# #                 animation_state["last_scales"] = new_scales.copy()
# #             else:
# #                 # Ensure every newly-visible clip has a starting pos/scale (use target as fallback)
# #                 for idx in visible:
# #                     if idx not in animation_state["last_positions"]:
# #                         animation_state["last_positions"][idx] = new_positions[idx]
# #                     if idx not in animation_state["last_scales"]:
# #                         animation_state["last_scales"][idx] = new_scales[idx]

# #             animation_state["animation_start_time"] = global_t
# #             animation_state["last_visible_set"] = visible_set

# #     def current_interp(global_t: float):
# #         """
# #         Ensure layout is up-to-date and return eased interpolation factor (0..1).
# #         Also commits target state when the animation window ends.
# #         """
# #         ensure_layout_for_time(global_t)

# #         in_anim = (
# #             animation_state["animation_start_time"] is not None and
# #             global_t < animation_state["animation_start_time"] + ANIMATION_DURATION
# #         )
# #         if not in_anim:
# #             # Lock in the target layout after animation window ends
# #             animation_state["last_positions"] = animation_state["target_positions"].copy()
# #             animation_state["last_scales"] = animation_state["target_scales"].copy()
# #             return 1.0

# #         # Progress (0..1) eased
# #         raw = (global_t - animation_state["animation_start_time"]) / ANIMATION_DURATION
# #         eased = apply_easing(max(0.0, min(1.0, raw)), ANIMATION_EASING)
# #         return eased

# #     def make_position_fn(self_idx: int, own_appear_time: float):
# #         def pos(local_t: float):
# #             # Convert to absolute timeline (global time)
# #             local_t = max(0.0, local_t)
# #             global_t = own_appear_time + local_t

# #             # Visibility gate
# #             if global_t < own_appear_time:
# #                 return (-99999, -99999)

# #             eased = current_interp(global_t)

# #             # Interpolate this clip's position
# #             last_pos = animation_state["last_positions"].get(self_idx)
# #             target_pos = animation_state["target_positions"].get(self_idx)

# #             if last_pos is None or target_pos is None:
# #                 return (-99999, -99999)

# #             x0, y0 = last_pos
# #             x1, y1 = target_pos
# #             cx = int(x0 + (x1 - x0) * eased)
# #             cy = int(y0 + (y1 - y0) * eased)

# #             # Entrance slide-in for this clip only (local time window)
# #             if local_t < ENTRANCE_DURATION:
# #                 p = apply_easing(local_t / ENTRANCE_DURATION, "ease_out")
# #                 offset = int(ENTRANCE_TRANSLATE_OFFSET * (1 - p))
# #                 cx += offset

# #             return (cx, cy)
# #         return pos

# #     def make_scale_fn(self_idx: int, own_appear_time: float):
# #         def scale(local_t: float):
# #             local_t = max(0.0, local_t)
# #             global_t = own_appear_time + local_t

# #             # If not yet visible, return something (won't be sampled visually anyway)
# #             if global_t < own_appear_time:
# #                 return animation_state["last_scales"].get(self_idx, animation_state["target_scales"].get(self_idx, 1.0))

# #             eased = current_interp(global_t)

# #             # Interpolate this clip's scale between last and target per-item scales
# #             s0 = animation_state["last_scales"].get(self_idx)
# #             s1 = animation_state["target_scales"].get(self_idx)
# #             if s0 is None or s1 is None:
# #                 # Fallback to target scale if something is missing
# #                 s = s1 if s1 is not None else 1.0
# #             else:
# #                 s = s0 + (s1 - s0) * eased

# #             # Tiny entrance emphasis
# #             if local_t < ENTRANCE_DURATION:
# #                 p = apply_easing(local_t / ENTRANCE_DURATION, "ease_out")
# #                 s = s * (0.985 + 0.015 * p)

# #             return s
# #         return scale

# #     # Compose clips with dynamic position + scale + fade-in
# #     composed = []
# #     for idx, (clip, appear_at, _, _, _, _, _) in enumerate(base_clips):
# #         clip_duration = max(0.01, final_duration - appear_at)
# #         fade_dur = min(ENTRANCE_DURATION, clip_duration)

# #         animated_clip = (
# #             clip
# #             .with_start(appear_at)
# #             .with_duration(clip_duration)
# #             .with_position(make_position_fn(idx, appear_at))
# #             .with_effects([
# #                 vfx.Resize(make_scale_fn(idx, appear_at)),   # dynamic, uniform scaling
# #                 vfx.CrossFadeIn(fade_dur),                   # entrance fade
# #             ])
# #         )
# #         composed.append(animated_clip)

# #     # Render
# #     print(f"BuildShot: Generating new video: {cache_path}")
# #     CompositeVideoClip(
# #         composed,
# #         size=(VIDEO_WIDTH, VIDEO_HEIGHT),
# #         bg_color=BACKGROUND_COLOR,
# #     ).with_duration(final_duration).write_videofile(
# #         cache_path,
# #         fps=FPS,
# #         codec="libx264",
# #         audio=False,
# #         preset="medium",
# #     )
    
# #     return cache_path

# from typing import List, Dict, Any, Tuple
# from moviepy import ImageClip, CompositeVideoClip, TextClip, VideoClip, vfx
# import numpy as np
# import os
# import hashlib
# import json

# # ===== Constants =====
# VIDEO_WIDTH = 1920
# VIDEO_HEIGHT = 1080
# FPS = 30
# BACKGROUND_COLOR = (10, 10, 10)  # RGB

# # Layout controls
# MAX_ITEMS_PER_ROW = 2           # 👈 cap items per row; overflow wraps to the next row
# H_GAP_MIN = 64                  # minimum horizontal gap inside a row
# V_GAP_MIN = 56                  # minimum vertical gap between rows

# # Cache settings
# CACHE_DIR = "cache/buildshot"
# os.makedirs(CACHE_DIR, exist_ok=True)

# PADDING_LEFT = 120
# PADDING_RIGHT = 120
# PADDING_TOP = 120
# PADDING_BOTTOM = 120

# TEXT_COLOR = (255, 255, 255)
# TEXT_FONT_SIZE = 80

# POST_HOLD_SECONDS = 3

# # Animation settings
# ANIMATION_DURATION = 0.4   # seconds for smooth repositioning/resize
# ANIMATION_EASING = "ease_out"  # easing type
# ENTRANCE_DURATION = 0.45   # seconds for fade-in and translate-in
# ENTRANCE_TRANSLATE_OFFSET = 28  # pixels to slide in from

# # Max allowed absolute image upscaling relative to its original/native resolution
# # This prevents noticeable pixelation when a single/small image would otherwise be blown up
# MAX_IMAGE_UPSCALE_ABS = 1.5


# def ease_out_cubic(t: float) -> float:
#     """Ease-out cubic easing function for smooth animations."""
#     return 1 - pow(1 - t, 3)


# def ease_in_out_cubic(t: float) -> float:
#     """Ease-in-out cubic easing function."""
#     return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


# def apply_easing(t: float, easing_type: str = "ease_out") -> float:
#     """Apply easing function to time value t (0 to 1)."""
#     t = max(0.0, min(1.0, t))  # clamp to [0, 1]
#     if easing_type == "ease_out":
#         return ease_out_cubic(t)
#     elif easing_type == "ease_in_out":
#         return ease_in_out_cubic(t)
#     else:
#         return t  # linear


# def _cache_path(media_plan: List[Dict[str, Any]], duration: float) -> str:
#     """Generate cache path based on media_plan and duration."""
#     media_plan_str = json.dumps(media_plan, sort_keys=True, separators=(',', ':'))
#     key_src = f"{duration}|{media_plan_str}".encode("utf-8")
#     return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp4")


# def buildShot(media_plan: List[Dict[str, Any]], duration: float) -> str:
#     """
#     Layout + animation engine with dynamic, uniform scaling and row wrapping:
#       • When few items are visible, they render large.
#       • As new items appear, all visible items scale and reflow smoothly.
#       • Items wrap to additional rows when MAX_ITEMS_PER_ROW is reached.
#       • Rows and items are perfectly centered with even spacing.
#     Returns:
#         str: Path to the cached video file
#     """
#     if not isinstance(media_plan, list):
#         raise ValueError("media_plan must be a list")

#     print(f"BuildShot: Processing media_plan with {len(media_plan)} items, duration: {duration}s...")

#     # Check cache first
#     cache_path = _cache_path(media_plan, duration)
#     if os.path.exists(cache_path):
#         print(f"BuildShot: Using cached video: {cache_path}")
#         return cache_path

#     # --- Layout bounds ---
#     available_width = max(1, VIDEO_WIDTH - PADDING_LEFT - PADDING_RIGHT)
#     available_height = max(1, VIDEO_HEIGHT - PADDING_TOP - PADDING_BOTTOM)

#     # --- Tunables for layout feel ---
#     MIN_SCALE = 0.35            # never shrink below this before global fit checks
#     MAX_BASE_W = 2048           # cap initial raster size to avoid huge frames (but allow clean upscales)
#     MAX_BASE_H = 1536

#     # Keep only items that actually render
#     render_items = [
#         it for it in media_plan
#         if ("path" in it and it.get("path")) or ("text" in it and it.get("text") is not None)
#     ]
#     if not render_items:
#         from moviepy import ColorClip
#         empty_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=BACKGROUND_COLOR, duration=max(0.1, duration))
#         empty_clip.write_videofile(
#             cache_path,
#             fps=FPS,
#             codec="libx264",
#             audio=False,
#             preset="medium",
#         )
#         return cache_path

#     # Build base clips (no time-dependent transforms yet)
#     # Tuple: (clip, appear_at, base_w, base_h, is_image, orig_w, orig_h)
#     base_clips: List[Tuple[VideoClip, float, int, int, bool, int, int]] = []

#     for item in render_items:
#         appear_at = float(item.get("appearAt", 0) or 0)
#         is_image = bool("path" in item and item.get("path"))

#         if is_image:
#             clip = ImageClip(item["path"])
#         else:
#             text_color_hex = f"#{TEXT_COLOR[0]:02x}{TEXT_COLOR[1]:02x}{TEXT_COLOR[2]:02x}"
#             clip = TextClip(
#                 text=str(item.get("text", "")),
#                 font_size=TEXT_FONT_SIZE,
#                 color=text_color_hex,
#                 size=(None, available_height),
#             )

#         # Constrain the *base* raster size (no upscaling)
#         orig_w, orig_h = max(1, clip.w), max(1, clip.h)
#         scale_w = min(1.0, MAX_BASE_W / orig_w)
#         scale_h = min(1.0, MAX_BASE_H / orig_h)
#         s = min(scale_w, scale_h)
#         if s < 1.0:
#             clip = clip.resized(s)

#         base_clips.append((clip, appear_at, clip.w, clip.h, is_image, orig_w, orig_h))

#     # Timeline end: show for given duration or last appear + hold
#     last_appear = max(a for _, a, _, _, _, _, _ in base_clips) if base_clips else 0.0
#     final_duration = float(max(duration, last_appear + POST_HOLD_SECONDS))

#     # Pre-extract arrays for speed
#     appear_times = [a for _, a, _, _, _, _, _ in base_clips]
#     widths = [w for _, _, w, _, _, _, _ in base_clips]
#     heights = [h for _, _, _, h, _, _, _ in base_clips]
#     is_image_flags = [img for _, _, _, _, img, _, _ in base_clips]
#     original_widths = [ow for _, _, _, _, _, ow, _ in base_clips]
#     original_heights = [oh for _, _, _, _, _, _, oh in base_clips]

#     # --- Shared animation state across all callbacks ---
#     animation_state = {
#         "last_visible_set": None,          # tuple of indices
#         "last_positions": {},              # idx -> (x, y) from previous layout
#         "target_positions": {},            # idx -> (x, y) for current layout
#         "last_scales": {},                 # idx -> scale for previous layout
#         "target_scales": {},               # idx -> scale for current layout
#         "animation_start_time": None,      # global t when layout changed
#     }

#     def compute_target_layout(visible: List[int]):
#         """
#         Compute per-item scales and positions with row wrapping.
#         - Items are split into rows of at most MAX_ITEMS_PER_ROW.
#         - Within each row, items target equal widths; rows are centered and evenly spaced.
#         - If overall content exceeds available height, all rows/items shrink uniformly.
#         Returns: (positions: dict[idx]->(x,y), scales: dict[idx]->float)
#         """
#         if not visible:
#             return {}, {}

#         # Helper: per-item max allowed dynamic scale relative to base raster
#         def allowed_scale_limit(idx: int) -> float:
#             if not is_image_flags[idx]:
#                 return float("inf")  # no hard cap for text
#             base_w = max(1.0, widths[idx])
#             base_h = max(1.0, heights[idx])
#             o_w = max(1.0, original_widths[idx])
#             o_h = max(1.0, original_heights[idx])
#             limit_w = MAX_IMAGE_UPSCALE_ABS * (o_w / base_w)
#             limit_h = MAX_IMAGE_UPSCALE_ABS * (o_h / base_h)
#             return max(MIN_SCALE, min(limit_w, limit_h))

#         # Split into rows
#         rows: List[List[int]] = []
#         if MAX_ITEMS_PER_ROW <= 0:
#             rows.append(list(visible))
#         else:
#             for i in range(0, len(visible), MAX_ITEMS_PER_ROW):
#                 rows.append(visible[i:i + MAX_ITEMS_PER_ROW])

#         # First pass: compute raw per-item scales per row (equal target width inside a row)
#         scales: Dict[int, float] = {}
#         row_heights: List[float] = []

#         for row in rows:
#             n = len(row)
#             if n == 0:
#                 row_heights.append(0.0)
#                 continue

#             content_width_budget = max(1.0, available_width - H_GAP_MIN * (n + 1))
#             equal_target_width = content_width_budget / n

#             # Ensure equal width doesn't exceed any item's allowed cap
#             max_width_per_item = []
#             for idx in row:
#                 cap_scale = allowed_scale_limit(idx)
#                 max_width_per_item.append(widths[idx] * cap_scale)
#             if max_width_per_item:
#                 equal_target_width = min(equal_target_width, min(max_width_per_item))

#             # Per-item scale to reach equal width, clamped to limits
#             for idx in row:
#                 s = equal_target_width / max(1.0, widths[idx])
#                 s = max(MIN_SCALE, min(s, allowed_scale_limit(idx)))
#                 scales[idx] = s

#             # Row height is the max scaled height in the row
#             row_heights.append(max(heights[idx] * scales[idx] for idx in row))

#         # Second pass: ensure total vertical fit (rows + gaps) within available height
#         total_rows = len(rows)
#         total_content_height = sum(row_heights) + V_GAP_MIN * max(0, total_rows - 1)
#         if total_content_height > available_height:
#             # Uniformly scale down all items to fit vertically
#             shrink = available_height / total_content_height
#             for idx in scales:
#                 scales[idx] *= shrink
#             row_heights = [h * shrink for h in row_heights]
#             total_content_height = sum(row_heights) + V_GAP_MIN * max(0, total_rows - 1)

#         # Third pass: compute positions (center block vertically; center items in rows with even gaps)
#         positions: Dict[int, Tuple[int, int]] = {}
#         y_cursor = PADDING_TOP + (available_height - total_content_height) / 2.0

#         for r, row in enumerate(rows):
#             n = len(row)
#             if n == 0:
#                 continue

#             # Row width after scaling
#             row_scaled_width = sum(widths[idx] * scales[idx] for idx in row)
#             free_w = max(0.0, available_width - row_scaled_width)
#             gap = free_w / (n + 1)

#             x_cursor = PADDING_LEFT + gap
#             row_h = row_heights[r]

#             for idx in row:
#                 scaled_w = widths[idx] * scales[idx]
#                 scaled_h = heights[idx] * scales[idx]
#                 # Vertically center each item inside the row band
#                 y_top = int(y_cursor + (row_h - scaled_h) / 2.0)
#                 positions[idx] = (int(x_cursor), y_top)
#                 x_cursor += scaled_w + gap

#             y_cursor += row_h + (V_GAP_MIN if r < total_rows - 1 else 0.0)

#         return positions, scales

#     def ensure_layout_for_time(global_t: float):
#         """
#         Update target layout if the set of visible clips has changed.
#         Start a new reflow animation window when it does.
#         """
#         visible = [i for i, a in enumerate(appear_times) if a <= global_t]
#         visible_set = tuple(sorted(visible))

#         if animation_state["last_visible_set"] != visible_set:
#             new_positions, new_scales = compute_target_layout(visible)
#             animation_state["target_positions"] = new_positions
#             animation_state["target_scales"] = new_scales

#             # Initialize or carry previous layout for smooth interpolation
#             if animation_state["last_visible_set"] is None:
#                 animation_state["last_positions"] = new_positions.copy()
#                 animation_state["last_scales"] = new_scales.copy()
#             else:
#                 for idx in visible:
#                     if idx not in animation_state["last_positions"]:
#                         animation_state["last_positions"][idx] = new_positions[idx]
#                     if idx not in animation_state["last_scales"]:
#                         animation_state["last_scales"][idx] = new_scales[idx]

#             animation_state["animation_start_time"] = global_t
#             animation_state["last_visible_set"] = visible_set

#     def current_interp(global_t: float):
#         """
#         Ensure layout is up-to-date and return eased interpolation factor (0..1).
#         Also commits target state when the animation window ends.
#         """
#         ensure_layout_for_time(global_t)

#         in_anim = (
#             animation_state["animation_start_time"] is not None and
#             global_t < animation_state["animation_start_time"] + ANIMATION_DURATION
#         )
#         if not in_anim:
#             # Lock in the target layout after animation window ends
#             animation_state["last_positions"] = animation_state["target_positions"].copy()
#             animation_state["last_scales"] = animation_state["target_scales"].copy()
#             return 1.0

#         raw = (global_t - animation_state["animation_start_time"]) / ANIMATION_DURATION
#         eased = apply_easing(max(0.0, min(1.0, raw)), ANIMATION_EASING)
#         return eased

#     def make_position_fn(self_idx: int, own_appear_time: float):
#         def pos(local_t: float):
#             local_t = max(0.0, local_t)
#             global_t = own_appear_time + local_t

#             eased = current_interp(global_t)

#             last_pos = animation_state["last_positions"].get(self_idx)
#             target_pos = animation_state["target_positions"].get(self_idx)
#             if last_pos is None or target_pos is None:
#                 return (-99999, -99999)

#             x0, y0 = last_pos
#             x1, y1 = target_pos
#             cx = int(x0 + (x1 - x0) * eased)
#             cy = int(y0 + (y1 - y0) * eased)

#             # Entrance slide-in for this clip only (local time window)
#             if local_t < ENTRANCE_DURATION:
#                 p = apply_easing(local_t / ENTRANCE_DURATION, "ease_out")
#                 offset = int(ENTRANCE_TRANSLATE_OFFSET * (1 - p))
#                 cx += offset

#             return (cx, cy)
#         return pos

#     def make_scale_fn(self_idx: int, own_appear_time: float):
#         def scale(local_t: float):
#             local_t = max(0.0, local_t)
#             global_t = own_appear_time + local_t

#             eased = current_interp(global_t)

#             s0 = animation_state["last_scales"].get(self_idx)
#             s1 = animation_state["target_scales"].get(self_idx)
#             if s0 is None or s1 is None:
#                 s = s1 if s1 is not None else 1.0
#             else:
#                 s = s0 + (s1 - s0) * eased

#             # Tiny entrance emphasis
#             if local_t < ENTRANCE_DURATION:
#                 p = apply_easing(local_t / ENTRANCE_DURATION, "ease_out")
#                 s = s * (0.985 + 0.015 * p)

#             return s
#         return scale

#     # Compose clips with dynamic position + scale + fade-in
#     composed = []
#     for idx, (clip, appear_at, _, _, _, _, _) in enumerate(base_clips):
#         clip_duration = max(0.01, final_duration - appear_at)
#         fade_dur = min(ENTRANCE_DURATION, clip_duration)

#         animated_clip = (
#             clip
#             .with_start(appear_at)
#             .with_duration(clip_duration)
#             .with_position(make_position_fn(idx, appear_at))
#             .with_effects([
#                 vfx.Resize(make_scale_fn(idx, appear_at)),   # dynamic, uniform scaling
#                 vfx.CrossFadeIn(fade_dur),                   # entrance fade
#             ])
#         )
#         composed.append(animated_clip)

#     # Render
#     print(f"BuildShot: Generating new video: {cache_path}")
#     CompositeVideoClip(
#         composed,
#         size=(VIDEO_WIDTH, VIDEO_HEIGHT),
#         bg_color=BACKGROUND_COLOR,
#     ).with_duration(final_duration).write_videofile(
#         cache_path,
#         fps=FPS,
#         codec="libx264",
#         audio=False,
#         preset="medium",
#     )

#     return cache_path

# from typing import List, Dict, Any, Tuple
# from moviepy import ImageClip, CompositeVideoClip, TextClip, VideoClip, vfx
# import os
# import hashlib
# import json

# # ===== Constants =====
# VIDEO_WIDTH = 1920
# VIDEO_HEIGHT = 1080
# FPS = 30
# BACKGROUND_COLOR = (10, 10, 10)  # RGB

# # Layout controls
# MAX_ITEMS_PER_ROW = 2            # 👈 cap items per row; overflow wraps to next row(s)
# H_GAP_MIN = 64                   # minimum horizontal gap inside a row
# V_GAP_MIN = 16                   # minimum vertical gap between rows
# ROW_HEIGHT_DECAY = 0.3           # 👈 bottom row gets most height; each row above has this fraction of the row below

# # Cache settings
# CACHE_DIR = "cache/buildshot"
# os.makedirs(CACHE_DIR, exist_ok=True)

# PADDING_LEFT = 120
# PADDING_RIGHT = 120
# PADDING_TOP = 120
# PADDING_BOTTOM = 120

# TEXT_COLOR = (0, 0, 0)
# TEXT_FONT_SIZE = 80
# FONT_FILE = "font.ttf"
# BACKGROUND_IMAGE = "background.png"

# POST_HOLD_SECONDS = 3

# # Animation settings
# ANIMATION_DURATION = 0.4         # seconds for smooth repositioning/resize
# ANIMATION_EASING = "ease_out"    # easing type
# ENTRANCE_DURATION = 0.45         # seconds for fade-in and translate-in
# ENTRANCE_TRANSLATE_OFFSET = 28   # pixels to slide in from

# # Group near-simultaneous arrivals to reduce layout thrashing/jitter
# COALESCE_LOOKAHEAD = 0.25        # seconds to look ahead when computing layout

# # Max allowed absolute image upscaling relative to its original/native resolution
# # This prevents noticeable pixelation when a single/small image would otherwise be blown up
# MAX_IMAGE_UPSCALE_ABS = 1.5


# def ease_out_cubic(t: float) -> float:
#     return 1 - pow(1 - t, 3)


# def ease_in_out_cubic(t: float) -> float:
#     return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


# def apply_easing(t: float, easing_type: str = "ease_out") -> float:
#     t = max(0.0, min(1.0, t))
#     if easing_type == "ease_out":
#         return ease_out_cubic(t)
#     elif easing_type == "ease_in_out":
#         return ease_in_out_cubic(t)
#     return t


# def _cache_path(media_plan: List[Dict[str, Any]], duration: float) -> str:
#     media_plan_str = json.dumps(media_plan, sort_keys=True, separators=(',', ':'))
#     key_src = f"{duration}|{media_plan_str}".encode("utf-8")
#     return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp4")


# def buildShot(media_plan: List[Dict[str, Any]], duration: float) -> str:
#     """
#     Layout + animation engine with dynamic scaling, row wrapping, and prioritized bottom-row height:
#       • Items wrap when MAX_ITEMS_PER_ROW is reached.
#       • Bottom row takes the majority of vertical space; rows above receive progressively less (ROW_HEIGHT_DECAY).
#       • Items in each row have equal target widths, are horizontally centered with even gaps, and vertically centered within their row band.
#       • Smooth eased transitions on reflow and entrance.
#     Returns:
#         str: Path to the cached video file
#     """
#     if not isinstance(media_plan, list):
#         raise ValueError("media_plan must be a list")

#     cache_path = _cache_path(media_plan, duration)
#     if os.path.exists(cache_path):
#         return cache_path

#     available_width = max(1, VIDEO_WIDTH - PADDING_LEFT - PADDING_RIGHT)
#     available_height = max(1, VIDEO_HEIGHT - PADDING_TOP - PADDING_BOTTOM)

#     # Tunables
#     MIN_SCALE = 0.35
#     MAX_BASE_W = 2048
#     MAX_BASE_H = 1536

#     # Filter items that actually render
#     render_items = [
#         it for it in media_plan
#         if ("path" in it and it.get("path")) or ("text" in it and it.get("text") is not None)
#     ]
#     if not render_items:
#         from moviepy import ColorClip
#         ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=BACKGROUND_COLOR, duration=max(0.1, duration)).write_videofile(
#             cache_path, fps=FPS, codec="libx264", audio=False, preset="medium"
#         )
#         return cache_path

#     # Build base clips
#     base_clips: List[Tuple[VideoClip, float, int, int, bool, int, int]] = []
#     for item in render_items:
#         appear_at = float(item.get("appearAt", 0) or 0)
#         is_image = bool("path" in item and item.get("path"))

#         if is_image:
#             clip = ImageClip(item["path"])
#         else:
#             text_color_hex = f"#{TEXT_COLOR[0]:02x}{TEXT_COLOR[1]:02x}{TEXT_COLOR[2]:02x}"
#             clip = TextClip(
#                 text=str(item.get("text", "")),
#                 font_size=TEXT_FONT_SIZE,
#                 color=text_color_hex,
#                 size=(None, available_height),
#                 font=FONT_FILE,
#             )

#         orig_w, orig_h = max(1, clip.w), max(1, clip.h)
#         s = min(1.0, MAX_BASE_W / orig_w, MAX_BASE_H / orig_h)
#         if s < 1.0:
#             clip = clip.resized(s)

#         base_clips.append((clip, appear_at, clip.w, clip.h, is_image, orig_w, orig_h))

#     last_appear = max(a for _, a, _, _, _, _, _ in base_clips) if base_clips else 0.0
#     final_duration = float(max(duration, last_appear + POST_HOLD_SECONDS))

#     appear_times = [a for _, a, _, _, _, _, _ in base_clips]
#     widths = [w for _, _, w, _, _, _, _ in base_clips]
#     heights = [h for _, _, _, h, _, _, _ in base_clips]
#     is_image_flags = [img for _, _, _, _, img, _, _ in base_clips]
#     original_widths = [ow for _, _, _, _, _, ow, _ in base_clips]
#     original_heights = [oh for _, _, _, _, _, _, oh in base_clips]

#     # Animation state
#     animation_state = {
#         "last_visible_set": None,
#         "last_positions": {},
#         "target_positions": {},
#         "last_scales": {},
#         "target_scales": {},
#         "animation_start_time": None,
#     }

#     def allowed_scale_limit(idx: int) -> float:
#         if not is_image_flags[idx]:
#             return float("inf")
#         base_w = max(1.0, widths[idx])
#         base_h = max(1.0, heights[idx])
#         o_w = max(1.0, original_widths[idx])
#         o_h = max(1.0, original_heights[idx])
#         limit_w = MAX_IMAGE_UPSCALE_ABS * (o_w / base_w)
#         limit_h = MAX_IMAGE_UPSCALE_ABS * (o_h / base_h)
#         return max(MIN_SCALE, min(limit_w, limit_h))

#     def compute_target_layout(visible: List[int]):
#         if not visible:
#             return {}, {}

#         # Split into rows by MAX_ITEMS_PER_ROW
#         rows: List[List[int]] = []
#         if MAX_ITEMS_PER_ROW <= 0:
#             rows.append(list(visible))
#         else:
#             for i in range(0, len(visible), MAX_ITEMS_PER_ROW):
#                 rows.append(visible[i:i + MAX_ITEMS_PER_ROW])

#         num_rows = len(rows)

#         # Compute row weights so bottom row has weight 1.0 and each row above decays
#         # Example (3 rows): top=decay^2, mid=decay^1, bottom=1.0
#         weights = [ROW_HEIGHT_DECAY ** (num_rows - 1 - r) for r in range(num_rows)]
#         weight_sum = max(1e-6, sum(weights))

#         # Total vertical gap space
#         total_gap_h = V_GAP_MIN * max(0, num_rows - 1)
#         band_total_height = max(1.0, available_height - total_gap_h)

#         # Row band heights from weights (bottom gets the largest share)
#         row_bands: List[float] = [band_total_height * (w / weight_sum) for w in weights]

#         # Per-item scales and positions to fill bands, preserving equal widths inside each row
#         scales: Dict[int, float] = {}
#         row_heights: List[float] = []

#         for r, row in enumerate(rows):
#             n = len(row)
#             if n == 0:
#                 row_heights.append(0.0)
#                 continue

#             # Width budget for content (keeping at least H_GAP_MIN gaps)
#             content_width_budget = max(1.0, available_width - H_GAP_MIN * (n + 1))
#             equal_target_width = content_width_budget / n

#             # Cap equal target width by each item's upscale limit
#             max_width_per_item = [widths[idx] * allowed_scale_limit(idx) for idx in row]
#             if max_width_per_item:
#                 equal_target_width = min(equal_target_width, min(max_width_per_item))

#             # Initial per-item scales to hit equal target width
#             for idx in row:
#                 s_i = equal_target_width / max(1.0, widths[idx])
#                 s_i = min(s_i, allowed_scale_limit(idx))
#                 scales[idx] = max(1e-6, s_i)  # avoid zero/neg

#             # Enforce band height: shrink uniformly within this row if needed
#             max_scaled_h = max(heights[idx] * scales[idx] for idx in row)
#             band_h = row_bands[r]
#             if max_scaled_h > band_h:
#                 shrink = band_h / max_scaled_h
#                 for idx in row:
#                     scales[idx] *= shrink

#             # If row still exceeds horizontal width (numerical edge cases), shrink uniformly
#             row_scaled_w = sum(widths[idx] * scales[idx] for idx in row)
#             if row_scaled_w > available_width:
#                 shrink_w = available_width / row_scaled_w
#                 for idx in row:
#                     scales[idx] *= shrink_w

#             # Record actual row height used by tallest item after adjustments
#             row_heights.append(max(heights[idx] * scales[idx] for idx in row))

#         # Positions: allocate vertical bands (rows + fixed gaps fill the available height exactly)
#         positions: Dict[int, Tuple[int, int]] = {}
#         y_cursor = PADDING_TOP
#         for r, row in enumerate(rows):
#             n = len(row)
#             if n == 0:
#                 continue

#             # Horizontal layout: compute gap so items are evenly spaced and centered
#             row_scaled_width = sum(widths[idx] * scales[idx] for idx in row)
#             free_w = max(0.0, available_width - row_scaled_width)
#             gap_x = free_w / (n + 1)

#             x_cursor = PADDING_LEFT + gap_x
#             # Vertically center each item inside its row band
#             band_h = row_bands[r]
#             for idx in row:
#                 scaled_w = widths[idx] * scales[idx]
#                 scaled_h = heights[idx] * scales[idx]
#                 y_top = int(y_cursor + (band_h - scaled_h) / 2.0)
#                 positions[idx] = (int(x_cursor), y_top)
#                 x_cursor += scaled_w + gap_x

#             # Advance to next row band (add fixed vertical gap between rows)
#             y_cursor += band_h + (V_GAP_MIN if r < num_rows - 1 else 0.0)

#         return positions, scales

#     def ensure_layout_for_time(global_t: float):
#         # Coalesce items that arrive within a small lookahead window to avoid back-to-back reflows
#         planned_visible = [i for i, a in enumerate(appear_times) if a <= global_t + COALESCE_LOOKAHEAD]
#         planned_set = tuple(sorted(planned_visible))

#         if animation_state["last_visible_set"] != planned_set:
#             # Compute the current, in-flight position/scale as the new baseline to prevent jumps
#             prev_start = animation_state.get("animation_start_time")
#             if prev_start is not None and animation_state["target_positions"]:
#                 prev_raw = (global_t - prev_start) / ANIMATION_DURATION
#                 prev_eased = apply_easing(max(0.0, min(1.0, prev_raw)), ANIMATION_EASING)
#             else:
#                 prev_eased = 1.0

#             current_positions: Dict[int, Tuple[int, int]] = {}
#             current_scales: Dict[int, float] = {}
#             existing_indices = set(animation_state["last_positions"].keys()) | set(animation_state["target_positions"].keys())
#             for idx in existing_indices:
#                 lp = animation_state["last_positions"].get(idx)
#                 tp = animation_state["target_positions"].get(idx)
#                 if lp is not None and tp is not None:
#                     x0, y0 = lp
#                     x1, y1 = tp
#                     cx = int(x0 + (x1 - x0) * prev_eased)
#                     cy = int(y0 + (y1 - y0) * prev_eased)
#                     current_positions[idx] = (cx, cy)
#                 s0 = animation_state["last_scales"].get(idx)
#                 s1 = animation_state["target_scales"].get(idx)
#                 if s0 is not None and s1 is not None:
#                     cs = s0 + (s1 - s0) * prev_eased
#                     current_scales[idx] = cs

#             # Compute new targets using the coalesced visible set
#             new_positions, new_scales = compute_target_layout(planned_visible)
#             animation_state["target_positions"] = new_positions
#             animation_state["target_scales"] = new_scales

#             if animation_state["last_visible_set"] is None:
#                 # First layout: start from targets
#                 animation_state["last_positions"] = new_positions.copy()
#                 animation_state["last_scales"] = new_scales.copy()
#             else:
#                 # Continue from the current in-flight state for smoothness
#                 if current_positions:
#                     animation_state["last_positions"].update(current_positions)
#                 if current_scales:
#                     animation_state["last_scales"].update(current_scales)
#                 # Ensure new indices (e.g., planned but not yet visible) have a baseline
#                 for idx in new_positions.keys():
#                     if idx not in animation_state["last_positions"]:
#                         animation_state["last_positions"][idx] = new_positions[idx]
#                     if idx not in animation_state["last_scales"]:
#                         animation_state["last_scales"][idx] = new_scales[idx]

#             animation_state["animation_start_time"] = global_t
#             animation_state["last_visible_set"] = planned_set

#     def current_interp(global_t: float):
#         ensure_layout_for_time(global_t)
#         in_anim = (
#             animation_state["animation_start_time"] is not None and
#             global_t < animation_state["animation_start_time"] + ANIMATION_DURATION
#         )
#         if not in_anim:
#             animation_state["last_positions"] = animation_state["target_positions"].copy()
#             animation_state["last_scales"] = animation_state["target_scales"].copy()
#             return 1.0

#         raw = (global_t - animation_state["animation_start_time"]) / ANIMATION_DURATION
#         return apply_easing(max(0.0, min(1.0, raw)), ANIMATION_EASING)

#     def make_position_fn(self_idx: int, own_appear_time: float):
#         def pos(local_t: float):
#             local_t = max(0.0, local_t)
#             global_t = own_appear_time + local_t

#             eased = current_interp(global_t)

#             last_pos = animation_state["last_positions"].get(self_idx)
#             target_pos = animation_state["target_positions"].get(self_idx)
#             if last_pos is None or target_pos is None:
#                 return (-99999, -99999)

#             x0, y0 = last_pos
#             x1, y1 = target_pos
#             cx = int(x0 + (x1 - x0) * eased)
#             cy = int(y0 + (y1 - y0) * eased)

#             # Entrance slide-in
#             if local_t < ENTRANCE_DURATION:
#                 p = apply_easing(local_t / ENTRANCE_DURATION, "ease_out")
#                 offset = int(ENTRANCE_TRANSLATE_OFFSET * (1 - p))
#                 cx += offset

#             return (cx, cy)
#         return pos

#     def make_scale_fn(self_idx: int, own_appear_time: float):
#         def scale(local_t: float):
#             local_t = max(0.0, local_t)
#             global_t = own_appear_time + local_t

#             eased = current_interp(global_t)

#             s0 = animation_state["last_scales"].get(self_idx)
#             s1 = animation_state["target_scales"].get(self_idx)
#             if s0 is None or s1 is None:
#                 s = s1 if s1 is not None else 1.0
#             else:
#                 s = s0 + (s1 - s0) * eased

#             # Tiny entrance emphasis
#             if local_t < ENTRANCE_DURATION:
#                 p = apply_easing(local_t / ENTRANCE_DURATION, "ease_out")
#                 s = s * (0.985 + 0.015 * p)

#             return s
#         return scale

#     # Create background
#     background_clip = ImageClip(BACKGROUND_IMAGE)
#     # Scale background to fit video dimensions while maintaining aspect ratio
#     bg_scale_x = VIDEO_WIDTH / background_clip.w
#     bg_scale_y = VIDEO_HEIGHT / background_clip.h
#     bg_scale = max(bg_scale_x, bg_scale_y)  # scale to fill entire frame
#     background_clip = background_clip.resized(bg_scale).with_duration(final_duration)
    
#     # Crop to exact video dimensions if needed
#     if background_clip.w > VIDEO_WIDTH or background_clip.h > VIDEO_HEIGHT:
#         background_clip = background_clip.cropped(
#             x_center=background_clip.w/2, y_center=background_clip.h/2,
#             width=VIDEO_WIDTH, height=VIDEO_HEIGHT
#         )
    
#     # Compose with dynamic position + scale + fade-in
#     composed = [background_clip]
#     for idx, (clip, appear_at, *_rest) in enumerate(base_clips):
#         clip_duration = max(0.01, final_duration - appear_at)
#         fade_dur = min(ENTRANCE_DURATION, clip_duration)

#         animated_clip = (
#             clip
#             .with_start(appear_at)
#             .with_duration(clip_duration)
#             .with_position(make_position_fn(idx, appear_at))
#             .with_effects([
#                 vfx.Resize(make_scale_fn(idx, appear_at)),
#                 vfx.CrossFadeIn(fade_dur),
#             ])
#         )
#         composed.append(animated_clip)

#     CompositeVideoClip(
#         composed,
#         size=(VIDEO_WIDTH, VIDEO_HEIGHT),
#     ).with_duration(final_duration).write_videofile(
#         cache_path,
#         fps=FPS,
#         codec="libx264",
#         audio=False,
#         preset="medium",
#     )

#     return cache_path

from typing import List, Dict, Any, Tuple
from moviepy import ImageClip, CompositeVideoClip, TextClip, VideoClip, vfx
import os
import hashlib
import json
import random

# ===== Constants =====
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30
BACKGROUND_COLOR = (10, 10, 10)  # RGB

# Layout controls (rows are centered horizontally and vertically)
MAX_ITEMS_PER_ROW = 2            # cap items per row; overflow wraps to next row(s)
H_GAP_MIN = 64                   # minimum horizontal gap inside a row
V_GAP_MIN = 16                   # minimum vertical gap between rows

# Cache settings
CACHE_DIR = "cache/buildshot"
os.makedirs(CACHE_DIR, exist_ok=True)

PADDING_LEFT = 120
PADDING_RIGHT = 120
PADDING_TOP = 120
PADDING_BOTTOM = 120

TEXT_COLOR = (0, 0, 0)
TEXT_FONT_SIZE = 80
FONT_FILE = "font.ttf"
BACKGROUND_IMAGE = "background.png"

POST_HOLD_SECONDS = 3

# Animation settings
ENTRANCE_DURATION = 0.15         # seconds for fade-in and translate-in
ENTRANCE_TRANSLATE_OFFSET = 28   # pixels to slide in from (downwards)
EXIT_DURATION = 0.15             # seconds to fully slide off-screen

# Grouping: items with appearAt within this window belong to the same group
GROUP_WINDOW = 0.60              # seconds

# Max allowed absolute image upscaling relative to its original/native resolution
MAX_IMAGE_UPSCALE_ABS = 1.5
MIN_SCALE = 0.35                 # never scale below this (for readability)

def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def _cache_path(media_plan: List[Dict[str, Any]], duration: float, font_path: str = "font.ttf", background_path: str = "background.png") -> str:
    font_path = os.path.abspath(font_path)
    background_path = os.path.abspath(background_path)
    media_plan_str = json.dumps(media_plan, sort_keys=True, separators=(',', ':'))
    # include mtimes to invalidate cache if assets change
    font_mtime = os.path.getmtime(font_path) if os.path.exists(font_path) else "NA"
    bg_mtime   = os.path.getmtime(background_path) if os.path.exists(background_path) else "NA"
    key_src = f"{duration}|{media_plan_str}|{GROUP_WINDOW}|{EXIT_DURATION}|{MAX_ITEMS_PER_ROW}|{font_path}|{background_path}|{font_mtime}|{bg_mtime}".encode("utf-8")
    return os.path.join(CACHE_DIR, hashlib.md5(key_src).hexdigest() + ".mp4")

def _hex(rgb: Tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def buildShot(media_plan: List[Dict[str, Any]], duration: float, font_path: str = "font.ttf", background_path: str = "background.png") -> str:
    """
    Groups media objects by time windows so items appearing around the same time render together as one group.
    Only one group is on-screen at a time. Groups are laid out as centered rows.
    When the next group starts, the previous group slides fully off-screen in a random (left/top/right) direction.
    """
    if not isinstance(media_plan, list):
        raise ValueError("media_plan must be a list")

    cache_path = _cache_path(media_plan, duration, font_path, background_path)
    if os.path.exists(cache_path):
        return cache_path

    # ---- Build base clips (collect sizes, types, appear times) ----
    items: List[Dict[str, Any]] = []
    for it in media_plan:
        if not (("path" in it and it.get("path")) or ("text" in it and it.get("text") is not None)):
            continue
        appear_at = float(it.get("appearAt", 0) or 0)
        is_image = "path" in it and it.get("path")
        if is_image:
            try:
                clip = ImageClip(it["path"])
            except Exception as e:
                print(f"Error loading image {it['path']}: {e}")
                # Try to delete the corrupted file and skip this item
                try:
                    import os
                    if os.path.exists(it["path"]):
                        os.remove(it["path"])
                        print(f"Deleted corrupted image: {it['path']}")
                except:
                    pass
                continue  # Skip this corrupted image
        else:
            clip = TextClip(
                text=str(it.get("text", "")),
                font_size=TEXT_FONT_SIZE,
                color=_hex(TEXT_COLOR),
                font=font_path,
                size=(VIDEO_WIDTH, VIDEO_HEIGHT),
            )
        items.append({
            "clip": clip,
            "appearAt": appear_at,
            "is_image": is_image,
            "orig_w": clip.w,
            "orig_h": clip.h,
            "idx": len(items),
        })

    if not items:
        from moviepy import ColorClip
        ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=BACKGROUND_COLOR, duration=max(0.1, duration)).write_videofile(
            cache_path, fps=FPS, codec="libx264", audio=False, preset="medium"
        )
        return cache_path

    items.sort(key=lambda x: x["appearAt"])
    last_appear = max(x["appearAt"] for x in items)
    final_duration = float(max(duration, last_appear + POST_HOLD_SECONDS))

    # ---- Group by appearAt window ----
    groups = []
    grp = {"indices": [], "start": None}
    for x in items:
        t = x["appearAt"]
        if not grp["indices"]:
            grp["indices"].append(x["idx"])
            grp["start"] = t
            anchor = t
        else:
            if t - anchor <= GROUP_WINDOW:
                grp["indices"].append(x["idx"])
            else:
                groups.append(grp)
                grp = {"indices": [x["idx"]], "start": t}
                anchor = t
    if grp["indices"]:
        groups.append(grp)

    # compute group end times (end = next group's start; last group holds to final_duration)
    for gi, g in enumerate(groups):
        g["end"] = groups[gi + 1]["start"] if gi + 1 < len(groups) else final_duration

    # deterministic random per media_plan
    seed = int(hashlib.md5(("dirs|" + json.dumps([x["appearAt"] for x in items])).encode()).hexdigest(), 16) & 0xFFFFFFFF
    rng = random.Random(seed)
    for g in groups:
        g["exit_dir"] = rng.choice(["left", "top", "right"])

    # ---- Layout helpers (centered rows) ----
    avail_w = max(1, VIDEO_WIDTH - PADDING_LEFT - PADDING_RIGHT)
    avail_h = max(1, VIDEO_HEIGHT - PADDING_TOP - PADDING_BOTTOM)

    def allowed_scale_limit(idx: int) -> float:
        x = items[idx]
        if not x["is_image"]:
            return float("inf")
        # don't upscale bitmap images too much
        return max(MIN_SCALE, MAX_IMAGE_UPSCALE_ABS)

    def layout_group(g_indices: List[int]) -> Tuple[Dict[int, Tuple[float, float]], Dict[int, float], Dict[int, Tuple[float, float]]]:
        """
        Returns:
          positions[idx] -> (x, y) top-left (for BASE position, no entrance/exit offsets)
          scales[idx]    -> s
          scaled_size[idx] -> (w_s, h_s)
        """
        if not g_indices:
            return {}, {}, {}

        # split into rows
        rows: List[List[int]] = []
        if MAX_ITEMS_PER_ROW <= 0:
            rows.append(g_indices[:])
        else:
            for i in range(0, len(g_indices), MAX_ITEMS_PER_ROW):
                rows.append(g_indices[i:i + MAX_ITEMS_PER_ROW])

        # compute per-item scale: equal width per row; then fit vertically if needed
        scales: Dict[int, float] = {}
        scaled_size: Dict[int, Tuple[float, float]] = {}
        row_heights = []

        # first pass: width-driven scales per row
        for row in rows:
            n = len(row)
            content_w_budget = max(1.0, avail_w - H_GAP_MIN * (n + 1))
            equal_target_w = content_w_budget / n
            # respect per-item upscale caps
            for idx in row:
                base_w = float(items[idx]["orig_w"])
                s = equal_target_w / max(1.0, base_w)
                s = min(s, allowed_scale_limit(idx))
                s = max(MIN_SCALE, s)
                scales[idx] = s
                scaled_size[idx] = (items[idx]["orig_w"] * s, items[idx]["orig_h"] * s)

            row_heights.append(max(scaled_size[idx][1] for idx in row))

        # ensure each row fits horizontally with at least the minimum gaps
        for r, row in enumerate(rows):
            n = len(row)
            max_row_content_w = max(1.0, avail_w - H_GAP_MIN * (n + 1))
            row_content_w = sum(scaled_size[idx][0] for idx in row)
            if row_content_w > max_row_content_w:
                row_shrink = max_row_content_w / max(1.0, row_content_w)
                for idx in row:
                    s = scales[idx] * row_shrink
                    scales[idx] = s
                    scaled_size[idx] = (items[idx]["orig_w"] * s, items[idx]["orig_h"] * s)
        # recompute row heights after horizontal fitting
        row_heights = [max(scaled_size[idx][1] for idx in row) for row in rows]

        # check vertical fit (rows + gaps centered vertically). If too tall, shrink uniformly.
        total_h = sum(row_heights) + V_GAP_MIN * max(0, len(rows) - 1)
        if total_h > avail_h:
            shrink = avail_h / total_h
            for idx in g_indices:
                s = scales[idx] * shrink
                scales[idx] = s
                scaled_size[idx] = (items[idx]["orig_w"] * s, items[idx]["orig_h"] * s)
            # recompute row heights
            row_heights = [max(scaled_size[idx][1] for idx in row) for row in rows]
            total_h = sum(row_heights) + V_GAP_MIN * max(0, len(rows) - 1)

        # horizontal positions per row, then center the whole block vertically
        positions: Dict[int, Tuple[float, float]] = {}
        y_top = PADDING_TOP + (avail_h - total_h) / 2.0
        y_cursor = y_top
        for r, row in enumerate(rows):
            n = len(row)
            row_w_sum = sum(scaled_size[idx][0] for idx in row)
            free_w = max(0.0, avail_w - row_w_sum)
            gap_x = free_w / (n + 1)
            x_cursor = PADDING_LEFT + gap_x
            for idx in row:
                positions[idx] = (x_cursor, y_cursor + (row_heights[r] - scaled_size[idx][1]) / 2.0)
                x_cursor += scaled_size[idx][0] + gap_x
            y_cursor += row_heights[r] + (V_GAP_MIN if r < len(rows) - 1 else 0.0)

        return positions, scales, scaled_size

    # Precompute group layouts
    group_layouts = {}
    for g in groups:
        positions, scales, scaled_size = layout_group(g["indices"])
        group_layouts[id(g)] = (positions, scales, scaled_size)

    # ---- Background ----
    try:
        background_clip = ImageClip(background_path)
        bg_scale = max(VIDEO_WIDTH / background_clip.w, VIDEO_HEIGHT / background_clip.h)
        background_clip = background_clip.resized(bg_scale).with_duration(final_duration)
        if background_clip.w > VIDEO_WIDTH or background_clip.h > VIDEO_HEIGHT:
            background_clip = background_clip.cropped(
                x_center=background_clip.w / 2, y_center=background_clip.h / 2,
                width=VIDEO_WIDTH, height=VIDEO_HEIGHT
            )
    except Exception:
        # fallback to solid color to avoid crashes if image missing
        from moviepy import ColorClip
        background_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=BACKGROUND_COLOR, duration=final_duration)

    composed: List[VideoClip] = [background_clip]

    # --- helpers: exact-but-safe offscreen targets + hard integer clamps ---
    def _offscreen_targets(exit_dir: str, bx: int, by: int, w_int: int, h_int: int):
        """
        Use -w+1 / W-1 / -h+1 to avoid 0-width/height slices during mask compose.
        """
        if exit_dir == "left":
            return (-w_int + 1, by)
        elif exit_dir == "right":
            return (VIDEO_WIDTH - 1, by)
        else:  # "top"
            return (bx, -h_int + 1)

    def _clamp_xy(x: int, y: int, w_int: int, h_int: int) -> Tuple[int, int]:
        # Keep top-left within safe compositor bounds (never fully beyond).
        x = max(-w_int + 1, min(VIDEO_WIDTH - 1, x))
        y = max(-h_int + 1, min(VIDEO_HEIGHT - 1, y))
        return x, y

    # ---- Build animated clips per item (entrance + group exit slide) ----
    for g in groups:
        g_id = id(g)
        g_start = g["start"]
        g_end = g["end"]
        exit_dir = g["exit_dir"]
        positions, scales, scaled_size = group_layouts[g_id]

        for idx in g["indices"]:
            base = items[idx]
            clip = base["clip"]
            appear_at = base["appearAt"]

            # duration bounded by the group end (no overlap with next group)
            clip_duration = max(0.01, g_end - appear_at)
            fade_dur = min(ENTRANCE_DURATION, clip_duration)

            # force integer geometry
            base_x = int(round(positions[idx][0]))
            base_y = int(round(positions[idx][1]))
            s = scales[idx]
            w_s, h_s = scaled_size[idx]
            w_int = int(round(w_s))
            h_int = int(round(h_s))
            bx = int(round(base_x))
            by = int(round(base_y))
            ox, oy = _offscreen_targets(exit_dir, bx, by, w_int, h_int)

            def pos_fn_factory(_appear_at, _g_end, bx, by, ox, oy, w_int, h_int):
                def _pos(local_t: float):
                    local_t = 0.0 if local_t is None else max(0.0, local_t)
                    global_t = _appear_at + local_t

                    # entrance: slide up from below
                    if local_t < ENTRANCE_DURATION:
                        p = ease_out_cubic(local_t / ENTRANCE_DURATION)
                        x = bx
                        y = by + int(round(ENTRANCE_TRANSLATE_OFFSET * (1 - p)))
                        return _clamp_xy(int(x), int(y), w_int, h_int)

                    # exit: last EXIT_DURATION of the group
                    if global_t >= (_g_end - EXIT_DURATION):
                        u = (global_t - (_g_end - EXIT_DURATION)) / EXIT_DURATION
                        u = 0.0 if u < 0 else 1.0 if u > 1 else ease_out_cubic(u)
                        x = bx + int(round((ox - bx) * u))
                        y = by + int(round((oy - by) * u))
                        return _clamp_xy(int(x), int(y), w_int, h_int)

                    # hold
                    return _clamp_xy(bx, by, w_int, h_int)
                return _pos

            animated = (
                clip
                .with_start(appear_at)
                .with_duration(clip_duration)
                .with_position(pos_fn_factory(appear_at, g_end, bx, by, ox, oy, w_int, h_int))
                .with_effects([
                    vfx.Resize(s),
                    vfx.CrossFadeIn(fade_dur),
                ])
            )
            composed.append(animated)

    # ---- Compose & render ----
    CompositeVideoClip(composed, size=(VIDEO_WIDTH, VIDEO_HEIGHT)) \
        .with_duration(final_duration) \
        .write_videofile(
            cache_path,
            fps=FPS,
            codec="libx264",
            audio=False,
            preset="medium",
        )

    return cache_path
