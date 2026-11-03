"""Small data types shared by the screen reader, price providers and the window."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field


def normalize_name(name: str) -> str:
    """Lower-case, letters and digits only: 'Blue Dragon Helmet' -> 'bluedragonhelmet'."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def fmt_mesos(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def fmt_volume(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def parse_mesos(text: str) -> int | None:
    """'1.2m', '500k', '2b', '1,234,567' -> mesos. None if it isn't a number."""
    text = str(text).strip().lower().replace(",", "").replace(" ", "")
    if not text:
        return None
    mult = 1
    if text.endswith("k"):
        mult, text = 1_000, text[:-1]
    elif text.endswith("m"):
        mult, text = 1_000_000, text[:-1]
    elif text.endswith("b"):
        mult, text = 1_000_000_000, text[:-1]
    try:
        number = float(text)
    except ValueError:
        return None
    if number < 0:
        return None
    return int(round(number * mult))


def parse_count(text: str) -> int | None:
    text = str(text).strip().replace(",", "")
    return int(text) if text.isdigit() else None


@dataclass(frozen=True)
class TextLine:
    """One line from the OCR, with its box in the captured image.

    `box` is (x, y, width, height), normalised to 0..1, with the origin at the
    BOTTOM left (macOS Vision's convention).
    """

    text: str
    confidence: float
    box: tuple[float, float, float, float]

    @property
    def left(self) -> float:
        return self.box[0]

    @property
    def bottom(self) -> float:
        return self.box[1]

    @property
    def top(self) -> float:
        return self.box[1] + self.box[3]

    @property
    def right(self) -> float:
        return self.box[0] + self.box[2]

    @property
    def center_x(self) -> float:
        return self.box[0] + self.box[2] / 2

    @property
    def center_y(self) -> float:
        return self.box[1] + self.box[3] / 2


@dataclass
class ShopItem:
    """The item read from a shop tooltip.

    `stats` keeps the raw values as read, e.g. {"Req Lev": "30", "STR": "+2"}.
    `key` includes the stats for equipment, so a clean item and a scrolled one
    don't share a manual price by accident.
    """

    name: str
    lines: list[str] = field(default_factory=list)
    stats: dict[str, str] = field(default_factory=dict)
    quantity: int = 1
    category: str = ""
    confidence: float = 0.0

    @property
    def variant(self) -> str:
        if self.category not in ("equip", "scroll"):
            return ""
        return "|".join(f"{k}={v}" for k, v in sorted(self.stats.items()) if k != "Quantity")

    @property
    def key(self) -> str:
        base = normalize_name(self.name)
        return f"{base}|{self.variant}" if self.variant else base

    @property
    def display_stats(self) -> list[tuple[str, str]]:
        return [(k, v) for k, v in self.stats.items() if k != "Quantity"]

    def renamed(self, name: str) -> "ShopItem":
        return ShopItem(name=name.strip() or self.name, lines=list(self.lines), stats=dict(self.stats),
                        quantity=self.quantity, category=self.category, confidence=self.confidence)


@dataclass
class PriceQuote:
    source: str
    typical: int | None = None
    last: int | None = None
    volume: int | None = None
    low: int | None = None
    high: int | None = None
    updated: str = ""
    url: str = ""
    note: str = ""


@dataclass
class PriceSummary:
    quotes: list[PriceQuote] = field(default_factory=list)
    typical: int | None = None
    last: int | None = None
    volume: int | None = None
    low: int | None = None
    high: int | None = None

    @classmethod
    def from_quotes(cls, quotes: list[PriceQuote]) -> "PriceSummary":
        typicals = [q.typical for q in quotes if q.typical is not None]
        lasts = [q.last for q in quotes if q.last is not None]
        volumes = [q.volume for q in quotes if q.volume is not None]
        lows = [q.low for q in quotes if q.low is not None]
        highs = [q.high for q in quotes if q.high is not None]
        return cls(
            quotes=list(quotes),
            typical=int(statistics.median(typicals)) if typicals else None,
            last=lasts[-1] if lasts else None,
            volume=sum(volumes) if volumes else None,
            low=min(lows) if lows else None,
            high=max(highs) if highs else None,
        )

    @property
    def sources(self) -> list[str]:
        return list(dict.fromkeys(q.source for q in self.quotes))

    def suggested(self, undercut: float = 0.05) -> int | None:
        if self.typical is None:
            return None
        return max(1, int(round(self.typical * (1 - undercut))))

    def total_for(self, quantity: int, undercut: float = 0.05) -> int | None:
        unit = self.suggested(undercut)
        return None if unit is None else unit * max(1, quantity)
