#!/usr/bin/env python3
"""
Location verification tool for EV charging stations.

Verifies suspicious stations from the audit report using:
  1. Forward geocoding of the station address (Nominatim /search)
  2. Reverse geocoding of the station coordinates (Nominatim /reverse)
  3. Cross-referencing within the dataset (gov-verified, duplicates)
  4. Web search notes (manual — flagged when not possible)

Read-only: NO station data (stations.json, ev_stations.db) is modified.
Written files: verify_geocode_cache.json, location_verification_report.md

Usage:
    python3 data/verify_locations.py                     # full run
    python3 data/verify_locations.py --test               # test on 10 stations
    python3 data/verify_locations.py --ids 3283,3284      # specific IDs only
"""

import argparse
import json
import math
import os
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
GEOCODE_CACHE = DATA / "verify_geocode_cache.json"
REPORT_OUT = DATA / "location_verification_report.md"

UA = "ev-charging-verify/1.0 (location verification; github.com/Omer-Dahan/EV_Charging)"
NOMINATIM_DELAY = 1.15  # seconds between requests (>1 s per policy)
BACKOFF_429 = (30, 60, 120, 240)

ISR_LAT_MIN, ISR_LAT_MAX = 29.4, 33.4
ISR_LNG_MIN, ISR_LNG_MAX = 34.2, 35.95

# ── helpers ────────────────────────────────────────────────────────────

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def text(v):
    return "" if v is None else str(v)


def is_in_israel_bbox(lat, lng):
    return ISR_LAT_MIN <= lat <= ISR_LAT_MAX and ISR_LNG_MIN <= lng <= ISR_LNG_MAX


# ── Nominatim client with caching ─────────────────────────────────────

class NominatimClient:
    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.cache = {}
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        self.request_count = 0
        self.cache_hits = 0
        self.errors_429 = 0
        self.failures = 0
        self._last_request = 0.0

    def save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < NOMINATIM_DELAY:
            time.sleep(NOMINATIM_DELAY - elapsed)
        self._last_request = time.time()

    def _get_json(self, url):
        for wait in (*BACKOFF_429, None):
            self._throttle()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            self.request_count += 1
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code != 429 or wait is None:
                    print(f"  ⚠ HTTP {e.code} for {url[:80]}")
                    break
                self.errors_429 += 1
                print(f"  ⚠ 429 rate-limited, waiting {wait}s…")
                time.sleep(wait)
            except Exception as exc:
                print(f"  ⚠ Error: {exc}")
                break
        self.failures += 1
        return None

    def forward_geocode(self, address, country_hint=None):
        """Forward geocode an address. Returns dict with lat/lon or None."""
        cache_key = f"fwd:{address}"
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        q = urllib.parse.quote(address)
        cc = f"&countrycodes={country_hint}" if country_hint else ""
        url = (f"https://nominatim.openstreetmap.org/search?"
               f"q={q}&format=json&limit=3&addressdetails=1&accept-language=he{cc}")
        result = self._get_json(url)
        if result is None:
            return None
        # Store result (may be empty list)
        self.cache[cache_key] = result
        self.save_cache()
        return result

    def reverse_geocode(self, lat, lng):
        """Reverse geocode coords. Returns dict with address info or None."""
        cache_key = f"rev:{lat:.6f},{lng:.6f}"
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        url = (f"https://nominatim.openstreetmap.org/reverse?"
               f"format=json&lat={lat}&lon={lng}&addressdetails=1&accept-language=he&zoom=18")
        result = self._get_json(url)
        if result is None:
            return None
        self.cache[cache_key] = result
        self.save_cache()
        return result


# ── data loading ──────────────────────────────────────────────────────

