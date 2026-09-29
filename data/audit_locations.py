#!/usr/bin/env python3
"""
Location audit tool for EV charging stations.

Scans stations.json for:
  1. Coordinates in water (sea/lake) — via simplified land polygon + Nominatim
  2. Stations far from their declared city center
  3. Duplicate pairs with divergent coordinates

Read-only: station data (stations.json, ev_stations.db) is never modified.
The only files written are the report and the git-ignored city-center cache.

Usage:
    python3 data/audit_locations.py                     # full scan, dry-run
    python3 data/audit_locations.py --limit 150         # first 150 only
    python3 data/audit_locations.py --out report.md     # custom output path
"""

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
STATIONS_JSON = REPO / "webapp" / "stations.json"
STATIONS_DB = DATA / "ev_stations.db"
CITY_CACHE = DATA / "city_centers_cache.json"
ISRAEL_BOUNDARY = DATA / "israel_boundary.json"
DEFAULT_REPORT = DATA / "location_audit_report.md"

UA = "ev-charging-audit/1.0 (location quality audit; github.com/Omer-Dahan/EV_Charging)"
NOMINATIM_DELAY = 1.1  # seconds between requests (>1 s)
BACKOFF_429 = (30, 60, 120, 240)  # seconds to wait after each consecutive 429

# Returned by NominatimClient when a request failed (network, 429 exhausted).
# Distinct from None, which means "Nominatim answered, nothing found".
LOOKUP_FAILED = object()

# Values in the "c" field that mean "no city" even though they are strings.
NO_CITY_VALUES = ("none", "null", "city")


def text(value):
    """Return value as str, mapping None to ''. Station fields may be JSON null."""
    return "" if value is None else str(value)


def has_city(station):
    city = text(station.get("c")).strip()
    return bool(city) and city.lower() not in NO_CITY_VALUES

# ── Israel approximate bounding box ───────────────────────────────────
# Generous bbox; anything outside is "outside Israel"
ISR_LAT_MIN, ISR_LAT_MAX = 29.4, 33.4
ISR_LNG_MIN, ISR_LNG_MAX = 34.2, 35.95

