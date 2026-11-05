# mesos.watch — API Reference (extracted from HAR)

Sources:
- `~/mesos.watch_Archive [26-11-03 19-15-06].har` (34 entries — early browse session)
- `~/mesos.watch_Archive [26-11-03 19-22-49].har` (309 entries — full session; **superset**)

Generated: 2026-11-04
Purpose: Provide subagents a precise map of the live API surface so they can investigate the reported issue without re-deriving the endpoints.

---

## 1. Capture metadata

| Field | Value |
|---|---|
| Tool | Firefox 159.0 |
| Page title | `https://mesos.watch/` |
| Page started (new) | `2026-11-03T19:21:10.465-08:00` |
| Total entries (new) | 309 (`GET` 306, `POST` 3) |
| API host | `https://api.mesos.watch` (separate origin from site `https://mesos.watch`) |
| Site host | `https://mesos.watch` (HTML/JS/CSS/assets) |

### Hosts observed in the new capture

| Host | Count | Role |
|---|---|---|
| `mesos.watch` | 191 | Site HTML, JS modules, CSS, art, 3D models |
| `api.mesos.watch` | 93 | JSON API + owner avatars |
| `cdn.jsdelivr.net` | 15 | three.js 0.160.0 modules |
| `challenges.cloudflare.com` | 7 | Cloudflare Turnstile (bot challenge) |
| `brunhild.challenges.cloudflare.com` | 1 | Turnstile telemetry |
| `fonts.googleapis.com` | 1 | Google Fonts (Manrope, Outfit) |

---

## 2. Authentication, session & bot protection

The site uses an anonymous session cookie (`mw_s`) that is issued only after a **Cloudflare Turnstile** proof-of-human check.

### `POST /session` — create session (the auth bootstrap)

Request 1 (no body of note): `{}` → **401**
```json
{ "error": "challenge", "sitekey": "0x4AAAAAAFsxiakGb0_JOMLV" }
```
- The client receives a Turnstile `sitekey`, renders the widget, and the user/browser solves it.

Request 2: `{ "turnstile": "<turnstile token>" }` → **200**
```json
{ "ok": true, "session": true }
```
- Response sets the session cookie:
  - `Set-Cookie: mw_s=v2...; Path=/; Max-Age=1800; HttpOnly; Secure; SameSite=...`
  - `mw_s` is `HttpOnly`, TTL **1800s** (30 min), session-scoped.
- The same `mw_s` cookie is then sent on every subsequent API request.

### Other auth endpoints

| Endpoint | Response | Notes |
|---|---|---|
| `GET /auth/config` | `{"discord":true}` | Toggles which login providers are enabled (Discord login enabled). |
| `GET /auth/me` | `{"user":null}` | Current user; `null` = anonymous. |

> No OAuth `Authorization` header appears in this capture. Account login (Discord) is configured but not exercised.

### CORS / security headers (API responses)

- `access-control-allow-origin: https://mesos.watch`
- `access-control-allow-credentials: true`
- `access-control-allow-methods: GET, POST, DELETE, OPTIONS`
- `access-control-allow-headers: Content-Type, Authorization`
- `access-control-max-age: 86400`, `vary: Origin`
- Served behind **Cloudflare** (`server: cloudflare`, `cf-ray`, `nel`/`report-to`).
- `content-security-policy: default-src 'none'; frame-ancestors 'none'`.
- Cached GETs carry `cache-control: public, max-age=14400`, `last-modified`, `cf-cache-status: HIT`, `age`; `POST /session` uses `cache-control: private, no-store`.
- `content-encoding: zstd` observed.

---

## 3. Endpoint inventory (all `https://api.mesos.watch`)

16 unique endpoints. New endpoints (not present in the earlier 19:15 capture) are marked ★.

| # | Method | Endpoint | Query params | Purpose |
|---|---|---|---|---|
| 1 | POST | `/session` ★ | — (body) | Create session; Turnstile challenge → cookie |
| 2 | GET | `/auth/config` ★ | — | Auth provider toggles |
| 3 | GET | `/auth/me` ★ | — | Current user |
| 4 | GET | `/geo` ★ | — | Geo-IP + consent flag |
| 5 | GET | `/notices` ★ | — | Site announcements |
| 6 | GET | `/site-status` | — | Maintenance/status banner |
| 7 | GET | `/channels` | — | Per-channel scanner health + 24h rollups |
| 8 | GET | `/live` | `channel`, `v` | Live store/room dump per channel (versioned polling) |
| 9 | GET | `/browse` | `sort`, `dir`, `item`, `q` | Search/browse stores & listings |
| 10 | GET | `/players` ★ | `q` | Player-name autocomplete |
| 11 | GET | `/item/names` ★ | — | Full item catalog (id → name) |
| 12 | GET | `/item/summary` ★ | `ids` | Bulk item stats for many ids |
| 13 | GET | `/item/trending` | — | Trending items |
| 14 | GET | `/item/{item_id}/sales` | `days` | Sale history for one item |
| 15 | GET | `/item/{item_id}/history` | `days`, `summary` | Aggregate sales stats for one item |
| 16 | GET | `/owner/{store_id}.png` ★ | — | Owner avatar image (often 404) |

