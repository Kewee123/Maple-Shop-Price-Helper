"""Price sources.

The prototype does NOT scrape meso.watch or cozy.markets. Both protect their
item data (meso.watch's terms forbid automated collection; cozy.markets gates
its item endpoints behind a Cloudflare Turnstile pass), so the live providers
below are deliberately disabled until written permission or an official API is
available.

Until then the app has:
  - manual prices stored on this computer, and
  - buttons that open the item search on each site in the browser.
"""
from __future__ import annotations

import json
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote_plus

from .model import PriceQuote, PriceSummary, ShopItem, normalize_name


def app_data_dir() -> Path:
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "MapleShopPriceHelper"


class SourceUnavailable(RuntimeError):
    """A source exists but this app has no permission/API access to it."""


class PriceProvider(ABC):
    name = "?"
    available = False
    permission_note = ""

    @abstractmethod
    def lookup(self, item: ShopItem) -> list[PriceQuote]:
        """Quotes for this item, or an empty list. Raise SourceUnavailable if blocked."""

    def url_for(self, item: ShopItem) -> str:
        return ""


SITE_LINKS = {
    # Browser links only. The app never fetches these pages or copies their data.
    "MesoWatch": "https://meso.watch/?q={query}",
    # Cozy's item search is client-side and does not read a query parameter.
    # Open the list; the app copies the item name so it can be pasted.
    "Cozy Market": "https://cozy.markets/items",
}


def site_links(item: ShopItem) -> list[tuple[str, str]]:
    """Where the user can look the item up themselves, in a normal browser."""
    return [(name, template.format(query=quote_plus(item.name)) if "{query}" in template else template)
            for name, template in SITE_LINKS.items()]


class ManualStore:
    """Prices the user typed in, kept in the app's data folder only."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else app_data_dir() / "prices.json"

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def put(self, item: ShopItem, *, typical: int | None, last: int | None, volume: int | None,
            low: int | None, high: int | None) -> None:
        data = self._load()
        data[item.key] = {
            "name": item.name,
            "variant": item.variant,
            "category": item.category,
            "typical": typical,
            "last": last,
            "volume": volume,
            "low": low,
            "high": high,
            "updated": time.strftime("%Y-%m-%d %H:%M"),
        }
        self._save(data)

    def quote(self, item: ShopItem) -> PriceQuote | None:
        data = self._load()
        entry = data.get(item.key)
        note = ""
        if entry is None and item.category in ("equip", "scroll"):
            # The same item with different stats is a different price; a base
            # entry is still useful, but say that it isn't an exact match.
            name_key = normalize_name(item.name)
            for key, candidate in data.items():
                if key.split("|", 1)[0] == name_key:
                    entry, note = candidate, "manual price is for a different stat variant"
                    break
        if not isinstance(entry, dict):
            return None
        return PriceQuote(
            source="manual",
            typical=_int_or_none(entry.get("typical")),
            last=_int_or_none(entry.get("last")),
            volume=_int_or_none(entry.get("volume")),
            low=_int_or_none(entry.get("low")),
            high=_int_or_none(entry.get("high")),
            updated=str(entry.get("updated") or ""),
            note=note,
        )


class ManualPriceProvider(PriceProvider):
    name = "manual"
    available = True

    def __init__(self, store: ManualStore | None = None):
        self.store = store or ManualStore()

    def lookup(self, item: ShopItem) -> list[PriceQuote]:
        quote = self.store.quote(item)
        return [quote] if quote else []


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


class PriceService:
    def __init__(self, providers: list[PriceProvider]):
        self.providers = providers

    def lookup(self, item: ShopItem) -> tuple[PriceSummary, list[str]]:
        quotes: list[PriceQuote] = []
        notices: list[str] = []
        for provider in self.providers:
            try:
                quotes.extend(provider.lookup(item))
            except SourceUnavailable as exc:
                notices.append(f"{provider.name}: {exc}")
            except Exception as exc:  # a provider must never break the window
                notices.append(f"{provider.name}: {type(exc).__name__}: {exc}")
        return PriceSummary.from_quotes(quotes), notices

