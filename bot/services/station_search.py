import sqlite3
import math
import json
import asyncio
from typing import Optional, Tuple, Union


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_station_max_power(connectors_raw) -> float:
    """מחשב מהירות מקסימלית (kW) של עמדה מתוך המחברים. מחזיר 0.0 אם אין מחברים/נתונים."""
    if isinstance(connectors_raw, dict):
        connectors_raw = connectors_raw.get("connectors")
    if isinstance(connectors_raw, str):
        try:
            connectors = json.loads(connectors_raw or "[]")
        except (json.JSONDecodeError, TypeError):
            connectors = []
    elif isinstance(connectors_raw, list):
        connectors = connectors_raw
    else:
        connectors = []

    powers = []
    for c in connectors:
        if isinstance(c, dict):
            p = c.get("maxPower")
            if p is not None:
                try:
                    powers.append(float(p))
                except (ValueError, TypeError):
                    pass
    return max(powers) if powers else 0.0


def station_matches_connector(connectors_raw, connector_filter: str) -> bool:
    """connector_filter: 'CCS2_COMBO' | 'TYPE2' | 'CHADEMO' | 'ALL'"""
    if connector_filter == "ALL":
        return True
    if isinstance(connectors_raw, dict):
        connectors_raw = connectors_raw.get("connectors")
    if isinstance(connectors_raw, str):
        try:
            connectors = json.loads(connectors_raw or "[]")
        except (json.JSONDecodeError, TypeError):
            connectors = []
    elif isinstance(connectors_raw, list):
        connectors = connectors_raw
    else:
        connectors = []
    return any(isinstance(c, dict) and c.get("standard") == connector_filter for c in connectors)


def station_matches_speed(connectors_raw, speed_filter: str) -> bool:
    """
    SLOW: max_power <= 22 (AC)
    FAST: 50 <= max_power < 150
    ULTRA: max_power >= 150
    ALL: הכל
    """
    if speed_filter == "ALL":
        return True
    max_power = get_station_max_power(connectors_raw)
    if max_power == 0.0:
        return True
    if speed_filter == "SLOW":
        return max_power <= 22.0
    elif speed_filter == "FAST":
        return 50.0 <= max_power < 150.0
    elif speed_filter == "ULTRA":
        return max_power >= 150.0
    return True


def is_in_israel(lat: float, lng: float) -> bool:
    """Bounding Box גסה של ישראל."""
    return 29.5 <= lat <= 33.3 and 34.2 <= lng <= 35.9


def sort_stations(stations: list[dict], sort_by: str = "distance") -> list[dict]:
    """
    ממיין רשימת עמדות לפי distance או speed:
    - distance: מרחק עולה; שובר שוויון לפי מהירות יורדת.
    - speed: מהירות יורדת; שובר שוויון לפי מרחק עולה.
    """
    def _power(s: dict) -> float:
        p = s.get("max_power")
        if p is not None:
            try:
                return float(p)
            except (ValueError, TypeError):
                pass
        return get_station_max_power(s.get("connectors"))

    def _dist(s: dict) -> float:
        d = s.get("distance_km")
        if d is not None:
            try:
                return float(d)
            except (ValueError, TypeError):
                pass
        return float("inf")

    if sort_by == "speed":
        return sorted(
            stations,
            key=lambda x: (
                -_power(x),
                _dist(x),
            ),
        )
    # default: distance
    return sorted(
        stations,
        key=lambda x: (
            _dist(x),
            -_power(x),
        ),
    )


def get_smart_mix_limit(radius_km: float) -> int:
    """
    מחשב את מגבלת התוצאות (limit) לשילוב החכם לפי רדיוס החיפוש (בק"מ):
    - רדיוס <= 10 ק"מ: 15 תוצאות
    - 10 < רדיוס <= 20 ק"מ: 18 תוצאות
    - 20 < רדיוס <= 40 ק"מ: 20 תוצאות
    - רדיוס > 40 ק"מ (כולל 100 ק"מ): 25 תוצאות
    """
    if radius_km <= 10:
        return 15
    elif radius_km <= 20:
        return 18
    elif radius_km <= 40:
        return 20
    else:
        return 25


