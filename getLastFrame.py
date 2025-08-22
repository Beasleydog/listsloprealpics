#!/usr/bin/env python3
"""
Save the last frame of an MP4 as a PNG and print the output path.

Usage:
  python save_last_frame.py /path/to/video.mp4
"""
from __future__ import annotations
import sys
from pathlib import Path
import cv2  # type: ignore

def getLastFrame(video_path: str | Path, out_path: str | Path | None = None) -> str:
    p = Path(video_path)
    if not p.exists():
        raise FileNotFoundError(p)

    if out_path is None:
        out_path = p.with_suffix("")  # drop .mp4
        out_path = Path(f"{out_path}_lastframe.png")
    out = Path(out_path)

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        raise RuntimeError("cv2.VideoCapture failed to open file")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count and frame_count > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count - 1))
        ok, frame = cap.read()
        if not ok or frame is None:
            ok, frame = _read_to_last(cap)
    else:
        ok, frame = _read_to_last(cap)
    cap.release()

    if not ok or frame is None:
        raise RuntimeError("Could not read last frame via OpenCV")

    if not cv2.imwrite(str(out), frame):
        raise RuntimeError(f"cv2.imwrite failed for {out}")

    return str(out)

def _read_to_last(cap):
    last = None
    ok = False
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        ok, last = ret, frame
    return ok, last
