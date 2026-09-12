import math
from typing import Optional

from bot.services.station_search import find_nearby, haversine_km

# הנחות קבועות למצב נסיעה (גרסה ירוקה - לא ניתנות לשינוי דרך הגדרות עדיין)
TRIP_CONSUMPTION_KWH_PER_100KM = 18.0
TRIP_RANGE_KM = 400.0
TRIP_STOP_FRACTION = 0.8  # כל עצירה מתוכננת אחרי כ-80% מטווח הסוללה מהעצירה הקודמת
TRIP_AVG_SPEED_KMH = 90.0

TRIP_SEARCH_RADII_KM: tuple[float, ...] = (10.0, 20.0)
TRIP_PREFERRED_MIN_POWER_KW = 150.0
TRIP_FALLBACK_MIN_POWER_KW = 100.0


def calculate_stops_needed(distance_km: float, range_km: float = TRIP_RANGE_KM) -> int:
    """מספר עצירות הטעינה הנדרשות = ceil(מרחק/טווח) - 1, לא פחות מאפס."""
    if distance_km <= 0:
        return 0
    return max(0, math.ceil(distance_km / range_km) - 1)


def interpolate_point(
    lat1: float, lng1: float, lat2: float, lng2: float, fraction: float
) -> tuple[float, float]:
    """נקודה על הציר הישר (אינטרפולציה לינארית) בין שתי נקודות, לפי fraction ב-[0,1]."""
    fraction = max(0.0, min(1.0, fraction))
    return lat1 + (lat2 - lat1) * fraction, lng1 + (lng2 - lng1) * fraction


async def _fastest_station_at_least(
    db_path: str, lat: float, lng: float, radius_km: float, min_power_kw: float
) -> Optional[dict]:
    results = await find_nearby(db_path, lat, lng, radius_km=radius_km, sort_by="speed", limit=50)
    candidates = [s for s in results if s.get("max_power", 0.0) >= min_power_kw]
    if not candidates:
        return None
    candidates.sort(key=lambda s: (-s.get("max_power", 0.0), s.get("distance_km", math.inf)))
    return candidates[0]


async def find_station_near_point(db_path: str, lat: float, lng: float) -> Optional[dict]:
    """
    מוצא את עמדת הטעינה המהירה ביותר בסביבת נקודה על ציר הנסיעה:
    מעדיף עמדות ≥150kW, נופל ל-≥100kW, ומרחיב את רדיוס החיפוש בהדרגה (10 ק"מ, ואז 20 ק"מ).
    מחזיר None אם לא נמצאה עמדה מתאימה באף אחד מהרדיוסים.
    """
    for radius_km in TRIP_SEARCH_RADII_KM:
        station = await _fastest_station_at_least(db_path, lat, lng, radius_km, TRIP_PREFERRED_MIN_POWER_KW)
        if station is None:
            station = await _fastest_station_at_least(db_path, lat, lng, radius_km, TRIP_FALLBACK_MIN_POWER_KW)
        if station is not None:
            return station
    return None


async def plan_trip(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    db_path: str,
) -> dict:
    """
    מתכנן נסיעה בין מוצא ליעד: מחשב מרחק/זמן ובוחר עמדות טעינה לאורך הציר הישר.

    מחזיר dict עם: total_distance_km, duration_hours, num_stops,
    stops (רשימת {segment_index, distance_from_origin_km, station}),
    missing_segments (רשימת {segment_index, distance_km} לקטעים בלי עמדה מתאימה).
    """
    total_distance_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    num_stops = calculate_stops_needed(total_distance_km)
    duration_hours = total_distance_km / TRIP_AVG_SPEED_KMH

    stops: list[dict] = []
    missing_segments: list[dict] = []

    for i in range(1, num_stops + 1):
        target_distance_km = min(i * TRIP_STOP_FRACTION * TRIP_RANGE_KM, total_distance_km)
        fraction = target_distance_km / total_distance_km if total_distance_km > 0 else 0.0
        point_lat, point_lng = interpolate_point(origin_lat, origin_lng, dest_lat, dest_lng, fraction)

        station = await find_station_near_point(db_path, point_lat, point_lng)
        if station is None:
            missing_segments.append({"segment_index": i, "distance_km": target_distance_km})
        else:
            stops.append({
                "segment_index": i,
                "distance_from_origin_km": target_distance_km,
                "station": station,
            })

    return {
        "origin": {"lat": origin_lat, "lng": origin_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "total_distance_km": total_distance_km,
        "duration_hours": duration_hours,
        "num_stops": num_stops,
        "stops": stops,
        "missing_segments": missing_segments,
    }
