# avlib

**Private adult video library**: scraper + WebDAV scanner + Web service. LAN deployment on rk3528, with active development in WSL on Windows.

## Snapshot (2026-07-22)

| Component | State |
|---|---|
| Deploy | WSL · `node src/server.js`. systemd unit exists at `bin/avlib.service` but **not loaded** (`sudo systemctl status avlib` → "could not be found"). Run via `bin/avlib-start.sh` instead. |
| Address | `http://0.0.0.0:8123` · host `0.0.0.0`, port `8123` (no auth — `auth.password` empty in `config.json`) |
| WebDAV | `http://localhost:21998/dav` · account `cd2adult` (the `/迅雷云盘/ABV/JP` mount on local CD2 instance) |
| DB | SQLite WAL · `data/avlib.db` · **NEW: 2 tables (`movies`, `videos`)** since 2026-07-22 refactor (was 4: `movies`/`movie_parts`/`moov_cache`/`head_cache`) |
| Schema migration | **2026-07-22** — `movies` / `videos` split, multi-part playback via API-layer concat (no `video_parts` table). No migration script: user wiped DB + re-scraped from scratch. |
| Disk | `data/covers/` 4.3 MB · `data/avlib.db*` ~1 MB. **No `data/head/` or `data/moov/`** (orphans cleared 2026-07-22 — see "Dead cache cleanup" below). |
| scrape_status | run `npm run scan` to populate. Default is `pending` until scraper hits Recombee. |
| Node | >= 20 required (`node:sqlite` built-in, npm `webdav` ^5.8.0 only dep). Use `/home/buumi/n/bin/node` (n-managed 24.x). |

---

## Architecture

```
avlib/
├── src/
│   ├── server.js        # HTTP entry. routes, WebDAV client, multi-part Range proxy, cover cache, scan child-process
│   ├── config.js        # loadConfig('./config.json') + env overrides (WEBDAV_USERNAME / WEBDAV_PASSWORD / WEBDAV_BASE_URL take precedence; empty env falls back to JSON)
│   ├── db.js            # SQLite + schema. movies + videos tables. (was: movies + movie_parts + moov_cache + head_cache)
│   ├── probe.js         # ffprobe wrapper. 15s timeout (deliberate fast-fail — see Known hacks).
│   ├── scanner.js       # WebDAV filename parser + grouper. PURE: no DB / disk writes.
│   ├── scan.js          # CLI orchestrator: scan → scrape → probe. --limit / --rescan / --scan-only / --probe-only / --variant-set.
│   ├── scraper/
│   │   ├── missav.js    # Recombee metadata (POST + HMAC-SHA1) + fourhoi CDN cover. Public token embedded.
│   │   └── cli.js       # `node src/scraper/cli.js ABP-001 [--save-cover[=dir]]`. JSON to stdout.
│   ├── web/             # Browser frontend (no framework; plain JS + CSS)
│   │   ├── app.js       # SPA: browse / search / detail / play / scan-poll. variant tabs in detail+player.
│   │   ├── review-queue.html  # batch tag editor for multi-file / conflict cases.
│   │   ├── index.html, login.html
│   │   ├── style.css
│   │   ├── plyr.css + plyr.polyfilled.js  # Plyr v3.8.4 — replaced native <video controls>. Mobile touch-drag scrubbing on progress bar.
│
├── bin/
│   ├── avlib.service        # systemd unit (Type=simple, Restart=on-failure). NOT active.
│   └── avlib-start.sh       # manual WSL launcher — cd's to repo root, sets n-managed PATH, exec node.
│
├── data/                  # runtime. gitignored.
│   ├── avlib.db            # SQLite main db
│   ├── avlib.db-wal, -shm  # WAL mode files (live)
│   └── covers/<code>.jpg   # cover cache (fourhoi CDN). All lowercased codes.
│   # NB (2026-07-22): data/head/ and data/moov/ removed — see "Dead cache cleanup".
│
├── mdlibs/                # reference data: JAV top-250 snapshot (2023-09-11 from 2TimesMeta/Javdb-Top250)
│                          # 22 .md files, each ~1002 lines. {fc2,readme,uncensored,western,censored,all} +
│                          # per-year 2008.md..2023.md. Format: Ranking / Tag(=code) / Date / Title.
│
├── config.json            # live config (plaintext credentials — store elsewhere for prod)
├── config.example.json    # field template
├── package.json           # ESM, Node>=20, only dep = `webdav`
│                          # scripts: start / scan / scan:dry / scrape
└── ~50 .py scripts at root  # experimental iteration trace — see "Tooling scripts" below
```

