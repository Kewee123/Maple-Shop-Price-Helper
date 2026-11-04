"""Read the stack count from the bottom-left of the hovered inventory slot.

MapleStory draws slot counts in a tiny pixel font.  macOS Vision OCR does not
read those glyphs reliably, so this module matches the 12x18 fill shapes
directly.  The capture is only searched around the cursor, and a group of
digits is accepted only when it is not separated from the cursor by a slot
border (or another bright divider).

The templates are for the 2x Retina rendering used by the Mac client.  A 1x
capture is still attempted; if the count cannot be read, the caller keeps its
existing quantity instead of guessing.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from PIL import Image

# The count font is 12x18 at 2x (the "1" glyph is 6x18 and sits inside the same
# 12-wide cell).  These masks are the light fill only; the black outline is not
# part of the glyph.
_TEMPLATE_ROWS: dict[str, tuple[str, ...]] = {
    "0": (
        "..########..",
        "..########..",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "..########..",
        "..########..",
    ),
    "1": (
        "......##....",
        "......##....",
        "....######..",
        "....######..",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
    ),
    "2": (
        "..########..",
        "..########..",
        "##........##",
        "##........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "........##..",
        "........##..",
        "....####....",
        "....####....",
        "..##........",
        "..##........",
        "##..........",
        "##..........",
        "############",
        "############",
    ),
    "3": (
        "..########..",
        "..########..",
        "##........##",
        "##........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "....######..",
        "....######..",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "##........##",
        "##........##",
        "..########..",
        "..########..",
    ),
    "4": (
        "........##..",
        "........##..",
        "......####..",
        "......####..",
        "....##..##..",
        "....##..##..",
        "..##....##..",
        "..##....##..",
        "##......##..",
        "##......##..",
        "############",
        "############",
        "........##..",
        "........##..",
        "........##..",
        "........##..",
        "........##..",
        "........##..",
    ),
    "5": (
        "############",
        "############",
        "##..........",
        "##..........",
        "##..........",
        "##..........",
        "##########..",
        "##########..",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "##........##",
        "##........##",
        "..########..",
        "..########..",
    ),
    # Taken from a real in-game "16" count.  The left side is a staircase, not
    # the closed loop an "8" has.
    "6": (
        "....######..",
        "....######..",
        "..##........",
        "..##........",
        "##..........",
        "##..........",
        "##########..",
        "##########..",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "..########..",
        "..########..",
    ),
    "7": (
        "############",
        "############",
        "..........##",
        "..........##",
        "........##..",
        "........##..",
        "........##..",
        "........##..",
        "......##....",
        "......##....",
        "......##....",
        "......##....",
        "....##......",
        "....##......",
        "....##......",
        "....##......",
        "..##........",
        "..##........",
    ),
    "8": (
        "..########..",
        "..########..",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "..########..",
        "..########..",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "..########..",
        "..########..",
    ),
    "9": (
        "..########..",
        "..########..",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "..##########",
        "..##########",
        "..........##",
        "..........##",
        "..........##",
        "..........##",
        "..########..",
        "..########..",
    ),
}

TEMPLATES: dict[str, np.ndarray] = {
    digit: np.array([[cell == "#" for cell in row] for row in rows], dtype=bool)
    for digit, rows in _TEMPLATE_ROWS.items()
}

DIGIT_WIDTH = 12
DIGIT_HEIGHT = 18
_MAX_DISTANCE = 0.13


@dataclass(frozen=True)
class _Component:
    x0: int
    y0: int
    x1: int
    y1: int
    area: int
    mask: np.ndarray

    @property
    def width(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def height(self) -> int:
        return self.y1 - self.y0 + 1


@dataclass(frozen=True)
class _Digit:
    component: _Component
    digit: str
    distance: float

    @property
    def x0(self) -> int:
        return self.component.x0

    @property
    def y0(self) -> int:
        return self.component.y0

    @property
    def x1(self) -> int:
        return self.component.x1

    @property
    def y1(self) -> int:
        return self.component.y1


def _components(mask: np.ndarray) -> list[_Component]:
    """8-connected components of a small boolean mask."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    found: list[_Component] = []
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or seen[y, x]:
                continue
            queue = deque([(y, x)])
            seen[y, x] = True
            points: list[tuple[int, int]] = []
            while queue:
                cy, cx = queue.popleft()
                points.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < height and 0 <= nx < width:
                            if mask[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True
                                queue.append((ny, nx))
            ys = [point[0] for point in points]
            xs = [point[1] for point in points]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            local = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=bool)
            for py, px in points:
                local[py - y0, px - x0] = True
            found.append(_Component(x0, y0, x1, y1, len(points), local))
    return found