`{item_id}` = 7-digit MapleStory item ID (int). `{store_id}` = UUID v4 (hyphenated).

---

## 4. Endpoint detail

### 4.1 `POST /session` ★

See §2. Two-phase: `{}` → 401 challenge, then `{"turnstile":"..."}` → 200 + cookie.

---

### 4.2 `GET /auth/config`, `GET /auth/me`, `GET /geo`, `GET /notices` ★

```json
// /auth/config
{ "discord": true }

// /auth/me
{ "user": null }

// /geo
{ "country": "US", "consent_required": false }

// /notices
{
  "notices": [
    {
      "id": 2,
      "at": 1793322066,
      "title": "We are up and running",
      "body": "Hey!\nWe are up and running. ...",
      "url": "https://discord.gg/jABuFSpBA",
      "tr": null
    },
    { "id": 1, "at": 1793317409, "title": "We are warming up the engines!", "body": "...", "url": null, "tr": null }
  ]
}
```
- `notices[].at` = unix seconds; `url` may be `null`; `tr` appears to be a translation slot (always `null` in capture).

---

### 4.3 `GET /site-status`

```json
{
  "mode": "auto",
  "title": "Maplestory Update",
  "body": "Our scanners will go back online few hours post maintenance.\nYou are welcome to join our discord in the meanwhile.",
  "updated_at": 1793403945
}
```

---

### 4.4 `GET /channels`

```json
{
  "world": "classic",
  "generated_at": 1793762060,
  "sales_24h": 204844,
  "volume_24h": 18629433946,
  "channels": [
    { "channel": 1, "stores": 499, "rooms_scanned": 20, "last_scan_at": 1793761402 },
    { "channel": 2, "stores": 492, "rooms_scanned": 20, "last_scan_at": 1793761271 }
  ]
}
```
- 40 channel objects (1–40). `rooms_scanned` = 20 (all rooms).

---

### 4.5 `GET /live`

Query params: `channel` (int, required), `v` (optional version token = unix seconds).

**Unchanged (200, ~94–96 B):**
```json
{ "world": "classic", "channel": 1, "generated_at": 1793762032, "version": 1793761402, "unchanged": true }
```

**Changed (200, ~67–76 KB):**
```json
{
  "world": "classic",
  "channel": 30,
  "generated_at": 1793762039,
  "version": 1793762002,
  "max_age": 86400,
  "area": { "1": [-488, -445, 1028, 34], "2": [-488, -445, 1028, 34] },
  "rooms": [
    {
      "room": 1,
      "last_scan_at": 1793761639,
      "stores": [
        {
          "id": "5265214a-662f-4887-9c6e-74225d6496fb",
          "shop_id": "14424",
          "kind": "player",
          "owner": "PinkRuntz",
          "title": "2Crit | Scrolls | NX",
          "x": 887, "y": 34,
          "look": { "skin": 0, "ids": [20000, 30020, 1002000, 1040003, 1060001, 1072001, 1332001] },
          "first_seen": 1793547222,
          "last_seen": 1793761617,
          "items_seen_at": 1793758108,
          "items": [
            {
              "slot": 0, "item_id": 1032007, "name": "Emerald Earrings",
              "bundles": 1, "per_bundle": 1, "price": 28999, "unit_price": 28999,
              "stats": { "crit_damage": 2, "mdef": 26, "slots": 5 },
              "listed_at": 1793744923
            }
          ]
        }
      ]
    }
  ]
}
```
- `area`: `room_id -> [x1, y1, x2, y2]` bounding box. Two geometries observed.
- `rooms`: 20 entries. `stats` is a sparse `{stat: value}` map (item-dependent keys).
- Polling loop observed: repeated `GET /live?channel=1&v=1793762368` → `unchanged:true`.

---

### 4.6 `GET /browse`

Query params: `sort` (`seen`|`price`), `dir` (`asc`|`desc`), `item` (item_id), `q` (text search). `type`/`cat` were still **not** exercised.

Three observed modes:

