import math
from typing import Optional

from bot.services.station_search import find_nearby, haversine_km

# ברירות מחדל למצב נסיעה, בשימוש כאשר המשתמש לא הגדיר ערך אישי בהגדרות הנסיעה שלו.
TRIP_DEFAULT_REAL_RANGE_KM = 350.0
TRIP_DEFAULT_BATTERY_PERCENT = 80.0
TRIP_DEFAULT_SAFETY_MARGIN_PERCENT = 10.0
TRIP_CONSUMPTION_KWH_PER_100KM = 18.0
TRIP_AVG_SPEED_KMH = 90.0

# כל עצירה מתוכננת בתוך כ-85% מהטווח הזמין שנותר, כדי להשאיר מרווח לחיפוש עמדה
# בקרבת נקודת היעד המחושבת (ולא בדיוק על קצה הטווח).
TRIP_STOP_SEARCH_FRACTION = 0.85

# מרחק כביש בישראל ארוך בממוצע ב-15%-25% ממרחק קו אווירי (למשל ת"א-אילת: כ-282 ק"מ
# קו אווירי מול כ-330 ק"מ כביש בפועל). בהיעדר שירות ניתוב, משתמשים במקדם קבוע זה
# כדי לא להציג הערכת מרחק/זמן אופטימית מדי.
TRIP_ROAD_DISTANCE_FACTOR = 1.25

TRIP_SEARCH_RADII_KM: tuple[float, ...] = (10.0, 20.0, 40.0)
TRIP_PREFERRED_MIN_POWER_KW = 150.0
TRIP_POWER_FALLBACK_FLOOR_KW = 1.0


def calculate_available_range_km(
    real_range_km: float,
    battery_percent: float,
    safety_margin_percent: float,
) -> float:
    """טווח נסיעה זמין בפועל: הטווח האמיתי של הרכב, מוכפל בחלק הסוללה שמעל מרווח הביטחון.

    מניחים שבכל עצירת טעינה הרכב חוזר לאותה רמת סוללה כמו בתחילת הנסיעה - הנחה
    מפשטת שנועדה לשמור על חישוב אחיד ופשוט להסבר למשתמש.
    """
    usable_percent = battery_percent - safety_margin_percent
    if usable_percent <= 0:
        return 0.0
    return real_range_km * (usable_percent / 100.0)


def calculate_stops_needed(distance_km: float, range_km: float) -> int:
    """מספר עצירות הטעינה הנדרשות = ceil(מרחק/טווח) - 1, לא פחות מאפס."""
    if distance_km <= 0 or range_km <= 0:
        return 0
    return max(0, math.ceil(distance_km / range_km) - 1)


def interpolate_point(
    lat1: float, lng1: float, lat2: float, lng2: float, fraction: float
) -> tuple[float, float]:
    """נקודה על הציר הישר (אינטרפולציה לינארית) בין שתי נקודות, לפי fraction ב-[0,1]."""
    fraction = max(0.0, min(1.0, fraction))
    return lat1 + (lat2 - lat1) * fraction, lng1 + (lng2 - lng1) * fraction


def _power_thresholds(min_power_kw: Optional[float]) -> list[float]:
    """סולם ירידה של סף הספק: מהעדפת המשתמש (או ברירת המחדל) ועד רצפה מינימלית."""
    base = min_power_kw if min_power_kw is not None else TRIP_PREFERRED_MIN_POWER_KW
    pool = {t for t in (100.0, 50.0, TRIP_POWER_FALLBACK_FLOOR_KW) if t <= base}
    pool.add(base)
    return sorted(pool, reverse=True)


async def _query_best_station(
    db_path: str,
    lat: float,
    lng: float,
    radius_km: float,
    min_power_kw: float,
    max_price: Optional[float],
    allowed_providers: Optional[list[str]],
) -> Optional[dict]:
    results = await find_nearby(
        db_path, lat, lng, radius_km=radius_km, sort_by="speed", limit=50, max_price=max_price
    )
    candidates = [s for s in results if s.get("max_power", 0.0) >= min_power_kw]
    if allowed_providers:
        candidates = [s for s in candidates if s.get("provider_name") in allowed_providers]
    if not candidates:
        return None
    candidates.sort(key=lambda s: (-s.get("max_power", 0.0), s.get("distance_km", math.inf)))
    return candidates[0]