---

## Quick start

```bash
# 0. install deps + configure
npm install
cp config.example.json config.json   # then edit webdav.{username,password}

# 1. launch (foreground, manual — current convention)
./bin/avlib-start.sh
# → http://localhost:8123

# 2. or via npm
npm start

# 3. one-shot scrape a code
npm run scrape -- ABP-001 --save-cover=./data/covers

# 4. full WebDAV scan (scanner → scrape (limit N) → probe)
npm run scan -- --limit 50     # scan + scrape up to 50 new codes
npm run scan:dry               # list what's on WebDAV without touching db

# 5. probe-only refill tech metadata
npm run scan -- --probe-only   # fills v_codec / width / etc. on already-scraped rows

# 6. tag a video (debug helper; UI does it via PATCH)
npm run scan -- --variant-set 92=leak
```

Browse UI:
- `/` — poster wall + filters + search + variant-tabbed detail + player
- `/review-queue.html` — batch variant editor (only movies with >1 video / conflict)

Stop: `Ctrl-C` (or `pkill -f 'node src/server.js'`).

**systemd route (intended for RK, not currently loaded on WSL):**

```bash
sudo cp bin/avlib.service /etc/systemd/system/avlib.service
sudo systemctl daemon-reload
sudo systemctl enable --now avlib
sudo journalctl -fu avlib
```

The unit runs Node in foreground and restarts on failure (RestartSec=5). It depends on `network-online.target`. No env-vars are read — config still comes from `config.json` next to the WorkingDirectory.

---

## Config

`config.json` (current live values):

```json
{
  "webdav": { "baseUrl": "http://localhost:21998/dav", "username": "cd2adult", "password": "xdxis1234" },
  "db":     { "path": "./data/avlib.db" },
  "scrape": { "rateLimitMs": 300 }
}
```

Fields consumed (`config.js` is a one-liner — no defaults merged there; server.js applies defaults):

| Key | Default | Notes |
|---|---|---|
| `webdav.baseUrl`      | (required) | e.g. `http://localhost:21998/dav` |
| `webdav.username`     | (required) | |
| `webdav.password`     | (required) | |
| `db.path`             | (required) | resolved relative to process CWD |
| `scrape.rateLimitMs`  | `300`      | sleep between Recombee scrapes (lower → louder) |
| `auth.password`       | (empty)    | non-empty enables cookie auth on `/login` (currently off) |
| `server.port`         | `8123`     | CLI override: `--port <N>` |
| `server.host`         | `0.0.0.0`  | CLI override: `--host <addr>` |

⚠️ **Security:** `config.json` contains plaintext creds. For RK deployment move to env-vars / systemd `LoadCredential=` and read in `config.js`. Currently `auth.password` is empty so anyone on the LAN can reach the UI.

---

## HTTP API

| Route | Behavior |
|---|---|
| `GET /` + static | serves `src/web/` (`/` → `index.html`) |
| `GET /review-queue.html` | batch variant editor for multi-file / conflict cases |
| `GET /login` | `login.html` (only if `auth.password` set) |
| `POST /api/login` / `/api/logout` | cookie auth (`avlib_auth` HttpOnly) |
| `POST /api/scan` | forks `src/scan.js`; `202 Accepted` or `409` if already running |
| `GET  /api/scan/status` | in-flight state + 200-line log ring buffer + parsed counts |
| `GET  /api/movies` | paginated + filtered list (`maker / genre / series / actress / year / zh_subtitle / uncensored`); sort `added | released | title`; default `added`; page=24 |
| `GET  /api/search?q=&limit=40` | by code / titles / actress |
| `GET  /api/facets` | counts per filter bucket |
| `GET  /api/movies/:code` | full meta + `videos[]` (one row per file, grouped by variant priority) |
| `GET  /api/videos` | list all videos; filters: `?movie_code=&variant=&presence=` |
| `GET  /api/videos/:id` | single video (full row incl probe data) |
| `PATCH /api/videos/:id` | body `{variant?, part_label?}` — UI tag editor |
| `GET  /api/review-queue` | movies with >1 video or any conflict_reason |
| `GET  /api/cover/:code` | cached or fetched fourhoi cover JPG (proxies on miss) |
| `GET  /api/stream/:code[?variant=&part=]` | WebDAV Range proxy (`mp4 / mkv / webm / mov / avi / ts / m2ts / mts / wmv / flv / mpg / mpeg / rmvb / rm / iso`). Multi-part: no Range → 200 concatenated; Range inside one part → 206 with translated Content-Range; Range crossing parts → 416. `?variant=` picks variant (default = highest priority); `?part=` legacy single-part playback. Keep-alive Agent (`maxSockets=32`, `keepAliveMsecs=30000`). |
| `GET  /api/play/:code[?variant=]` | returns `{mode, v_codec, a_codec, container, variant, variants[], part, partCount}` — `direct` / `unsupported` / `notfound` |
| `GET  /api/playlist/:code.m3u[?variant=]` | M3U pointing at `/api/stream/:code?variant=&part=N` for VLC / mpv / IINA fallback |