**`mode:"latest"`** (`/browse?sort=seen&dir=desc`) and **`mode:"search"`** (via `item=` or `q=`). Response:
```json
{
  "world": "classic",
  "generated_at": 1793762001,
  "q": "", "item": null, "type": null, "cat": null,
  "sort": "seen", "dir": "desc", "mode": "latest",
  "items": { "1002015": "Black Bandana", "1002016": "Bronze Koif" },
  "stores": { "db00d7d8-...": [11, 7, "player", "BuffHeals", "Random", 1793761997] },
  "total": 2024,
  "truncated": true,
  "fields": ["store_id", "slot", "item_id", "bundles", "per_bundle", "price", "stats", "listed_at"],
  "rows": [ ["db00d7d8-...", 11, 4010001, 72, 1, 369, null, 1793761997] ]
}
```
- `items`: `item_id -> name`.
- `stores`: `store_id -> [channel, room, kind, owner, title, listed_at]` (kind observed: `"player"`).
- `rows` (mapped by `fields`): `[store_id, slot, item_id, bundles, per_bundle, price, stats, listed_at]`.
  - `stats` may be `null`.
- **`q` search** (`/browse?q=emear&sort=seen&dir=desc`) returns `mode:"search"`, `q:"emear"`, `item:null`, `total:0`, empty `items`/`rows`/`stores`, and `fields:null` when nothing matches. (Partial-name search that produced no match here.)

---

### 4.7 `GET /players` ★ (player autocomplete)

Query: `q` (partial name). Response:
```json
{
  "world": "classic",
  "q": "emer",
  "players": [
    ["EmergencyAid", 12, 2, "a5f2ee5e-82ea-4cde-9e78-374aa8737bfe", "REFINED ORE", 1793759735],
    ["Emerlender", 11, 5, "00bd023a-2964-4116-98ef-ff3d9caa40d5", "Earrings", 1793761919]
  ]
}
```
- `players` is an array of positional rows: `[name, channel, room, store_id, store_title, seen_at]`.
- Short queries (`q=eme`, `q=emea`) returned **status 0** = the browser aborted the in-flight request when the user kept typing. Debounce/abort behavior, not an error.

---

### 4.8 `GET /item/names` ★ (item catalog)

No params. Response: `{"world":"classic","items":[[item_id, name], ...]}` — **1492 items**, e.g. `[1002000,"Brown Skullcap"] ... [5680001,"Selective 5-slot Coupon"]`.

---

### 4.9 `GET /item/summary` ★ (bulk item stats)

Query: `ids` = comma-separated item ids. Response:
```json
{
  "world": "classic",
  "generated_at": 1793762451,
  "fields": ["item_id","name","listings","stores","channels","cheapest_unit","cheapest_where","newest_seen_at","typical","sales_30d"],
  "items": [
    [1032007, "Emerald Earrings", 1435, 939, 40, 21999,
     [5, 16, "8c2b23a2-63b1-4316-ac4e-6ec60c8b0f11", "GIida", 1793747352],
     1793762444, 24999, 14573]
  ]
}
```
Row columns (mapped by `fields`):
| idx | field | type | notes |
|---|---|---|---|
| 0 | `item_id` | int | |
| 1 | `name` | string | |
| 2 | `listings` | int | active listings |
| 3 | `stores` | int | distinct stores |
| 4 | `channels` | int | distinct channels |
| 5 | `cheapest_unit` | int | mesos |
| 6 | `cheapest_where` | array | `[channel, room, store_id, owner, listed_at]` |
| 7 | `newest_seen_at` | int | unix seconds |
| 8 | `typical` | int | typical/median price |
| 9 | `sales_30d` | int | 30-day sale count |

---

### 4.10 `GET /item/trending`

```json
{
  "world": "classic",
  "generated_at": 1793761935,
  "window": 86400,
  "items": [
    [1032007, "Emerald Earrings", 8151, 8151, 1587239620, 24999, 23333, 9006, 4759],
    [1082000, "Work Gloves",      6393, 6393, 2493065373, 5999,  3333, 6678, 3028]
  ]
}
```
- Positional rows **without** a `fields` list (columns are undocumented in-band). Inferred per-row order:
  `[item_id, name, <metric>, <metric>, <large counter>, <price hi/median>, <price lo>, <metric>, <metric>]`.
- ⚠️ Column semantics **unconfirmed** — verify against frontend (`app.js`/`market.js`) if trending values are in scope.

---

### 4.11 `GET /item/{item_id}/sales`

Query: `days` (observed `30`). Response:
```json
{
  "world": "classic",
  "item_id": 1032007,
  "name": "Emerald Earrings",
  "days": 30,
  "since": 1791170007,
  "fields": ["sold_at", "unit_price", "quantity", "time_to_sell", "channel", "stats"],
  "truncated": true,
  "sales": [
    [1793761979, 12999, 1, 6612, 38, { "crit_damage": 2, "mdef": 26, "slots": 5 }]
  ]
}
```
- `sales` rows (mapped by `fields`): `[sold_at, unit_price, quantity, time_to_sell, channel, stats]`.
  - `quantity: 0` + `time_to_sell: null` = unsold listing.
