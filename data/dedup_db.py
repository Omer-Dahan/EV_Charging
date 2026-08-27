#!/usr/bin/env python3
"""
Deduplicate EV Charging Stations Database (locations table) in ev_stations.db.
- Detects duplicates within 50 meters or identical specific normalized names.
- Retains the richest record (highest source coverage, connectors, tariffs, Paz branding).
- Merges sources, connectors, and metadata into the kept record.
- Deletes redundant records.
- Updates the 'meta' table with accurate build statistics.
"""

import json
import math
import os
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = "/home/vm/projects/ev-charging-bot/data/ev_stations.db"
BACKUP_PATH = "/home/vm/projects/ev-charging-bot/data/ev_stations_backup_dup2.db"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def normalize_text(s: str) -> str:
    """Normalize Hebrew and alphanumeric text for matching."""
    if not s:
        return ""
    s = s.lower().strip()
    return re.sub(r"[^\w\u0590-\u05fe]", "", s)


def merge_connectors(conns_list: list) -> list:
    """Merge connector lists, deduplicating by standard, powerType, maxPower."""
    seen = set()
    merged = []
    for conns in conns_list:
        if not conns:
            continue
        try:
            items = json.loads(conns) if isinstance(conns, str) else conns
            if isinstance(items, list):
                for c in items:
                    if not isinstance(c, dict):
                        continue
                    std = (c.get("standard") or "").strip()
                    ptype = (c.get("powerType") or "").strip()
                    pwr = c.get("maxPower")
                    key = (std, ptype, pwr)
                    if key not in seen and std:
                        seen.add(key)
                        merged.append({
                            "standard": std,
                            "powerType": ptype or "UNKNOWN",
                            "maxPower": pwr,
                        })
        except Exception:
            pass
    return merged


def score_record(r: dict) -> tuple:
    """Score a location record to pick the richest one to keep."""
    sources = (r["sources"] or "").split(",")
    src_score = len(sources) * 100
    has_paz = 50 if "paz" in sources or (r["provider_name"] or "").lower() in ("yellow", "paz") else 0
    conns_len = len(r["connectors"] or "")
    has_tariffs = 20 if r["has_tariffs"] == 1 else 0
    has_cello = 10 if r["cello_id"] else 0
    is_gov = 5 if r["is_gov_official"] == 1 else 0
    return (src_score + has_paz + has_tariffs + has_cello + is_gov, conns_len, -r["id"])


