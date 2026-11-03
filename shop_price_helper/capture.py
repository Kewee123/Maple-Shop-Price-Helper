"""macOS screen capture and mouse helpers.

The capture is a small rectangle around the cursor, so the app can read the
tooltip that appears when the player hovers a shop row. Coordinates are in
points, which is what both CoreGraphics and mss use on macOS.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

import mss
import numpy as np
from PIL import Image

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 560


def _cg() -> ctypes.CDLL:
    return ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")


def screen_recording_granted() -> bool:
    """Whether this process may capture other applications' windows."""
    if sys.platform != "darwin":
        return True
    try:
        fn = _cg().CGPreflightScreenCaptureAccess
        fn.restype = ctypes.c_bool
        fn.argtypes = []
        return bool(fn())
    except Exception:
        return True  # old macOS / no API: let the first grab tell us


def request_screen_recording() -> bool:
    if sys.platform != "darwin":
        return True
    try:
        fn = _cg().CGRequestScreenCaptureAccess
        fn.restype = ctypes.c_bool
        fn.argtypes = []
        return bool(fn())
    except Exception:
        return False


def open_screen_recording_settings() -> None:
    if sys.platform == "darwin":
        subprocess.Popen(
            ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def mouse_position() -> tuple[int, int] | None:
    """The cursor in top-left screen points, or None if Quartz isn't usable."""
    if sys.platform != "darwin":
        return None
    try:
        import Quartz
        point = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return int(point.x), int(point.y)
    except Exception:
        return None


def _monitors() -> list[dict]:
    try:
        with mss.MSS() as sct:
            return list(sct.monitors[1:]) or list(sct.monitors[:1])
    except Exception:
        return []


def region_around(x: int, y: int, width: int = DEFAULT_WIDTH,
                  height: int = DEFAULT_HEIGHT) -> dict[str, int]:
    """A capture rectangle around the cursor, clipped to the screen it is on."""
    monitors = _monitors()
    monitor = next((m for m in monitors if m["left"] <= x < m["left"] + m["width"]
                    and m["top"] <= y < m["top"] + m["height"]), None)
    if monitor is None:
        monitor = monitors[0] if monitors else {"left": 0, "top": 0, "width": width, "height": height}
    w = min(width, monitor["width"])
    h = min(height, monitor["height"])
    left = min(max(x - w // 2, monitor["left"]), monitor["left"] + monitor["width"] - w)
    top = min(max(y - h // 2, monitor["top"]), monitor["top"] + monitor["height"] - h)
    return {"left": int(left), "top": int(top), "width": int(w), "height": int(h)}


def grab(region: dict[str, int]) -> Image.Image:
    """Grab one rectangle as an RGB PIL image."""
    with mss.MSS() as sct:
        shot = sct.grab(region)
        pixels = np.asarray(shot)                       # BGRA
        return Image.fromarray(pixels[:, :, :3][:, :, ::-1])   # RGB


def frame_difference(a: Image.Image | None, b: Image.Image) -> float:
    """A cheap 0..255 difference between frames, enough to notice a tooltip."""
    if a is None:
        return 255.0
    small_a = np.asarray(a.convert("L").resize((160, 120)), dtype=np.int16)
    small_b = np.asarray(b.convert("L").resize((160, 120)), dtype=np.int16)
    return float(np.abs(small_a - small_b).mean())


def save_debug(image: Image.Image, folder: Path, name: str = "last-capture.png") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    image.save(path)
    return path
