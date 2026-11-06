# Maple Shop Price Helper

A Mac-first companion for MapleStory Classic shop owners. Hover an item in a
shop or in your inventory; the helper reads the tooltip on your own screen and
opens the item in MesoWatch.

The compact helper positions itself beside the MapleStory window when it first
opens. MesoWatch is positioned and sized once per app session; later item
searches reuse that browser layout and only update the search.

> **Status: prototype.** It reads shop tooltips and uses browser automation to
> search MesoWatch. Prices are displayed by MesoWatch, not copied into the app.
> See [docs/PERMISSIONS.md](docs/PERMISSIONS.md).

## What works

- Reads the item tooltip near the cursor with macOS Vision OCR (no Tesseract
  download and no screen-recording cloud service). Works for shop rows and
  inventory slots; inventory tabs, quest text and hover bullets are ignored.
- Keeps the item name, stats (Req Lev, STR/DEX/INT/LUK, attack/defence, slots)
  and quantity.
- Reads the stack count automatically from the bottom-left of the hovered
  inventory slot. No typing: hover the stack and the total-for-stack updates.
- Lets you correct the OCR name or quantity before searching.
- Automatically reuses an existing MesoWatch tab, enters the item in
  **Filter items…**, and selects the matching item.
- Cross-references the OCR name against a bundled 5,576-item copy of MeowDB's
  MapleStory Classic Item Database A-Z index; unrecognized names are not sent
  to MesoWatch, so scans do not wait on a MeowDB page.
- Positions the MesoWatch window in the lower-right corner, below the helper
  when screen space allows, and sizes it to the available space outside the
  MapleStory window.
- A **Retry search** button is available when the browser action needs
  to be repeated.
- “Save capture” for tuning the tooltip detection.

## Current limits

- Mac only for now.
- It only reads while the cursor is over a recognised game window: MapleStory,
  CrossOver, Whisky, Wine or Parallels. A browser game stream will need a window
  picker (roadmap).
- Tooltip OCR is best-effort; the item name is editable. **Save capture** writes
  the exact crop if a hover is misread, which makes parser tuning quick.
- Slot-count reading is tuned for the 2x Retina rendering used by the Mac client.
  On a 1x display it falls back to 1, which you can edit.

## Install (macOS)

Requires macOS 14+ and Python 3.12.

```bash
cd Maple-Shop-Price-Helper
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m shop_price_helper
```

The first time, allow **Screen Recording** for the app (or for **Terminal** when
running from source):

**System Settings → Privacy & Security → Screen Recording**, then restart the
helper.

## Use

1. Start MapleStory and open your shop or inventory.
2. Open the helper and press **Start watching** if it isn’t already watching.
3. Hover an item for about half a second.
4. The panel fills with the OCR’d item and the stack count from the slot.
   Correct the name or quantity only if the read needs it.
5. The helper automatically searches the scanned item in MesoWatch. Use
   **Retry search** if needed. MesoWatch shows the last-sold and
   average prices in the browser.

To enable automatic MesoWatch searching on macOS, open Chrome's macOS menu bar
and choose **Develop → Allow JavaScript from Apple Events**. You may set
`MESO_WATCH_BROWSER` if you use a Chromium browser with a different app name.
The app's **Chrome setup** button activates Chrome and shows this
setup instruction; Chrome does not provide a deep link directly to this menu
switch.
The helper never clicks or types into the game. It only reads the small screen
area around the cursor.

## Where data is saved

- Saved captures: `~/Library/Application Support/MapleShopPriceHelper/captures/`

Nothing is uploaded by default. The app controls Chrome locally and does not
copy pricing data from the site.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Design

The code is deliberately split so the OCR side and the price side can evolve
independently:

```
shop_price_helper/
  capture.py    cursor, screen rectangle, screen-recording permission
  ocr.py        macOS Vision OCR (ocrmac)
  tooltip.py    OCR lines -> item name/stats/quantity
  quantity.py   slot count -> number (12x18 pixel-font templates)
  model.py      ShopItem and weapon metadata
  catalog.py    bundled item names and categories
  pricing.py    browser source links
  app.py        Tk window and hover loop
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the application structure.
The captured mesos.watch endpoint reference is in [docs/apis.md](docs/apis.md).

## Roadmap

- [x] Automatic MesoWatch browser search from scanned inventory items.
- [ ] Add 1x-display count templates (currently Retina 2x is tuned).
- [ ] Tune tooltip-box detection against real shop screenshots (send one with
      the overlay out of the way).
- [ ] Import/export the user's own price notes (CSV), not site datasets.
- [ ] Match equipment stat variants more exactly; show “clean vs scrolled”.
- [ ] Windows build (Win32 capture + the same OCR and browser layers).
- [ ] A small PyInstaller app and GitHub release workflow.

## Legal

This is a fan-made tool, not affiliated with NEXON. MapleStory and its item
names belong to NEXON. MesoWatch has no API and does not share its data; this
project does not copy, scrape or redistribute it. Cozy Market is linked to, never
read by the app. Manual price notes are the user's own and stay on their Mac.

MIT licensed; see [LICENSE](LICENSE).
