"""Turn OCR lines into an item: name, stats and quantity.

The shop tooltip is a small block of lines: the item name first, then its
stats/quantity. A screen capture around the cursor can also contain chat and
HUD text, so the lines are grouped into blocks and the most item-like block is
used. Everything is kept on the item as raw lines as well, so the window can
show what was read.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from .model import ShopItem, TextLine

_NOISE = re.compile(
    r"^(?:you\s+(?:received|have\s+gained|can(?:'|’)?t|cannot)|"
    r"you\s+can(?:'|’)?t\s+get|"
    r"(?:party|buddy|guild|notice|system)\s*[:：])",
    re.IGNORECASE,
)

# Most specific first: "Magic Attack" must be tried before "Attack".
_STATS: tuple[tuple[str, str], ...] = (
    ("Req Lev", r"req(?:uired)?\s*lev(?:el)?\s*[:：]?\s*(\d+)"),
    ("Class", r"class\s*[:：]?\s*([A-Za-z ]+)"),
    ("STR", r"\bstr\s*[:=]?\s*([+-]?\s*\d+)"),
    ("DEX", r"\bdex\s*[:=]?\s*([+-]?\s*\d+)"),
    ("INT", r"\bint\s*[:=]?\s*([+-]?\s*\d+)"),
    ("LUK", r"\bluk\s*[:=]?\s*([+-]?\s*\d+)"),
    ("HP", r"\bhp\s*[:=]?\s*([+-]?\s*\d+)"),
    ("MP", r"\bmp\s*[:=]?\s*([+-]?\s*\d+)"),
    ("Weapon Attack", r"weapon\s*att(?:ack)?\s*[:：]?\s*(\d+)"),
    ("Magic Attack", r"magic\s*att(?:ack)?\s*[:：]?\s*(\d+)"),
    ("Attack", r"\batt(?:ack)?\s*[:：]?\s*(\d+)"),
    ("Weapon DEF", r"weapon\s*def(?:ense)?\s*[:：]?\s*(\d+)"),
    ("Magic DEF", r"magic\s*def(?:ense)?\s*[:：]?\s*(\d+)"),
    ("DEF", r"\bdef(?:ense)?\s*[:：]?\s*(\d+)"),
    ("Accuracy", r"accuracy\s*[:：]?\s*(\d+)"),
    ("Avoidability", r"avoid(?:ability)?\s*[:：]?\s*(\d+)"),
    ("Speed", r"\bspeed\s*[:：]?\s*(\d+)"),
    ("Jump", r"\bjump\s*[:：]?\s*(\d+)"),
    ("Slots", r"slots?\s*[:：]?\s*(\d+)"),
    ("Upgrades", r"upgrades?\s*[:：]?\s*(\d+)"),
    ("Quantity", r"(?:quantity|qty)\s*[:：]?\s*(\d+)"),
)

_QUANTITY_SUFFIX = re.compile(r"\s*(?:[x×]\s*(\d+))\s*$", re.IGNORECASE)
_STATISH = re.compile(
    r"^(?:req|class|str|dex|int|luk|hp|mp|weapon|magic|attack|def|accuracy|avoid|speed|jump|slots?|upgrades?|quantity|qty)\b",
    re.IGNORECASE,
)
_CODEISH = re.compile(r"(&&|\|\||[<>/\\{}\[\]_=]|\.venv|\bpython\b|\bpip\b|/tmp|\bcd\b)", re.IGNORECASE)


def _num(value: str) -> str:
    """Fix the usual OCR letter/number mix-up in a numeric field."""
    return value.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1").strip()


_NUMBER_TOKEN = re.compile(r"\b[0-9OoIl]+\b")


def _prepare_numbers(text: str) -> str:
    """Fix only number-looking tokens: '3O' -> '30', but never 'Slots' or 'LUK'."""
    def fix(match: re.Match) -> str:
        token = match.group(0)
        return _num(token) if any(ch.isdigit() for ch in token) else token
    return _NUMBER_TOKEN.sub(fix, text)


def _stats_of(text: str) -> list[tuple[str, str]]:
    """Every stat on one line: tooltips often put 'STR +2  DEX +1' together."""
    prepared = _prepare_numbers(text)
    found: list[tuple[str, str]] = []
    for label, pattern in _STATS:
        match = re.search(pattern, prepared, re.IGNORECASE)
        if match:
            value = _num(match.group(1)).strip()
            if value:
                found.append((label, value))
    labels = {label for label, _ in found}
    if "Weapon Attack" in labels or "Magic Attack" in labels:
        found = [item for item in found if item[0] != "Attack"]
    if "Weapon DEF" in labels or "Magic DEF" in labels:
        found = [item for item in found if item[0] != "DEF"]
    return found


def _is_noise(text: str) -> bool:
    return bool(_NOISE.match(text.strip()))


def _blocks(lines: list[TextLine]) -> list[list[TextLine]]:
    """Group lines that sit on top of one another with little vertical gap."""
    if not lines:
        return []
    lines = sorted(lines, key=lambda line: -line.top)
    blocks: list[list[TextLine]] = [[lines[0]]]
    for line in lines[1:]:
        prev = blocks[-1][-1]
        gap = prev.bottom - line.top
        overlap = min(prev.right, line.right) - max(prev.left, line.left)
        close = gap <= max(0.03, 1.1 * min(prev.box[3], line.box[3]))
        if close and overlap > 0:
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return blocks


def _score(block: list[TextLine]) -> float:
    """Prefer a multi-line block with stats, near the middle of the capture."""
    if not block:
        return -1.0
    stat_lines = sum(1 for line in block if _stats_of(line.text))
    confidence = sum(line.confidence for line in block) / len(block)
    cx = sum(line.center_x for line in block) / len(block)
    cy = sum(line.center_y for line in block) / len(block)
    distance = abs(cx - 0.5) + abs(cy - 0.5)
    return len(block) * 1.0 + stat_lines * 3.0 + confidence * 2.0 - distance * 1.5


def _item_name(block: list[TextLine]) -> tuple[str, int] | None:
    """The first line that looks like an item name, plus its quantity suffix if any."""
    for line in block:
        text = line.text.strip(" .:-")
        if not text or _is_noise(text) or _STATISH.match(text):
            continue
        if len(text) < 3 or len(text) > 80:
            continue
        if sum(ch.isalpha() for ch in text) < 3 or _CODEISH.search(text):
            continue
        quantity = 1
        suffix = _QUANTITY_SUFFIX.search(text)
        if suffix:
            quantity = int(suffix.group(1)) or 1
            text = text[:suffix.start()].strip(" .:-")
        if text:
            return text, quantity
    return None


def parse(lines: Iterable[TextLine]) -> ShopItem | None:
    """Best item in the OCR lines, or None when nothing looks like an item."""
    clean = [line for line in lines if line.text.strip() and not _is_noise(line.text)]
    if not clean:
        return None

    blocks = _blocks(clean)
    block = max(blocks, key=_score)
    found = _item_name(block)
    if not found:
        return None
    name, quantity = found

    stats: dict[str, str] = {}
    for line in block:
        for label, value in _stats_of(line.text):
            stats.setdefault(label, value)
    if "Quantity" in stats:
        try:
            quantity = max(1, int(stats["Quantity"]))
        except ValueError:
            pass

    category = "item"
    if name.lower().startswith("scroll"):
        category = "scroll"
    elif any(key in stats for key in ("Req Lev", "Slots", "Weapon Attack", "Magic Attack",
                                      "Weapon DEF", "Magic DEF", "DEF", "Attack")):
        category = "equip"
    elif "Quantity" in stats or quantity > 1:
        category = "stackable"

    confidence = sum(line.confidence for line in block) / len(block)
    return ShopItem(
        name=name,
        lines=[line.text for line in block],
        stats=stats,
        quantity=quantity,
        category=category,
        confidence=confidence,
    )
