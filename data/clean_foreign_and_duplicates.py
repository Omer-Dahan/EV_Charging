"""
Removes confirmed-foreign/test stations and merges confirmed duplicate pairs
from data/ev_stations.db (table `locations`) and webapp/stations.json.

Source of truth for what to remove: data/location_verification_report.md
    - "Foreign / Test Stations" table, verdict == CONFIRMED_FOREIGN_OR_TEST
    - "Duplicate Pairs" table, verdict == CONFIRMED_DUPLICATE, with a clear
      keep=id=<N> recommendation (rows recommending "manual review needed"
      are skipped, never guessed)

Safety notes:
    - The live table is `locations`, not the legacy/unrelated `stations`
      table that happens to share the same DB file and id range but holds
      unrelated (older) data. `locations` is what bot/services/station_search.py
      and webapp/export_stations.py actually read.
    - Coordinates are never modified. Only whole rows are deleted (the ids
      listed above, or the losing half of a confirmed duplicate pair).
    - Every station that is actually a member of two CONFIRMED_DUPLICATE
      pairs with two different "keep" targets (a genuine 3-way cluster where
      the report never directly compares the two candidate survivors) is
      treated as ambiguous and skipped entirely, even though the individual
      pairs looked clear in isolation.
    - Any duplicate pair where the losing record has a known price
      (max_per_kwh) and the surviving record does not is skipped.

Usage:
    python3 data/clean_foreign_and_duplicates.py            # dry run (default)
    python3 data/clean_foreign_and_duplicates.py --dry-run  # explicit dry run
    python3 data/clean_foreign_and_duplicates.py --apply    # actually write
"""
import argparse
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "ev_stations.db"
JSON_PATH = REPO_ROOT / "webapp" / "stations.json"
REPORT_PATH = REPO_ROOT / "data" / "location_verification_report.md"
DB_BACKUP_PATH = REPO_ROOT / "data" / "ev_stations_backup_prefixclean.db"
JSON_BACKUP_PATH = REPO_ROOT / "webapp" / "stations.json.bak"
AUDIT_PATH = REPO_ROOT / "data" / "removed_stations.json"

ISRAEL_BBOX = {"lat_min": 29.4, "lat_max": 33.4, "lng_min": 34.2, "lng_max": 35.95}

PROTECTED_IDS = {3283, 3284}  # "Grand Canyon" - handled separately, never touched here


def parse_markdown_table(lines: list[str], header_prefix: str) -> list[list[str]]:
    start = None
    for i, line in enumerate(lines):
        if line.startswith(header_prefix):
            start = i
            break
    if start is None:
        raise RuntimeError(f"Could not find table starting with {header_prefix!r}")
    rows = []
    i = start + 2  # skip header + separator row
    while i < len(lines) and lines[i].startswith("|"):
        cells = [c.strip() for c in lines[i].split("|")[1:-1]]
        rows.append(cells)
        i += 1
    return rows


def load_foreign_ids(lines: list[str]) -> list[dict]:
    rows = parse_markdown_table(lines, "| id | name | city | lat | lng | verdict")
    out = []
    for r in rows:
        station_id, name, city, lat, lng, verdict = r[0], r[1], r[2], r[3], r[4], r[5]
        if verdict != "CONFIRMED_FOREIGN_OR_TEST":
            continue
        out.append({"id": int(station_id), "name": name, "city": city,
                     "lat": float(lat), "lng": float(lng)})
    return out


def load_duplicate_pairs(lines: list[str]) -> tuple[list[dict], list[dict]]:
    rows = parse_markdown_table(lines, "| id_a |")
    confirmed = []
    not_dup = []
    for r in rows:
        id_a, name_a, id_b, name_b, dist_m, verdict, keep, reason = (
            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
        )
        entry = {
            "id_a": int(id_a), "name_a": name_a, "id_b": int(id_b), "name_b": name_b,
            "dist_m": dist_m, "verdict": verdict, "keep": keep, "reason": reason,
        }
        if verdict == "CONFIRMED_DUPLICATE":
            confirmed.append(entry)
        elif verdict == "NOT_DUPLICATE":
            not_dup.append(entry)
    return confirmed, not_dup