def _normalize(mask: np.ndarray) -> np.ndarray:
    """Scale a component into the 12x18 template box without stretching an axis."""
    height, width = mask.shape
    if height == 0 or width == 0:
        return np.zeros((DIGIT_HEIGHT, DIGIT_WIDTH), dtype=bool)
    scale = min(DIGIT_WIDTH / width, DIGIT_HEIGHT / height)
    new_w = max(1, round(width * scale))
    new_h = max(1, round(height * scale))
    image = Image.fromarray((mask * 255).astype(np.uint8))
    image = image.resize((new_w, new_h), Image.BILINEAR)
    scaled = np.asarray(image) > 110
    out = np.zeros((DIGIT_HEIGHT, DIGIT_WIDTH), dtype=bool)
    x0 = (DIGIT_WIDTH - new_w) // 2
    y0 = (DIGIT_HEIGHT - new_h) // 2
    out[y0:y0 + new_h, x0:x0 + new_w] = scaled
    return out


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    """Smallest fraction of differing pixels over a one-pixel neighbour shift."""
    best = 1.0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = np.roll(np.roll(b, dy, axis=0), dx, axis=1)
            best = min(best, float(np.mean(a != shifted)))
    return best


def _classify(mask: np.ndarray) -> tuple[str | None, float]:
    normalized = _normalize(mask)
    matches = sorted((_distance(normalized, template), digit)
                     for digit, template in TEMPLATES.items())
    distance, digit = matches[0]
    return digit, distance


