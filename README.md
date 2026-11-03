# Maple Shop Price Helper

A Mac-first companion for MapleStory Classic shop owners. Hover an item in your
shop; the helper reads the tooltip on your own screen and shows a price panel
next to it.

> **Status: prototype.** It reads shop tooltips and keeps manual prices. It does
> **not** automatically fetch from meso.watch or cozy.markets yet: both protect
> their item data, so that part waits for written permission or an official API.
> See [docs/PERMISSIONS.md](docs/PERMISSIONS.md).

## What works

- Reads the item tooltip near the cursor with macOS Vision OCR (no Tesseract
  download and no screen-recording cloud service).
- Keeps the item name, stats (Req Lev, STR/DEX/INT/LUK, attack/defence, slots)
  and quantity.
- Lets you correct the OCR name; the price lookup uses the corrected name.
- Manual price entries per item (and per stat variant for equipment), saved on
  this computer only.
- Suggested list price = median × 0.95, plus the raw median, last sold, volume,
  low/high and sources.
- Buttons to open the matching search on **meso.watch** and **cozy.markets**.
- “Save capture” for tuning the tooltip detection.
- No network requests in this build. Opening a site button launches your normal
  browser; nothing is sent by the app.

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
5. Type a price with **Set price…** (values like `1.2m`, `500k` and `1,234,567`
   work), or click **MesoWatch** / **Cozy Market** to look it up.
6. **Copy suggested** puts the suggested listing price on the clipboard.

The helper never clicks or types into the game. It only reads the small screen
area around the cursor.

## Where data is saved

- Manual prices: `~/Library/Application Support/MapleShopPriceHelper/prices.json`
- Saved captures: `~/Library/Application Support/MapleShopPriceHelper/captures/`

Nothing is uploaded. The two site buttons only open a browser URL.

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

- [ ] Get written permission / API access from meso.watch and cozy.markets.
- [ ] Add `MesoWatchProvider` and `CozyMarketProvider` behind the existing
      interface, with caching, rate limits and attribution.
- [ ] Tune tooltip-box detection against real shop screenshots (send one with
      the overlay out of the way).
- [ ] Match equipment stat variants more exactly; show “clean vs scrolled”.
- [ ] Windows build (Win32 capture + the same OCR/provider layers).
- [ ] A small PyInstaller app and GitHub release workflow.

## Legal

This is a fan-made tool, not affiliated with NEXON. MapleStory and its item
names belong to NEXON. Price data belongs to the site that collected it; this
prototype does not copy or redistribute either site's data.

MIT licensed; see [LICENSE](LICENSE).