async def find_station_near_point(
    db_path: str,
    lat: float,
    lng: float,
    min_power_kw: Optional[float] = None,
    max_price: Optional[float] = None,
    allowed_providers: Optional[list[str]] = None,
) -> tuple[Optional[dict], dict]:
    """
    מוצא את עמדת הטעינה המתאימה ביותר בסביבת נקודה על ציר הנסיעה, תוך כיבוד
    העדפות המשתמש (הספק מינימלי, מחיר מקסימלי, מפעילים מועדפים) ורדיוס חיפוש הולך וגדל.

    אם לא נמצאה עמדה שעומדת בכל ההעדפות, ההעדפות מוקלות בהדרגה (קודם מפעילים
    מועדפים, אחר כך תקרת מחיר, ולבסוף סף ההספק המינימלי) עד שנמצאת עמדה או שאוזלות
    האפשרויות. מחזיר (עמדה או None, dict המתאר אילו הקלות בוצעו בפועל).
    """
    thresholds = _power_thresholds(min_power_kw)
    preferred_power = thresholds[0]
    relaxed = {"providers": False, "price": False, "power_kw": None}

    # שלב 1: כל ההעדפות כלשונן.
    for radius_km in TRIP_SEARCH_RADII_KM:
        station = await _query_best_station(db_path, lat, lng, radius_km, preferred_power, max_price, allowed_providers)
        if station is not None:
            relaxed["power_kw"] = preferred_power
            return station, relaxed

    # שלב 2: הסרת הגבלת המפעילים המועדפים.
    if allowed_providers:
        for radius_km in TRIP_SEARCH_RADII_KM:
            station = await _query_best_station(db_path, lat, lng, radius_km, preferred_power, max_price, None)
            if station is not None:
                relaxed["providers"] = True
                relaxed["power_kw"] = preferred_power
                return station, relaxed

    # שלב 3: הסרת תקרת המחיר המקסימלי.
    if max_price is not None:
        for radius_km in TRIP_SEARCH_RADII_KM:
            station = await _query_best_station(db_path, lat, lng, radius_km, preferred_power, None, None)
            if station is not None:
                relaxed["providers"] = bool(allowed_providers)
                relaxed["price"] = True
                relaxed["power_kw"] = preferred_power
                return station, relaxed

    # שלב 4: הקלה בסף ההספק המינימלי, ללא הגבלת מפעיל או מחיר.
    for power_t in thresholds[1:]:
        for radius_km in TRIP_SEARCH_RADII_KM:
            station = await _query_best_station(db_path, lat, lng, radius_km, power_t, None, None)
            if station is not None:
                relaxed["providers"] = bool(allowed_providers)
                relaxed["price"] = max_price is not None
                relaxed["power_kw"] = power_t
                return station, relaxed

    return None, relaxed


async def plan_trip(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    db_path: str,
    *,
    real_range_km: float = TRIP_DEFAULT_REAL_RANGE_KM,
    battery_percent: float = TRIP_DEFAULT_BATTERY_PERCENT,
    safety_margin_percent: float = TRIP_DEFAULT_SAFETY_MARGIN_PERCENT,
    consumption_kwh_per_100km: float = TRIP_CONSUMPTION_KWH_PER_100KM,
    min_power_kw: Optional[float] = None,
    max_price: Optional[float] = None,
    allowed_providers: Optional[list[str]] = None,
) -> dict:
    """
    מתכנן נסיעה בין מוצא ליעד: מחשב מרחק כביש משוער וזמן, גוזר טווח זמין מפרמטרי
    הרכב של המשתמש (טווח אמיתי/אחוז סוללה/מרווח ביטחון), ובוחר עמדות טעינה לאורך
    הציר הישר תוך כיבוד העדפות הטעינה (הספק/מחיר/מפעילים).

    מחזיר dict עם: total_distance_km (מרחק כביש משוער), straight_line_km (קו אווירי),
    duration_hours, num_stops, available_range_km, car_params (הפרמטרים ששימשו לחישוב),
    stops (רשימת {segment_index, distance_from_origin_km, station, relaxation_note}),
    missing_segments (רשימת {segment_index, distance_km} לקטעים בלי עמדה מתאימה).
    """
    straight_line_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    total_distance_km = straight_line_km * TRIP_ROAD_DISTANCE_FACTOR
    duration_hours = total_distance_km / TRIP_AVG_SPEED_KMH

    available_range_km = calculate_available_range_km(real_range_km, battery_percent, safety_margin_percent)
    num_stops = calculate_stops_needed(total_distance_km, available_range_km)

    stops: list[dict] = []
    missing_segments: list[dict] = []

    leg_km = available_range_km * TRIP_STOP_SEARCH_FRACTION

    for i in range(1, num_stops + 1):
        target_distance_km = min(i * leg_km, total_distance_km)
        fraction = target_distance_km / total_distance_km if total_distance_km > 0 else 0.0
        point_lat, point_lng = interpolate_point(origin_lat, origin_lng, dest_lat, dest_lng, fraction)

        station, relaxed = await find_station_near_point(
            db_path, point_lat, point_lng,
            min_power_kw=min_power_kw, max_price=max_price, allowed_providers=allowed_providers,
        )
        if station is None:
            missing_segments.append({"segment_index": i, "distance_km": target_distance_km})
        else:
            stops.append({
                "segment_index": i,
                "distance_from_origin_km": target_distance_km,
                "station": station,
                "relaxation": relaxed,
            })

    return {
        "origin": {"lat": origin_lat, "lng": origin_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "straight_line_km": straight_line_km,
        "total_distance_km": total_distance_km,
        "duration_hours": duration_hours,
        "num_stops": num_stops,
        "available_range_km": available_range_km,
        "car_params": {
            "real_range_km": real_range_km,
            "battery_percent": battery_percent,
            "safety_margin_percent": safety_margin_percent,
            "consumption_kwh_per_100km": consumption_kwh_per_100km,
            "min_power_kw": min_power_kw,
        },
        "stops": stops,
        "missing_segments": missing_segments,
    }
