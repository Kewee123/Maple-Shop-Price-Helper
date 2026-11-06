# Price sources

The app does **not** fetch price data from either site. It only opens a normal
browser link when the user clicks a button.

## MesoWatch

- **No public API.**
- **Does not share its data.**
- **Do not copy it.** Do not scrape, crawl, download, mirror, store its table or
  build a dataset from it. MesoWatch's terms explicitly forbid automated
  collection and building an app/product from its data.
- This app does not access MesoWatch data directly. It automates the user's
  local Chrome tab to search for the scanned item.
- Before MesoWatch is opened, the OCR name is checked against the public
  MeowDB MapleStory Classic Item Database A-Z index. The app only uses the
  exact item name returned by that index and does not copy market data.
- Clicking **Search item in MesoWatch** opens:

  `https://meso.watch/`

  in the user's browser. With macOS browser automation permission enabled, it
  fills the client-side search box and clicks the first matching item. Without
  that permission, it copies the OCR-read item name so the user can paste it
  manually. The app never reads or saves market data.
- The **Chrome setup** button activates Chrome and shows the exact
  macOS menu-bar path: `Develop → Allow JavaScript from Apple Events`.
  Chrome does not expose this menu switch through a direct settings URL.

## Cozy Market

- The public overview endpoints work, but item search/detail/sightings require a
  browser pass (Cloudflare Turnstile): `401 {"error":"pass needed: open the site
  in a browser"}`.
- The app does not bypass that gate and does not fetch item data.
- Clicking **Open Cozy** only opens:

  `https://cozy.markets/items`

  and copies the item name to the clipboard so the user can paste it into
  Cozy's own search box. (Cozy's search is client-side; it ignores `?q=`.)
- If Cozy Market ever publishes an official third-party API, it can be
  considered separately after reading its terms.

## What the app does instead

1. **Browser automation** — the app enters the OCR-read item name into the
   user's existing MesoWatch tab and selects the matching result.

2. **Manual fallback** — if browser automation is unavailable, the item name is
   copied so the user can paste it into MesoWatch themselves.

3. **No site data is stored** — prices remain visible only in the user's browser.

## Do not

- Do not add a scraper, headless browser, Turnstile bypass, or proxy for either
  site.
- Do not add bundled/exported MesoWatch price tables.
