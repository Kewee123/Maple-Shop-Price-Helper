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
from difflib import get_close_matches

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
    ("Type", r"type\s*[:：]?\s*([A-Za-z][A-Za-z -]*)"),
    ("Class", r"class\s*[:：]?\s*([A-Za-z ]+)"),
    ("STR", r"\bstr\s*[:=]?\s*([+-]?\s*\d+)"),
    ("DEX", r"\bdex\s*[:=]?\s*([+-]?\s*\d+)"),
    ("INT", r"\bint\s*[:=]?\s*([+-]?\s*\d+)"),
    ("LUK", r"\bluk\s*[:=]?\s*([+-]?\s*\d+)"),
    ("HP", r"\bhp\s*[:=]?\s*([+-]?\s*\d+)"),
    ("MP", r"\bmp\s*[:=]?\s*([+-]?\s*\d+)"),
    ("Weapon Attack", r"weapon\s*att(?:ack)?\s*[:：]?\s*([+-]?\d+)"),
    ("Magic Attack", r"magic\s*att(?:ack)?\s*[:：]?\s*([+-]?\d+)"),
    ("Attack", r"\batt(?:ack)?\s*[:：]?\s*([+-]?\d+)"),
    ("Weapon DEF", r"weapon\s*def(?:ense)?\s*[:：]?\s*([+-]?\d+)"),
    ("Magic DEF", r"magic\s*def(?:ense)?\s*[:：]?\s*([+-]?\d+)"),
    ("DEF", r"\bdef(?:ense)?\s*[:：]?\s*([+-]?\d+)"),
    ("Accuracy", r"accuracy\s*[:：]?\s*([+-]?\d+)"),
    ("Avoidability", r"avoid(?:ability)?\s*[:：]?\s*([+-]?\d+)"),
    ("Speed", r"\bspeed\s*[:：]?\s*([+-]?\d+)"),
    ("Jump", r"\bjump\s*[:：]?\s*([+-]?\d+)"),
    ("Attack Speed", r"attack\s*speed\s*[:：]?\s*([A-Za-z]+)"),
    ("Slots", r"slots?\s*[:：]?\s*(\d+)"),
    ("Upgrades", r"(?:upgrades?|remaining\s*enhancements)\s*[:：]?\s*(\d+)"),
    ("Quantity", r"(?:quantity|qty)\s*[:：]?\s*(\d+)"),
)

_QUANTITY_SUFFIX = re.compile(r"\s*(?:[x×]\s*(\d+))\s*$", re.IGNORECASE)
_STATISH = re.compile(
    r"^(?:req|required|type|class|str|dex|int|luk|hp|mp|weapon|magic|attack|def|accuracy|avoid|speed|jump|slots?|upgrades?|remaining|quantity|qty)\b",
    re.IGNORECASE,
)
_META_LINE = re.compile(
    r"^(?:quest\s+item|untradeable|tradeable|account[- ]bound|"
    r"usable\s+until|cash\s+item|expires?)\b",
    re.IGNORECASE,
)
_CODEISH = re.compile(r"(&&|\|\||[<>/\\{}\[\]_=]|\.venv|\bpython\b|\bpip\b|/tmp|\bcd\b)", re.IGNORECASE)
_QUEST_PROGRESS = re.compile(r"\b\d+\s*/\s*\d+\b")

# Inventory tabs and headings. OCR often reads "Etc" as "Ete", so short words
# are also matched approximately.
_UI_TOKENS = {
    "equip", "use", "setup", "etc", "cash", "deco", "mesos", "meso", "items",
    "shop", "inventory", "quest", "helper",
}
_UI_PHRASES = {"iteminventory", "inventory", "freemarket", "questhelper"}
_UI_PREFIXES = ("iteminventory", "questhelper")

_DESCRIPTION_STARTS = {"the", "a", "an", "this", "it", "you", "your", "when", "while", "can"}
_WEAPON_TYPES = {
    "bow", "crossbow", "dagger", "gun", "knuckle", "one-handed axe",
    "one-handed blunt weapon", "one-handed sword", "pole arm", "spear",
    "staff", "two-handed axe", "two-handed blunt weapon",
    "two-handed sword", "wand",
}

# The hover highlight puts a bullet (or similar glyph) in front of the item name.
_LEADING_MARKS = re.compile(r"^[\s•·●○◆◇■□▪▫►▶➤➢»*\-–—]+")


def _clean_text(text: str) -> str:
    """Drop hover bullets and extra whitespace, but keep the words."""
    return _LEADING_MARKS.sub("", " ".join(str(text).split())).strip(" .:-")


