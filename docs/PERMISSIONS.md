# Price-source permissions

The screen-reading side is fine: it only reads the user's own screen. The price
data is different. Both sites protect their item data, so the app does not fetch
from them until one of them says yes in writing.

## What the sites currently say

### meso.watch

From <https://meso.watch/terms.html> (updated 2026-10-14):

- No script, crawler or AI system may collect the price table or the data files.
- No direct requests to the site's data files.
- No republishing, resale, mirroring or building an app/product from the data
  without written permission.
- A person may browse the site and quote a small number of prices with a visible
  credit and link.

So: **no scraping, no automatic reads**. Contact: `contact@meso.watch`.

### cozy.markets

The public `api/overview`, `api/board`, `api/streams` and `api/scan-map` endpoints
work, but item search/detail/sightings return:

```json
{"error":"pass needed: open the site in a browser"}
```

The site obtains a short-lived `cozy-pass` through Cloudflare Turnstile. That is
a deliberate bot gate; the prototype does not bypass it. The site links a
Discord and Patreon from its pages; ask there for an approved desktop API or
partner access.

## Draft message — meso.watch

**To:** contact@meso.watch  
**Subject:** Read-only price lookup for a free MapleStory Classic shop helper

> Hi MesoWatch team,
>
> I'm building a free, open-source Mac/Windows companion for MapleStory Classic
> shop owners. It reads the item tooltip on the user's own screen (no clicks or
> key input into the game) and shows a suggested listing price.
>
> I would like to query MesoWatch's sold-price data for the one item the user is
> hovering, read-only. The design is deliberately small:
>
> - one item lookup at a time, initiated by the user hovering an item — no bulk
>   crawling or table copying;
> - a short cache and a rate limit, with a clear User-Agent and contact address;
> - attribution and a link back to meso.watch wherever a price is shown;
> - no republishing, resale, mirroring, AI training or redistribution;
> - no requests to your data files, and no attempt to get around rate limits or
>   bot checks.
>
> If you would rather provide an official API/export or a partner key, that works
> too. Could you tell me whether this is possible and what terms/attribution you
> would require? I can send the prototype and change it to whatever you are
> comfortable with.
>
> Thanks,
> [name]

## Draft message — cozy.markets

**To:** the Cozy Market Discord / contact listed on the site  
**Subject:** Approved desktop API access for a free shop price helper

> Hi Cozy Market team,
>
> I'm building a free, open-source Mac/Windows companion for MapleStory Classic
> shop owners. It reads the item tooltip on the user's own screen and shows a
> suggested listing price.
>
> I saw that the item endpoints need a `cozy-pass` from the site and I do not want
> to bypass that gate or pretend to be a browser. Is there an approved way for a
> desktop app to do read-only item lookups — a partner API/key, a documented
> endpoint, or a periodic export?
>
> The app would do one lookup at a time for the item the user is hovering, cache
> briefly, rate-limit, send a clear User-Agent/contact, show attribution and a
> link back, and never republish or redistribute the data. No bulk copying and no
> AI training.
>
> If that is not available, I'll keep the app on manual prices and links only.
> Could you point me to the right person/terms?
>
> Thanks,
> [name]

## Interim behaviour (this repo)

- `ManualPriceProvider` stores prices the user types, on their computer.
- `MesoWatchProvider` and `CozyMarketProvider` are deliberately disabled; they
  raise `SourceUnavailable` with the reason.
- The UI only opens normal browser search URLs; it never fetches them.
- If permission is granted later, implement the two providers behind the same
  interface, with a small cache and rate limit.