def apply_smart_mix(
    stations: list[dict],
    limit: Optional[int] = None,
    sort_by: str = "distance",
    radius_km: Optional[float] = None,
) -> list[dict]:
    """
    שילוב חכם לפי רדיוס החיפוש / limit:
    - חישוב limit לפי radius_km אם לא הועבר limit מפורש (ברירת מחדל: 15).
    - חלוקה מאוזנת: Math.ceil(limit / 2) קרובות ביותר + היתר (limit - closest) מהירות ביותר:
      * עבור limit=15 (רדיוס <= 10 ק"מ): 8 קרובות + 7 מהירות
      * עבור limit=18 (רדיוס <= 20 ק"מ): 9 קרובות + 9 מהירות
      * עבור limit=20 (רדיוס <= 40 ק"מ): 10 קרובות + 10 מהירות
      * עבור limit=25 (רדיוס > 40 ק"מ / 100 ק"מ): 13 קרובות + 12 מהירות
    - ממיין את העמדות הנבחרות לפי sort_by המבוקש.
    אם יש <= limit עמדות:
    - ממיין את כל העמדות לפי sort_by ומחזיר.
    """
    if limit is None:
        if radius_km is not None:
            limit = get_smart_mix_limit(radius_km)
        else:
            limit = 15

    if len(stations) <= limit:
        return sort_stations(stations, sort_by=sort_by)

    # 1. מיון לפי מרחק ובחירת הקרובות ביותר
    target_closest = (limit + 1) // 2
    by_distance = sort_stations(stations, sort_by="distance")
    closest_count = min(target_closest, len(by_distance))
    closest = by_distance[:closest_count]
    chosen_ids = {s.get("id") if s.get("id") is not None else id(s) for s in closest}

    # 2. היתר ממוינים לפי מהירות ובחירת המהירות ביותר
    remaining = [
        s for s in by_distance[closest_count:]
        if (s.get("id") if s.get("id") is not None else id(s)) not in chosen_ids
    ]
    by_speed = sort_stations(remaining, sort_by="speed")
    fastest_count = limit - len(closest)
    fastest = by_speed[:fastest_count]

    mixed = closest + fastest

    # 3. הגנה למקרה חריג שאין מספיק תוצאות ייחודיות
    if len(mixed) < limit:
        mixed_ids = {s.get("id") if s.get("id") is not None else id(s) for s in mixed}
        for s in by_distance:
            s_id = s.get("id") if s.get("id") is not None else id(s)
            if s_id not in mixed_ids:
                mixed.append(s)
                mixed_ids.add(s_id)
                if len(mixed) == limit:
                    break

    # 4. מיון סופי של העמדות הנבחרות לפי בחירת המשתמש
    return sort_stations(mixed, sort_by=sort_by)


def _find_nearby_sync(
    db_path: str,
    user_lat: float,
    user_lng: float,
    radius_km: float,
    connector_filter: str = "ALL",
    speed_filter: str = "ALL",
    max_price: Optional[float] = None,
    limit: Optional[int] = None,
    sort_by: str = "distance",
    return_all: bool = False,
) -> Union[list[dict], Tuple[list[dict], list[dict]]]:
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * math.cos(math.radians(user_lat)))
    lat_min = user_lat - lat_delta
    lat_max = user_lat + lat_delta
    lon_min = user_lng - lon_delta
    lon_max = user_lng + lon_delta

    query = """
        SELECT
            id, cello_id, name, address, city,
            lat, lng, provider_name, max_per_kwh,
            has_tariffs, status_summary, connectors,
            stations_count, is_gov_official, sources
        FROM locations
        WHERE
            lat IS NOT NULL AND lng IS NOT NULL
            AND lat BETWEEN :lat_min AND :lat_max
            AND lng BETWEEN :lon_min AND :lon_max
            AND (:max_price IS NULL OR max_per_kwh IS NULL OR max_per_kwh <= :max_price)
    """
    params = {
        "lat_min": lat_min, "lat_max": lat_max,
        "lon_min": lon_min, "lon_max": lon_max,
        "max_price": max_price,
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        dist = haversine_km(user_lat, user_lng, row["lat"], row["lng"])
        if dist > radius_km:
            continue
        if not station_matches_connector(row["connectors"], connector_filter):
            continue
        if not station_matches_speed(row["connectors"], speed_filter):
            continue
        d = dict(row)
        d["distance_km"] = dist
        d["max_power"] = get_station_max_power(row["connectors"])
        results.append(d)

    selected = apply_smart_mix(results, limit=limit, sort_by=sort_by, radius_km=radius_km)
    if return_all:
        return selected, results
    return selected


async def find_nearby(
    db_path: str,
    user_lat: float,
    user_lng: float,
    radius_km: float = 10.0,
    connector_filter: str = "ALL",
    speed_filter: str = "ALL",
    max_price: Optional[float] = None,
    limit: Optional[int] = None,
    sort_by: str = "distance",
    return_all: bool = False,
) -> Union[list[dict], Tuple[list[dict], list[dict]]]:
    """Async wrapper — מריץ את החיפוש ב-thread pool."""
    return await asyncio.to_thread(
        _find_nearby_sync,
        db_path, user_lat, user_lng, radius_km,
        connector_filter, speed_filter, max_price, limit, sort_by,
        return_all,
    )