- `truncated:true` = capped at 5000 rows.

---

### 4.12 `GET /item/{item_id}/history`

Query: `days` (observed `120`), `summary` (`1`). Response:
```json
{
  "world": "classic", "item_id": 1032007, "name": "Emerald Earrings",
  "days": 120, "since": 1783468800,
  "summary": {
    "volume": 14574, "trades": 14574,
    "median_unit_price": 22222, "median_time_to_sell": 5716,
    "unsold_units": 14659, "sell_through": 0.49854616358225295
  }
}
```
- `median_unit_price` / `median_time_to_sell` may be fractional.

---

### 4.13 `GET /owner/{store_id}.png` ★ (owner avatars)

- Returns `image/png`.
- Pattern: `GET /owner/<uuid>.png`, e.g. `.../owner/32194c95-6d41-4d94-b2a9-f7f9929b5d27.png` → 200.
- ⚠️ **Most return 404** — of ~40 avatar requests, only a handful returned 200 (e.g. `32194c95-...`, `d72e425d-...`, `fbb82fad-...`, `1d5bca52-...`, `78ed13ff-...`, `4afcbbea-...`). Missing avatars may be expected (only some owners have generated images), but the high 404 rate is a candidate debugging lead.

---

## 5. Cross-cutting conventions

- **Envelope**: every JSON response includes `"world":"classic"` and (except `site-status`, `auth/*`, `geo`, `notices`, `owner/*`) a `generated_at` unix-seconds timestamp.
- **Timestamps**: integer Unix epoch **seconds** (`1793761935` → `2026-11-04T03:12:15Z`).
- **IDs**: item_id = int; store_id/shop_id = UUID v4 string; channel/room/slot = int.
- **Positional rows**: `browse.rows`, `sales.sales`, `item/summary.items`, `item/names.items`, `players.players` are positional arrays paired with a `fields` array (except `item/trending` and `item/names`, which omit `fields`).
- **Stats**: sparse `{stat_name: value}`; keys item-dependent (`watk`, `mdef`, `wdef`, `str`, `dex`, `int`, `luk`, `crit_damage`, `slots`, `mp`, …).
- **Caching**: public GETs cached (Cloudflare `HIT`, `max-age=14400`); `POST /session` is `private, no-store`; `content-encoding: zstd`.

---

## 6. Static assets & frontend modules

Site JS modules (reveal frontend feature areas):
`app.js`, `live.js`, `market.js`, `account.js`, `news.js`, `data.js`, `webmcp.js`, `consent.js`, `i18n.js`, `scene3d.js`, `v2.css`, `app.css`.

Assets:
- 3D: `models/web/fm_entrance.glb`, `room_henesys.glb`, `room_perion.glb`; `art/fmmaps.json`; `art/equip_jobs.json`.
- Art: `art/bg_fm.webp`, `bg_henesys.webp`, `bg_perion.webp`; `art/npc_*.webp`; `art/icons/<item_id>.png` (per-item icon); `art/owners/oNN.png` (owner avatar placeholder atlas).

Third-party:
- three.js `0.160.0` via jsDelivr (GLTFLoader, EffectComposer, UnrealBloomPass, etc.).
- Cloudflare Turnstile (`challenges.cloudflare.com`).
- Google Fonts (Manrope, Outfit).

---

## 7. Observations & debugging leads

1. **Bot challenge gates the whole API.** `POST /session` must succeed (Turnstile) before other calls work; the `mw_s` cookie expires every **30 min** and is `HttpOnly`. If the site intermittently fails, first suspect an expired/absent session cookie or a failed Turnstile solve.
2. **`/players` aborts on rapid typing** — `q=eme`, `q=emea` returned status 0 (aborted), while `q=emear`/`emer`/`emerald` returned 200. This is normal autocomplete debouncing, not a server error.
3. **`/owner/{store_id}.png` 404s heavily.** If the reported bug is "missing owner avatars", this is the endpoint; note that many 404s may be legitimately absent images vs. a backend generation gap.
4. **`/browse?q=` text search** was exercised (`q=emear`) and returned an empty `mode:"search"` result. Confirm whether `q` is meant to match store titles, owner names, or item names — and whether empty-results-for-valid-queries is the bug.
5. **`/live` version-token polling** (`v=<unix seconds>` → `unchanged:true`) is where stale-live-data symptoms would manifest.
6. **`/item/trending` has no field labels** — verify column meanings in frontend JS before trusting values.
7. **`type` and `cat` filters on `/browse`** remain unobserved even in the new capture — if filtering is broken, these params are untested ground.
8. **`/auth/config` shows `discord:true`** — Discord login exists but was not used in either capture; account-gated features (`/auth/me` → `user:null`) were never exercised.