def resolve_duplicate_removals(confirmed_pairs: list[dict]):
    """Returns (removals: {remove_id: keep_id}, skipped: [ {pair, reason} ])."""
    manual_review = [p for p in confirmed_pairs if p["keep"].startswith("manual")]
    clear = [p for p in confirmed_pairs if not p["keep"].startswith("manual")]

    skipped = []
    for p in manual_review:
        skipped.append({
            "id_a": p["id_a"], "id_b": p["id_b"],
            "reason": "verdict=CONFIRMED_DUPLICATE but keep recommendation is "
                      "'manual review needed' - not an unambiguous decision, skipped",
        })

    edges = []  # (remove_id, keep_id, id_a, id_b)
    for p in clear:
        keep_id = int(p["keep"].split("=")[1])
        remove_id = p["id_b"] if keep_id == p["id_a"] else p["id_a"]
        edges.append((remove_id, keep_id, p["id_a"], p["id_b"]))

    remove_ids = {e[0] for e in edges}

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for remove_id, keep_id, _, _ in edges:
        union(remove_id, keep_id)

    clusters = defaultdict(set)
    edges_by_cluster = defaultdict(list)
    for e in edges:
        remove_id, keep_id = e[0], e[1]
        root = find(remove_id)
        clusters[root].add(remove_id)
        clusters[root].add(keep_id)
        edges_by_cluster[root].append(e)

    removals: dict[int, int] = {}
    for root, members in clusters.items():
        survivors = [m for m in members if m not in remove_ids]
        if len(survivors) == 1:
            survivor = survivors[0]
            for m in members:
                if m != survivor:
                    removals[m] = survivor
        else:
            # Genuine ambiguity: the report gives two (or more) different
            # candidate survivors within the same transitive cluster with no
            # direct pairwise comparison between them. Do not guess.
            for e in edges_by_cluster[root]:
                remove_id, keep_id, id_a, id_b = e
                skipped.append({
                    "id_a": id_a, "id_b": id_b,
                    "reason": f"ambiguous transitive cluster {sorted(members)}: "
                              f"candidate survivors {sorted(survivors)} are never "
                              f"directly compared in the report - skipped, needs "
                              f"manual decision",
                })

    return removals, skipped


def check_price_loss(conn: sqlite3.Connection, removals: dict[int, int]):
    """Drop (report, don't apply) any removal where the losing record has a
    known price and the surviving record does not."""
    clean = {}
    skipped = []
    for remove_id, keep_id in removals.items():
        r_row = conn.execute(
            "SELECT max_per_kwh FROM locations WHERE id=?", (remove_id,)
        ).fetchone()
        k_row = conn.execute(
            "SELECT max_per_kwh FROM locations WHERE id=?", (keep_id,)
        ).fetchone()
        if r_row is None or k_row is None:
            skipped.append({
                "id_a": remove_id, "id_b": keep_id,
                "reason": "one of the two ids no longer exists in `locations` - skipped",
            })
            continue
        r_price, k_price = r_row[0], k_row[0]
        if r_price is not None and k_price is None:
            skipped.append({
                "id_a": remove_id, "id_b": keep_id,
                "reason": f"losing record id={remove_id} has a known price "
                          f"({r_price}) that the surviving record id={keep_id} "
                          f"lacks - would lose information, skipped",
            })
            continue
        clean[remove_id] = keep_id
    return clean, skipped


