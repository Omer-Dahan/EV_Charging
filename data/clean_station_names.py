#!/usr/bin/env python3
"""
Clean leading price-tier symbols ($, ₪) from station names in the local DB and JSON.

Usage:
    python3 data/clean_station_names.py           # dry-run (default)
    python3 data/clean_station_names.py --apply   # actually modify files

Designed to run on the live server with zero external dependencies:
    cd /opt/bots/ev-charging-bot && python3 data/clean_station_names.py --apply
"""

import json
import os
import re
import shutil
import sqlite3
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Core cleaning function (identical to the one in build_db.py)
# ---------------------------------------------------------------------------

def strip_price_prefix(name: Optional[str]) -> str:
    """Strip leading price-tier symbols ($, ₪) from station names.

    Removes one or more $ or ₪ characters (and optional trailing whitespace)
    from the **beginning** of the name only.  Does NOT touch $ signs that
    appear in the middle of a name.  If stripping would produce an empty
    string the original name is returned unchanged.
    """
    if not name:
        return name or ""
    cleaned = re.sub(r'^[$₪]+\s*', '', name)
    # Safety: never return empty if original was non-empty
    if not cleaned.strip():
        return name
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Paths (relative to the project root = parent of this script's directory)
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(SCRIPT_DIR, "ev_stations.db")
JSON_PATH = os.path.join(PROJECT_ROOT, "webapp", "stations.json")
BACKUP_DB_PATH = os.path.join(SCRIPT_DIR, "ev_stations_backup_dollar.db")


def clean_db(apply: bool) -> int:
    """Clean leading $ / ₪ from the `name` column in tables `stations` and `locations`.

    Returns total number of rows that were (or would be) changed.
    """
    if not os.path.exists(DB_PATH):
        print(f"⚠️  DB not found: {DB_PATH}")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Identify tables that have a `name` column
    tables_to_clean = []
    for (tbl,) in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall():
        cols = [row[1] for row in cur.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if "name" in cols:
            tables_to_clean.append(tbl)

    total_changed = 0

    for tbl in tables_to_clean:
        rows = cur.execute(
            f"SELECT rowid, name FROM {tbl} WHERE name LIKE '$%' OR name LIKE '₪%'"
        ).fetchall()

        if not rows:
            continue

        print(f"\n📋 טבלת {tbl}: {len(rows)} רשומות לניקוי")
        changes = []
        for rowid, old_name in rows:
            new_name = strip_price_prefix(old_name)
            if new_name != old_name:
                changes.append((rowid, old_name, new_name))
                print(f"  [{rowid}] \"{old_name}\" → \"{new_name}\"")

        if apply and changes:
            for rowid, _, new_name in changes:
                cur.execute(f"UPDATE {tbl} SET name = ? WHERE rowid = ?", (new_name, rowid))
            conn.commit()
            print(f"  ✅ עודכנו {len(changes)} רשומות בטבלת {tbl}")

        total_changed += len(changes)

    conn.close()
    return total_changed


def clean_json(apply: bool) -> int:
    """Clean leading $ / ₪ from the `n` field in webapp/stations.json.

    Returns total number of entries that were (or would be) changed.
    """
    if not os.path.exists(JSON_PATH):
        print(f"\n⚠️  JSON not found: {JSON_PATH}")
        return 0

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    print(f"\n📋 קובץ JSON: {JSON_PATH}")
    for entry in data:
        old_name = entry.get("n", "")
        if not old_name:
            continue
        new_name = strip_price_prefix(old_name)
        if new_name != old_name:
            print(f"  [id={entry.get('id','?')}] \"{old_name}\" → \"{new_name}\"")
            entry["n"] = new_name
            changed += 1

    if changed == 0:
        print("  אין רשומות לניקוי.")
        return 0

    if apply:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  ✅ עודכנו {changed} רשומות ב-JSON")

    return changed


def main() -> None:
    apply = "--apply" in sys.argv
    mode = "🔧 מצב ביצוע (--apply)" if apply else "👁️  מצב תצוגה בלבד (dry-run)"
    print(f"\n{'='*60}")
    print(f" ניקוי סימני $ מתחילת שמות עמדות טעינה")
    print(f" {mode}")
    print(f"{'='*60}")

    # Backup DB before applying
    if apply and os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, BACKUP_DB_PATH)
        print(f"\n📦 גיבוי DB נוצר: {BACKUP_DB_PATH}")

    db_changes = clean_db(apply)
    json_changes = clean_json(apply)

    print(f"\n{'='*60}")
    total = db_changes + json_changes
    if apply:
        print(f" ✅ סה\"כ שונו {total} רשומות.")
    else:
        print(f" 👁️  סה\"כ {total} רשומות ישתנו. הרץ עם --apply לביצוע.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
