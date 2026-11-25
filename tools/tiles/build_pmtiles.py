#!/usr/bin/env python3
"""Pack tools/tiles/raw/{z}/{x}/{y}.png into an MBTiles (SQLite) file.

MBTiles uses TMS row numbering (y flipped): tile_row = (2**z - 1) - y.
The raw/ tree uses standard XYZ (Slippy Map) numbering, so the flip
happens here on the way in.
"""
import argparse
import pathlib
import sqlite3

RAW_DIR = pathlib.Path(__file__).parent / "raw"

# Bounds used for the fetch: lat 29.3-33.4, lng 34.2-35.95 (Israel)
BOUNDS = "34.2,29.3,35.95,33.4"


def build(raw_dir: pathlib.Path, out_path: pathlib.Path, minzoom: int, maxzoom: int) -> int:
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(out_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    cur.execute(
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)"
    )
    cur.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")

    metadata = {
        "name": "Israel basemap tiles (OSM)",
        "format": "png",
        "bounds": BOUNDS,
        "minzoom": str(minzoom),
        "maxzoom": str(maxzoom),
        "type": "baselayer",
        "attribution": "© OpenStreetMap contributors",
        "description": "Raster basemap tiles of Israel, zoom 6-13, derived from OpenStreetMap (ODbL)",
        "version": "1.0.0",
    }
    cur.executemany("INSERT INTO metadata (name, value) VALUES (?, ?)", metadata.items())

    count = 0
    for z_dir in sorted(raw_dir.iterdir(), key=lambda p: int(p.name)):
        if not z_dir.is_dir():
            continue
        z = int(z_dir.name)
        if z < minzoom or z > maxzoom:
            continue
        for x_dir in sorted(z_dir.iterdir(), key=lambda p: int(p.name)):
            if not x_dir.is_dir():
                continue
            x = int(x_dir.name)
            for png in sorted(x_dir.glob("*.png"), key=lambda p: int(p.stem)):
                y = int(png.stem)
                tile_row = (2**z - 1) - y  # XYZ -> TMS flip
                data = png.read_bytes()
                cur.execute(
                    "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                    (z, x, tile_row, data),
                )
                count += 1

    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=pathlib.Path, default=RAW_DIR)
    parser.add_argument(
        "--out", type=pathlib.Path, default=pathlib.Path(__file__).parent / "israel-z6-13.mbtiles"
    )
    parser.add_argument("--minzoom", type=int, default=6)
    parser.add_argument("--maxzoom", type=int, default=13)
    args = parser.parse_args()

    n = build(args.raw_dir, args.out, args.minzoom, args.maxzoom)
    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"Packed {n} tiles into {args.out} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
