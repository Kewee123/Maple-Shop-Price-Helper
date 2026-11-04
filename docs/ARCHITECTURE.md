# Architecture

## Flow

```
cursor ──► capture around cursor ──► macOS Vision OCR
                                      │
                                      ▼
                              tooltip block parser
                                      │
                                      ▼
                              ShopItem (name/stats/qty)
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
             manual price store              authorized providers only
                    │                         (none for MesoWatch)
                    └─────────────────┬─────────────────┘
                                      ▼
                              PriceSummary → window
```

## Modules

### `capture.py`

- `mouse_position()` uses `CGEventGetLocation` (top-left points, same as `mss`).
- `region_around()` clips a 760×600-point rectangle to the monitor under the
  cursor.
- `grab()` returns an RGB `PIL.Image` at the display's native pixel scale (2x on
  Retina), with the helper's own window blacked out in image coordinates.
- `frame_difference()` is a downscaled mean-absolute-difference check, so OCR
  only runs when a tooltip actually appears/changes.
- `screen_recording_granted()` / `request_screen_recording()` wrap the
  CoreGraphics permission helpers.
- `open_screen_recording_settings()` opens the right System Settings pane.

The cursor is read from the background loop, not from Tk, so the UI can stay
responsive. The loop skips while the cursor is over the helper's own window.

### `ocr.py`

`ocrmac` wraps Apple's Vision framework. No Tesseract binary or language data is
needed on macOS. Vision returns normalised boxes with a bottom-left origin; lines
are sorted top-to-bottom before parsing.

Windows will need a different `recognize()` implementation (Windows.Media.Ocr,
Tesseract, or a small helper process) behind the same signature.

### `tooltip.py`

A shop capture includes chat and HUD text. The parser:

1. drops the known pickup/chat noise (`You received EXP…`, `You have gained…`,
   `Party:` etc.);
2. groups lines that sit on top of each other;
3. scores groups by line count, stat-like lines and proximity to the capture
   centre;
4. takes the first non-stat line as the item name;
5. extracts numbers with a small OCR fix (`3O` → `30`, `Slots` stays `Slots`);
6. derives quantity and a variant signature for equipment.

The item name is editable in the window because OCR on a small tooltip will not
be perfect.

### `quantity.py`

Classic draws an inventory stack count at the bottom-left of the slot in a tiny
pixel font that Vision OCR does not read reliably. This module matches the 12x18
light-fill glyphs directly (the `1` is 6x18). It searches only the rectangle
around the cursor, groups adjacent digits, prefers the group nearest the cursor,
and rejects groups separated from the cursor by a bright slot border. A wide
component caused by an icon highlight is trimmed before matching.

The templates are for the 2x Retina rendering. A 1x capture is still attempted,
but if the count is not confident the item keeps its previous quantity (usually
`1`) instead of guessing.

### `pricing.py`

`PriceProvider` is the seam for data sources:

```python
class PriceProvider:
    name: str
    available: bool
    def lookup(self, item: ShopItem) -> list[PriceQuote]: ...
    def url_for(self, item: ShopItem) -> str: ...
```

- `ManualPriceProvider` reads `prices.json` in the app data folder.
- `site_links()` returns the browser URLs for MesoWatch and Cozy Market. There is
  **no MesoWatch provider**: it has no public API and does not share its data, so
  the app must not copy it. Cozy item endpoints need a browser pass, so there is
  no automated Cozy provider either.
- If an authorized third-party API is published later, implement `PriceProvider`
  behind `PriceService`. Until then, the only data source is the user's own
  manual notes.
- `PriceService` combines quotes into a `PriceSummary`: median typical, last,
  summed volume, low/high and suggested list price.

No provider may break the window: `PriceService` catches `SourceUnavailable` and
other exceptions and shows them as notices.

### `app.py`

Tk window, always-on-top by default. The watch thread captures/OCRs and pushes
results through a `queue.Queue`; only the Tk thread touches widgets. The item
name entry pauses OCR replacement while it has focus.

## Price variant matching

Equipment price depends on the exact stats. The manual store keys equipment by
normalised name plus a variant string such as:

```
bluedragonhelmet|DEX=+1|Req Lev=30|STR=+2|Slots=7
```

If the user only has a price for a different variant, the quote is shown with a
warning (`manual price is for a different stat variant`) rather than silently
treated as exact. A future provider should do the same and prefer a clean item
match over a scrolled one.

## Windows plan

Keep the parser/provider/window layers unchanged and add:

- `platforms/windows_capture.py` using the existing window handle + GDI/BitBlt
  (or `mss` on Windows, which already works).
- A Windows OCR backend (Windows.Media.Ocr is bundled with Windows 10/11; a
  Tesseract fallback is possible).
- The same `PriceProvider` interface and manual store path (`%APPDATA%`).

## Things not to do

- Do not bypass cozy.markets' Turnstile pass or meso.watch's rate/bot controls.
- Do not scrape, download, store or rebuild MesoWatch's price table. It has no
  API and does not share its data.
- Do not read either site's pages from the app; only open a browser link.
- Do not ship a provider that silently reads a site.
- Do not add network calls to the existing overlay; this is a separate app.