def deduplicate_database(db_path: str = DB_PATH) -> dict:
    # 0. Backup verification
    if not os.path.exists(BACKUP_PATH):
        print(f"📦 יצירת גיבוי: {BACKUP_PATH}")
        shutil.copy2(db_path, BACKUP_PATH)
    else:
        print(f"ℹ️ קובץ גיבוי קיים כבר: {BACKUP_PATH}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM locations")
    total_before = cur.fetchone()[0]

    cur.execute("""
        SELECT id, cello_id, name, address, city, lat, lng, provider_id,
               provider_name, max_per_kwh, has_tariffs, payment_options,
               facilities, status_summary, connectors, stations_count,
               updated_at, sources, is_gov_official
        FROM locations
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Graph union-find for clustering
    parent = {r["id"]: r["id"] for r in rows}

    def find(i):
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i, j):
        pi = find(i)
        pj = find(j)
        if pi != pj:
            parent[pi] = pj

    # 1. Proximity matching (< 50m)
    with_coords = [r for r in rows if r["lat"] is not None and r["lng"] is not None]
    for i in range(len(with_coords)):
        r1 = with_coords[i]
        for j in range(i + 1, len(with_coords)):
            r2 = with_coords[j]
            if abs(r1["lat"] - r2["lat"]) > 0.001 or abs(r1["lng"] - r2["lng"]) > 0.001:
                continue
            d = haversine_distance(r1["lat"], r1["lng"], r2["lat"], r2["lng"])
            if d < 50.0:
                union(r1["id"], r2["id"])

    # 2. Specific matching normalized names
    generic_names = {"nvidiaמשתמשיםמורשיםבלבד", "בריכה", "הרדוף", "חניוןהעירייה", "משרדיהמועצה", "רחובהאירוס"}
    norm_groups = defaultdict(list)
    for r in rows:
        nn = normalize_text(r["name"])
        if nn and len(nn) >= 6 and nn not in generic_names:
            norm_groups[nn].append(r)

    for name, group in norm_groups.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    r1, r2 = group[i], group[j]
                    c1 = normalize_text(r1["city"])
                    c2 = normalize_text(r2["city"])
                    if c1 == c2 or not c1 or not c2 or (
                        r1["lat"] is not None
                        and r2["lat"] is not None
                        and haversine_distance(r1["lat"], r1["lng"], r2["lat"], r2["lng"]) < 30000.0
                    ):
                        union(r1["id"], r2["id"])

    clusters = defaultdict(list)
    for r in rows:
        clusters[find(r["id"])].append(r)

    multi_clusters = [v for v in clusters.values() if len(v) > 1]
    print(f"🔍 זוהו {len(multi_clusters)} אשכולות של עמדות כפולות (כפילויות).")

    ids_to_delete = []
    updates = []

    for c in multi_clusters:
        c_sorted = sorted(c, key=score_record, reverse=True)
        kept = dict(c_sorted[0])
        deleted = c_sorted[1:]
        for d in deleted:
            ids_to_delete.append(d["id"])

        all_sources = set()
        for r in c:
            for s in (r["sources"] or "").split(","):
                if s.strip():
                    all_sources.add(s.strip())
        source_order = ["cello", "auto_coil", "evm", "data_gov", "paz"]
        ordered_sources = [s for s in source_order if s in all_sources]
        new_sources = ",".join(ordered_sources)

        new_conns = json.dumps(merge_connectors([r["connectors"] for r in c]), ensure_ascii=False)
        new_is_gov = 1 if any(r["is_gov_official"] == 1 or "data_gov" in (r["sources"] or "") for r in c) else 0

        new_tariffs = kept["has_tariffs"]
        new_max_kwh = kept["max_per_kwh"]
        if not new_tariffs:
            for r in c:
                if r["has_tariffs"]:
                    new_tariffs = 1
                    new_max_kwh = r["max_per_kwh"]
                    break

        new_name = kept["name"] or ""
        new_provider = kept["provider_name"]
        has_paz = "paz" in all_sources or any((r["provider_name"] or "").lower() in ("yellow", "paz") for r in c)
        if has_paz:
            if (new_provider or "").lower() in ("advice", "paz", "") or not new_provider:
                new_provider = "Yellow"
            if "פז" not in new_name and "paz" not in new_name.lower():
                new_name = f"פז - {new_name}"

        new_address = kept["address"]
        if not new_address:
            for r in c:
                if r["address"]:
                    new_address = r["address"]
                    break

        new_city = kept["city"]
        if not new_city:
            for r in c:
                if r["city"]:
                    new_city = r["city"]
                    break

        new_stations_count = max(r["stations_count"] or 1 for r in c)

        updates.append((
            new_name, new_address, new_city, new_provider, new_max_kwh, new_tariffs,
            new_conns, new_stations_count, new_sources, new_is_gov, kept["id"]
        ))

    print(f"🔄 מעדכן {len(updates)} רשומות עשירות נבחרות ומוחק {len(ids_to_delete)} רשומות כפולות...")
    cur.executemany("""
        UPDATE locations SET
            name = ?, address = ?, city = ?, provider_name = ?, max_per_kwh = ?, has_tariffs = ?,
            connectors = ?, stations_count = ?, sources = ?, is_gov_official = ?
        WHERE id = ?
    """, updates)

    cur.executemany("DELETE FROM locations WHERE id = ?", [(i,) for i in ids_to_delete])
    conn.commit()

    # Verify count
    cur.execute("SELECT COUNT(*) FROM locations")
    total_after = cur.fetchone()[0]

    # Verify no remaining <50m duplicates
    cur.execute("SELECT id, lat, lng FROM locations WHERE lat IS NOT NULL AND lng IS NOT NULL")
    remaining_coords = cur.fetchall()
    rem_dups = 0
    for i in range(len(remaining_coords)):
        for j in range(i + 1, len(remaining_coords)):
            if (
                abs(remaining_coords[i][1] - remaining_coords[j][1]) > 0.001
                or abs(remaining_coords[i][2] - remaining_coords[j][2]) > 0.001
            ):
                continue
            d = haversine_distance(
                remaining_coords[i][1], remaining_coords[i][2],
                remaining_coords[j][1], remaining_coords[j][2]
            )
            if d < 50.0:
                rem_dups += 1

    # Update meta statistics
    cur.execute("SELECT COUNT(*) FROM locations WHERE lat IS NOT NULL AND lng IS NOT NULL")
    with_coords = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE has_tariffs = 1")
    with_tariffs = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE is_gov_official = 1")
    is_gov_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT provider_name) FROM locations WHERE provider_name IS NOT NULL AND provider_name != ''")
    unique_providers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%cello%'")
    cello_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'auto_coil'")
    auto_unique = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'evm'")
    evm_unique = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'data_gov'")
    gov_unique = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'paz'")
    paz_unique = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%paz%'")
    paz_count = cur.fetchone()[0]

    meta_entries = [
        ("build_time", datetime.now().isoformat()),
        ("version", "2.1"),
        ("primary_source", "CelloCharge (Ministry of Energy)"),
        ("sources_list", "cello, auto_coil, evm, data_gov, paz"),
        ("total_locations", str(total_after)),
        ("cello_locations", str(cello_count)),
        ("auto_coil_unique", str(auto_unique)),
        ("evm_unique", str(evm_unique)),
        ("data_gov_unique", str(gov_unique)),
        ("paz_unique", str(paz_unique)),
        ("paz_locations", str(paz_count)),
        ("records_with_coords", str(with_coords)),
        ("records_with_tariffs", str(with_tariffs)),
        ("is_gov_official_count", str(is_gov_count)),
        ("unique_providers", str(unique_providers)),
    ]
    cur.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", meta_entries)
    conn.commit()
    conn.close()

    return {
        "total_before": total_before,
        "total_after": total_after,
        "clusters_found": len(multi_clusters),
        "deleted_count": len(ids_to_delete),
        "remaining_dups_50m": rem_dups,
        "with_coords": with_coords,
        "with_tariffs": with_tariffs,
        "is_gov_count": is_gov_count,
        "unique_providers": unique_providers,
        "paz_locations": paz_count,
    }


if __name__ == "__main__":
    res = deduplicate_database(DB_PATH)
    print("\n" + "=" * 60)
    print("📊 תוצאות איחוד כפילויות:")
    print(f" • סה\"כ רשומות לפני:         {res['total_before']:,}")
    print(f" • אשכולות כפילויות שנמצאו:   {res['clusters_found']:,}")
    print(f" • רשומות שנמחקו:             {res['deleted_count']:,}")
    print(f" • סה\"כ רשומות אחרי:         {res['total_after']:,}")
    print(f" • כפילויות שנותרו (<50m):    {res['remaining_dups_50m']}")
    print(f" • עמדות פז / Yellow:         {res['paz_locations']}")
    print(f" • מפעילים ייחודיים:          {res['unique_providers']}")
    print("=" * 60)