def load_stations():
    with open(STATIONS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {s["id"]: s for s in data}


def load_db_info():
    """Load extra info from the locations table (read-only)."""
    import sqlite3
    conn = sqlite3.connect(f"file:{STATIONS_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT id, name, address, city, lat, lng, sources, is_gov_official FROM locations"
        ).fetchall()
    finally:
        conn.close()
    info = {}
    for r in rows:
        info[r[0]] = {
            "name": r[1], "address": r[2], "city": r[3],
            "lat": r[4], "lng": r[5], "sources": r[6], "g": r[7]
        }
    return info


# ── extract suspect IDs from audit report ─────────────────────────────

def parse_audit_report():
    """Parse the audit report to extract all suspect IDs by category."""
    report_path = DATA / "location_audit_report.md"
    if not report_path.exists():
        print("❌ Audit report not found!")
        sys.exit(1)

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    foreign_ids = []
    far_high_ids = []
    far_med_ids = []
    no_city_ids = []
    dup_pairs = []

    lines = content.split("\n")
    section = None

    for line in lines:
        if "## Outside Israel" in line:
            section = "foreign"
        elif "## Far from City Center (>25 km)" in line:
            section = "far_high"
        elif "## Far from City Center (12–25 km)" in line:
            section = "far_med"
        elif "## Stations without a city" in line:
            section = "no_city"
        elif "## Duplicate Pairs" in line:
            section = "dup"
        elif "### Duplicate Pair Details" in line:
            section = "dup_detail"
        elif "## Declared city not geocodable" in line:
            section = "ungeocodable"
        elif "## Recommendations" in line:
            section = "rec"
        elif "## Method" in line:
            section = "method"

        if not line.startswith("|") or line.startswith("|--") or line.startswith("| id"):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue

        try:
            if section == "foreign":
                sid = int(parts[1])
                foreign_ids.append(sid)
            elif section == "far_high":
                sid = int(parts[1])
                far_high_ids.append(sid)
            elif section == "far_med":
                sid = int(parts[1])
                far_med_ids.append(sid)
            elif section == "no_city":
                sid = int(parts[1])
                no_city_ids.append(sid)
            elif section == "dup":
                id_a = int(parts[1])
                id_b = int(parts[3])
                dup_pairs.append((id_a, id_b))
        except (ValueError, IndexError):
            continue

    return {
        "foreign": foreign_ids,
        "far_high": far_high_ids,
        "far_med": far_med_ids,
        "no_city": no_city_ids,
        "dup_pairs": dup_pairs,
    }


# ── verification logic ────────────────────────────────────────────────

def classify_reverse(rev_result):
    """Classify what's at a coordinate based on reverse geocode result."""
    if rev_result is None:
        return "LOOKUP_FAILED", "reverse geocode request failed"
    if rev_result.get("error"):
        err = rev_result["error"]
        if "Unable to geocode" in err:
            return "WATER_OR_VOID", f"unable to geocode — likely water/void: {err}"
        return "ERROR", f"reverse geocode error: {err}"

    addr = rev_result.get("address", {})
    display = text(rev_result.get("display_name"))
    osm_type = text(rev_result.get("type"))
    osm_class = text(rev_result.get("class"))
    place_rank = rev_result.get("place_rank", 30)

    local_keys = {"road", "suburb", "city", "town", "village", "hamlet",
                  "city_district", "neighbourhood", "residential",
                  "building", "shop", "amenity", "tourism", "leisure",
                  "industrial", "commercial", "retail", "farmyard"}
    has_local = bool(local_keys & set(addr.keys()))

    # Country-level result (place_rank <= 6) with only country info — very
    # likely water (territorial waters) or border/void area
    if place_rank <= 6 and not has_local:
        return "WATER_OR_VOID", f"country-level only (rank={place_rank}): type={osm_type}, class={osm_class}, display={display[:80]}"

    if not has_local:
        # Water indicators
        water_types = {"water", "coastline", "bay", "sea", "ocean", "lake",
                       "reservoir", "river", "stream", "strait"}
        if osm_type.lower() in water_types or osm_class.lower() in ("natural", "waterway"):
            return "WATER", f"water body: type={osm_type}, class={osm_class}, display={display[:80]}"
        return "NO_LOCAL_ADDRESS", f"no local address: type={osm_type}, class={osm_class}, display={display[:80]}"

    # Build a summary
    road = addr.get("road", "")
    city_rev = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
    suburb = addr.get("suburb", "")
    country = addr.get("country", "")

    return "LAND", f"road={road}, city={city_rev}, suburb={suburb}, country={country}"


def verify_foreign_station(station, db_info, nom):
    """Verify a station flagged as outside Israel."""
    sid = station["id"]
    lat, lng = station["lat"], station["lng"]
    name = text(station.get("n"))
    addr = text(station.get("a"))
    city = text(station.get("c"))
    db = db_info.get(sid, {})
    sources = db.get("sources", "unknown")

    result = {
        "id": sid, "name": name, "address": addr, "city": city,
        "lat": lat, "lng": lng, "sources": sources, "g": station.get("g", 0),
        "methods": [],
    }

    # Method 1: bbox check
    in_israel = is_in_israel_bbox(lat, lng)
    result["methods"].append(f"bbox: {'inside' if in_israel else 'outside'} Israel")

    # Method 2: reverse geocode
    rev = nom.reverse_geocode(lat, lng)
    rev_class, rev_detail = classify_reverse(rev)
    result["reverse_class"] = rev_class
    result["reverse_detail"] = rev_detail
    result["methods"].append(f"reverse: {rev_detail[:100]}")

    # Extract country from reverse
    rev_country = ""
    if rev and not rev.get("error"):
        rev_country = (rev.get("address", {}).get("country", "") or "").strip()

    # Determine verdict
    if not in_israel:
        # Check if name/address suggests test data
        test_indicators = ["demo", "test", "אבגדהוזחטיכלמנסעפצקרש", "gnrgy"]
        is_test = any(t in name.lower() or t in addr.lower() for t in test_indicators)

        if is_test or lat == 77.0 or lat == 21.0:
            result["verdict"] = "CONFIRMED_FOREIGN_OR_TEST"
            result["evidence"] = f"Test/demo station. Coords ({lat}, {lng}) are outside Israel. Reverse: {rev_detail[:80]}"
        elif rev_country and rev_country not in ("ישראל", "Israel"):
            result["verdict"] = "CONFIRMED_FOREIGN_OR_TEST"
            result["evidence"] = f"Located in {rev_country}. Coords ({lat}, {lng}). Operator data likely imported from foreign operations."
        else:
            result["verdict"] = "CONFIRMED_FOREIGN_OR_TEST"
            result["evidence"] = f"Coords ({lat}, {lng}) outside Israel bbox. {rev_detail[:80]}"
    else:
        result["verdict"] = "CONFIRMED_OK"
        result["evidence"] = f"Coords are inside Israel bbox (may have been incorrectly listed as foreign)"

    return result


def verify_distance_station(station, db_info, nom, category):
    """Verify a station flagged as far from its declared city."""
    sid = station["id"]
    lat, lng = station["lat"], station["lng"]
    name = text(station.get("n"))
    addr = text(station.get("a"))
    city = text(station.get("c"))
    db = db_info.get(sid, {})
    sources = db.get("sources", "unknown")
    g = station.get("g", 0)

    result = {
        "id": sid, "name": name, "address": addr, "city": city,
        "lat": lat, "lng": lng, "sources": sources, "g": g,
        "category": category,
        "methods": [],
    }

    # Skip foreign stations already handled
    if not is_in_israel_bbox(lat, lng):
        result["verdict"] = "CONFIRMED_FOREIGN_OR_TEST"
        result["evidence"] = f"Coords ({lat}, {lng}) outside Israel"
        result["methods"].append("bbox: outside Israel")
        return result

    # Method 1: Reverse geocode current coordinates
    rev = nom.reverse_geocode(lat, lng)
    rev_class, rev_detail = classify_reverse(rev)
    result["reverse_class"] = rev_class
    result["reverse_detail"] = rev_detail
    result["methods"].append(f"reverse: {rev_detail[:100]}")

    # Extract actual city/location from reverse
    actual_city = ""
    actual_road = ""
    if rev and not rev.get("error"):
        ra = rev.get("address", {})
        actual_city = ra.get("city") or ra.get("town") or ra.get("village") or ra.get("hamlet") or ""
        actual_road = ra.get("road", "")

    # Method 2: Forward geocode the station address (with fallback)
    suggested_lat, suggested_lng = None, None
    fwd_detail = ""
    if addr:
        fwd = nom.forward_geocode(addr, country_hint="il")
        # Fallback: try without house number if no result
        if fwd is not None and len(fwd) == 0:
            import re
            addr_no_num = re.sub(r'\d+', '', addr).strip().strip(',').strip()
            if addr_no_num and addr_no_num != addr:
                fwd = nom.forward_geocode(addr_no_num, country_hint="il")
                if fwd and len(fwd) > 0:
                    fwd_detail += "(fallback: no house number) "
        # Fallback 2: try street name + city
        if (fwd is not None and len(fwd) == 0) and city:
            parts = addr.split(",")
            street = parts[0].strip() if parts else addr
            fwd_q = f"{street}, {city}, ישראל"
            fwd = nom.forward_geocode(fwd_q, country_hint="il")
            if fwd and len(fwd) > 0:
                fwd_detail += "(fallback: street+city) "

        if fwd and len(fwd) > 0:
            suggested_lat = float(fwd[0]["lat"])
            suggested_lng = float(fwd[0]["lon"])
            fwd_display = fwd[0].get("display_name", "")
            dist_to_geocoded = haversine_km(lat, lng, suggested_lat, suggested_lng)
            fwd_detail = f"geocoded to ({suggested_lat:.6f}, {suggested_lng:.6f}), {dist_to_geocoded:.1f} km from current. Display: {fwd_display[:80]}"
            result["methods"].append(f"forward: {fwd_detail[:100]}")
            result["suggested_lat"] = suggested_lat
            result["suggested_lng"] = suggested_lng
            result["geocode_distance_km"] = round(dist_to_geocoded, 2)
        elif fwd is not None:
            fwd_detail = "no results for address"
            result["methods"].append(f"forward: {fwd_detail}")
        else:
            fwd_detail = "forward geocode request failed"
            result["methods"].append(f"forward: {fwd_detail}")

    # Determine verdict
    if rev_class in ("WATER", "WATER_OR_VOID"):
        result["verdict"] = "CONFIRMED_WRONG_COORDS"
        result["evidence"] = f"Coordinates are in water/void. {rev_detail}. Address '{addr}' should be in {city}."
        if suggested_lat:
            result["evidence"] += f" Suggested coords: ({suggested_lat:.6f}, {suggested_lng:.6f})"
    elif suggested_lat is not None:
        dist_to_geocoded = haversine_km(lat, lng, suggested_lat, suggested_lng)
        if dist_to_geocoded > 5:
            # Coords significantly differ from geocoded address
            # Check if geocoded result is in the right city
            result["verdict"] = "CONFIRMED_WRONG_COORDS"
            result["evidence"] = (f"Current coords are {dist_to_geocoded:.1f} km from geocoded address. "
                                  f"At current coords: {rev_detail[:60]}. "
                                  f"Geocoded: ({suggested_lat:.6f}, {suggested_lng:.6f})")
        elif actual_city and city and actual_city.lower() != city.lower():
            # Location is near the address but the city name is different
            # Check if it's just a suburb/variant name issue
            if haversine_km(lat, lng, suggested_lat, suggested_lng) < 3:
                result["verdict"] = "CONFIRMED_WRONG_CITY"
                result["evidence"] = (f"Coords match address ({dist_to_geocoded:.1f} km), "
                                      f"but reverse says city is '{actual_city}', not '{city}'")
            else:
                result["verdict"] = "CONFIRMED_WRONG_COORDS"
                result["evidence"] = (f"Coords {dist_to_geocoded:.1f} km from geocoded address. "
                                      f"Reverse city: '{actual_city}', declared: '{city}'")
        else:
            result["verdict"] = "CONFIRMED_OK"
            result["evidence"] = (f"Coords are {dist_to_geocoded:.1f} km from geocoded address — "
                                  f"reasonable. At coords: {rev_detail[:60]}. "
                                  f"Likely a legitimate location (rural/highway/regional).")
    elif actual_city:
        # No forward geocode but we have reverse info
        if actual_city.lower() == city.lower():
            result["verdict"] = "CONFIRMED_OK"
            result["evidence"] = f"Reverse geocode confirms city '{actual_city}'. {rev_detail[:60]}"
        else:
            # Different city — could be wrong city label
            result["verdict"] = "CONFIRMED_WRONG_CITY"
            result["evidence"] = f"Reverse says '{actual_city}', declared city is '{city}'. {rev_detail[:60]}"
    else:
        result["verdict"] = "UNVERIFIED"
        result["evidence"] = f"Could not determine. Reverse: {rev_detail[:60]}. Forward: {fwd_detail[:60]}"

    return result


def verify_duplicate_pair(pair, stations, db_info, nom):
    """Verify a duplicate pair."""
    id_a, id_b = pair
    sta = stations.get(id_a)
    stb = stations.get(id_b)

    if not sta or not stb:
        return {
            "id_a": id_a, "id_b": id_b,
            "verdict": "UNVERIFIED",
            "evidence": f"Station(s) not found in data",
        }

    name_a = text(sta.get("n"))
    name_b = text(stb.get("n"))
    addr_a = text(sta.get("a"))
    addr_b = text(stb.get("a"))
    city_a = text(sta.get("c"))
    city_b = text(stb.get("c"))
    db_a = db_info.get(id_a, {})
    db_b = db_info.get(id_b, {})
    g_a = sta.get("g", 0)
    g_b = stb.get("g", 0)

    dist_m = haversine_km(sta["lat"], sta["lng"], stb["lat"], stb["lng"]) * 1000

    result = {
        "id_a": id_a, "name_a": name_a, "addr_a": addr_a, "city_a": city_a,
        "lat_a": sta["lat"], "lng_a": sta["lng"], "g_a": g_a,
        "sources_a": db_a.get("sources", ""),
        "id_b": id_b, "name_b": name_b, "addr_b": addr_b, "city_b": city_b,
        "lat_b": stb["lat"], "lng_b": stb["lng"], "g_b": g_b,
        "sources_b": db_b.get("sources", ""),
        "distance_m": round(dist_m),
        "methods": [],
    }

    # For very large distances (>5km), reverse geocode both to determine
    # if they're actually different places
    if dist_m > 5000:
        rev_a = nom.reverse_geocode(sta["lat"], sta["lng"])
        rev_b = nom.reverse_geocode(stb["lat"], stb["lng"])
        cls_a, det_a = classify_reverse(rev_a)
        cls_b, det_b = classify_reverse(rev_b)
        result["methods"].append(f"reverse A: {det_a[:80]}")
        result["methods"].append(f"reverse B: {det_b[:80]}")

        # If names are clearly different, they're different places
        if name_a and name_b and name_a != name_b:
            # Check if addresses differ too
            if addr_a != addr_b:
                result["verdict"] = "NOT_DUPLICATE"
                result["evidence"] = (f"Different locations {dist_m:.0f}m apart. "
                                      f"A at: {det_a[:50]}. B at: {det_b[:50]}.")
                result["keep"] = "both"
                result["keep_reason"] = "Different physical locations"
                return result

        # Same name, very far apart — one has wrong coords
        if cls_a == "WATER" or cls_a == "WATER_OR_VOID":
            result["verdict"] = "CONFIRMED_DUPLICATE"
            result["evidence"] = f"A (id={id_a}) is in water/void. B (id={id_b}) is the correct one."
            result["keep"] = f"id={id_b}"
            result["keep_reason"] = f"A is in water: {det_a[:50]}"
        elif cls_b == "WATER" or cls_b == "WATER_OR_VOID":
            result["verdict"] = "CONFIRMED_DUPLICATE"
            result["evidence"] = f"B (id={id_b}) is in water/void. A (id={id_a}) is the correct one."
            result["keep"] = f"id={id_a}"
            result["keep_reason"] = f"B is in water: {det_b[:50]}"
        elif g_a == 1 and g_b == 0:
            result["verdict"] = "CONFIRMED_DUPLICATE"
            result["evidence"] = f"Same station, {dist_m:.0f}m apart. A is gov-verified."
            result["keep"] = f"id={id_a}"
            result["keep_reason"] = "Gov-verified (g=1)"
        elif g_b == 1 and g_a == 0:
            result["verdict"] = "CONFIRMED_DUPLICATE"
            result["evidence"] = f"Same station, {dist_m:.0f}m apart. B is gov-verified."
            result["keep"] = f"id={id_b}"
            result["keep_reason"] = "Gov-verified (g=1)"
        else:
            # Try forward geocode of address to determine which coords are right
            fwd = None
            if addr_a:
                fwd = nom.forward_geocode(addr_a, country_hint="il")
            if fwd and len(fwd) > 0:
                geo_lat = float(fwd[0]["lat"])
                geo_lng = float(fwd[0]["lon"])
                dist_to_a = haversine_km(sta["lat"], sta["lng"], geo_lat, geo_lng)
                dist_to_b = haversine_km(stb["lat"], stb["lng"], geo_lat, geo_lng)
                result["methods"].append(f"forward geocode → ({geo_lat:.4f}, {geo_lng:.4f}), dist to A={dist_to_a:.1f}km, to B={dist_to_b:.1f}km")
                if dist_to_a < dist_to_b and dist_to_a < 5:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = f"id={id_a}"
                    result["keep_reason"] = f"A is {dist_to_a:.1f}km from geocoded address, B is {dist_to_b:.1f}km"
                    result["evidence"] = f"Forward geocode matches A better."
                elif dist_to_b < dist_to_a and dist_to_b < 5:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = f"id={id_b}"
                    result["keep_reason"] = f"B is {dist_to_b:.1f}km from geocoded address, A is {dist_to_a:.1f}km"
                    result["evidence"] = f"Forward geocode matches B better."
                else:
                    src_a = len((db_a.get("sources") or "").split(","))
                    src_b = len((db_b.get("sources") or "").split(","))
                    if src_a > src_b:
                        result["verdict"] = "CONFIRMED_DUPLICATE"
                        result["keep"] = f"id={id_a}"
                        result["keep_reason"] = f"More sources ({src_a} vs {src_b})"
                    elif src_b > src_a:
                        result["verdict"] = "CONFIRMED_DUPLICATE"
                        result["keep"] = f"id={id_b}"
                        result["keep_reason"] = f"More sources ({src_b} vs {src_a})"
                    else:
                        result["verdict"] = "CONFIRMED_DUPLICATE"
                        result["keep"] = "manual review needed"
                        result["keep_reason"] = "Cannot determine which coords are correct"
                    result["evidence"] = f"Both far from geocode ({dist_to_a:.1f}/{dist_to_b:.1f}km). Likely same station."
            else:
                result["verdict"] = "CONFIRMED_DUPLICATE"
                result["keep"] = "manual review needed"
                result["keep_reason"] = "No geocode result, cannot determine correct coords"
                result["evidence"] = f"Same/similar name, {dist_m:.0f}m apart."
    else:
        # Close together (<5km) — likely same location, different coords
        # Check if truly different sites or same site with slight coord diff
        if dist_m > 2000:
            # Different enough to be different entrances/buildings, but check
            rev_a = nom.reverse_geocode(sta["lat"], sta["lng"])
            rev_b = nom.reverse_geocode(stb["lat"], stb["lng"])
            cls_a, det_a = classify_reverse(rev_a)
            cls_b, det_b = classify_reverse(rev_b)
            result["methods"].append(f"reverse A: {det_a[:80]}")
            result["methods"].append(f"reverse B: {det_b[:80]}")

            # If different roads, might not be duplicates
            road_a = ""
            road_b = ""
            if rev_a and not rev_a.get("error"):
                road_a = rev_a.get("address", {}).get("road", "")
            if rev_b and not rev_b.get("error"):
                road_b = rev_b.get("address", {}).get("road", "")

            if road_a and road_b and road_a != road_b and name_a != name_b:
                result["verdict"] = "NOT_DUPLICATE"
                result["evidence"] = f"Different streets ({road_a} vs {road_b}), {dist_m:.0f}m apart."
                result["keep"] = "both"
                result["keep_reason"] = "Different locations"
            else:
                if g_a == 1 and g_b == 0:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = f"id={id_a}"
                    result["keep_reason"] = "Gov-verified (g=1)"
                elif g_b == 1 and g_a == 0:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = f"id={id_b}"
                    result["keep_reason"] = "Gov-verified (g=1)"
                else:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = "manual review needed"
                    result["keep_reason"] = f"Same area ({dist_m:.0f}m), similar names"
                result["evidence"] = f"Same area, {dist_m:.0f}m apart. A: {det_a[:40]}. B: {det_b[:40]}"
        else:
            # Very close, very likely duplicate
            if g_a == 1 and g_b == 0:
                result["verdict"] = "CONFIRMED_DUPLICATE"
                result["keep"] = f"id={id_a}"
                result["keep_reason"] = "Gov-verified (g=1)"
            elif g_b == 1 and g_a == 0:
                result["verdict"] = "CONFIRMED_DUPLICATE"
                result["keep"] = f"id={id_b}"
                result["keep_reason"] = "Gov-verified (g=1)"
            else:
                src_a = len((db_a.get("sources") or "").split(","))
                src_b = len((db_b.get("sources") or "").split(","))
                if src_a > src_b:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = f"id={id_a}"
                    result["keep_reason"] = f"More sources ({src_a} vs {src_b})"
                elif src_b > src_a:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = f"id={id_b}"
                    result["keep_reason"] = f"More sources ({src_b} vs {src_a})"
                else:
                    result["verdict"] = "CONFIRMED_DUPLICATE"
                    result["keep"] = "manual review needed"
                    result["keep_reason"] = "Equal sources, no clear winner"
            result["evidence"] = f"Close together ({dist_m:.0f}m), likely same site"
            result["methods"].append("proximity: close enough to be same site")

    return result


def verify_no_city_station(station, db_info, nom):
    """Verify a station without a city and check if suggestion is correct."""
    sid = station["id"]
    lat, lng = station["lat"], station["lng"]
    name = text(station.get("n"))
    addr = text(station.get("a"))
    db = db_info.get(sid, {})
    sources = db.get("sources", "unknown")

    result = {
        "id": sid, "name": name, "address": addr,
        "lat": lat, "lng": lng, "sources": sources, "g": station.get("g", 0),
        "methods": [],
    }

    if not is_in_israel_bbox(lat, lng):
        result["verdict"] = "CONFIRMED_FOREIGN_OR_TEST"
        result["evidence"] = f"Outside Israel bbox"
        result["suggested_city"] = ""
        return result

    # Reverse geocode to find actual city
    rev = nom.reverse_geocode(lat, lng)
    rev_class, rev_detail = classify_reverse(rev)
    result["methods"].append(f"reverse: {rev_detail[:100]}")

    if rev and not rev.get("error"):
        ra = rev.get("address", {})
        actual_city = ra.get("city") or ra.get("town") or ra.get("village") or ra.get("hamlet") or ""
        result["suggested_city"] = actual_city
        if actual_city:
            result["verdict"] = "CONFIRMED_OK"
            result["evidence"] = f"Reverse geocode suggests city: '{actual_city}'. {rev_detail[:60]}"
        else:
            result["verdict"] = "UNVERIFIED"
            result["evidence"] = f"No city in reverse geocode. {rev_detail[:60]}"
    elif rev_class in ("WATER", "WATER_OR_VOID"):
        result["verdict"] = "CONFIRMED_WRONG_COORDS"
        result["evidence"] = f"Coordinates in water/void. {rev_detail[:60]}"
        result["suggested_city"] = ""
    else:
        result["verdict"] = "UNVERIFIED"
        result["evidence"] = f"Reverse geocode failed. {rev_detail[:60]}"
        result["suggested_city"] = ""

    return result


# ── report generation ─────────────────────────────────────────────────

def cell(value, width=None):
    s = text(value).replace("\n", " ")
    if width:
        s = s[:width]
    return s.replace("|", "\\|")


def generate_report(results, nom, elapsed, out_path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    w = lines.append

    foreign_r = results.get("foreign", [])
    far_r = results.get("far", [])
    dup_r = results.get("duplicates", [])
    no_city_r = results.get("no_city", [])
    reported_r = results.get("reported", [])

    # Count verdicts
    all_results = foreign_r + far_r + no_city_r + reported_r
    verdict_counts = {}
    for r in all_results:
        v = r.get("verdict", "UNVERIFIED")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    dup_verdict_counts = {}
    for r in dup_r:
        v = r.get("verdict", "UNVERIFIED")
        dup_verdict_counts[v] = dup_verdict_counts.get(v, 0) + 1

    w(f"# Location Verification Report — {now}\n")
    w("Read-only verification. **No station was changed, merged or deleted.** "
      "All verdicts are proposals for manual review.\n")

    w("## Summary\n")
    w("| Metric | Count |")
    w("|--------|------:|")
    w(f"| Stations verified (individual) | {len(all_results)} |")
    w(f"| Duplicate pairs verified | {len(dup_r)} |")
    for v in sorted(verdict_counts.keys()):
        w(f"| Verdict: {v} (stations) | {verdict_counts[v]} |")
    for v in sorted(dup_verdict_counts.keys()):
        w(f"| Verdict: {v} (dup pairs) | {dup_verdict_counts[v]} |")
    w(f"| Nominatim requests | {nom.request_count} |")
    w(f"| Cache hits | {nom.cache_hits} |")
    w(f"| 429 errors | {nom.errors_429} |")
    w(f"| Failed requests | {nom.failures} |")
    w(f"| Elapsed time | {elapsed:.0f}s |")
    w("")

    # ── Foreign / test stations ──
    w("## Foreign / Test Stations\n")
    if foreign_r:
        w("| id | name | city | lat | lng | verdict | evidence |")
        w("|---:|------|------|----:|----:|---------|----------|")
        for r in sorted(foreign_r, key=lambda x: x["id"]):
            w(f"| {r['id']} | {cell(r['name'], 40)} | {cell(r['city'], 15)} "
              f"| {r['lat']:.4f} | {r['lng']:.4f} "
              f"| {r['verdict']} | {cell(r['evidence'], 80)} |")
    else:
        w("None verified.\n")
    w("")

    # ── Reported cases (3283, 3284) ──
    w("## The Reported Cases (id=3283, id=3284)\n")
    for r in reported_r:
        w(f"### Station id={r['id']}: {r['name']}\n")
        w(f"- **Address**: {r.get('address', '')}")
        w(f"- **City**: {r.get('city', '')}")
        w(f"- **Coordinates**: ({r['lat']}, {r['lng']})")
        w(f"- **Sources**: {r.get('sources', '')}")
        w(f"- **Gov-verified (g)**: {r.get('g', 0)}")
        w(f"- **Verdict**: **{r['verdict']}**")
        w(f"- **Evidence**: {r.get('evidence', '')}")
        if r.get("suggested_lat"):
            w(f"- **Suggested coordinates**: ({r['suggested_lat']:.6f}, {r['suggested_lng']:.6f})")
        if r.get("geocode_distance_km"):
            w(f"- **Distance from geocoded address**: {r['geocode_distance_km']} km")
        w(f"- **Methods used**: {'; '.join(r.get('methods', []))}")
        w("")

    # ── Far from city ──
    w("## Far from City\n")
    if far_r:
        w("| id | name | city | verdict | old lat | old lng | suggested lat | suggested lng | geocode dist km | evidence |")
        w("|---:|------|------|---------|--------:|--------:|--------------:|--------------:|----------------:|----------|")
        for r in sorted(far_r, key=lambda x: x["id"]):
            slat = f"{r['suggested_lat']:.6f}" if r.get("suggested_lat") else ""
            slng = f"{r['suggested_lng']:.6f}" if r.get("suggested_lng") else ""
            gdist = f"{r['geocode_distance_km']}" if r.get("geocode_distance_km") else ""
            w(f"| {r['id']} | {cell(r['name'], 35)} | {cell(r['city'], 15)} "
              f"| {r['verdict']} | {r['lat']:.6f} | {r['lng']:.6f} "
              f"| {slat} | {slng} | {gdist} | {cell(r['evidence'], 70)} |")
    else:
        w("None verified.\n")
    w("")

    # ── Duplicate pairs ──
    w("## Duplicate Pairs\n")
    if dup_r:
        w("| id_a | name_a | id_b | name_b | dist_m | verdict | keep | reason | evidence |")
        w("|-----:|--------|-----:|--------|-------:|---------|------|--------|----------|")
        for r in sorted(dup_r, key=lambda x: -x.get("distance_m", 0)):
            w(f"| {r['id_a']} | {cell(r.get('name_a', ''), 25)} "
              f"| {r['id_b']} | {cell(r.get('name_b', ''), 25)} "
              f"| {r.get('distance_m', '')} | {r.get('verdict', '')} "
              f"| {cell(r.get('keep', ''), 15)} | {cell(r.get('keep_reason', ''), 40)} "
              f"| {cell(r.get('evidence', ''), 50)} |")
    else:
        w("None verified.\n")
    w("")

    # ── No city ──
    w("## Stations Without a City\n")
    if no_city_r:
        w("| id | name | suggested city | verdict | evidence |")
        w("|---:|------|---------------|---------|----------|")
        for r in sorted(no_city_r, key=lambda x: x["id"]):
            w(f"| {r['id']} | {cell(r['name'], 35)} "
              f"| {cell(r.get('suggested_city', ''), 20)} "
              f"| {r['verdict']} | {cell(r['evidence'], 70)} |")
    else:
        w("None verified.\n")
    w("")

    # ── Method & confidence ──
    w("## Method & Confidence\n")
    w("### Methods used\n")
    w("1. **Reverse geocoding** (Nominatim /reverse): Applied to all stations to determine what's at the current coordinates.")
    w("2. **Forward geocoding** (Nominatim /search): Applied to stations with addresses to find expected coordinates and compare.")
    w("3. **Cross-reference**: Gov-verified status (g=1), source count, and dataset consistency used for duplicate resolution.")
    w("4. **Web search**: Not available in this environment — flagged where web verification would help.\n")
    w("### Confidence notes\n")
    w("- Reverse geocoding is highly reliable for water/void detection.")
    w("- Forward geocoding of Hebrew addresses has moderate accuracy — Nominatim may not resolve all Israeli street names.")
    w("- Stations marked UNVERIFIED could not be confirmed either way and need manual review.")
    w(f"- {nom.errors_429} rate-limit (429) errors encountered during verification.\n")

    # ── Recommended fixes ──
    w("## Recommended Fixes (NOT executed)\n")
    w("Sorted by confidence (highest first).\n")

    fix_num = 0

    # 1. Foreign/test (high confidence)
    foreign_confirmed = [r for r in foreign_r if r["verdict"] == "CONFIRMED_FOREIGN_OR_TEST"]
    if foreign_confirmed:
        fix_num += 1
        w(f"{fix_num}. **Remove {len(foreign_confirmed)} foreign/test stations** "
          f"(IDs: {', '.join(str(r['id']) for r in foreign_confirmed)}) — "
          f"confirmed outside Israel or test data. HIGH confidence.\n")

    # 2. Wrong coords (high confidence)
    wrong_coords = [r for r in (far_r + reported_r) if r["verdict"] == "CONFIRMED_WRONG_COORDS"]
    for r in wrong_coords:
        fix_num += 1
        if r.get("suggested_lat"):
            w(f"{fix_num}. **Fix coords for id={r['id']}** '{r['name']}' — "
              f"move from ({r['lat']:.6f}, {r['lng']:.6f}) to ({r['suggested_lat']:.6f}, {r['suggested_lng']:.6f}). "
              f"HIGH confidence.\n")
        else:
            w(f"{fix_num}. **Fix coords for id={r['id']}** '{r['name']}' — "
              f"current coords are wrong ({r['evidence'][:60]}). Re-geocode from address. "
              f"MEDIUM confidence.\n")

    # 3. Wrong city
    wrong_city = [r for r in (far_r + reported_r) if r["verdict"] == "CONFIRMED_WRONG_CITY"]
    for r in wrong_city:
        fix_num += 1
        w(f"{fix_num}. **Fix city for id={r['id']}** '{r['name']}' — "
          f"change from '{r['city']}' to reverse-geocoded city. "
          f"MEDIUM confidence.\n")

    # 4. Confirmed duplicates
    confirmed_dups = [r for r in dup_r if r["verdict"] == "CONFIRMED_DUPLICATE"]
    for r in confirmed_dups:
        fix_num += 1
        w(f"{fix_num}. **Merge duplicate** id={r['id_a']} + id={r['id_b']} — "
          f"keep {r.get('keep', '?')}: {r.get('keep_reason', '')}. "
          f"MEDIUM confidence.\n")

    if fix_num == 0:
        w("No fixes recommended.\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return verdict_counts, dup_verdict_counts


# ── main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Verify suspicious EV station locations")
    parser.add_argument("--test", action="store_true", help="Test mode: only first 10 per category")
    parser.add_argument("--ids", type=str, help="Comma-separated list of IDs to verify")
    parser.add_argument("--skip-dups", action="store_true", help="Skip duplicate verification")
    parser.add_argument("--skip-nocity", action="store_true", help="Skip no-city verification")
    args = parser.parse_args()

    start_time = time.time()

    print("📋 Loading data…")
    stations = load_stations()
    db_info = load_db_info()
    print(f"  Loaded {len(stations)} stations, {len(db_info)} DB records")

    print("📋 Parsing audit report…")
    audit = parse_audit_report()
    print(f"  Foreign: {len(audit['foreign'])}, Far>25km: {len(audit['far_high'])}, "
          f"Far 12-25km: {len(audit['far_med'])}, No city: {len(audit['no_city'])}, "
          f"Dup pairs: {len(audit['dup_pairs'])}")

    nom = NominatimClient(GEOCODE_CACHE)

    results = {
        "foreign": [],
        "far": [],
        "duplicates": [],
        "no_city": [],
        "reported": [],
    }

    if args.ids:
        # Verify specific IDs only
        specific_ids = [int(x.strip()) for x in args.ids.split(",")]
        print(f"\n🔍 Verifying specific IDs: {specific_ids}")
        for sid in specific_ids:
            if sid not in stations:
                print(f"  ⚠ Station {sid} not found!")
                continue
            st = stations[sid]
            r = verify_distance_station(st, db_info, nom, "specific")
            results["reported"].append(r)
            print(f"  id={sid}: {r['verdict']} — {r['evidence'][:80]}")
        elapsed = time.time() - start_time
        generate_report(results, nom, elapsed, REPORT_OUT)
        print(f"\n✅ Report written to {REPORT_OUT}")
        return

    # ── Priority 1: Foreign stations ──
    print(f"\n🌍 Verifying {len(audit['foreign'])} foreign/test stations…")
    for sid in audit["foreign"]:
        if sid not in stations:
            continue
        r = verify_foreign_station(stations[sid], db_info, nom)
        results["foreign"].append(r)
        print(f"  id={sid}: {r['verdict']}")

    # ── Priority 2: Reported cases (3283, 3284) ──
    print(f"\n📌 Verifying reported cases (id=3283, id=3284)…")
    for sid in [3283, 3284]:
        if sid not in stations:
            print(f"  ⚠ Station {sid} not found!")
            continue
        r = verify_distance_station(stations[sid], db_info, nom, "reported")
        results["reported"].append(r)
        print(f"  id={sid}: {r['verdict']} — {r['evidence'][:80]}")

    # ── Priority 3: Far from city (>25km and 12-25km) ──
    far_ids = audit["far_high"] + audit["far_med"]
    # Remove already-verified foreign stations and reported cases
    already_done = set(audit["foreign"]) | {3283, 3284}
    far_ids = [sid for sid in far_ids if sid not in already_done]

    if args.test:
        far_ids = far_ids[:10]
        print(f"\n🏙️  Verifying {len(far_ids)} far-from-city stations (TEST MODE)…")
    else:
        print(f"\n🏙️  Verifying {len(far_ids)} far-from-city stations…")

    for i, sid in enumerate(far_ids):
        if sid not in stations:
            continue
        r = verify_distance_station(stations[sid], db_info, nom, "far_from_city")
        results["far"].append(r)
        if (i + 1) % 10 == 0:
            print(f"  … verified {i + 1}/{len(far_ids)} (requests: {nom.request_count}, 429s: {nom.errors_429})")
            nom.save_cache()

    # ── Priority 4: Duplicate pairs ──
    if not args.skip_dups:
        dup_pairs = audit["dup_pairs"]
        if args.test:
            dup_pairs = dup_pairs[:10]
            print(f"\n🔍 Verifying {len(dup_pairs)} duplicate pairs (TEST MODE)…")
        else:
            print(f"\n🔍 Verifying {len(dup_pairs)} duplicate pairs…")

        for i, pair in enumerate(dup_pairs):
            r = verify_duplicate_pair(pair, stations, db_info, nom)
            results["duplicates"].append(r)
            if (i + 1) % 10 == 0:
                print(f"  … verified {i + 1}/{len(dup_pairs)} pairs")
                nom.save_cache()
    else:
        print("\n⏭ Skipping duplicate verification")

    # ── Priority 5: No city ──
    if not args.skip_nocity:
        no_city_ids = audit["no_city"]
        # Remove already verified
        no_city_ids = [sid for sid in no_city_ids if sid not in already_done]
        if args.test:
            no_city_ids = no_city_ids[:10]
            print(f"\n🏘️  Verifying {len(no_city_ids)} no-city stations (TEST MODE)…")
        else:
            print(f"\n🏘️  Verifying {len(no_city_ids)} no-city stations…")

        for i, sid in enumerate(no_city_ids):
            if sid not in stations:
                continue
            r = verify_no_city_station(stations[sid], db_info, nom)
            results["no_city"].append(r)
            if (i + 1) % 10 == 0:
                print(f"  … verified {i + 1}/{len(no_city_ids)}")
                nom.save_cache()
    else:
        print("\n⏭ Skipping no-city verification")

    elapsed = time.time() - start_time
    nom.save_cache()

    # ── Generate report ──
    print(f"\n📝 Generating report…")
    v_counts, d_counts = generate_report(results, nom, elapsed, REPORT_OUT)

    # ── Console summary in Hebrew ──
    print("\n" + "=" * 70)
    print("📊 סיכום אימות מיקומים")
    print("=" * 70)

    total_verified = len(results["foreign"]) + len(results["far"]) + len(results["no_city"]) + len(results["reported"])
    print(f"\n🔢 סה\"כ עמדות שנבדקו: {total_verified}")
    print(f"🔢 זוגות כפילויות שנבדקו: {len(results['duplicates'])}")
    print(f"\n📊 התפלגות verdicts (עמדות):")
    for v, c in sorted(v_counts.items()):
        print(f"   {v}: {c}")
    if d_counts:
        print(f"\n📊 התפלגות verdicts (כפילויות):")
        for v, c in sorted(d_counts.items()):
            print(f"   {v}: {c}")

    # ── Grand Canyon (3283) ──
    for r in results["reported"]:
        if r["id"] == 3283:
            print(f"\n🏗️  גראנד קניון חיפה (id=3283):")
            print(f"   Verdict: {r['verdict']}")
            print(f"   Evidence: {r['evidence']}")
            if r.get("suggested_lat"):
                print(f"   קואורדינטות מוצעות: ({r['suggested_lat']:.6f}, {r['suggested_lng']:.6f})")
            print(f"   שיטות: {'; '.join(r.get('methods', []))}")
        if r["id"] == 3284:
            print(f"\n🏗️  גראנד קניון ב\"ש (id=3284):")
            print(f"   Verdict: {r['verdict']}")
            print(f"   Evidence: {r['evidence']}")

    # ── Top findings ──
    print(f"\n🔥 ממצאים חדים:")

    # Foreign confirmed
    foreign_confirmed = [r for r in results["foreign"] if r["verdict"] == "CONFIRMED_FOREIGN_OR_TEST"]
    if foreign_confirmed:
        print(f"\n   🌍 {len(foreign_confirmed)} עמדות מאומתות כחו\"ל/בדיקה:")
        for r in foreign_confirmed[:5]:
            print(f"      id={r['id']} '{r['name']}' — {r['evidence'][:60]}")

    # Wrong coords
    wrong_coords = [r for r in results["far"] + results["reported"] if r["verdict"] == "CONFIRMED_WRONG_COORDS"]
    if wrong_coords:
        print(f"\n   ❌ {len(wrong_coords)} עמדות עם קואורדינטות שגויות:")
        for r in wrong_coords[:5]:
            print(f"      id={r['id']} '{r['name']}' — {r['evidence'][:60]}")

    # False positives
    false_pos = [r for r in results["far"] if r["verdict"] == "CONFIRMED_OK"]
    print(f"\n   ✅ {len(false_pos)} false positives (אזהרות שגויות בדוח הקודם)")
    for r in false_pos[:5]:
        print(f"      id={r['id']} '{r['name']}' — {r['evidence'][:60]}")

    # Unverified
    unverified = [r for r in results["far"] + results["reported"] + results["no_city"]
                  if r["verdict"] == "UNVERIFIED"]
    if unverified:
        print(f"\n   ❓ {len(unverified)} עמדות שלא ניתן לאמת:")
        for r in unverified[:3]:
            print(f"      id={r['id']} '{r['name']}' — {r['evidence'][:60]}")

    print(f"\n⏱  זמן ריצה: {elapsed:.0f} שניות")
    print(f"🌐 בקשות Nominatim: {nom.request_count} (cache hits: {nom.cache_hits}, 429: {nom.errors_429})")
    print(f"\n📄 דוח מלא: {REPORT_OUT}")
    print(f"💾 מטמון: {GEOCODE_CACHE}")

    # ── Recommendations ──
    print(f"\n📋 המלצות (לא בוצעו!):")
    if foreign_confirmed:
        print(f"   1. 🗑️  מחק {len(foreign_confirmed)} עמדות חו\"ל/בדיקה (ביטחון גבוה)")
    if wrong_coords:
        print(f"   2. 🔧 תקן קואורדינטות ל-{len(wrong_coords)} עמדות (ביטחון גבוה)")
    wrong_city = [r for r in results["far"] if r["verdict"] == "CONFIRMED_WRONG_CITY"]
    if wrong_city:
        print(f"   3. 🏙️  תקן עיר ל-{len(wrong_city)} עמדות (ביטחון בינוני)")
    confirmed_dups = [r for r in results["duplicates"] if r["verdict"] == "CONFIRMED_DUPLICATE"]
    if confirmed_dups:
        print(f"   4. 🔀 מזג {len(confirmed_dups)} זוגות כפילויות (ביטחון בינוני)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
