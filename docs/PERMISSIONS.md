# Price sources

The app does **not** fetch price data from either site. It only opens a normal
browser link when the user clicks a button.

## MesoWatch

- **No public API.**
- **Does not share its data.**
- **Do not copy it.** Do not scrape, crawl, download, mirror, store its table or
  build a dataset from it. MesoWatch's terms explicitly forbid automated
  collection and building an app/product from its data.
- This app does not ask for access and does not implement a MesoWatch provider.
- Clicking **Open MesoWatch** only opens:

  `https://meso.watch/?q=<item name>`

  in the user's browser. The app never reads the page or saves its contents.
- Manual prices in the app are the user's own notes. They are not a copy of
  MesoWatch's data and stay on the user's computer.

## Cozy Market

- The public overview endpoints work, but item search/detail/sightings require a
  browser pass (Cloudflare Turnstile): `401 {"error":"pass needed: open the site
  in a browser"}`.
- The app does not bypass that gate and does not fetch item data.
- Clicking **Open Cozy** only opens:

  `https://cozy.markets/items?q=<item name>`

  in the user's browser.
- If Cozy Market ever publishes an official third-party API, it can be added
  behind the `PriceProvider` interface after reading its terms.

## What the app does instead

1. **Manual price notes** — the user types what they found (or their own sale
   data) into **Set price…**. Stored only in:

   `~/Library/Application Support/MapleShopPriceHelper/prices.json`

2. **Browser links** — the user checks the live site themselves.

3. **Future, only with permission** — an authorized API or a CSV of the user's
   own notes. No site datasets.

## Do not

- Do not add a scraper, headless browser, Turnstile bypass, or proxy for either
  site.
- Do not add bundled/exported MesoWatch price tables.
- Do not ship a provider that silently reads a site.
