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
                                      │
                                      ▼
                         local item catalog validation
                                      │
                                      ▼
                         Chrome MesoWatch automation
                         (search and select item)
```

## Modules

### `capture.py`

- `mouse_position()` uses `CGEventGetLocation` (top-left points, same as `mss`).
- `region_around()` clips a 760×600-point rectangle to the monitor under the
  cursor.
- `grab()` returns an RGB `PIL.Image` at the display's native pixel scale (2x on
  Retina), with the helper's own window blacked out in image coordinates.
- `frame_difference()` is a downscaled mean-absolute-difference check, so OCR
  only runs when the cursor-centered inventory/tooltip crop actually
  appears/changes; animated map pixels outside that crop are ignored.
- `screen_recording_granted()` / `request_screen_recording()` wrap the
  CoreGraphics permission helpers.
- `open_screen_recording_settings()` opens the right System Settings pane.

The cursor is read from the background loop, not from Tk, so the UI can stay
responsive. The loop skips while the cursor is over the helper's own window or
an unrelated window; supported wrappers must also identify MapleStory in their
window title. It also skips cursor positions outside the MapleStory inventory
panel.

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
- strongly prefers the tooltip block nearest the cursor anchor when multiple
   tooltip blocks are visible;
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

### `browser.py`

The browser automation reuses an existing MesoWatch tab when possible. It
activates Chrome, sets the client-side `#search` input using the native DOM
setter, waits for rendered `.item-select` results, and clicks the first match.
Unknown OCR text is rejected by the local `data/item_catalog.json` index before
MesoWatch is opened. It then positions and sizes Chrome beside the helper,
falling back to below, left, or the available screen edge. The operation runs
off the Tk thread so OCR and the UI remain responsive.

### `catalog.py`

Loads the MeowDB item index bundled with the application once and provides
case- and punctuation-insensitive item lookup. The level suffixes displayed in
the MeowDB A-Z page are treated as metadata, so `Jean Capris` and
`Jean Capris (Lv 5)` resolve to the same canonical item.

### `app.py`

Tk window, always-on-top by default. At startup it finds the MapleStory window
and places the compact helper beside it. The watch thread captures/OCRs and
pushes results through a `queue.Queue`; only the Tk thread touches widgets. The
item name entry pauses OCR replacement while it has focus. MesoWatch window
placement is performed when the helper moves to a different position; later
searches at the same helper position do not resize or move Chrome.

## Windows plan

Keep the parser/window layers unchanged and add:

- `platforms/windows_capture.py` using the existing window handle + GDI/BitBlt
  (or `mss` on Windows, which already works).
- A Windows OCR backend (Windows.Media.Ocr is bundled with Windows 10/11; a
  Tesseract fallback is possible).
- A browser automation backend appropriate for the target platform.

## Things not to do

- Do not bypass cozy.markets' Turnstile pass or meso.watch's rate/bot controls.
- Do not scrape, download, store or rebuild MesoWatch's price table. It has no
  API and does not share its data.
- Do not read either site's pages from the app; only open a browser link.
- Do not ship a provider that silently reads a site.
- Do not add network calls to the existing overlay; this is a separate app.
