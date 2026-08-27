import sqlite3
import math
import json
import asyncio
from typing import Optional


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def station_matches_connector(connectors_json: str, connector_filter: str) -> bool:
    """connector_filter: 'CCS2_COMBO' | 'TYPE2' | 'CHADEMO' | 'ALL'"""
    if connector_filter == "ALL":
        return True
    try:
        connectors = json.loads(connectors_json or "[]")
        return any(c.get("standard") == connector_filter for c in connectors)
    except (json.JSONDecodeError, TypeError):
        return False


def station_matches_speed(connectors_json: str, speed_filter: str) -> bool:
    """
    SLOW: max_power <= 22 (AC)
    FAST: 50 <= max_power < 150
    ULTRA: max_power >= 150
    ALL: הכל
    """
    if speed_filter == "ALL":
        return True
    try:
        connectors = json.loads(connectors_json or "[]")
        powers = [float(c["maxPower"]) for c in connectors if c.get("maxPower") is not None]
        if not powers:
            return True
        max_power = max(powers)
        if speed_filter == "SLOW":
            return max_power <= 22
        elif speed_filter == "FAST":
            return 50 <= max_power < 150
        elif speed_filter == "ULTRA":
            return max_power >= 150
    except (json.JSONDecodeError, TypeError, ValueError):
        return True
    return False


def is_in_israel(lat: float, lng: float) -> bool:
    """Bounding Box גסה של ישראל."""
    return 29.5 <= lat <= 33.3 and 34.2 <= lng <= 35.9


def _find_nearby_sync(
    db_path: str,
    user_lat: float,
    user_lng: float,
    radius_km: float,
    connector_filter: str = "ALL",
    speed_filter: str = "ALL",
    max_price: Optional[float] = None,
    limit: int = 15,
) -> list[dict]:
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * math.cos(math.radians(user_lat)))
    lat_min = user_lat - lat_delta
    lat_max = user_lat + lat_delta
    lon_min = user_lng - lon_delta
    lon_max = user_lng + lon_delta

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

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
        LIMIT 300
    """
    params = {
        "lat_min": lat_min, "lat_max": lat_max,
        "lon_min": lon_min, "lon_max": lon_max,
        "max_price": max_price,
    }
    rows = conn.execute(query, params).fetchall()
    conn.close()

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
        results.append(d)

    results.sort(key=lambda x: x["distance_km"])
    return results[:limit]


async def find_nearby(
    db_path: str,
    user_lat: float,
    user_lng: float,
    radius_km: float = 10.0,
    connector_filter: str = "ALL",
    speed_filter: str = "ALL",
    max_price: Optional[float] = None,
    limit: int = 15,
) -> list[dict]:
    """Async wrapper — מריץ את החיפוש ב-thread pool."""
    return await asyncio.to_thread(
        _find_nearby_sync,
        db_path, user_lat, user_lng, radius_km,
        connector_filter, speed_filter, max_price, limit,
    )
