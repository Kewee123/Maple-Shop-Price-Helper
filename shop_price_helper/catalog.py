"""Fast local validation for OCR item names."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .model import normalize_name

_LEVEL_SUFFIX = re.compile(r"\s*\(lv\.?\s*\d+\)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogItem:
    item_id: int
    name: str
    category: str
    subcategory: str


def _lookup_key(name: str) -> str:
    """Normalize OCR punctuation and remove MeowDB's displayed level suffix."""
    without_level = _LEVEL_SUFFIX.sub("", name.strip())
    return normalize_name(without_level)


@lru_cache(maxsize=1)
def _items_by_name() -> dict[str, CatalogItem]:
    path = Path(__file__).with_name("data") / "item_catalog.json"
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    items: dict[str, CatalogItem] = {}
    for raw in payload["items"]:
        item = CatalogItem(
            item_id=int(raw["id"]),
            name=_LEVEL_SUFFIX.sub("", str(raw["name"]).strip()),
            category=str(raw.get("category", "")),
            subcategory=str(raw.get("subcategory", "")),
        )
        # Keep the first entry for duplicate names. The browser search is by
        # name, while the catalog can contain several IDs for one name.
        items.setdefault(_lookup_key(item.name), item)
    return items


def lookup(name: str) -> CatalogItem | None:
    """Return the canonical local item for an OCR or manually entered name."""
    if not name.strip():
        return None
    return _items_by_name().get(_lookup_key(name))


def clear_cache() -> None:
    """Clear the loaded catalog cache for tests or a future data reload."""
    _items_by_name.cache_clear()
