"""Authorized, read-only client for the documented mesos.watch API."""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import PriceQuote, ShopItem
from .pricing import PriceProvider, SourceUnavailable


class MesosWatchProvider(PriceProvider):
    name = "mesos.watch"
    available = True

    def __init__(self, session_cookie: str | None = None):
        self.session_cookie = session_cookie or os.environ.get("MESOS_WATCH_SESSION", "")
        self._names: dict[str, int] | None = None

    def lookup(self, item: ShopItem) -> list[PriceQuote]:
        if not item.is_weapon:
            return []
        if not self.session_cookie:
            raise SourceUnavailable("set MESOS_WATCH_SESSION after completing Turnstile")
        item_id = self._item_id(item.name)
        if item_id is None:
            return []
        summary = self._get("/item/summary", ids=str(item_id)).get("items", [])
        if not summary:
            return []
        fields = self._fields(summary[0], ("item_id", "name", "listings", "stores",
                                           "channels", "cheapest_unit", "cheapest_where",
                                           "newest_seen_at", "typical", "sales_30d"))
        try:
            history = self._get(f"/item/{item_id}/history", days="120", summary="1").get("summary", {})
        except SourceUnavailable:
            history = {}
        typical = _int(fields.get("typical")) or _int(fields.get("cheapest_unit"))
        return [PriceQuote(source=self.name, typical=typical,
                           last=_int(history.get("median_unit_price")),
                           volume=_int(history.get("volume")) or _int(fields.get("sales_30d")),
                           low=_int(fields.get("cheapest_unit")))]

    def _item_id(self, name: str) -> int | None:
        if self._names is None:
            payload = self._get("/item/names")
            self._names = {str(row[1]).casefold(): int(row[0])
                           for row in payload.get("items", [])
                           if isinstance(row, list) and len(row) >= 2}
        return self._names.get(name.casefold())

    @staticmethod
    def _fields(row: list, names: tuple[str, ...]) -> dict:
        return dict(zip(names, row))

    def _get(self, path: str, **params) -> dict:
        url = "https://api.mesos.watch" + path
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers={"Accept": "application/json",
                                        "Cookie": f"mw_s={self.session_cookie}"})
        try:
            with urlopen(request, timeout=8) as response:
                data = json.loads(response.read())
        except Exception as exc:
            raise SourceUnavailable(f"request failed: {type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise SourceUnavailable("API returned an invalid response")
        return data


def _int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
