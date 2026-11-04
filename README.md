# Maple Shop Price Helper

A Mac-first companion for MapleStory Classic shop owners. Hover an item in a
shop or in your inventory; the helper reads the tooltip on your own screen and
shows a price panel next to it.

> **Status: prototype.** It reads shop tooltips and keeps manual prices. It does
> **not** fetch from meso.watch or cozy.markets: **MesoWatch has no public API and
> does not share its data — do not copy it.** Cozy Market's item endpoints need a
> browser pass. The app is manual prices plus browser links only.
> See [docs/PERMISSIONS.md](docs/PERMISSIONS.md).

## What works

- Reads the item tooltip near the cursor with macOS Vision OCR (no Tesseract
  download and no screen-recording cloud service). Works for shop rows and
  inventory slots; inventory tabs, quest text and hover bullets are ignored.
- Keeps the item name, stats (Req Lev, STR/DEX/INT/LUK, attack/defence, slots)
  and quantity.
- Lets you correct the OCR name; the price lookup uses the corrected name.
- Manual price entries per item (and per stat variant for equipment), saved on
  this computer only.
- Suggested list price = median × 0.95, plus the raw median, last sold, volume,
  low/high and sources. The quantity is editable, so a stack shows the total for
  the whole stack (e.g. 189 Aquamarine Ore).
- Browser buttons for **meso.watch** and **cozy.markets** (links only; no page
  reading, no data copying).
- “Save capture” for tuning the tooltip detection.
- No network requests in this build. Opening a site button launches your normal
  browser; nothing is sent by the app.

## Current limits

- Mac only for now.
- It only reads while the cursor is over a recognised game window: MapleStory,
  CrossOver, Whisky, Wine or Parallels. A browser game stream will need a window
  picker (roadmap).
- Tooltip OCR is best-effort; the item name is editable. **Save capture** writes
  the exact crop if a hover is misread, which makes parser tuning quick.
- No automatic price API: MesoWatch is link-only by policy; manual prices plus
  browser links are the supported path.

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

1. Start MapleStory and open your shop.
2. Open the helper and press **Start watching** if it isn’t already watching.
3. Hover an item in the shop for about half a second.
4. The panel fills with the OCR’d item. Correct the name if needed.
5. Set the **Quantity** from the inventory slot if it isn’t in the tooltip.
6. Type a price with **Set price…** (values like `1.2m`, `500k` and `1,234,567`
   work), or click **Open MesoWatch** / **Open Cozy** to look it up yourself.
7. **Copy suggested** puts the unit price — or the total for the stack — on the
   clipboard.

The helper never clicks or types into the game. It only reads the small screen
area around the cursor.

## Where data is saved

- Manual prices: `~/Library/Application Support/MapleShopPriceHelper/prices.json`
- Saved captures: `~/Library/Application Support/MapleShopPriceHelper/captures/`

Nothing is uploaded. The two site buttons only open a browser URL; the app never
reads the page or stores its contents.

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
  model.py      ShopItem, PriceQuote, PriceSummary
  pricing.py    provider interface, manual store, source links
  app.py        Tk window and hover loop
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the planned provider API,
caching and Windows path.

## Roadmap

- [ ] If an authorized price API is published, add it behind `PriceProvider`
      (with caching/rate limits). Until then: manual prices and links only.
- [ ] Editable quantity and total-for-stack on the main panel.
- [ ] Tune tooltip-box detection against real shop screenshots (send one with
      the overlay out of the way).
- [ ] Import/export the user's own price notes (CSV), not site datasets.
- [ ] Match equipment stat variants more exactly; show “clean vs scrolled”.
- [ ] Windows build (Win32 capture + the same OCR/provider layers).
- [ ] A small PyInstaller app and GitHub release workflow.

## Legal

This is a fan-made tool, not affiliated with NEXON. MapleStory and its item
names belong to NEXON. MesoWatch has no API and does not share its data; this
project does not copy, scrape or redistribute it. Cozy Market is linked to, never
read by the app. Manual price notes are the user's own and stay on their Mac.

MIT licensed; see [LICENSE](LICENSE).
