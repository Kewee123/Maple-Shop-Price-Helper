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
             manual price store                 price providers
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
                              PriceSummary → window
```

## Modules

### `capture.py`

- `mouse_position()` uses `CGEventGetLocation` (top-left points, same as `mss`).
- `region_around()` clips a 640×560 rectangle to the monitor under the cursor.
- `grab()` returns an RGB `PIL.Image`.
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
- `MesoWatchProvider` and `CozyMarketProvider` are disabled placeholders until
  permission/API access exists. They provide the browser search URL.
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
- Do not download/store their price tables or data files.
- Do not ship a provider that is disabled by default without a clear UI notice.
- Do not add network calls to the existing overlay; this is a separate app.