def verify_foreign_ids(conn: sqlite3.Connection, foreign_entries: list[dict]):
    """Cross-check every foreign id against the current DB row and the Israel
    bbox before agreeing to delete it."""
    confirmed = []
    skipped = []
    for entry in foreign_entries:
        station_id = entry["id"]
        row = conn.execute(
            "SELECT id, name, city, lat, lng FROM locations WHERE id=?", (station_id,)
        ).fetchone()
        if row is None:
            skipped.append({"id": station_id, "reason": "id not found in `locations` - skipped"})
            continue
        _, name, city, lat, lng = row
        print(f"  id={station_id:5} | name={name!r:35} | city={city!r:20} | lat={lat} | lng={lng}")
        if lat is None or lng is None:
            skipped.append({"id": station_id, "reason": "lat/lng is NULL - skipped"})
            continue
        inside_israel = (
            ISRAEL_BBOX["lat_min"] <= lat <= ISRAEL_BBOX["lat_max"]
            and ISRAEL_BBOX["lng_min"] <= lng <= ISRAEL_BBOX["lng_max"]
        )
        if inside_israel:
            skipped.append({
                "id": station_id,
                "reason": f"coordinate ({lat},{lng}) is INSIDE the Israel bbox - "
                          f"NOT deleting, needs manual review",
            })
            continue
        if station_id in PROTECTED_IDS:
            skipped.append({"id": station_id, "reason": "protected id - skipped"})
            continue
        confirmed.append(station_id)
    return confirmed, skipped


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Default. No files are written.")
    mode.add_argument("--apply", action="store_true", help="Actually perform the deletions.")
    args = parser.parse_args()
    apply_changes = args.apply

    lines = REPORT_PATH.read_text(encoding="utf-8").splitlines()
    foreign_entries = load_foreign_ids(lines)
    confirmed_pairs, not_dup_pairs = load_duplicate_pairs(lines)

    print(f"{'=' * 70}\nMODE: {'APPLY' if apply_changes else 'DRY-RUN (no files touched)'}\n{'=' * 70}")

    print(f"\nParsed report: {len(foreign_entries)} CONFIRMED_FOREIGN_OR_TEST stations, "
          f"{len(confirmed_pairs)} CONFIRMED_DUPLICATE pairs, "
          f"{len(not_dup_pairs)} NOT_DUPLICATE pairs (untouched).")

    # --- Foreign / test stations -------------------------------------------------
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    print(f"\n--- Fix 1: Foreign / test stations ({len(foreign_entries)} candidates) ---")
    foreign_ok, foreign_skipped = verify_foreign_ids(conn, foreign_entries)

    # --- Duplicate pairs -----------------------------------------------------------
    print(f"\n--- Fix 2: Duplicate pairs ({len(confirmed_pairs)} CONFIRMED_DUPLICATE) ---")
    dup_removals, dup_skipped = resolve_duplicate_removals(confirmed_pairs)
    dup_removals, price_skipped = check_price_loss(conn, dup_removals)
    dup_skipped += price_skipped
    conn.close()

    all_removal_ids = set(foreign_ok) | set(dup_removals.keys())
    assert not (all_removal_ids & PROTECTED_IDS), "protected id would be removed - aborting"

    print(f"\nForeign stations to remove: {len(foreign_ok)} -> {sorted(foreign_ok)}")
    print(f"Foreign stations skipped:   {len(foreign_skipped)}")
    for s in foreign_skipped:
        print(f"  SKIP id={s['id']}: {s['reason']}")

    print(f"\nDuplicate records to remove: {len(dup_removals)}")
    for remove_id, keep_id in sorted(dup_removals.items()):
        print(f"  remove id={remove_id:5} -> keep id={keep_id}")
    print(f"\nDuplicate pairs skipped: {len(dup_skipped)}")
    for s in dup_skipped:
        print(f"  SKIP pair ({s['id_a']}, {s['id_b']}): {s['reason']}")

    print(f"\n{'=' * 70}\nTOTAL: {len(foreign_ok)} foreign + {len(dup_removals)} duplicate "
          f"= {len(all_removal_ids)} rows to remove\n{'=' * 70}")

    if not apply_changes:
        print("\nDry run complete. No files were modified. Re-run with --apply to execute.")
        return

    # ---------------------------------------------------------------- APPLY ----
    print("\nApplying changes...")

    shutil.copy2(DB_PATH, DB_BACKUP_PATH)
    shutil.copy2(JSON_PATH, JSON_BACKUP_PATH)
    print(f"  DB backup   -> {DB_BACKUP_PATH}")
    print(f"  JSON backup -> {JSON_BACKUP_PATH}")

    rw_conn = sqlite3.connect(DB_PATH)
    rw_conn.row_factory = sqlite3.Row
    removed_records = []
    for station_id in sorted(all_removal_ids):
        row = rw_conn.execute("SELECT * FROM locations WHERE id=?", (station_id,)).fetchone()
        if row is None:
            continue
        record = dict(row)
        if station_id in foreign_ok:
            record["_removal_reason"] = "foreign_or_test"
        else:
            record["_removal_reason"] = "duplicate"
            record["_kept_id"] = dup_removals[station_id]
        removed_records.append(record)

    placeholders = ",".join("?" for _ in all_removal_ids)
    cur = rw_conn.execute(
        f"DELETE FROM locations WHERE id IN ({placeholders})", tuple(all_removal_ids)
    )
    rw_conn.commit()
    deleted_count = cur.rowcount
    rw_conn.close()
    print(f"  DB: deleted {deleted_count} rows from `locations`")

    stations = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    before_json = len(stations)
    stations = [s for s in stations if s["id"] not in all_removal_ids]
    after_json = len(stations)
    JSON_PATH.write_text(
        json.dumps(stations, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"  JSON: {before_json} -> {after_json} stations ({before_json - after_json} removed)")

    AUDIT_PATH.write_text(
        json.dumps(removed_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Audit trail -> {AUDIT_PATH} ({len(removed_records)} full records)")

    print("\nDone.")


if __name__ == "__main__":
    main()