Internal-only:

| Route | Caller | Effect |
|---|---|---|
| `POST /api/internal/probe/:videoId` | UI "⚙" button | runs ffprobe on one video (15s timeout), updates the row |

---

## Database schema (since 2026-07-22)

SQLite (`data/avlib.db`), WAL mode, lazy-migrated.

### `movies` (PK: `code`) — scrape metadata + provenance

- **titles**: `title`, `title_zh`, `title_cn`, `title_en`
- **lists as JSON arrays**: `actresses`, `actors`, `directors`, `labels`, `markers`, `genres`, `series`, `tags`
- **flags**: `is_uncensored_leak` (column `has_chinese_subtitle` / `has_english_subtitle` deprecated 2026-07-22, kept for compat but always 0 and never read)
- **time**: `released_at` (ms), `released_date` (str), `duration_sec`
- **diag**: `scrape_status` (`pending | scraped | unmatched | error`), `scrape_error`, `scrape_fetched_at`, `scrape_added_at`, `scrape_ms`, `scrape_http`, `scrape_etag`, `scrape_url`, `scrape_version`, `cover_url`, `raw_json`
- **derived**: `video_count` (COUNT(videos WHERE movie_code=), kept in sync by `upsertVideo`)

indices: `scrape_status`, `scrape_added_at`, `released_at`.

### `videos` (PK: synthetic `id`) — 1 row per file

- **identity**: `webdav_path` (UNIQUE — re-scans update path/size without touching variant/probe)
- **link**: `movie_code` REFERENCES `movies(code)` ON DELETE SET NULL
- **variant / part**: `variant` (TEXT NOT NULL DEFAULT ''), `part_index` (1-based, parsed from filename), `part_label` (parsed `-A` / `-cd1` / `上` etc, or NULL), `conflict_reason` (when UNIQUE collision blocks the row)
- **file metadata**: `filename`, `container`, `size_bytes`, `mtime_ms`
- **probe metadata**: `probe_status` (`pending | probed | failed`), `probed_at`, `probe_ms`, `v_codec`, `a_codec`, `width`, `height`, `fps`, `duration_real`, `video_bitrate`, `video_profile`, `audio_tracks`, `subtitle_tracks` (last 2 are JSON arrays)
- **lifecycle**: `presence` (`present` | …), `created_at`, `updated_at`
- **UNIQUE**: `(movie_code, variant, part_index)` — same playback slot can't have two files; collision → row skipped, `conflict_reason` set for review queue

indices: `movie_code`, `probe_status`, `presence`.

### Variant priority (used in all "default" queries)

`censored` (0) → `leak` (1) → `''` / untagged (2) → other custom (3). The first video by this ordering defines the default variant for stream/play/playlist when `?variant=` is omitted. **Variant is user-driven; the scraper never auto-detects from filename.**

### Multi-part playback

No `video_parts` table — multi-part is **N rows in `videos`** for the same `(movie_code, variant)` with different `part_index`. The API layer (`src/server.js` `streamMany()`) computes a byte-offset table and:
- No Range header → 200 OK, pipes all parts in `part_index` order
- Range inside one part → 206 with translated `Content-Range` (global offset)
- Range crossing parts → 416 Range Not Satisfiable (TODO stitch via multi-fetch)

