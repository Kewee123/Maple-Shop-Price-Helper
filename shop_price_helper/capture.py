"""macOS screen capture and mouse helpers.

The capture is a small rectangle around the cursor, so the app can read the
tooltip that appears when the player hovers a shop row. Coordinates are in
points, which is what both CoreGraphics and mss use on macOS.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import mss
import numpy as np
from PIL import Image, ImageDraw

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


def grab(region: dict[str, int], exclude: tuple[int, int, int, int] | None = None) -> Image.Image:
    """Grab one rectangle as an RGB PIL image.

    `exclude` is a screen rectangle (left, top, right, bottom) to black out, normally
    this helper's own window so its text can never be mistaken for a game tooltip.
    """
    with mss.MSS() as sct:
        shot = sct.grab(region)
        pixels = np.asarray(shot)                       # BGRA
        image = Image.fromarray(pixels[:, :, :3][:, :, ::-1])   # RGB
    if exclude:
        left, top, right, bottom = exclude
        x0 = max(0, left - region["left"])
        y0 = max(0, top - region["top"])
        x1 = min(image.width, right - region["left"])
        y1 = min(image.height, bottom - region["top"])
        if x1 > x0 and y1 > y0:
            ImageDraw.Draw(image).rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, 0, 0))
    return image


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


@dataclass(frozen=True)
class WindowInfo:
    number: int
    pid: int
    owner: str
    title: str
    left: int
    top: int
    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.left + self.width and self.top <= y < self.top + self.height


def on_screen_windows() -> list[WindowInfo]:
    """Normal windows on screen, front to back. The app's own windows are left out."""
    if sys.platform != "darwin":
        return []
    try:
        import os
        import Quartz
        options = Quartz.kCGWindowListOptionOnScreenOnly | getattr(
            Quartz, "kCGWindowListExcludeDesktopElements", 0)
        raw = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        found = []
        for window in raw or []:
            if window.get("kCGWindowLayer") != 0:
                continue
            if window.get("kCGWindowOwnerPID") == os.getpid():
                continue
            bounds = window.get("kCGWindowBounds") or {}
            if not all(k in bounds for k in ("X", "Y", "Width", "Height")):
                continue
            found.append(WindowInfo(
                number=int(window.get("kCGWindowNumber") or 0),
                pid=int(window.get("kCGWindowOwnerPID") or 0),
                owner=str(window.get("kCGWindowOwnerName") or ""),
                title=str(window.get("kCGWindowName") or ""),
                left=int(bounds["X"]), top=int(bounds["Y"]),
                width=int(bounds["Width"]), height=int(bounds["Height"]),
            ))
        return found
    except Exception:
        return []


def window_under_cursor(x: int, y: int) -> WindowInfo | None:
    """The frontmost normal window at the cursor."""
    return next((window for window in on_screen_windows() if window.contains(x, y)), None)


def is_game_window(window: WindowInfo | None) -> bool:
    """MapleStory itself, or the wrapper a Mac player commonly runs it in."""
    if window is None:
        return False
    text = f"{window.owner} {window.title}".lower()
    if "maplestory" in text:
        return True
    return window.owner.lower() in {
        "crossover", "whisky", "wine", "wine64", "wine-preloader",
        "parallels desktop", "parallels",
    }