def _classify_component(component: _Component) -> tuple[str | None, float]:
    """Classify one fill component, trimming icon highlights when needed.

    A white highlight from the item icon can stick to a digit and make the
    component a little wider than the font cell.  In that case the extra
    columns are at one side; try the three 12-column windows before giving up.
    """
    digit, distance = _classify(component.mask)
    if distance <= _MAX_DISTANCE:
        return digit, distance

    max_width = max(2, round(DIGIT_WIDTH * component.height / DIGIT_HEIGHT))
    if component.width <= max_width:
        return digit, distance

    best_digit: str | None = None
    best_distance = distance
    for start in (0, component.width - max_width, (component.width - max_width) // 2):
        candidate, candidate_distance = _classify(
            component.mask[:, start:start + max_width])
        if candidate is not None and candidate_distance < best_distance:
            best_digit, best_distance = candidate, candidate_distance
    if best_digit is not None and best_distance <= _MAX_DISTANCE:
        return best_digit, best_distance
    return digit, distance


def _fill_mask(rgb: np.ndarray) -> np.ndarray:
    """The light fill of the count glyphs, separated from the dark outline."""
    red = rgb[:, :, 0].astype(np.int16)
    green = rgb[:, :, 1].astype(np.int16)
    blue = rgb[:, :, 2].astype(np.int16)
    white = (red >= 232) & (green >= 232) & (blue >= 232)
    blue_glow = (blue - red >= 8) & (blue >= 220)
    return white | blue_glow


def _bright(rgb: np.ndarray) -> np.ndarray:
    """Near-white pixels, used to spot the slot borders around a count."""
    red = rgb[:, :, 0].astype(np.int16)
    green = rgb[:, :, 1].astype(np.int16)
    blue = rgb[:, :, 2].astype(np.int16)
    spread = np.maximum(np.maximum(red, green), blue) - np.minimum(np.minimum(red, green), blue)
    return (np.minimum(np.minimum(red, green), blue) >= 238) & (spread <= 12)


def _has_vertical_line(rgb: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> bool:
    x0, x1 = max(0, x0), min(rgb.shape[1], x1)
    y0, y1 = max(0, y0), min(rgb.shape[0], y1)
    if x1 - x0 < 1 or y1 - y0 < 4:
        return False
    coverage = _bright(rgb[y0:y1, x0:x1]).mean(axis=0)
    return bool((coverage >= 0.7).any())


def _has_horizontal_line(rgb: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> bool:
    x0, x1 = max(0, x0), min(rgb.shape[1], x1)
    y0, y1 = max(0, y0), min(rgb.shape[0], y1)
    if x1 - x0 < 4 or y1 - y0 < 1:
        return False
    coverage = _bright(rgb[y0:y1, x0:x1]).mean(axis=1)
    return bool((coverage >= 0.7).any())


def _digit_groups(digits: list[_Digit], scale: float) -> list[list[_Digit]]:
    digits = sorted(digits, key=lambda digit: (digit.x0, digit.y0))
    groups: list[list[_Digit]] = []
    for index, digit in enumerate(digits):
        group = [digit]
        for other in digits[index + 1:]:
            previous = group[-1]
            overlap = min(previous.y1, other.y1) - max(previous.y0, other.y0)
            shortest = min(previous.y1 - previous.y0, other.y1 - other.y0)
            gap = other.x0 - previous.x1
            if overlap >= 0.7 * shortest and -1 <= gap <= 5.5 * scale:
                group.append(other)
        groups.append(group)
    return groups


def read_count(image: Image.Image | np.ndarray, cursor: tuple[float, float],
               scale: float = 2.0) -> int | None:
    """The stack count near `cursor`, or None when no reliable count is visible.

    `cursor` is in image pixels.  `scale` is the capture's backing scale (2.0 on
    a Retina display).  The search box covers the bottom-left of the slot the
    cursor is over: the count sits roughly 0-40 points left and 0-37 points
    below the cursor.
    """
    if isinstance(image, Image.Image):
        rgb = np.asarray(image.convert("RGB"))
    else:
        rgb = np.asarray(image)
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            return None
        rgb = rgb[:, :, :3]

    height, width = rgb.shape[:2]
    cx, cy = cursor
    left = max(0, int(cx - 40 * scale))
    right = min(width, int(cx + 39 * scale))
    top = max(0, int(cy - 14 * scale))
    bottom = min(height, int(cy + 37 * scale))
    if right <= left or bottom <= top:
        return None
    crop = rgb[top:bottom, left:right]
    mask = _fill_mask(crop)

    expected_height = 9.0 * scale
    digits: list[_Digit] = []
    for component in _components(mask):
        digit_width = component.width
        digit_height = component.height
        if not (0.55 * expected_height <= digit_height <= 1.6 * expected_height):
            continue
        if not (1 <= digit_width <= 0.95 * digit_height):
            continue
        if component.area < max(6, 0.12 * digit_width * digit_height):
            continue
        digit, distance = _classify_component(component)
        if digit is not None and distance <= _MAX_DISTANCE:
            digits.append(_Digit(component, digit, distance))
    if not digits:
        return None

    groups = _digit_groups(digits, scale)

    def sort_key(group: list[_Digit]) -> tuple[float, int, int]:
        center = (min(digit.y0 for digit in group) + max(digit.y1 for digit in group)) / 2
        return (abs(center - (cy - top)),
                min(digit.x0 for digit in group),
                -len(group))

    groups.sort(key=sort_key)
    for group in groups:
        group_left = min(digit.x0 for digit in group)
        group_right = max(digit.x1 for digit in group)
        group_top = min(digit.y0 for digit in group)
        group_bottom = max(digit.y1 for digit in group)
        members = {id(digit) for digit in group}

        # Don't return the tail of a longer count.  The grouping loop also
        # creates a group starting at every digit, so without this check "159"
        # could become "59" when the first glyph is rejected.
        tail = False
        for digit in digits:
            if id(digit) in members or digit.x1 >= group_left:
                continue
            overlap = min(digit.y1, group_bottom) - max(digit.y0, group_top)
            shortest = min(digit.y1 - digit.y0, group_bottom - group_top)
            if overlap >= 0.7 * shortest and group_left - digit.x1 <= 5.5 * scale:
                tail = True
                break
        if tail:
            continue

        # Reject a group on the other side of a slot border.
        if group_left > cx - left:
            if _has_vertical_line(crop, int(cx - left) + 1, group_left,
                                  group_top - 4, group_bottom + 4):
                continue
        elif group_right < cx - left:
            if _has_vertical_line(crop, group_right + 1, int(cx - left),
                                  group_top - 4, group_bottom + 4):
                continue
        if group_top > cy - top:
            if _has_horizontal_line(crop, group_left - 4, group_right + 4,
                                    int(cy - top) + 1, group_top):
                continue
        elif group_bottom < cy - top:
            if _has_horizontal_line(crop, group_left - 4, group_right + 4,
                                    group_bottom + 1, int(cy - top)):
                continue

        value = "".join(digit.digit for digit in group)
        if len(value) > 4 or value[0] == "0":
            continue
        return int(value)
    return None
