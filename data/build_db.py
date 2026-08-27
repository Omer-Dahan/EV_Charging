#!/usr/bin/env python3
"""
EV Charging Stations Database Builder for Israel (v2.1)
======================================================
Builds a unified, enriched SQLite database of EV charging stations in Israel.

Primary Backbone:
- CelloCharge API (Ministry of Energy official real-time platform)
  Providing live statuses, dynamic pricing (tariffsSummary / maxPerKwh),
  connectors specifications, and operator metadata.

Enrichment & Complementary Sources:
- auto.co.il (API with coordinates, enriched operators & connector types)
- evm.co.il (Fast & Ultra-Fast charging stations map with coordinates)
- data.gov.il (Ministry of Energy official static registry via CKAN API)
- paz.co.il / Yellow (Paz Charge DC ultra-fast charging stations network)

Outputs to a SQLite database: ev_stations.db
Designed for recurring execution (idempotent full rebuild with backup).
Uses only Python Standard Library (no external pip dependencies required).
"""

import base64
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ev_stations.db")
BACKUP_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ev_stations_v1_backup.db")
PAZ_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paz_stations_cache.json")

CELLO_TOKEN = "[REDACTED]"
CELLO_BASE = "https://api.prod.ev.cellocharge.com/evsfeed/api/v2/portal"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def normalize_text(s: Optional[str]) -> str:
    """Normalize text for matching (lowercase, strip whitespace, punctuation, non-alphanumeric)."""
    if not s:
        return ""
    s = s.lower().strip()
    # Keep Hebrew letters, Latin alphanumeric characters
    s = re.sub(r"[^\w\u0590-\u05fe]", "", s)
    return s


class SpatialGrid:
    """In-memory 2D spatial grid for fast O(1) radius proximity searches."""

    def __init__(self, cell_size_deg: float = 0.01):
        self.cell_size = cell_size_deg
        self.grid: Dict[Tuple[int, int], List[Tuple[int, float, float]]] = {}

    def insert(self, item_id: int, lat: float, lng: float) -> None:
        gx = int(lat / self.cell_size)
        gy = int(lng / self.cell_size)
        self.grid.setdefault((gx, gy), []).append((item_id, lat, lng))

    def find_nearest(self, lat: float, lng: float, max_dist_meters: float = 150.0) -> Tuple[Optional[int], float]:
        gx = int(lat / self.cell_size)
        gy = int(lng / self.cell_size)
        best_id: Optional[int] = None
        best_dist = float("inf")
        # Check neighboring grid cells (0.01 deg is ~1.1km, 150m is ~0.0015 deg)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = self.grid.get((gx + dx, gy + dy))
                if not cell:
                    continue
                for item_id, c_lat, c_lng in cell:
                    d = haversine_distance(lat, lng, c_lat, c_lng)
                    if d <= max_dist_meters and d < best_dist:
                        best_dist = d
                        best_id = item_id
        return best_id, best_dist