def _ui_like(text: str) -> bool:
    """Whether a line is inventory chrome rather than the item name."""
    clean = _clean_text(text).lower()
    if not clean:
        return False
    normalized = re.sub(r"[^a-z0-9]+", "", clean)
    if normalized in _UI_TOKENS or normalized in _UI_PHRASES or normalized.startswith(_UI_PREFIXES):
        return True
    words = [word for word in re.split(r"[^a-z]+", clean) if word]
    if not words:
        return False
    for word in words:
        if word in _UI_TOKENS:
            continue
        if len(word) <= 4 and get_close_matches(word, _UI_TOKENS, n=1, cutoff=0.6):
            continue
        return False
    return True


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
    """Group lines into tooltip-like blocks.

    A stray count or HUD label can sit vertically between an item name and its
    description, so each line is matched against every open block, not just the
    most recently created one.
    """
    if not lines:
        return []
    ordered = sorted(lines, key=lambda line: -line.top)
    blocks: list[list[TextLine]] = [[ordered[0]]]
    for line in ordered[1:]:
        best_block = None
        best_gap = None
        for block in blocks:
            for prev in block:
                overlap = min(prev.right, line.right) - max(prev.left, line.left)
                if overlap <= 0:
                    continue
                gap = prev.bottom - line.top
                limit = max(0.045, 1.4 * min(prev.box[3], line.box[3]))
                if 0 <= gap <= limit and (best_gap is None or gap < best_gap):
                    best_gap, best_block = gap, block
        if best_block is not None:
            best_block.append(line)
        else:
            blocks.append([line])
    return blocks


def _name_likeness(text: str) -> float:
    """Item names are short and title-cased; descriptions start with 'The'/'A'."""
    clean = _clean_text(text)
    low = clean.lower()
    if _ui_like(clean):
        return -10.0
    if clean.isupper() and len(clean) > 3:
        return -6.0
    words = clean.split()
    if not words:
        return -10.0
    if len(words) > 7:
        return -6.0
    if words[0].lower() in _DESCRIPTION_STARTS:
        return -5.0
    title = sum(word[:1].isupper() for word in words) / len(words)
    return title * 6.0 - max(0, len(words) - 5) * 1.5


def _score(block: list[TextLine], focus: tuple[float, float] = (0.5, 0.5)) -> float:
    """Prefer a multi-line block with stats near the cursor, whose first line
    looks like an item name rather than a tooltip description."""
    if not block:
        return -1.0
    stat_lines = sum(1 for line in block if _stats_of(line.text))
    confidence = sum(line.confidence for line in block) / len(block)
    cx = sum(line.center_x for line in block) / len(block)
    cy = sum(line.center_y for line in block) / len(block)
    distance = abs(cx - focus[0]) + abs(cy - focus[1])
    if distance > 0.65:
        return -20.0
    found = _item_name(block)
    name_bonus = _name_likeness(found[0]) if found else -10.0
    return (len(block) * 1.0 + stat_lines * 3.0 + confidence * 2.0
            - distance * 16.0 + name_bonus * 2.0)


def _item_name(block: list[TextLine]) -> tuple[str, int] | None:
    """The first line that looks like an item name, plus its quantity suffix if any."""
    for line in block:
        text = _clean_text(line.text)
        if (not text or _is_noise(text) or _STATISH.match(text)
                or _META_LINE.match(text) or _ui_like(text)):
            continue
        if len(text) < 3 or len(text) > 80:
            continue
        words = text.split()
        if words and words[0].lower() in _DESCRIPTION_STARTS and len(words) >= 3:
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


def _tooltip_like(block: list[TextLine], found: tuple[str, int]) -> bool:
    """Whether the block looks like an item tooltip, not a lone HUD/player name.

    Every item tooltip in Classic has at least a second line (description, stats
    or price). A single "Kewee" over the character is a player name, not an item.
    Single-line stack entries with an "x 250" suffix are still accepted.
    """
    _, quantity = found
    if quantity > 1 or any(_stats_of(line.text) for line in block):
        return True
    texts = [_clean_text(line.text) for line in block if _clean_text(line.text)]
    if len(texts) < 2:
        return False
    if any(_QUEST_PROGRESS.search(text) and not _META_LINE.match(text) for text in texts):
        return False
    return True


def parse(lines: Iterable[TextLine], focus: tuple[float, float] | None = None) -> ShopItem | None:
    """Best item in the OCR lines, or None when nothing looks like an item.

    `focus` is the cursor position in the capture (0..1, origin bottom left).
    Tooltips appear next to the cursor, so this separates them from HUD text.
    """
    focus = focus or (0.5, 0.5)
    clean = [line for line in lines if line.text.strip() and not _is_noise(line.text)]
    if not clean:
        return None

    blocks = _blocks(clean)
    block = max(blocks, key=lambda found: _score(found, focus))
    if _score(block, focus) < -10.0:
        return None
    found = _item_name(block)
    if not found:
        return None
    if not _tooltip_like(block, found):
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
    elif stats.get("Type", "").strip().lower() in _WEAPON_TYPES or "Weapon Attack" in stats:
        category = "weapon"
    elif any(key in stats for key in ("Req Lev", "Type", "Attack Speed", "Slots",
                                      "Weapon Attack", "Magic Attack", "Weapon DEF",
                                      "Magic DEF", "DEF", "Attack")):
        category = "equip"
    elif "Quantity" in stats or quantity > 1:
        category = "stackable"

    description = ""
    if category == "weapon":
        name_index = next((index for index, line in enumerate(block)
                           if _clean_text(line.text) == name), -1)
        prose = []
        for line in block[name_index + 1:]:
            text = " ".join(str(line.text).split()).strip()
            if text and not _stats_of(text) and not _META_LINE.match(text):
                prose.append(text)
        description = " ".join(prose)

    confidence = sum(line.confidence for line in block) / len(block)
    return ShopItem(
        name=name,
        lines=[line.text for line in block],
        stats=stats,
        description=description,
        quantity=quantity,
        category=category,
        confidence=confidence,
    )
