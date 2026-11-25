#!/usr/bin/env python3
"""Download OSM raster tiles for Israel for offline packaging into PMTiles.

One-shot, polite bulk download from tile.openstreetmap.org. Respects the OSM
tile usage policy: identified User-Agent, capped request rate, no parallel
hammering. See tools/tiles/README.md for background and usage.
"""

import argparse
import math
import os
import sys
import time
import urllib.error
import urllib.request

# Israel bounding box - must match the app's maxBounds.
LAT_MIN = 29.30
LAT_MAX = 33.40
LNG_MIN = 34.20
LNG_MAX = 35.95

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "EVChargingIsrael/1.0 (https://github.com/Omer-Dahan/EV_Charging)"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

MAX_RETRIES = 4
BASE_BACKOFF = 2.0  # seconds, doubled each retry
PROGRESS_EVERY = 200


def deg2num(lat_deg, lng_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lng_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    max_index = int(n) - 1
    return max(0, min(xtile, max_index)), max(0, min(ytile, max_index))


def tile_range(zoom):
    """Return (x_min, x_max, y_min, y_max) inclusive for the Israel bbox at this zoom."""
    x_min, _ = deg2num(LAT_MAX, LNG_MIN, zoom)
    x_max, _ = deg2num(LAT_MAX, LNG_MAX, zoom)
    _, y_min = deg2num(LAT_MAX, LNG_MIN, zoom)
    _, y_max = deg2num(LAT_MIN, LNG_MIN, zoom)
    return x_min, x_max, y_min, y_max


def iter_tiles(zoom_min, zoom_max):
    for z in range(zoom_min, zoom_max + 1):
        x_min, x_max, y_min, y_max = tile_range(z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                yield z, x, y


def count_tiles(zoom_min, zoom_max):
    per_zoom = {}
    total = 0
    for z in range(zoom_min, zoom_max + 1):
        x_min, x_max, y_min, y_max = tile_range(z)
        count = (x_max - x_min + 1) * (y_max - y_min + 1)
        per_zoom[z] = count
        total += count
    return per_zoom, total


class Logger:
    def __init__(self, log_path):
        self._fh = open(log_path, "a", buffering=1, encoding="utf-8")

    def log(self, msg):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        self._fh.write(line + "\n")

    def close(self):
        self._fh.close()


def is_valid_png(data):
    return len(data) > 8 and data.startswith(PNG_MAGIC)


def fetch_tile(z, x, y):
    """Return (ok, data_or_none, status_note). Handles retries/backoff internally."""
    url = TILE_URL.format(z=z, x=x, y=y)
    backoff = BASE_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                if is_valid_png(data):
                    return True, data, "ok"
                return False, None, "invalid-png-body"
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                retry_after = e.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff * 4
                time.sleep(wait)
                backoff *= 2
                continue
            if 400 <= e.code < 500:
                return False, None, f"http-{e.code}"
            time.sleep(backoff)
            backoff *= 2
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(backoff)
            backoff *= 2
    return False, None, "retries-exhausted"


def main():
    parser = argparse.ArgumentParser(description="Download OSM tiles for Israel (offline packaging pipeline).")
    parser.add_argument("--zoom-min", type=int, default=6)
    parser.add_argument("--zoom-max", type=int, default=13)
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "raw"))
    parser.add_argument("--rate", type=float, default=2.0, help="max requests per second")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.zoom_max > 13:
        print("Refusing to fetch zoom > 13 (tile count explodes; not part of this task's scope).", file=sys.stderr)
        sys.exit(1)

    per_zoom, total = count_tiles(args.zoom_min, args.zoom_max)

    if args.dry_run:
        print(f"Dry run: zoom {args.zoom_min}-{args.zoom_max}, bbox lat [{LAT_MIN},{LAT_MAX}] lng [{LNG_MIN},{LNG_MAX}]")
        for z, count in per_zoom.items():
            print(f"  z{z}: {count} tiles")
        print(f"Total: {total} tiles")
        eta_min = total / args.rate / 60
        print(f"Estimated time at {args.rate} req/s: ~{eta_min:.1f} minutes")
        return

    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(os.path.dirname(args.out), "fetch.log")
    logger = Logger(log_path)

    min_interval = 1.0 / args.rate
    downloaded = 0
    skipped = 0
    failed = []
    start_time = time.time()
    last_request_time = 0.0
    processed = 0

    logger.log(f"Starting fetch: {total} tiles, zoom {args.zoom_min}-{args.zoom_max}, rate={args.rate}/s")

    for z, x, y in iter_tiles(args.zoom_min, args.zoom_max):
        out_dir = os.path.join(args.out, str(z), str(x))
        out_path = os.path.join(out_dir, f"{y}.png")

        if os.path.exists(out_path) and os.path.getsize(out_path) > 8:
            with open(out_path, "rb") as f:
                head = f.read(8)
            if head == PNG_MAGIC:
                skipped += 1
                processed += 1
                continue

        elapsed_since_last = time.time() - last_request_time
        if elapsed_since_last < min_interval:
            time.sleep(min_interval - elapsed_since_last)
        last_request_time = time.time()

        ok, data, note = fetch_tile(z, x, y)
        processed += 1

        if ok:
            os.makedirs(out_dir, exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            downloaded += 1
        else:
            failed.append((z, x, y, note))
            logger.log(f"FAILED z{z}/{x}/{y}: {note}")

        if processed % PROGRESS_EVERY == 0:
            elapsed = time.time() - start_time
            rate_actual = processed / elapsed if elapsed > 0 else 0
            remaining = total - processed
            eta_sec = remaining / rate_actual if rate_actual > 0 else 0
            logger.log(
                f"Progress: {processed}/{total} ({downloaded} downloaded, {skipped} skipped, "
                f"{len(failed)} failed) - ETA ~{eta_sec / 60:.1f} min"
            )

    elapsed_total = time.time() - start_time
    logger.log(
        f"Done: {processed}/{total} processed, {downloaded} downloaded, {skipped} skipped, "
        f"{len(failed)} failed, took {elapsed_total / 60:.1f} min"
    )
    if failed:
        logger.log(f"Failed tiles ({len(failed)}):")
        for z, x, y, note in failed:
            logger.log(f"  z{z}/{x}/{y}: {note}")

    logger.close()


if __name__ == "__main__":
    main()