# ── haversine ─────────────────────────────────────────────────────────
def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── ray-casting point-in-polygon ──────────────────────────────────────
def point_in_polygon(lat, lng, polygon):
    """polygon: list of [lng, lat] pairs (GeoJSON order)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]   # lng, lat
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and \
           (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ── Nominatim helpers ─────────────────────────────────────────────────
class NominatimClient:
    def __init__(self):
        self.request_count = 0
        self._last_request = 0.0
        self.errors_429 = 0
        self.failures = 0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < NOMINATIM_DELAY:
            time.sleep(NOMINATIM_DELAY - elapsed)
        self._last_request = time.time()

    def _get_json(self, url):
        """GET a Nominatim URL. Returns parsed JSON or LOOKUP_FAILED."""
        for wait in (*BACKOFF_429, None):
            self._throttle()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            self.request_count += 1
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code != 429 or wait is None:
                    break
                self.errors_429 += 1
                print(f"  ⚠ 429 rate-limited, waiting {wait}s…")
                time.sleep(wait)
            except Exception:
                break
        self.failures += 1
        return LOOKUP_FAILED

    def reverse(self, lat, lng):
        """Reverse geocode. Returns dict or LOOKUP_FAILED."""
        return self._get_json(
            f"https://nominatim.openstreetmap.org/reverse?"
            f"format=json&lat={lat}&lon={lng}&accept-language=he&zoom=18")

    def search_city(self, city):
        """Forward geocode a city name. Returns (lat, lng), None, or LOOKUP_FAILED."""
        q = urllib.parse.quote(f"{city}, Israel")
        data = self._get_json(
            f"https://nominatim.openstreetmap.org/search?"
            f"q={q}&format=json&limit=1&accept-language=he")
        if data is LOOKUP_FAILED:
            return LOOKUP_FAILED
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        return None


# ── water detection ───────────────────────────────────────────────────
def is_water_by_reverse(nominatim, lat, lng):
    """
    Heuristic: reverse geocode the point.
    - Error / "Unable to geocode" → definitely water or void
    - Only country-level result (no road/city/suburb) → likely water (territorial waters)
    - Normal address → land
    Returns: (is_water: bool | None, detail: str); None = lookup failed, unverified
    """
    result = nominatim.reverse(lat, lng)
    if result is LOOKUP_FAILED:
        return None, "reverse geocode failed (timeout/429/error)"
    if result.get("error"):
        return True, f"reverse geocode error: {result['error']}"
    addr = result.get("address", {})
    # If we only get country (and maybe country_code) — no local detail
    local_keys = {"road", "suburb", "city", "town", "village", "hamlet",
                  "city_district", "neighbourhood", "residential",
                  "building", "shop", "amenity", "tourism", "leisure",
                  "industrial", "commercial", "retail", "farmyard"}
    has_local = bool(local_keys & set(addr.keys()))
    if not has_local:
        # Check the type/class for water-specific values
        osm_type = text(result.get("type"))
        osm_class = text(result.get("class"))
        display = text(result.get("display_name"))
        return True, f"no local address (type={osm_type}, class={osm_class}, display={display[:60]})"
    return False, ""


# ── duplicate detection helpers ───────────────────────────────────────
def normalize_name(name):
    """Normalize station name for fuzzy matching."""
    if not name:
        return ""
    s = name.lower()
    # Remove common operator prefixes that appear in names
    for op in ["scala energy", "scala", "advice", "gnrgy", "greenspot",
               "ev-plug", "sonolevi", "yellow", "nofar", "tesla",
               "evlink", "evtech", "evedge", "sync", "xeed", "xeed",
               "zen energy", "on ev", "on-ev", "tdsd", "greems",
               "energy one", "enova", "vimore", "seven ev", "interev",
               "elexify", "edgecontrol", "gencell", "doral urban energy",
               "amis", "ragreen"]:
        s = s.replace(op, "")
    # Remove Hebrew operator names
    s = re.sub(r'[-–—|/\\,.:;!?\'\"()\[\]{}]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def normalize_address(addr):
    if not addr:
        return ""
    s = addr.lower()
    # Remove ", Israel" / ", ישראל"
    s = re.sub(r',?\s*(israel|ישראל)\s*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[-–—|/\\,.:;!?\'\"()\[\]{}]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# Tokens shared by more than this many stations (chain names, "parking",
# "lot", city names) carry no identity and are ignored by name_similarity.
COMMON_TOKEN_DF = 10

# Placeholder addresses that say nothing about the location.
GENERIC_ADDRESSES = {"unnamed road", "unnamed", "israel", "ישראל", "כביש"}


def specific_address(station):
    """Normalized address, or '' when it cannot identify a site: placeholders
    and one-word values (usually just a city or kibbutz name, in any language)."""
    na = normalize_address(station.get("a"))
    if (na in GENERIC_ADDRESSES or len(na.split()) < 2
            or na == normalize_address(station.get("c"))):
        return ""
    return na


def common_tokens(strings):
    df = {}
    for s in strings:
        for tok in set(s.split()):
            df[tok] = df.get(tok, 0) + 1
    return {tok for tok, n in df.items() if n > COMMON_TOKEN_DF}


def name_similarity(a, b, ignore=frozenset()):
    """Word-overlap Jaccard similarity over distinctive (non-common) tokens."""
    if not a or not b:
        return 0.0
    wa = set(a.split()) - ignore
    wb = set(b.split()) - ignore
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


# ── main audit ────────────────────────────────────────────────────────
def load_stations(limit=None):
    """Returns (stations to scan, total count in file). Read-only."""
    with open(STATIONS_JSON, "r", encoding="utf-8") as f:
        stations = json.load(f)
    total = len(stations)
    if limit:
        stations = stations[:limit]
    return stations, total


def load_israel_polygon():
    if ISRAEL_BOUNDARY.exists():
        with open(ISRAEL_BOUNDARY, "r", encoding="utf-8") as f:
            geom = json.load(f)
        if geom["type"] == "Polygon":
            return geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            # Use the largest polygon
            return max(geom["coordinates"], key=lambda p: len(p[0]))[0]
    return None


_sources = None


def get_source_from_db(station_id):
    """Get source info from the locations table (DB opened read-only, loaded once)."""
    global _sources
    if _sources is None:
        import sqlite3
        conn = sqlite3.connect(f"file:{STATIONS_DB}?mode=ro", uri=True)
        try:
            _sources = dict(conn.execute("SELECT id, sources FROM locations"))
        finally:
            conn.close()
    return _sources.get(station_id) or "unknown"


def audit_water(stations, nominatim, polygon):
    """Find stations with coordinates in water."""
    print("\n🌊 Checking for water coordinates…")
    water_stations = []
    outside_israel = []
    unverified = []  # coastal suspects whose reverse lookup failed

    for i, s in enumerate(stations):
        lat, lng = s["lat"], s["lng"]

        # Phase 1: outside Israel bbox → definitely wrong (foreign or void)
        if not (ISR_LAT_MIN <= lat <= ISR_LAT_MAX and
                ISR_LNG_MIN <= lng <= ISR_LNG_MAX):
            src = get_source_from_db(s["id"])
            outside_israel.append({
                **s, "source": src,
                "reason": f"Outside Israel bbox (lat={lat:.4f}, lng={lng:.4f})"
            })
            continue

        # Phase 2: use polygon to check if outside Israel land boundary
        # Note: the Nominatim polygon includes territorial waters,
        # so "inside polygon but no address" = likely water.
        # We only reverse-geocode points that are near the coast (low lng).
        # Rough coastline heuristic: in the coastal strip, lng is suspicious
        # if it's west of a latitude-dependent threshold.
        coast_lng = _coast_threshold(lat)
        if coast_lng is not None and lng < coast_lng:
            # Suspicious — reverse geocode to confirm
            is_water, detail = is_water_by_reverse(nominatim, lat, lng)
            if is_water is None:
                unverified.append({**s, "source": get_source_from_db(s["id"]),
                                   "reason": detail})
            elif is_water:
                src = get_source_from_db(s["id"])
                water_stations.append({
                    **s, "source": src,
                    "reason": detail
                })

        if (i + 1) % 500 == 0:
            print(f"  … checked {i + 1}/{len(stations)}")

    return water_stations, outside_israel, unverified


def _coast_threshold(lat):
    """
    Return the approximate longitude of the Israeli Mediterranean coast
    for a given latitude, plus a small margin inland.
    Returns None for latitudes where there's no western coast concern.
    
    These are approximate values from the actual coastline:
    """
    # Approximate coastal longitude (west edge of land) by latitude band
    # Format: (lat_min, lat_max, coast_lng)
    # Points with lng < coast_lng at this latitude are in the sea
    bands = [
        (31.2,  31.5,  34.48),   # Ashkelon - Ashdod area
        (31.5,  31.8,  34.53),   # Ashdod - Rishon area
        (31.8,  32.1,  34.72),   # Tel Aviv area
        (32.1,  32.3,  34.75),   # Netanya area
        (32.3,  32.5,  34.82),   # Hadera area
        (32.5,  32.75, 34.88),   # South of Haifa
        (32.75, 32.85, 34.95),   # Haifa (bay protrudes west)
        (32.85, 33.0,  34.96),   # Haifa bay - Akko
        (33.0,  33.1,  35.05),   # Nahariya area
        (33.1,  33.35, 35.07),   # Rosh Hanikra
        (29.4,  31.2,  34.25),   # Southern Negev / Gaza coast
    ]
    for lat_min, lat_max, clng in bands:
        if lat_min <= lat < lat_max:
            return clng
    return None


def suggest_city(station, known_cities, centers):
    """
    Suggest a city for a station without one, without guessing:
      1. a comma-separated segment of the address or name that exactly matches
         a city already used elsewhere in the dataset, or
      2. the nearest geocoded center of a dataset city, only if within 5 km (hint).
    Returns (city, how) or (None, reason).
    """
    for field, label in (("a", "address"), ("n", "name")):
        for part in text(station.get(field)).split(","):
            part = part.strip()
            if part in known_cities:
                return part, f"exact match in {label}"
    best, best_d = None, None
    for city in known_cities:
        center = centers.get(city)
        if not center:
            continue
        d = haversine_km(station["lat"], station["lng"], center["lat"], center["lng"])
        if best_d is None or d < best_d:
            best, best_d = city, d
    if best is not None and best_d <= 5:
        return best, f"nearest city center, {best_d:.1f} km (hint only)"
    return None, "no confident suggestion"


def audit_city_distance(stations, nominatim, cached):
    """
    Find stations far from their declared city center.
    Stations without a city are skipped and returned separately with a suggestion.
    """
    print("\n🏙️  Checking distance from city centers…")

    cities = {text(s.get("c")).strip() for s in stations if has_city(s)}
    print(f"  {len(cities)} unique cities to geocode")

    # Geocode missing cities. Transient failures are not cached, so a later
    # run retries them instead of silently skipping the city forever.
    geocode_failed = set()
    missing = sorted(c for c in cities if c not in cached)
    if missing:
        print(f"  {len(missing)} cities not in cache, geocoding…")
        for i, city in enumerate(missing):
            result = nominatim.search_city(city)
            if result is LOOKUP_FAILED:
                geocode_failed.add(city)
            elif result:
                cached[city] = {"lat": result[0], "lng": result[1]}
            else:
                cached[city] = None  # Nominatim found nothing
            if (i + 1) % 50 == 0:
                print(f"    … geocoded {i + 1}/{len(missing)} cities")

        # The cache is a derived, git-ignored file; station data is never written.
        with open(CITY_CACHE, "w", encoding="utf-8") as f:
            json.dump(cached, f, ensure_ascii=False, indent=2)
        print(f"  City cache saved ({len(cached)} entries)")

    high_severity = []  # >25 km
    medium_severity = []  # 12-25 km
    no_city = []  # no declared city: distance check skipped
    city_not_found = []  # declared city could not be geocoded: skipped

    # Where the dataset itself puts each city: median of its stations. Used to
    # tell a wrong station apart from a wrong Nominatim city center.
    by_city = {}
    for s in stations:
        if has_city(s):
            by_city.setdefault(text(s.get("c")).strip(), []).append(s)
    medians = {}
    for city, group in by_city.items():
        lats = sorted(x["lat"] for x in group)
        lngs = sorted(x["lng"] for x in group)
        medians[city] = (lats[len(lats) // 2], lngs[len(lngs) // 2], len(group))

    def verdict(s, city, center):
        mlat, mlng, n = medians[city]
        if n < 3:
            return f"unconfirmed: only {n} station(s) in this city"
        if haversine_km(s["lat"], s["lng"], mlat, mlng) <= 12:
            off = haversine_km(mlat, mlng, center["lat"], center["lng"])
            return (f"city center suspect: station is with the other {n - 1} "
                    f"stations of this city; geocoded center is {off:.0f} km away")
        return f"station outlier: far from the other {n - 1} stations of this city too"

    for s in stations:
        if not has_city(s):
            city, how = suggest_city(s, cities, cached)
            no_city.append({**s, "source": get_source_from_db(s["id"]),
                            "suggested_city": city or "", "suggest_how": how})
            continue
        city = text(s.get("c")).strip()
        center = cached.get(city)
        if not center:
            reason = ("geocode request failed" if city in geocode_failed
                      else "Nominatim found no match")
            city_not_found.append({**s, "reason": reason})
            continue

        dist = haversine_km(s["lat"], s["lng"], center["lat"], center["lng"])

        if dist > 12:
            row = {**s, "source": get_source_from_db(s["id"]),
                   "distance_km": round(dist, 1), "verdict": verdict(s, city, center)}
            (high_severity if dist > 25 else medium_severity).append(row)

    return high_severity, medium_severity, no_city, city_not_found


def audit_duplicates(stations):
    """Find duplicate pairs with divergent coordinates (>500m apart)."""
    print("\n🔍 Checking for duplicates with divergent coordinates…")

    # Build index by normalized name and normalized address
    # The address field often holds only street + number, so the same address
    # in two different cities is not a duplicate: key it by city too.
    by_addr = {}
    for s in stations:
        na = specific_address(s)
        if na and has_city(s):
            by_addr.setdefault((na, text(s.get("c")).strip()), []).append(s)

    common_name = common_tokens(normalize_name(s.get("n")) for s in stations)
    common_addr = common_tokens(normalize_address(s.get("a")) for s in stations)

    pairs = []
    seen = set()

    # Phase 1: exact address matches
    for addr, group in by_addr.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                if key in seen:
                    continue
                dist_m = haversine_km(a["lat"], a["lng"], b["lat"], b["lng"]) * 1000
                if dist_m > 500:
                    seen.add(key)
                    pairs.append(_make_pair(a, b, dist_m, "same address + city"))

    # Phase 2: similar names with same city
    name_groups = {}
    for s in stations:
        nn = normalize_name(s.get("n"))
        city = text(s.get("c")).strip()
        if nn and has_city(s):
            name_groups.setdefault((nn, city), []).append(s)

    for (nn, city), group in name_groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                if key in seen:
                    continue
                dist_m = haversine_km(a["lat"], a["lng"], b["lat"], b["lng"]) * 1000
                if dist_m > 500:
                    seen.add(key)
                    pairs.append(_make_pair(a, b, dist_m, "same normalized name + city"))

    # Phase 3: fuzzy name similarity (Jaccard > 0.6) with same city
    city_index = {}
    for s in stations:
        city = text(s.get("c")).strip()
        if has_city(s):
            city_index.setdefault(city, []).append(s)

    for city, group in city_index.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            nn_i = normalize_name(group[i].get("n"))
            na_i = specific_address(group[i])
            for j in range(i + 1, len(group)):
                key = (min(group[i]["id"], group[j]["id"]),
                       max(group[i]["id"], group[j]["id"]))
                if key in seen:
                    continue
                nn_j = normalize_name(group[j].get("n"))
                na_j = specific_address(group[j])
                # Check name similarity OR address similarity
                sim_n = name_similarity(nn_i, nn_j, common_name)
                sim_a = name_similarity(na_i, na_j, common_addr)
                if max(sim_n, sim_a) < 0.6:
                    continue
                dist_m = haversine_km(
                    group[i]["lat"], group[i]["lng"],
                    group[j]["lat"], group[j]["lng"]
                ) * 1000
                if dist_m > 500:
                    seen.add(key)
                    match_type = "name" if sim_n >= sim_a else "address"
                    pairs.append(_make_pair(
                        group[i], group[j], dist_m,
                        f"fuzzy {match_type} (sim={max(sim_n, sim_a):.2f})"
                    ))

    # Sort by distance (largest first)
    pairs.sort(key=lambda p: p["distance_m"], reverse=True)
    return pairs


def _make_pair(a, b, dist_m, match_reason):
    src_a = get_source_from_db(a["id"])
    src_b = get_source_from_db(b["id"])
    # Recommend which to keep
    keep, reason = _recommend_keep(a, b, src_a, src_b)
    return {
        "id_a": a["id"], "name_a": text(a.get("n")),
        "lat_a": a["lat"], "lng_a": a["lng"],
        "g_a": a.get("g", 0), "source_a": src_a,
        "provider_a": text(a.get("p")), "price_a": a.get("pr"),
        "power_a": a.get("mp") or 0,
        "id_b": b["id"], "name_b": text(b.get("n")),
        "lat_b": b["lat"], "lng_b": b["lng"],
        "g_b": b.get("g", 0), "source_b": src_b,
        "provider_b": text(b.get("p")), "price_b": b.get("pr"),
        "power_b": b.get("mp") or 0,
        "distance_m": round(dist_m),
        "match_reason": match_reason,
        "recommended_keep": keep,
        "keep_reason": reason,
    }


def _recommend_keep(a, b, src_a, src_b):
    """Recommend which station to keep in a duplicate pair."""
    score_a, score_b = 0, 0
    reasons = []

    # Prefer g=1 (government-verified)
    if a.get("g", 0) == 1 and b.get("g", 0) == 0:
        score_a += 3
        reasons.append("A is gov-verified")
    elif b.get("g", 0) == 1 and a.get("g", 0) == 0:
        score_b += 3
        reasons.append("B is gov-verified")

    # Prefer more source diversity
    src_count_a = len(src_a.split(",")) if src_a else 0
    src_count_b = len(src_b.split(",")) if src_b else 0
    if src_count_a > src_count_b:
        score_a += 2
        reasons.append(f"A has more sources ({src_count_a} vs {src_count_b})")
    elif src_count_b > src_count_a:
        score_b += 2
        reasons.append(f"B has more sources ({src_count_b} vs {src_count_a})")

    # Prefer higher power
    if (a.get("mp") or 0) > (b.get("mp") or 0):
        score_a += 1
        reasons.append(f"A has higher power ({a.get('mp')}kW)")
    elif (b.get("mp") or 0) > (a.get("mp") or 0):
        score_b += 1
        reasons.append(f"B has higher power ({b.get('mp')}kW)")

    # Prefer having a price
    if a.get("pr") and not b.get("pr"):
        score_a += 1
        reasons.append("A has price info")
    elif b.get("pr") and not a.get("pr"):
        score_b += 1
        reasons.append("B has price info")

    if score_a > score_b:
        return f"id={a['id']}", "; ".join(reasons)
    elif score_b > score_a:
        return f"id={b['id']}", "; ".join(reasons)
    else:
        return "manual review needed", "; ".join(reasons) or "no clear winner"


# ── report generation ─────────────────────────────────────────────────
def cell(value, width=None):
    """Markdown-table-safe text: None → '', pipes escaped, newlines flattened."""
    s = text(value).replace("\n", " ")
    if width:
        s = s[:width]
    return s.replace("|", "\\|")


def station_table(w, rows, extra_header, extra_cells, sort_key):
    """Shared table layout for per-station findings."""
    if not rows:
        w("None found.\n")
        return
    w(f"| id | name | city | lat | lng | source | g | {' | '.join(extra_header)} |")
    w("|---:|------|------|----:|----:|--------|:-:|" + "---|" * len(extra_header))
    for s in sorted(rows, key=sort_key):
        extra = " | ".join(extra_cells(s))
        w(f"| {s['id']} | {cell(s.get('n'), 45)} | {cell(s.get('c'), 20)} "
          f"| {s['lat']:.6f} | {s['lng']:.6f} | {cell(s.get('source'))} "
          f"| {cell(s.get('g'))} | {extra} |")


def generate_report(r, out_path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    w = lines.append

    w(f"# Location Audit Report — {now}\n")
    w("Read-only audit. **No station was changed, merged or deleted.** Every "
      "fix below is a proposal for manual review.\n")
    w("## Summary\n")
    w("| Metric | Count |")
    w("|--------|------:|")
    w(f"| Total stations in dataset | {r['total']} |")
    w(f"| Stations scanned | {r['scanned']} |")
    w(f"| **Outside Israel (foreign/test)** | **{len(r['outside'])}** ⚠️ high |")
    w(f"| **Water coordinates (coastal)** | **{len(r['water'])}** ⚠️ high |")
    w(f"| Coastal suspects not verified (lookup failed) | {len(r['unverified'])} |")
    w(f"| **Far from city (>25 km)** | **{len(r['high_dist'])}** ⚠️ high |")
    w(f"| Far from city (12–25 km) | {len(r['med_dist'])} ⚡ medium |")
    w(f"| Duplicate pairs with divergent coords | {len(r['dup_pairs'])} |")
    w(f"| Stations without a city (distance check skipped) | {len(r['no_city'])} |")
    w(f"| Stations whose city could not be geocoded (skipped) | {len(r['city_not_found'])} |")
    w(f"| Nominatim requests made | {r['nom_requests']} |")
    w(f"| Nominatim 429 responses | {r['nom_429']} |")
    w(f"| Nominatim failed lookups | {r['nom_failures']} |")
    w(f"| Elapsed time | {r['elapsed']:.0f}s |")
    w("")

    by_id = lambda x: x["id"]
    by_dist = lambda x: -x["distance_km"]

    w("## Outside Israel (foreign / test stations)\n")
    station_table(w, r["outside"], ["reason"],
                  lambda s: [cell(s.get("reason"))], by_id)
    w("")

    w("## Water Coordinates (Mediterranean coast)\n")
    station_table(w, r["water"], ["detail"],
                  lambda s: [cell(s.get("reason"), 60)], by_id)
    w("")

    if r["unverified"]:
        w("## Coastal Suspects Not Verified (reverse lookup failed)\n")
        w("West of the coastline threshold but Nominatim did not answer. "
          "Not counted as water; re-run to verify.\n")
        station_table(w, r["unverified"], ["detail"],
                      lambda s: [cell(s.get("reason"), 60)], by_id)
        w("")

    for label, rows in (("> 25 km", r["high_dist"]), ("12–25 km", r["med_dist"])):
        kinds = {}
        for x in rows:
            k = x["verdict"].split(":")[0]
            kinds[k] = kinds.get(k, 0) + 1
        if rows:
            w(f"- City distance {label}: " +
              ", ".join(f"{k} = {n}" for k, n in sorted(kinds.items())))
    w("\n\"city center suspect\" rows most likely point at a wrong Nominatim "
      "geocode of the city name (e.g. a same-named neighbourhood elsewhere), "
      "not a wrong station. \"station outlier\" rows are the real candidates.\n")
    w("## Far from City Center (>25 km) — High Severity\n")
    station_table(w, r["high_dist"], ["distance_km", "verdict"],
                  lambda s: [f"{s['distance_km']:.1f}", cell(s["verdict"])], by_dist)
    w("")

    w("## Far from City Center (12–25 km) — Medium Severity\n")
    station_table(w, r["med_dist"], ["distance_km", "verdict"],
                  lambda s: [f"{s['distance_km']:.1f}", cell(s["verdict"])], by_dist)
    w("")

    no_city = r["no_city"]
    suggested = [s for s in no_city if s["suggested_city"]]
    w(f"## Stations without a city (skipped city-distance check) — {len(no_city)}\n")
    w("These stations have no declared city (`c` is null or empty), so there is "
      "no center to measure against. They are **not** flagged as suspicious and "
      "no city was assigned. A suggestion is shown only when the address/name "
      "contains a city already used in the dataset, or a geocoded city center "
      "is within 5 km (marked \"hint only\").\n")
    w(f"- With a suggestion: {len(suggested)} "
      f"(exact text match: {sum('exact' in s['suggest_how'] for s in suggested)}, "
      f"nearest center: {sum('nearest' in s['suggest_how'] for s in suggested)})")
    w(f"- Without a suggestion: {len(no_city) - len(suggested)}\n")
    station_table(w, no_city, ["address", "suggested city", "basis"],
                  lambda s: [cell(s.get("a"), 45), cell(s["suggested_city"]),
                             cell(s["suggest_how"])], by_id)
    w("")

    if r["city_not_found"]:
        w(f"## Declared city not geocodable (skipped) — {len(r['city_not_found'])}\n")
        counts = {}
        for s in r["city_not_found"]:
            key = (text(s.get("c")).strip(), s["reason"])
            counts[key] = counts.get(key, 0) + 1
        w("| city | stations | reason |")
        w("|------|---------:|--------|")
        for (city, reason), n in sorted(counts.items(), key=lambda kv: -kv[1]):
            w(f"| {cell(city)} | {n} | {reason} |")
        w("")

    dup_pairs = r["dup_pairs"]
    w("## Duplicate Pairs with Divergent Coordinates\n")
    if dup_pairs:
        w("| id_a | name_a | id_b | name_b | distance_m | match | recommended_keep | reason |")
        w("|-----:|--------|-----:|--------|----------:|-------|-----------------|--------|")
        for p in dup_pairs:
            w(f"| {p['id_a']} | {cell(p['name_a'], 30)} "
              f"| {p['id_b']} | {cell(p['name_b'], 30)} "
              f"| {p['distance_m']} | {cell(p['match_reason'], 25)} "
              f"| {p['recommended_keep']} | {cell(p['keep_reason'], 50)} |")
        w("")
        w("### Duplicate Pair Details (top 30 by distance)\n")
        for i, p in enumerate(dup_pairs[:30], 1):
            w(f"**Pair {i}** — distance: {p['distance_m']}m, match: {p['match_reason']}")
            for side in ("a", "b"):
                w(f"- **{side.upper()}**: id={p['id_' + side]} `{p['name_' + side]}` | "
                  f"lat={p['lat_' + side]}, lng={p['lng_' + side]} | "
                  f"g={p['g_' + side]} | source={p['source_' + side]} | "
                  f"provider={p['provider_' + side]} | price={p['price_' + side]} | "
                  f"power={p['power_' + side]}kW")
            w(f"- **Recommendation**: keep {p['recommended_keep']} — {p['keep_reason']}")
            w("")
    else:
        w("None found.\n")
    w("")

    # Recommendations (proposals only; nothing here was executed)
    w("## Recommendations (not executed)\n")
    w("### High Priority\n")
    if r["outside"]:
        w(f"- **Review {len(r['outside'])} stations outside Israel's bounding box** — "
          f"likely test/demo data or foreign locations; candidates for removal.\n")
    if r["water"]:
        w(f"- **Review {len(r['water'])} stations with coordinates in the sea** — "
          f"re-geocode from the station address and compare.\n")
    if r["high_dist"]:
        w(f"- **Review {len(r['high_dist'])} stations >25 km from their declared city** — "
          f"either the coordinates or the city label is wrong.\n")
    w("### Medium Priority\n")
    if r["med_dist"]:
        w(f"- **Review {len(r['med_dist'])} stations 12–25 km from city center** — "
          f"many are legitimate (highway, industrial zones, regional councils).\n")
    if dup_pairs:
        w(f"- **Review {len(dup_pairs)} duplicate pairs** — decide per pair; the "
          f"`recommended_keep` column is a heuristic (g=1, more sources, power, price).\n")
    if suggested:
        w(f"- **Fill the city for {len(suggested)} stations** from the suggestions above, "
          f"after checking each one.\n")
    w("### Systemic\n")
    w("- The existing dedup (`data/dedup_db.py`) matches within 50 m or identical "
      "names; pairs above show duplicates it cannot catch when one copy has "
      "wrong coordinates.\n")
    w("- Add a coastline / bounding-box check to the import pipeline.\n")
    w("")

    w("## Method & Limitations\n")
    w("### Water Detection\n")
    w("1. **Bounding box**: outside lat 29.4–33.4, lng 34.2–35.95 → 'outside Israel'.\n")
    w("2. **Coastline threshold + reverse geocoding**: inside the bbox, a "
      "latitude-banded longitude threshold approximates the Mediterranean coast. "
      "Points west of it are reverse-geocoded; no local address component "
      "(road, city, suburb, …) → 'water'. Failed lookups are listed separately "
      "as unverified, never counted as water.\n")
    w("**Potential false positives**: beaches, marinas, ports, and new areas "
      "missing from OSM. The Sea of Galilee, Dead Sea and Eilat bay are not checked.\n")
    w("### City Distance\n")
    w("- City centers from Nominatim search (cached in city_centers_cache.json). "
      "Haversine distance station → center.\n")
    w("- **Potential false positives**: highway stations, industrial zones, "
      "regional councils / moshavim labelled with a council name whose geocoded "
      "point is arbitrary, large municipalities, and ambiguous city names that "
      "Nominatim resolved to the wrong place.\n")
    w("### Duplicate Detection\n")
    w("- Exact normalized address + city; exact normalized name + city; fuzzy name "
      "or address (Jaccard ≥ 0.6) within the same city. Fuzzy matching ignores "
      f"tokens shared by more than {COMMON_TOKEN_DF} stations (chain names, "
      "'parking lot', city names). Only pairs >500 m apart.\n")
    w("- **Potential false positives**: different sites sharing a generic name "
      "(e.g. a chain's name only) or a generic address (a mall, a street without "
      "number) in the same city.\n")

    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report


def print_summary(r):
    """Print the full summary (what and how many) to stdout."""
    bar = "=" * 78
    print("\n" + bar)
    print("📊 סיכום סריקת מיקומים")
    print(bar)
    print(f"  סה\"כ עמדות במאגר:                 {r['total']}")
    print(f"  עמדות שנסרקו:                      {r['scanned']}")
    print(f"  מחוץ לישראל:                       {len(r['outside'])}")
    print(f"  בים:                               {len(r['water'])}")
    print(f"  חשודות חוף שלא אומתו (בקשה נכשלה): {len(r['unverified'])}")
    print(f"  רחוקות מהעיר >25 ק\"מ:              {len(r['high_dist'])}")
    print(f"  רחוקות מהעיר 12-25 ק\"מ:            {len(r['med_dist'])}")
    for label, rows in ((">25", r["high_dist"]), ("12-25", r["med_dist"])):
        kinds = {}
        for x in rows:
            k = x["verdict"].split(":")[0]
            kinds[k] = kinds.get(k, 0) + 1
        print(f"      {label}: " + ", ".join(f"{k}={n}" for k, n in sorted(kinds.items())))
    print(f"  זוגות כפילויות (>500 מ'):          {len(r['dup_pairs'])}")
    print(f"  בלי עיר (דילוג על בדיקת מרחק):     {len(r['no_city'])}"
          f"  (עם הצעת עיר: {sum(bool(s['suggested_city']) for s in r['no_city'])})")
    print(f"  עיר שלא נמצאה ב-Nominatim (דילוג): {len(r['city_not_found'])}")
    print(f"  בקשות Nominatim: {r['nom_requests']}   429: {r['nom_429']}   "
          f"כשלונות: {r['nom_failures']}")
    print(f"  זמן ריצה: {r['elapsed']:.0f} שניות")
    print(bar)

    def row(s, tail=""):
        print(f"  id={s['id']:<5} {text(s.get('n'))[:38]:38s} | {text(s.get('c'))[:14]:14s} "
              f"| ({s['lat']:.5f}, {s['lng']:.5f}) | {text(s.get('source'))[:28]}{tail}")

    sections = [
        ("🌍 מחוץ לישראל", sorted(r["outside"], key=lambda x: x["id"]), ""),
        ("🌊 בים", sorted(r["water"], key=lambda x: x["id"]), "reason"),
        ("❔ חשודות חוף שלא אומתו", r["unverified"], "reason"),
        ("📍 רחוקות מהעיר >25 ק\"מ", sorted(r["high_dist"], key=lambda x: -x["distance_km"]), "dist"),
        ("📍 רחוקות מהעיר 12-25 ק\"מ", sorted(r["med_dist"], key=lambda x: -x["distance_km"]), "dist"),
    ]
    for title, rows, kind in sections:
        if not rows:
            continue
        print(f"\n{title} ({len(rows)}), top 10:")
        for s in rows[:10]:
            tail = f" | {s['distance_km']:.1f} ק\"מ" if kind == "dist" else ""
            row(s, tail)
            if kind == "dist":
                print(f"         {s['verdict']}")
            if kind == "reason":
                print(f"         {text(s.get('reason'))[:70]}")

    if r["no_city"]:
        print(f"\n🏷️  בלי עיר ({len(r['no_city'])}), top 10:")
        for s in r["no_city"][:10]:
            row(s, f" | הצעה: {s['suggested_city'] or '-'} ({s['suggest_how']})")

    if r["dup_pairs"]:
        print(f"\n🔍 כפילויות ({len(r['dup_pairs'])}), top 10 לפי מרחק:")
        for p in r["dup_pairs"][:10]:
            print(f"  [{p['id_a']}] {p['name_a'][:30]:30s} ↔ "
                  f"[{p['id_b']}] {p['name_b'][:30]:30s}  "
                  f"{p['distance_m']}מ'  ({p['match_reason']})")
            print(f"         המלצה: להשאיר {p['recommended_keep']} — {p['keep_reason'][:60]}")

    print("\n" + bar)
    print("⛔ לא בוצעו שינויים בנתונים — דוח בלבד!")
    print(bar)


# ── main ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Audit EV station locations (read-only)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Scan only the first N stations")
    parser.add_argument("--out", type=str, default=str(DEFAULT_REPORT),
                        help="Output report path")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Read-only mode. Always on: this tool never modifies "
                             "station data; the flag exists so callers can be explicit.")
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    if out_path in (STATIONS_JSON.resolve(), STATIONS_DB.resolve()):
        sys.exit(f"Refusing to write the report over a data file: {out_path}")

    print("🔍 EV Station Location Audit")
    print(f"   Data source: {STATIONS_JSON}")
    print("   Mode: DRY-RUN (read-only, report only)")

    t0 = time.time()

    stations, total = load_stations(args.limit)
    scanned = len(stations)
    print(f"   Loaded {scanned} stations (total in file: {total})")

    polygon = load_israel_polygon()
    if polygon:
        print(f"   Israel boundary polygon: {len(polygon)} points")
    else:
        print("   ⚠ No Israel boundary polygon found (water detection less accurate)")

    nominatim = NominatimClient()

    if CITY_CACHE.exists():
        with open(CITY_CACHE, "r", encoding="utf-8") as f:
            city_cache = json.load(f)
        print(f"   City center cache: {len(city_cache)} entries loaded")
    else:
        city_cache = {}

    water, outside, unverified = audit_water(stations, nominatim, polygon)
    high_dist, med_dist, no_city, city_not_found = audit_city_distance(
        stations, nominatim, city_cache)
    dup_pairs = audit_duplicates(stations)

    results = {
        "total": total, "scanned": scanned,
        "water": water, "outside": outside, "unverified": unverified,
        "high_dist": high_dist, "med_dist": med_dist,
        "no_city": no_city, "city_not_found": city_not_found,
        "dup_pairs": dup_pairs,
        "nom_requests": nominatim.request_count,
        "nom_429": nominatim.errors_429,
        "nom_failures": nominatim.failures,
        "elapsed": time.time() - t0,
    }

    generate_report(results, out_path)
    print(f"\n📝 Report saved to: {out_path}")
    print_summary(results)


if __name__ == "__main__":
    main()