---

## Run modes

```bash
# full scan — scanner.js picks up new files, missav scrapes them, ffprobe fills tech fields
node src/scan.js [--limit N] [--rescan] [--scan-only] [--probe-only] [--variant-set <id>=<variant>]

#  --limit        : max NEW scrapes this run (existing rows just get touched)
#  --rescan       : re-scrape already-scraped codes (force re-pull from Recombee)
#  --scan-only    : walk WebDAV + print, no scrape (lists multi-part codes + files)
#  --probe-only   : skip scan/scrape, fill probe fields where probe_status='pending'
#  --variant-set  : debug helper — `node src/scan.js --variant-set 92=leak` to tag a video

# manual single-code scrape
node src/scraper/cli.js ABP-001                  # metadata JSON
node src/scraper/cli.js ABP-001 --save-cover     # metadata + ./ABP-001.jpg
node src/scraper/cli.js VDD-092 --save-cover ./covers
```

---

## Roadmap (actual status, 2026-07-22)

- [x] **P0 — Scraper module** · `src/scraper/{missav,cli}.js`. Recombee (no CF) + fourhoi CDN.
- [x] **P1 — WebDAV scanner** · `src/scanner.js` parses filenames + detects multi-parts (CN 上/下, A/B, CD1/2, 前/后篇); `src/db.js` SQLite + **two-table schema (`movies` / `videos`)**; `src/scan.js` orchestrator with `--limit / --rescan / --scan-only / --probe-only / --variant-set`.
- [x] **P2 — Web API + UI** · server routes + `src/web/{app.js,index.html,style.css,review-queue.html}`. No router framework (URL stays at `/`, all state in `app.js`'s `state` object). Detail/player UI shows variant tabs.
- [x] **P3 — Stream proxy** · `/api/stream/:code` (single-part Range pass-through, keep-alive Agent) + **multi-part concat (`streamMany`) with byte-offset Range translation**; `/api/play/:code` (`direct / unsupported / notfound` decision); `/api/playlist/:code.m3u` (VLC/mpv, variant-aware). Browser `<video>` plays native mp4; mkv → m3u fallback. HLS (fmp4 remux) is a P6 TODO.
- [x] **P4 — Facets, cover cache, auth gate, systemd unit** · `/api/facets`; `data/covers/`; cookie auth implemented but disabled; `bin/avlib.service` written but **not loaded** on WSL (manual `bin/avlib-start.sh` is current convention).
- [x] **P5 — Variant system** · user-driven `videos.variant` (defaults: `censored` / `leak` / `''`), no auto-detect; UI tag editor at `/review-queue.html`; PATCH `/api/videos/:id`. variant priority order: `censored > leak > untagged > others`.
- [ ] **P6 — ffmpeg remux mkv→fMP4, token auto-refresh, stats**. Multi-part Range across boundaries (cross-part stitching) is also a P6 TODO (currently returns 416).

---

## Known hacks / limitations

1. **`probe.js` 15s timeout is deliberate** (HACK): mkv files with moov-at-tail over slow WebDAV can take minutes. We chose "leave fields null" over stalling the batch. Re-test periodically — `ffprobe` is fast for mp4 faststart files.
2. **`missav.js` PUBLIC_TOKEN is hardcoded.** If Recombee returns 401/403, re-extract the long base64ish string from `missav.ws`'s `frontend_sign` JS (search `recombee` in the page source) and patch `PUBLIC_TOKEN` at top of `missav.js`. No auto-refresh.
3. **Cross-part Range returns 416.** `/api/stream/:code?variant=` on a multi-part movie accepts Range only when both endpoints fall in the same part. Cross-part stitching (multi-fetch + body splice) is a P6 TODO; for now use the no-Range full stream or `.m3u`.
4. **`scanner.js` `parsePartLabel()`** token order: single A-D letter > 1-2 digit number > `上/下/前/后/前篇/后篇/上集/下集/正片` > `cd/disc/disk/dvd/part/pt` + digits. Unusual labels (`上上`, `1a`) return null and fall back to `part_index=1` (single-file default). If a real multi-part file uses an unrecognized token it'll silently be treated as a single-file and may collide with another part via the `UNIQUE(movie_code, variant, part_index)` constraint — the second file lands in `conflict_reason` for review queue.
5. **No auth on the UI.** Cookie auth is implemented (`POST /api/login`) but `auth.password` is empty, so anyone on the LAN gets in. Set it to a real password before exposing beyond localhost.
6. **`config.json` plaintext creds.** Move to systemd `LoadCredential=` / env-vars before deploying to RK.
7. **Default variant = priority winner, not "most complete."** If you tag only part B of a 2-part movie as `leak`, the default `?variant=leak` stream plays only part B. Use the UI (`/review-queue.html`) to tag both parts together.

---

## Tooling scripts

All one-shot debugging / patching scripts (the avop-172 moov-prime bug arc) were deleted 2026-07-24. The streaming pipeline concerns they addressed are now baked into `src/server.js`. If you need to revisit that work, the memory note `2026-07-22-avop172-moov-bug` has the diagnosis.

---

## Reference data: `mdlibs/`

Snapshot of `2TimesMeta/Javdb-Top250` from 2023-09-11. 22 markdown files, each ~1002 lines:

- `readme.md` — landing page (year/category index)
- `all.md` / `censored.md` / `uncensored.md` / `western.md` / `fc2.md` — ranked lists
- `2008.md` … `2023.md` — per-year ranked lists

Each entry is a 3-block stanza: `Ranking:` / `Tag: <code>` (matching key, e.g. `ABP-984`, `LAFBD-41`, `FC2-3175924`) / `Release Date:` / `Title:` link to `javdb521.com/v/<id>`. Use `Tag` as the join key against `scanner.js` codes.

⚠ Pinned to 2023-09-11; if you want fresher top-250 lists, re-clone the upstream repo.

---

## File-naming conventions (cache files)

| Path | Naming | Example | Status |
|---|---|---|---|
| `data/covers/` | `<code-lowercase>.jpg` | `dpmx-001.jpg` | **live** — read by `/api/cover/:code`, lazily refilled from fourhoi CDN |
| `data/head/` | `<code-lowercase>__<part>.head` | `dpmx-007__.head` | **DELETED 2026-07-22** (see Dead cache cleanup) |
| `data/moov/` | `<code-lowercase>__<part>.moov` | `achj-040__.moov` | **DELETED 2026-07-22** (see Dead cache cleanup) |

Multi-part uses `__A` / `__B` / etc. for the part label. Single-part files use just `<code>.{head,moov}` (the `__` separator is present but the part token is empty). Existing files show `achj-040__.head` style with literal empty segment.

## Dead cache cleanup (2026-07-22, pre-refactor)

`data/head/` and `data/moov/` plus the `head_cache` and `moov_cache` SQLite tables were **orphaned**: no current code path reads or writes them. They were leftovers from an earlier `server.js` revision that registered `/api/internal/prime-moov` to write mp4 faststart priming caches. The route was eventually dropped; the streaming path now just forwards `Range` headers verbatim to WebDAV (single-part path) or concatenates multi-part videos via `streamMany` (offset table + sequential pipe).

The 2026-07-22 schema refactor **dropped** `head_cache`, `moov_cache`, `movie_parts` tables entirely (no more `db.invalidateMoovCache()` etc.). `data/head/` and `data/moov/` directories were already cleared earlier the same day.

The `moov_size` field for `AVOP-172` was also wrongly recorded as **2,400,989,856 bytes** (= the whole file) instead of the actual moov atom size — a separate latent bug, see memory `avop-172-moov-prime-bug`. Now moot after refactor (no moov cache at all).

---

## Tips

- If you wiped the `data/` directory and want to rebuild: launch server, `npm run scan:dry` to see WebDAV contents, then `npm run scan -- --limit 500` for first big pass. Probe fill happens automatically (each video gets ffprobe'd, ~15s timeout each).
- After a fresh scan, hit `/review-queue.html` to tag multi-file movies (`leak` vs `censored` vs leave untagged). The default `/api/stream/:code` will play the highest-priority variant.
- `auth.password` empty == open LAN access; set it before opening 8123 on the firewall.
- To watch live scan logs while it's running, tail the page `/api/scan/status` (returns the 200-line ring buffer + parsed `{scraped, unmatched, error, skipped, conflicts, videosTotal}` summary).
