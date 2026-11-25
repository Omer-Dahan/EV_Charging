# Offline map tiles for Israel

Replaces the app/WebApp's direct calls to `tile.openstreetmap.org` with a self-hosted,
offline-capable tileset for Israel. Pipeline: fetch raw PNGs, pack them into MBTiles,
convert to a PMTiles archive, publish it as a GitHub release asset.

## Why

OSM's tile usage policy explicitly forbids "heavy use (e.g. distributing an app that
uses tiles from openstreetmap.org)". Shipping an app that hits `tile.openstreetmap.org`
directly violates that policy and risks the tile server blocking the app's traffic.
The fix is to bake a local tileset covering only Israel into the app/site so there is
zero runtime dependency on any tile provider.

## What `fetch_tiles.py` does

Downloads OSM raster tiles for the Israel bounding box (lat 29.30-33.40,
lng 34.20-35.95) at zoom levels 6-13 into `tools/tiles/raw/{z}/{x}/{y}.png`.

- **stdlib only** - no dependencies to install.
- **Identified User-Agent** on every request: `EVChargingIsrael/1.0 (https://github.com/Omer-Dahan/EV_Charging)`.
- **Rate limited** to `--rate` requests/second (default 2), sequential (no parallel
  connections) - this is a polite one-time bulk fetch, not scraping.
- **Resumable**: tiles already present on disk (valid PNG header) are skipped, so a
  killed/interrupted run can just be restarted.
- **Retries with backoff** (up to 4 attempts) on network errors; 429/503 responses
  wait longer (honoring `Retry-After` when present) before retrying.
- **Validates output**: checks HTTP status and the PNG magic bytes before accepting
  a tile; corrupt/empty responses are treated as failures, not written to disk.
- **Progress reporting** every ~200 tiles to stdout and to `tools/tiles/fetch.log`,
  including an ETA.
- Failed tiles (after exhausting retries) are listed in the log at the end.

## Usage

```bash
# See exactly how many tiles would be downloaded, per zoom, with no network calls
python3 tools/tiles/fetch_tiles.py --dry-run

# Real run (takes ~50 minutes at the default rate) - always background it,
# the process must survive the calling shell/session exiting
nohup python3 tools/tiles/fetch_tiles.py > tools/tiles/fetch-nohup.log 2>&1 &
```

CLI flags: `--zoom-min` (default 6), `--zoom-max` (default 13, capped - this script
refuses anything above 13 since z14+ turns ~6K tiles into 70K+), `--out` (default
`tools/tiles/raw`), `--rate` (requests/second, default 2), `--dry-run`.

## OSM policy constraints this tool respects

- Identified User-Agent on every request.
- Max ~2 requests/second, single connection at a time.
- One-time bulk download for offline packaging, not a live proxy or ongoing scrape.
- No use of any paid tile provider API to route around this - the whole point is to
  own the tiles outright once downloaded.

See https://operations.osmfoundation.org/policies/tiles/ for the full policy.

## Packaging: `build_pmtiles.py`

Packs `tools/tiles/raw/{z}/{x}/{y}.png` into `tools/tiles/israel-z6-13.mbtiles`
(stdlib `sqlite3`, XYZ rows flipped to TMS as MBTiles requires). Flags: `--raw-dir`,
`--minzoom` (6), `--maxzoom` (13), plus an output path option (see `--help`).
The MBTiles file is then converted to `israel-z6-13.pmtiles` (~61 MB) with an external
PMTiles converter; that conversion step is not scripted in this repo.

## Publishing

The PMTiles archive is published as the asset of the GitHub release
`tiles-z6-13-v1`. The raw tiles, `.mbtiles`, `.pmtiles` and logs are git-ignored.

## CORS limitation (important)

GitHub release assets are served without an `Access-Control-Allow-Origin` header, so
a browser cannot read them: `pmtiles.getHeader()` always fails in the WebApp. The
release asset is therefore usable only by the native app. The WebApp integration is
parked, not committed, in `/home/vm/hermes-briefs/ev-bot-webapp-pmtiles.patch`
(a diff of `webapp/app.js` and `webapp/index.html`). It stays blocked until the
archive is hosted somewhere that sends CORS headers.