def merge_connectors(
    conns_a: Optional[List[Dict[str, Any]]],
    conns_b: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Merge two connector lists, deduplicating identical connector specs,
    ensuring that if one list is empty, the non-empty list is used.
    """
    a = conns_a or []
    b = conns_b or []
    if not a:
        return list(b)
    if not b:
        return list(a)

    seen = set()
    merged: List[Dict[str, Any]] = []

    for c in a + b:
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

    return merged if merged else list(a or b)


def find_matching_location_id(
    lat: Optional[float],
    lng: Optional[float],
    name: Optional[str],
    address: Optional[str],
    spatial_index: SpatialGrid,
    norm_name_to_ids: Dict[str, List[int]],
    location_coords: Dict[int, Tuple[float, float]],
    max_dist_meters: float = 150.0
) -> Optional[int]:
    """
    Find matching location ID using spatial proximity (<= 150m) or normalized name similarity.
    """
    # 1. Spatial proximity match (<= 150m)
    if lat is not None and lng is not None:
        matched_id, dist = spatial_index.find_nearest(lat, lng, max_dist_meters=max_dist_meters)
        if matched_id is not None:
            return matched_id

    # 2. Normalized name match (with 5km threshold if both have coordinates)
    norm_n = normalize_text(name)
    candidates = norm_name_to_ids.get(norm_n, []) if norm_n else []
    if not candidates and address:
        norm_a = normalize_text(address)
        candidates = norm_name_to_ids.get(norm_a, []) if norm_a else []

    if candidates:
        if lat is not None and lng is not None:
            best_cand = None
            best_dist = float("inf")
            for cid in candidates:
                if cid in location_coords:
                    clat, clng = location_coords[cid]
                    d = haversine_distance(lat, lng, clat, clng)
                    if d <= 5000.0 and d < best_dist:  # Within 5km
                        best_dist = d
                        best_cand = cid
                else:
                    return cid
            if best_cand is not None:
                return best_cand
        else:
            return candidates[0]

    # 3. Spatial proximity match within 300m for candidate with valid name
    if lat is not None and lng is not None and norm_n and len(norm_n) >= 4:
        matched_id, dist = spatial_index.find_nearest(lat, lng, max_dist_meters=300.0)
        if matched_id is not None:
            return matched_id

    return None


# ==============================================================================
# Source 1: CelloCharge (Backbone)
# ==============================================================================

def fetch_cello_data() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetch providers and locations from CelloCharge API.
    Endpoints:
      - GET /providers
      - GET /locations
    """
    print("[1/5] מוריד נתונים מ-CelloCharge API (עמוד השדרה)...")
    headers = {
        "Authorization": f"Bearer {CELLO_TOKEN}",
        "User-Agent": USER_AGENTS[0],
        "Accept": "application/json",
    }

    # 1. Providers lookup
    req_prov = urllib.request.Request(f"{CELLO_BASE}/providers", headers=headers)
    with urllib.request.urlopen(req_prov, timeout=25) as resp:
        providers_raw = json.loads(resp.read().decode("utf-8"))

    providers_map: Dict[str, Dict[str, Any]] = {}
    for p in providers_raw:
        pid = (p.get("id") or "").strip()
        pname = (p.get("name") or pid).strip().replace("\u202f", "").strip()
        providers_map[pid] = {
            "name": pname,
            "phone": (p.get("phone") or "").strip() or None,
            "imageUrl": p.get("imageUrl"),
        }
    print(f"  התקבלו {len(providers_map)} מפעילים מ-CelloCharge")

    # 2. Locations
    req_loc = urllib.request.Request(f"{CELLO_BASE}/locations", headers=headers)
    with urllib.request.urlopen(req_loc, timeout=30) as resp:
        locations_raw = json.loads(resp.read().decode("utf-8"))
    print(f"  התקבלו {len(locations_raw)} אתרי טעינה מ-CelloCharge")

    return providers_map, locations_raw


# ==============================================================================
# Source 2: auto.co.il
# ==============================================================================

def fetch_auto_coil() -> List[Dict[str, Any]]:
    """
    Fetch charging stations from auto.co.il API.
    URL: https://www.auto.co.il/api/chargingStations/map/stations?CultureCode=he-IL
    """
    print("[2/5] מוריד נתונים מ-auto.co.il...")
    url = "https://www.auto.co.il/api/chargingStations/map/stations?CultureCode=he-IL"
    headers = {
        "User-Agent": USER_AGENTS[0],
        "Referer": "https://www.auto.co.il/cars/electric-vehicles/charging-station-map/",
        "Accept": "application/json, text/plain, */*",
    }

    raw_data = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as response:
                content = response.read().decode("utf-8")
                raw_data = json.loads(content)
                break
        except Exception as e:
            print(f"  אזהרה: ניסיון {attempt + 1} נכשל ({e}). מנסה שוב...")
            headers["User-Agent"] = USER_AGENTS[(attempt + 1) % len(USER_AGENTS)]
            time.sleep(2)

    if not raw_data or "stations" not in raw_data:
        print("  שגיאה: לא התקבלו נתונים תקינים מ-auto.co.il")
        return []

    raw_stations = raw_data.get("stations", [])
    print(f"  התקבלו {len(raw_stations)} רשומות גולמיות מ-auto.co.il")

    normalized: List[Dict[str, Any]] = []
    for s in raw_stations:
        name = (s.get("name") or "").strip()
        address = (s.get("address") or "").strip()
        city = None
        if address and "," in address:
            parts = [p.strip() for p in address.split(",") if p.strip()]
            if parts:
                city = parts[0]

        lat = float(s["lat"]) if s.get("lat") is not None else None
        lng = float(s["lng"]) if s.get("lng") is not None else None
        operator = (s.get("companyDisplayName") or s.get("company") or "").strip() or None

        # Build connector types structure
        connectors: List[Dict[str, Any]] = []
        ct_list = s.get("chargerTypes")
        if isinstance(ct_list, list):
            for ct in ct_list:
                if isinstance(ct, dict):
                    ctype = ct.get("chargerType", "")
                    if ctype == "regular":
                        connectors.append({"standard": "TYPE2", "powerType": "AC", "maxPower": 22})
                    elif ctype in ("fast", "ultrafast"):
                        pwr = 150 if ctype == "ultrafast" else 50
                        connectors.append({"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": pwr})
                    elif ctype == "supercharger":
                        connectors.append({"standard": "TESLA", "powerType": "DC", "maxPower": 250})
                    else:
                        dname = ct.get("chargerTypeDisplayName", "")
                        connectors.append({"standard": dname or "UNKNOWN", "powerType": "UNKNOWN", "maxPower": None})
        if not connectors and s.get("chargerType"):
            ctype = str(s.get("chargerType"))
            if "regular" in ctype or "רגיל" in ctype:
                connectors.append({"standard": "TYPE2", "powerType": "AC", "maxPower": 22})
            elif "ultra" in ctype:
                connectors.append({"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 150})
            elif "fast" in ctype or "מהיר" in ctype:
                connectors.append({"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 50})

        normalized.append({
            "name": name or None,
            "address": address or None,
            "city": city,
            "lat": lat,
            "lng": lng,
            "operator": operator,
            "connectors": connectors,
            "raw": s,
        })
    return normalized


# ==============================================================================
# Source 3: evm.co.il
# ==============================================================================

def _decode_evm_b64_url(val: Any) -> str:
    """Decode base64 and url-encoded string from evm.co.il."""
    if not val:
        return ""
    try:
        decoded_b64 = base64.b64decode(str(val)).decode("utf-8", errors="replace")
        return urllib.parse.unquote_plus(decoded_b64).strip()
    except Exception:
        return str(val).strip()


def fetch_evm() -> List[Dict[str, Any]]:
    """
    Fetch fast charging stations from evm.co.il static JS dataset.
    URL: https://www.evm.co.il/wp-content/evm-scripts/charging-map/data/CM.92dabf3.min.js
    """
    print("[3/5] מוריד נתונים מ-evm.co.il...")
    url = "https://www.evm.co.il/wp-content/evm-scripts/charging-map/data/CM.92dabf3.min.js"
    headers = {"User-Agent": USER_AGENTS[0]}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=25) as resp:
            text = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  שגיאה בקריאת evm.co.il: {e}")
        return []

    idx = text.find("const N=[")
    if idx == -1:
        print("  שגיאה: מערך N לא נמצא בקובץ ה-JS של evm.co.il")
        return []

    sub = text[idx + len("const N="):]
    bracket_count = 0
    in_string = False
    str_char = ""
    escape = False
    end_idx = -1
    for i, c in enumerate(sub):
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == str_char:
                in_string = False
        else:
            if c in ('"', "'"):
                in_string = True
                str_char = c
            elif c == "[":
                bracket_count += 1
            elif c == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break

    if end_idx == -1:
        print("  שגיאה: לא הצליח לתחום את מערך ה-JSON מ-evm.co.il")
        return []

    arr_str = sub[:end_idx]
    s = arr_str.replace("!0", "true").replace("!1", "false")
    s = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)

    try:
        raw_stations = json.loads(s)
    except Exception as e:
        print(f"  שגיאה בפענוח JSON מ-evm.co.il: {e}")
        return []

    print(f"  התקבלו {len(raw_stations)} רשומות גולמיות מ-evm.co.il")

    normalized: List[Dict[str, Any]] = []
    for item in raw_stations:
        name = _decode_evm_b64_url(item.get("t"))
        address = _decode_evm_b64_url(item.get("a"))
        operator = _decode_evm_b64_url(item.get("o")) or None

        city = None
        if address and "," in address:
            parts = [p.strip() for p in address.split(",") if p.strip()]
            if len(parts) >= 2:
                city = parts[1] if not parts[1].isdigit() else (parts[0] if len(parts) > 1 else None)

        coords = item.get("p")
        lat = float(coords[0]) if coords and len(coords) >= 2 else None
        lng = float(coords[1]) if coords and len(coords) >= 2 else None

        connectors: List[Dict[str, Any]] = []
        if item.get("ct") and item.get("ct") > 0:
            connectors.append({"standard": "TESLA", "powerType": "DC", "maxPower": 250})
        if item.get("sf") and item.get("sf") > 0:
            connectors.append({"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 150})
        if item.get("cd") and item.get("cd") > (item.get("sf") or 0):
            connectors.append({"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 50})
        if item.get("ca") and item.get("ca") > 0:
            connectors.append({"standard": "TYPE2", "powerType": "AC", "maxPower": 22})

        count_total = item.get("cb") if item.get("cb") is not None else None

        normalized.append({
            "name": name or None,
            "address": address or None,
            "city": city,
            "lat": lat,
            "lng": lng,
            "operator": operator,
            "connectors": connectors,
            "count_total": count_total,
            "raw": item,
        })
    return normalized


# ==============================================================================
# Source 4: data.gov.il
# ==============================================================================

def fetch_data_gov() -> List[Dict[str, Any]]:
    """
    Fetch charging stations from data.gov.il CKAN API (Ministry of Energy registry).
    Resource ID: 528482f2-d410-4d62-8b17-566ab23a1c52
    """
    print("[4/5] מוריד נתונים מ-data.gov.il...")
    base_url = "https://data.gov.il/api/3/action/datastore_search"
    resource_id = "528482f2-d410-4d62-8b17-566ab23a1c52"
    limit = 1000
    offset = 0

    all_records: List[Dict[str, Any]] = []
    while True:
        url = f"{base_url}?resource_id={resource_id}&limit={limit}&offset={offset}"
        headers = {"User-Agent": USER_AGENTS[0], "Accept": "application/json"}
        req = urllib.request.Request(url, headers=headers)

        batch_records = []
        total = 0
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = data.get("result", {})
                batch_records = result.get("records", [])
                total = result.get("total", 0)
        except Exception as e:
            print(f"  שגיאה בקריאת data.gov.il ב-offset {offset}: {e}")
            break

        if not batch_records:
            break

        all_records.extend(batch_records)
        print(f"  הורדו {len(all_records)} / {total} רשומות...")
        if offset + len(batch_records) >= total or len(batch_records) < limit:
            break
        offset += len(batch_records)

    print(f"  סה\"כ התקבלו {len(all_records)} רשומות מ-data.gov.il")

    normalized: List[Dict[str, Any]] = []
    for r in all_records:
        name = (r.get("name") or "").strip()
        address = (r.get("Address") or "").strip()
        operator = (r.get("op") or "").strip() or None
        cnt_total = int(r["count"]) if r.get("count") is not None else None
        cnt_fast = int(r["cnt_fast"]) if r.get("cnt_fast") is not None else None
        cnt_slow = int(r["cnt_slow"]) if r.get("cnt_slow") is not None else None

        connectors: List[Dict[str, Any]] = []
        if cnt_fast and cnt_fast > 0:
            connectors.append({"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 50})
        if cnt_slow and cnt_slow > 0:
            connectors.append({"standard": "TYPE2", "powerType": "AC", "maxPower": 22})

        normalized.append({
            "name": name or None,
            "address": address or None,
            "operator": operator,
            "count_total": cnt_total,
            "connectors": connectors,
            "raw": r,
        })
    return normalized


# ==============================================================================
# Source 5: Paz / Yellow (Paz Charge)
# ==============================================================================

def _extract_paz_stations_from_html(html: str) -> List[Dict[str, Any]]:
    """Extract raw stations array from Paz service-locator HTML (Next.js SSR payload)."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*\"(.*?)\"\s*\]\)', html, re.DOTALL)
    for chunk in chunks:
        if "siteId" in chunk and "stations" in chunk:
            try:
                raw = json.loads('"' + chunk + '"')
            except Exception:
                raw = chunk.encode("utf-8").decode("unicode_escape", errors="ignore")

            idx = raw.find('"stations":[')
            if idx == -1:
                idx = raw.find('stations":[')
            if idx != -1:
                start = raw.find("[", idx)
                cnt = 0
                end = -1
                for j in range(start, len(raw)):
                    if raw[j] == "[":
                        cnt += 1
                    elif raw[j] == "]":
                        cnt -= 1
                        if cnt == 0:
                            end = j + 1
                            break
                if end != -1:
                    try:
                        return json.loads(raw[start:end])
                    except Exception as e:
                        print(f"  אזהרה בפענוח JSON של פז: {e}")
    return []


def fetch_paz_data() -> List[Dict[str, Any]]:
    """
    Fetch electric charging stations from Paz / Yellow service locator.
    URL: https://www.paz.co.il/service-locator
    Extracts stations where isElectric=True (Paz Charge DC ultra-fast network).
    Supports live fetch with WAF bypass (via curl_cffi/scrapling or subprocess)
    and automatic caching fallback.
    """
    print("[5/5] מוריד נתונים מ-Paz Charge (רשת פז / Yellow)...")
    url = "https://www.paz.co.il/service-locator"
    raw_stations: List[Dict[str, Any]] = []

    # 1. Try curl_cffi directly in Python if installed
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, impersonate="chrome", timeout=20)
        if resp.status_code == 200:
            raw_stations = _extract_paz_stations_from_html(resp.text)
    except Exception:
        pass

    # 2. Try scrapling venv via subprocess if not fetched yet
    if not raw_stations:
        scrapling_python = os.path.expanduser("~/venvs/scrapling/bin/python3")
        if os.path.exists(scrapling_python):
            try:
                sub_code = (
                    "from curl_cffi import requests\n"
                    "import sys\n"
                    "try:\n"
                    "    r = requests.get('https://www.paz.co.il/service-locator', impersonate='chrome', timeout=20)\n"
                    "    if r.status_code == 200:\n"
                    "        print(r.text)\n"
                    "except Exception:\n"
                    "    sys.exit(1)\n"
                )
                res = subprocess.run(
                    [scrapling_python, "-c", sub_code],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0 and res.stdout:
                    raw_stations = _extract_paz_stations_from_html(res.stdout)
            except Exception as e:
                print(f"  אזהרה: קריאה דרך scrapling נכשלה ({e})")

    # 3. Try standard urllib with browser headers
    if not raw_stations:
        for ua in USER_AGENTS:
            try:
                headers = {
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    extracted = _extract_paz_stations_from_html(html)
                    if extracted:
                        raw_stations = extracted
                        break
            except Exception:
                pass

    # 4. Save cache or fallback to cache file
    if raw_stations:
        try:
            with open(PAZ_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(raw_stations, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    elif os.path.exists(PAZ_CACHE_FILE):
        print(f"  ℹ️ טוען נתוני פז מקובץ מטמון מקומי: {PAZ_CACHE_FILE}")
        try:
            with open(PAZ_CACHE_FILE, "r", encoding="utf-8") as f:
                raw_stations = json.load(f)
        except Exception as e:
            print(f"  שגיאה בקריאת קובץ מטמון של פז: {e}")

    # Filter only electric stations (isElectric=True)
    electric_stations = [s for s in raw_stations if s.get("isElectric")]
    print(f"  התקבלו {len(electric_stations)} עמדות טעינה פעילות (isElectric=True) מתוך {len(raw_stations)} תחנות פז")

    normalized: List[Dict[str, Any]] = []
    for s in electric_stations:
        raw_name = (s.get("name") or "").strip()
        name = f"פז {raw_name}" if not raw_name.startswith("פז") else raw_name
        address = (s.get("address") or "").strip() or None
        city = (s.get("city") or "").strip() or None

        geo = s.get("geoLocation") or {}
        lat = float(geo["latitude"]) if geo.get("latitude") is not None else None
        lng = float(geo["longitude"]) if geo.get("longitude") is not None else None

        operator = "Yellow"

        # Paz Charge ultra-fast DC network (150kW CCS2)
        connectors: List[Dict[str, Any]] = [
            {"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 150}
        ]

        normalized.append({
            "name": name,
            "address": address,
            "city": city,
            "lat": lat,
            "lng": lng,
            "operator": operator,
            "connectors": connectors,
            "phone": (s.get("phone") or "").strip() or None,
            "raw": s,
        })

    return normalized


# ==============================================================================
# Database Schema & Initialization
# ==============================================================================

def init_db(conn: sqlite3.Connection) -> None:
    """Initialize SQLite tables and indices for v2 schema."""
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cello_id TEXT UNIQUE,
            name TEXT,
            address TEXT,
            city TEXT,
            lat REAL,
            lng REAL,
            provider_id TEXT,
            provider_name TEXT,
            max_per_kwh REAL,
            has_tariffs INTEGER,
            payment_options TEXT,
            facilities TEXT,
            status_summary TEXT,
            connectors TEXT,
            stations_count INTEGER,
            updated_at TEXT,
            sources TEXT,
            is_gov_official INTEGER
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_locations_cello_id ON locations(cello_id);
        CREATE INDEX IF NOT EXISTS idx_locations_coords ON locations(lat, lng);
        CREATE INDEX IF NOT EXISTS idx_locations_provider ON locations(provider_name);
        CREATE INDEX IF NOT EXISTS idx_locations_city ON locations(city);
        CREATE INDEX IF NOT EXISTS idx_locations_is_gov ON locations(is_gov_official);
        CREATE INDEX IF NOT EXISTS idx_locations_sources ON locations(sources);

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()


# ==============================================================================
# Pipeline & Merging Logic
# ==============================================================================

def build_database(db_path: str = DB_PATH) -> None:
    """Build the unified EV stations database with CelloCharge as backbone."""
    start_time = time.time()
    print(f"\n🚀 מתחיל בניית מסד הנתונים: {db_path}")

    # Backup existing database if it exists
    if os.path.exists(db_path) and not os.path.exists(BACKUP_DB_PATH):
        print(f"📦 יוצר גיבוי של מסד הנתונים הישן ל-{BACKUP_DB_PATH}...")
        shutil.copy2(db_path, BACKUP_DB_PATH)
    elif os.path.exists(BACKUP_DB_PATH):
        print(f"ℹ️ קובץ גיבוי קיים כבר: {BACKUP_DB_PATH}")

    # 1. Fetch data from all sources
    providers_map, cello_locations = fetch_cello_data()
    auto_stations = fetch_auto_coil()
    evm_stations = fetch_evm()
    gov_stations = fetch_data_gov()
    paz_stations = fetch_paz_data()

    # 2. Connect to database and clear/create tables
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS locations")
    cur.execute("DROP TABLE IF EXISTS meta")
    init_db(conn)

    spatial_index = SpatialGrid(cell_size_deg=0.01)
    location_sources: Dict[int, Set[str]] = {}
    location_connectors: Dict[int, List[Dict[str, Any]]] = {}
    location_coords: Dict[int, Tuple[float, float]] = {}
    norm_name_to_ids: Dict[str, List[int]] = {}

    # --------------------------------------------------------------------------
    # Step A: Ingest CelloCharge (Base Backbone)
    # --------------------------------------------------------------------------
    print("\n[A] מעבד ומכניס אתרי CelloCharge (עמוד שדרה)...")
    cello_inserted = 0
    for loc in cello_locations:
        cello_id = loc.get("id")
        name = (loc.get("name") or "").strip()
        address = (loc.get("address") or "").strip()
        city = (loc.get("city") or "").strip() or None

        coords = loc.get("coordinates") or {}
        lat = float(coords["lat"]) if coords.get("lat") is not None else None
        lng = float(coords["lng"]) if coords.get("lng") is not None else None

        pid = loc.get("providerId") or ""
        p_info = providers_map.get(pid, {})
        provider_name = p_info.get("name") or pid or None

        tariffs_summary = loc.get("tariffsSummary") or {}
        has_tariffs = 1 if tariffs_summary.get("hasTariffs") else 0
        max_kwh = tariffs_summary.get("maxPerKwh")
        max_per_kwh = float(max_kwh) if max_kwh is not None else None

        payment_options = json.dumps(loc.get("paymentOptions") or [], ensure_ascii=False)
        facilities = json.dumps(loc.get("facilities") or [], ensure_ascii=False)

        # Status summary
        status_counts: Dict[str, int] = {}
        for st in loc.get("stations") or []:
            st_stat = st.get("status") or "UNKNOWN"
            status_counts[st_stat] = status_counts.get(st_stat, 0) + 1
        status_summary = json.dumps(status_counts, ensure_ascii=False)

        # Connectors unified
        connectors_list: List[Dict[str, Any]] = []
        seen_conn = set()
        for st in loc.get("stations") or []:
            for conn_item in st.get("connectors") or []:
                item = {
                    "standard": conn_item.get("standard"),
                    "powerType": conn_item.get("powerType"),
                    "maxPower": conn_item.get("maxPower"),
                }
                k = (item["standard"], item["powerType"], item["maxPower"])
                if k not in seen_conn:
                    seen_conn.add(k)
                    connectors_list.append(item)
        connectors_json = json.dumps(connectors_list, ensure_ascii=False)

        stations_count = len(loc.get("stations") or [])
        updated_at = loc.get("updatedAt")
        sources = "cello"
        is_gov_official = 0

        cur.execute("""
            INSERT INTO locations (
                cello_id, name, address, city, lat, lng,
                provider_id, provider_name, max_per_kwh, has_tariffs,
                payment_options, facilities, status_summary, connectors,
                stations_count, updated_at, sources, is_gov_official
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cello_id, name, address, city, lat, lng,
            pid, provider_name, max_per_kwh, has_tariffs,
            payment_options, facilities, status_summary, connectors_json,
            stations_count, updated_at, sources, is_gov_official
        ))
        loc_id = cur.lastrowid
        location_sources[loc_id] = {"cello"}
        location_connectors[loc_id] = connectors_list
        if lat is not None and lng is not None:
            spatial_index.insert(loc_id, lat, lng)
            location_coords[loc_id] = (lat, lng)

        nn = normalize_text(name)
        if nn:
            norm_name_to_ids.setdefault(nn, []).append(loc_id)
        na = normalize_text(address)
        if na and na != nn:
            norm_name_to_ids.setdefault(na, []).append(loc_id)

        cello_inserted += 1

    conn.commit()
    print(f"  ✓ הוכנסו {cello_inserted} אתרים מ-CelloCharge")

    # --------------------------------------------------------------------------
    # Step B: Merge auto.co.il (Spatial match <= 150m or normalized name match)
    # --------------------------------------------------------------------------
    print("\n[B] ממזג נתונים מ-auto.co.il...")
    auto_matched = 0
    auto_unique_inserted = 0
    now_iso = datetime.now().isoformat()

    for st in auto_stations:
        lat = st.get("lat")
        lng = st.get("lng")
        name = st.get("name")
        address = st.get("address")
        st_conns = st.get("connectors") or []

        matched_id = find_matching_location_id(
            lat, lng, name, address,
            spatial_index, norm_name_to_ids, location_coords,
            max_dist_meters=150.0
        )
        if matched_id is not None:
            location_sources[matched_id].add("auto_coil")
            location_connectors[matched_id] = merge_connectors(
                location_connectors.get(matched_id, []),
                st_conns
            )
            auto_matched += 1
        else:
            if lat is None or lng is None:
                continue
            connectors_json = json.dumps(st_conns, ensure_ascii=False)
            cur.execute("""
                INSERT INTO locations (
                    cello_id, name, address, city, lat, lng,
                    provider_id, provider_name, max_per_kwh, has_tariffs,
                    payment_options, facilities, status_summary, connectors,
                    stations_count, updated_at, sources, is_gov_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                None, st.get("name"), st.get("address"), st.get("city"), lat, lng,
                None, st.get("operator"), None, 0,
                "[]", "[]", "{}", connectors_json,
                1, now_iso, "auto_coil", 0
            ))
            loc_id = cur.lastrowid
            location_sources[loc_id] = {"auto_coil"}
            location_connectors[loc_id] = st_conns
            location_coords[loc_id] = (lat, lng)
            spatial_index.insert(loc_id, lat, lng)

            nn = normalize_text(name)
            if nn:
                norm_name_to_ids.setdefault(nn, []).append(loc_id)
            na = normalize_text(address)
            if na and na != nn:
                norm_name_to_ids.setdefault(na, []).append(loc_id)

            auto_unique_inserted += 1

    conn.commit()
    print(f"  ✓ auto.co.il: {auto_matched} הוצלבו עם אתר קיים, {auto_unique_inserted} אתרים ייחודיים נוספו")

    # --------------------------------------------------------------------------
    # Step C: Merge evm.co.il (Spatial match <= 150m or normalized name match)
    # --------------------------------------------------------------------------
    print("\n[C] ממזג נתונים מ-evm.co.il...")
    evm_matched = 0
    evm_unique_inserted = 0

    for st in evm_stations:
        lat = st.get("lat")
        lng = st.get("lng")
        name = st.get("name")
        address = st.get("address")
        st_conns = st.get("connectors") or []

        matched_id = find_matching_location_id(
            lat, lng, name, address,
            spatial_index, norm_name_to_ids, location_coords,
            max_dist_meters=150.0
        )
        if matched_id is not None:
            location_sources[matched_id].add("evm")
            location_connectors[matched_id] = merge_connectors(
                location_connectors.get(matched_id, []),
                st_conns
            )
            evm_matched += 1
        else:
            if lat is None or lng is None:
                continue
            connectors_json = json.dumps(st_conns, ensure_ascii=False)
            cnt = st.get("count_total") or 1
            cur.execute("""
                INSERT INTO locations (
                    cello_id, name, address, city, lat, lng,
                    provider_id, provider_name, max_per_kwh, has_tariffs,
                    payment_options, facilities, status_summary, connectors,
                    stations_count, updated_at, sources, is_gov_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                None, st.get("name"), st.get("address"), st.get("city"), lat, lng,
                None, st.get("operator"), None, 0,
                "[]", "[]", "{}", connectors_json,
                cnt, now_iso, "evm", 0
            ))
            loc_id = cur.lastrowid
            location_sources[loc_id] = {"evm"}
            location_connectors[loc_id] = st_conns
            location_coords[loc_id] = (lat, lng)
            spatial_index.insert(loc_id, lat, lng)

            nn = normalize_text(name)
            if nn:
                norm_name_to_ids.setdefault(nn, []).append(loc_id)
            na = normalize_text(address)
            if na and na != nn:
                norm_name_to_ids.setdefault(na, []).append(loc_id)

            evm_unique_inserted += 1

    conn.commit()
    print(f"  ✓ evm.co.il: {evm_matched} הוצלבו עם אתר קיים, {evm_unique_inserted} אתרים ייחודיים נוספו")

    # --------------------------------------------------------------------------
    # Step D: Merge data.gov.il (Normalized Name/Address match)
    # --------------------------------------------------------------------------
    print("\n[D] ממזג נתונים מ-data.gov.il (משרד האנרגיה)...")
    gov_matched = 0
    gov_unique_inserted = 0
    matched_loc_ids: Set[int] = set()

    for r in gov_stations:
        gn = normalize_text(r.get("name"))
        ga = normalize_text(r.get("address"))
        r_conns = r.get("connectors") or []

        target_ids = norm_name_to_ids.get(gn) or norm_name_to_ids.get(ga)
        if target_ids:
            gov_matched += 1
            for tid in target_ids:
                matched_loc_ids.add(tid)
                location_sources[tid].add("data_gov")
                location_connectors[tid] = merge_connectors(
                    location_connectors.get(tid, []),
                    r_conns
                )
        else:
            connectors_json = json.dumps(r_conns, ensure_ascii=False)
            cnt = r.get("count_total") or 1
            cur.execute("""
                INSERT INTO locations (
                    cello_id, name, address, city, lat, lng,
                    provider_id, provider_name, max_per_kwh, has_tariffs,
                    payment_options, facilities, status_summary, connectors,
                    stations_count, updated_at, sources, is_gov_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                None, r.get("name"), r.get("address"), None, None, None,
                None, r.get("operator"), None, 0,
                "[]", "[]", "{}", connectors_json,
                cnt, now_iso, "data_gov", 1
            ))
            loc_id = cur.lastrowid
            location_sources[loc_id] = {"data_gov"}
            location_connectors[loc_id] = r_conns

            if gn:
                norm_name_to_ids.setdefault(gn, []).append(loc_id)
            if ga and ga != gn:
                norm_name_to_ids.setdefault(ga, []).append(loc_id)

            gov_unique_inserted += 1

    conn.commit()
    print(f"  ✓ data.gov.il: {gov_matched} רשומות הוצלבו (התאימו ל-{len(matched_loc_ids)} אתרים ב-DB), {gov_unique_inserted} אתרים ייחודיים נוספו")

    # --------------------------------------------------------------------------
    # Step E: Merge Paz Charge (Spatial match <= 150m or normalized name match)
    # --------------------------------------------------------------------------
    print("\n[E] ממזג נתונים מ-Paz Charge (רשת פז / Yellow)...")
    paz_matched = 0
    paz_unique_inserted = 0

    for st in paz_stations:
        lat = st.get("lat")
        lng = st.get("lng")
        name = st.get("name")
        address = st.get("address")
        st_conns = st.get("connectors") or []
        st_provider = st.get("operator") or "Yellow"

        matched_id = find_matching_location_id(
            lat, lng, name, address,
            spatial_index, norm_name_to_ids, location_coords,
            max_dist_meters=150.0
        )
        if matched_id is not None:
            location_sources[matched_id].add("paz")
            location_connectors[matched_id] = merge_connectors(
                location_connectors.get(matched_id, []),
                st_conns
            )
            # Ensure provider_name is Yellow when merged with Paz, and update name if needed
            cur.execute("SELECT name FROM locations WHERE id = ?", (matched_id,))
            row = cur.fetchone()
            cur_name = (row[0] or "").strip() if row else ""
            if not cur_name:
                new_name = name
            elif "פז" not in cur_name and "paz" not in cur_name.lower():
                new_name = f"פז - {cur_name}"
            else:
                new_name = cur_name

            cur.execute("""
                UPDATE locations
                SET provider_name = ?, name = ?
                WHERE id = ?
            """, (st_provider, new_name, matched_id))
            paz_matched += 1
        else:
            if lat is None or lng is None:
                continue
            connectors_json = json.dumps(st_conns, ensure_ascii=False)
            cur.execute("""
                INSERT INTO locations (
                    cello_id, name, address, city, lat, lng,
                    provider_id, provider_name, max_per_kwh, has_tariffs,
                    payment_options, facilities, status_summary, connectors,
                    stations_count, updated_at, sources, is_gov_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                None, name, address, st.get("city"), lat, lng,
                None, st_provider, None, 0,
                "[]", "[]", "{}", connectors_json,
                1, now_iso, "paz", 0
            ))
            loc_id = cur.lastrowid
            location_sources[loc_id] = {"paz"}
            location_connectors[loc_id] = st_conns
            location_coords[loc_id] = (lat, lng)
            spatial_index.insert(loc_id, lat, lng)

            nn = normalize_text(name)
            if nn:
                norm_name_to_ids.setdefault(nn, []).append(loc_id)
            na = normalize_text(address)
            if na and na != nn:
                norm_name_to_ids.setdefault(na, []).append(loc_id)

            paz_unique_inserted += 1

    conn.commit()
    print(f"  ✓ Paz Charge: {paz_matched} הוצלבו עם אתר קיים, {paz_unique_inserted} אתרים ייחודיים נוספו")

    # Update sources, connectors, and is_gov_official across all locations
    print("\n🔄 מעדכן עמודות sources, connectors ו-is_gov_official...")
    update_batch = []
    source_order = ["cello", "auto_coil", "evm", "data_gov", "paz"]
    for lid, src_set in location_sources.items():
        ordered_sources = [s for s in source_order if s in src_set]
        sources_str = ",".join(ordered_sources)
        is_gov = 1 if (lid in matched_loc_ids or "data_gov" in src_set) else 0
        conns_json = json.dumps(location_connectors.get(lid, []), ensure_ascii=False)
        update_batch.append((sources_str, is_gov, conns_json, lid))

    cur.executemany("UPDATE locations SET sources = ?, is_gov_official = ?, connectors = ? WHERE id = ?", update_batch)
    conn.commit()

    # --------------------------------------------------------------------------
    # Step F: Statistics & Metadata
    # --------------------------------------------------------------------------
    stats = print_statistics(conn)
    update_metadata(conn, stats)
    conn.close()

    elapsed = time.time() - start_time
    print(f"\n✨ תהליך הבנייה הושלם בהצלחה תוך {elapsed:.2f} שניות!\n")


def update_metadata(conn: sqlite3.Connection, stats: Dict[str, Any]) -> None:
    """Save execution metadata and build statistics into the meta table."""
    cur = conn.cursor()
    entries = [
        ("build_time", datetime.now().isoformat()),
        ("version", "2.1"),
        ("primary_source", "CelloCharge (Ministry of Energy)"),
        ("sources_list", "cello, auto_coil, evm, data_gov, paz"),
        ("total_locations", str(stats.get("total", 0))),
        ("cello_locations", str(stats.get("cello_count", 0))),
        ("auto_coil_unique", str(stats.get("auto_unique", 0))),
        ("evm_unique", str(stats.get("evm_unique", 0))),
        ("data_gov_unique", str(stats.get("gov_unique", 0))),
        ("paz_unique", str(stats.get("paz_unique", 0))),
        ("paz_locations", str(stats.get("paz_count", 0))),
        ("records_with_coords", str(stats.get("with_coords", 0))),
        ("records_with_tariffs", str(stats.get("with_tariffs", 0))),
        ("is_gov_official_count", str(stats.get("is_gov_count", 0))),
        ("unique_providers", str(stats.get("unique_providers", 0))),
    ]
    cur.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", entries)
    conn.commit()


def print_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Query and print comprehensive statistics and samples from the database."""
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM locations")
    total_locations = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE lat IS NOT NULL AND lng IS NOT NULL")
    with_coords = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE has_tariffs = 1")
    with_tariffs = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations WHERE is_gov_official = 1")
    is_gov_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT provider_name) FROM locations WHERE provider_name IS NOT NULL AND provider_name != ''")
    unique_providers = cur.fetchone()[0]

    # Source coverage breakdown
    cur.execute("SELECT sources, COUNT(*) FROM locations GROUP BY sources ORDER BY COUNT(*) DESC")
    source_combos = cur.fetchall()

    # Per source appearance counts
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%cello%'")
    cello_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%auto_coil%'")
    auto_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%evm%'")
    evm_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%data_gov%'")
    gov_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources LIKE '%paz%'")
    paz_count = cur.fetchone()[0]

    # Unique additions
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'auto_coil'")
    auto_unique = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'evm'")
    evm_unique = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'data_gov'")
    gov_unique = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM locations WHERE sources = 'paz'")
    paz_unique = cur.fetchone()[0]

    print("\n" + "=" * 70)
    print(" 📊 דוח סיכום מסד נתוני עמדות טעינה לרכב חשמלי בישראל (גרסה 2.1)")
    print("=" * 70)
    print(f" • סה\"כ אתרי טעינה ב-DB:         {total_locations:,}")
    print(f" • עם קואורדינטות (GPS):          {with_coords:,} ({with_coords / total_locations * 100:.1f}%)")
    print(f" • ללא קואורדינטות (משרד אנרגיה):  {total_locations - with_coords:,} ({(total_locations - with_coords) / total_locations * 100:.1f}%)")
    print(f" • אתרים עם מחיר (has_tariffs):   {with_tariffs:,} ({with_tariffs / total_locations * 100:.1f}%)")
    print(f" • מאומתים ממשלתית (Gov Official):{is_gov_count:,} ({is_gov_count / total_locations * 100:.1f}%)")
    print(f" • מספר מפעילים ייחודיים:         {unique_providers:,}")

    print("\n 🔹 כיסוי לפי מקור מידע:")
    print(f"   - CelloCharge (בסיס):       {cello_count:>5} אתרים ({cello_count / total_locations * 100:.1f}%)")
    print(f"   - auto.co.il (הצלבה):       {auto_count:>5} אתרים ({auto_count / total_locations * 100:.1f}%) [ייחודיים שנוספו: {auto_unique}]")
    print(f"   - evm.co.il (הצלבה):        {evm_count:>5} אתרים ({evm_count / total_locations * 100:.1f}%) [ייחודיים שנוספו: {evm_unique}]")
    print(f"   - data.gov.il (הצלבה):      {gov_count:>5} אתרים ({gov_count / total_locations * 100:.1f}%) [ייחודיים שנוספו: {gov_unique}]")
    print(f"   - Paz Charge / Yellow (הצלבה): {paz_count:>5} אתרים ({paz_count / total_locations * 100:.1f}%) [ייחודיים שנוספו: {paz_unique}]")

    print("\n 🔹 שילובי מקורות מובילים (Source Combinations):")
    for combo, cnt in source_combos[:8]:
        print(f"   - [{combo:<35}]: {cnt:>5} אתרים")

    print("\n 🔹 10 המפעילים הגדולים ביותר:")
    cur.execute("""
        SELECT provider_name, COUNT(*) as cnt
        FROM locations
        WHERE provider_name IS NOT NULL AND provider_name != ''
        GROUP BY provider_name
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for rank, (op, cnt) in enumerate(cur.fetchall(), 1):
        print(f"   {rank:>2}. {op:<30} ({cnt:,} אתרים)")

    print("\n 🔹 דוגמאות מייצגות מה-DB החדש:")
    print("-" * 70)

    # Sample 1: Cello with tariffs and multiple sources
    cur.execute("""
        SELECT id, cello_id, name, address, city, provider_name, max_per_kwh, sources, is_gov_official, status_summary, connectors
        FROM locations
        WHERE cello_id IS NOT NULL AND has_tariffs = 1 AND sources LIKE '%,%'
        LIMIT 2
    """)
    for row in cur.fetchall():
        _print_sample(row)

    # Sample 2: auto_coil unique
    cur.execute("""
        SELECT id, cello_id, name, address, city, provider_name, max_per_kwh, sources, is_gov_official, status_summary, connectors
        FROM locations
        WHERE sources = 'auto_coil'
        LIMIT 1
    """)
    for row in cur.fetchall():
        _print_sample(row)

    # Sample 3: evm unique
    cur.execute("""
        SELECT id, cello_id, name, address, city, provider_name, max_per_kwh, sources, is_gov_official, status_summary, connectors
        FROM locations
        WHERE sources = 'evm'
        LIMIT 1
    """)
    for row in cur.fetchall():
        _print_sample(row)

    # Sample 4: data_gov unique
    cur.execute("""
        SELECT id, cello_id, name, address, city, provider_name, max_per_kwh, sources, is_gov_official, status_summary, connectors
        FROM locations
        WHERE sources = 'data_gov'
        LIMIT 1
    """)
    for row in cur.fetchall():
        _print_sample(row)

    # Sample 5: paz unique
    cur.execute("""
        SELECT id, cello_id, name, address, city, provider_name, max_per_kwh, sources, is_gov_official, status_summary, connectors
        FROM locations
        WHERE sources = 'paz'
        LIMIT 1
    """)
    for row in cur.fetchall():
        _print_sample(row)

    stats = {
        "total": total_locations,
        "with_coords": with_coords,
        "with_tariffs": with_tariffs,
        "is_gov_count": is_gov_count,
        "unique_providers": unique_providers,
        "cello_count": cello_count,
        "auto_count": auto_count,
        "evm_count": evm_count,
        "gov_count": gov_count,
        "paz_count": paz_count,
        "auto_unique": auto_unique,
        "evm_unique": evm_unique,
        "gov_unique": gov_unique,
        "paz_unique": paz_unique,
    }
    return stats


def _print_sample(row: Tuple[Any, ...]) -> None:
    lid, cid, name, addr, city, op, max_price, sources, is_gov, status_s, conn_s = row
    price_str = f"{max_price} ₪/kWh" if max_price is not None else "לא צוין מחיר"
    gov_str = "כן (מאומת משרד האנרגיה)" if is_gov else "לא"
    print(f" [ID: {lid}] {name}")
    print(f"     כתובת: {addr or 'ללא כתובת'} | עיר: {city or 'לא צוין'} | מפעיל: {op or 'לא צוין'}")
    print(f"     מקורות: {sources} | Cello ID: {cid or 'אין'} | מחיר מקס': {price_str} | Gov Official: {gov_str}")
    print(f"     סטטוסים: {status_s} | מחברים: {conn_s[:80]}...")
    print("-" * 70)


def main() -> None:
    build_database(DB_PATH)


if __name__ == "__main__":
    main()
