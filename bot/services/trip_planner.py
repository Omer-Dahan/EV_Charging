import asyncio
import bisect
import logging
import math
from typing import Iterable, Optional

import requests

from bot.services.station_search import find_nearby, haversine_km

logger = logging.getLogger(__name__)

# ברירות מחדל למצב נסיעה, בשימוש כאשר המשתמש לא הגדיר ערך אישי בהגדרות הנסיעה שלו.
TRIP_DEFAULT_REAL_RANGE_KM = 350.0
TRIP_DEFAULT_BATTERY_PERCENT = 80.0
TRIP_DEFAULT_SAFETY_MARGIN_PERCENT = 10.0
TRIP_CONSUMPTION_KWH_PER_100KM = 18.0
TRIP_AVG_SPEED_KMH = 90.0

# לאיזו רמת סוללה מניחים שהנהג טוען בכל עצירה. זה מה שמחזיר את הטווח המלא של הרכב
# אחרי העצירה הראשונה, במקום להמשיך לגרור את אחוז הסוללה שאיתו יצאנו לדרך.
TRIP_DEFAULT_RECHARGE_TARGET_PERCENT = 100.0

# חלון החיפוש לעצירה הבא, כשבר מהטווח הזמין ברגל הנוכחית: לא קרוב מדי (בזבוז עצירה)
# ולא על קצה הטווח ממש (אין מרווח אם העמדה תפוסה או חסומה).
TRIP_STOP_WINDOW_MIN_FRACTION = 0.60
TRIP_STOP_WINDOW_MAX_FRACTION = 0.95
TRIP_STOP_WINDOW_SAMPLES = 5

# עמדה שהוטלה על המסלול רחוק מדי ממנו היא סטייה ולא עצירה בדרך.
TRIP_MAX_OFF_ROUTE_KM = 30.0
# רדיוס שאיבת המועמדים סביב כל נקודת דגימה, וצפיפות הדגימות לאורך הקטע. המרווח בין
# דגימות קטן מהרדיוס כדי שהרצועה סביב המסלול תכוסה ברציפות, בלי חורים בין דגימה לדגימה.
TRIP_ROUTE_POOL_RADIUS_KM = 45.0
TRIP_SAMPLE_SPACING_KM = 30.0
TRIP_MAX_SAMPLES_PER_LEG = 16
# עצירה שלא מקדמת אותנו בפועל תיצור לולאה אינסופית; דורשים התקדמות מינימלית.
TRIP_MIN_LEG_PROGRESS_KM = 5.0
# חסם ביטחון על מספר האיטרציות, גם אם הנתונים חריגים (טווח זעיר, מסלול ענק).
TRIP_MAX_STOPS = 12

# מרחק כביש בישראל ארוך בממוצע ב-15%-25% ממרחק קו אווירי (למשל ת"א-אילת: כ-282 ק"מ
# קו אווירי מול כ-330 ק"מ כביש בפועל). משמש רק כגיבוי, כששירות הניתוב לא זמין.
TRIP_ROAD_DISTANCE_FACTOR = 1.25

# OSRM הציבורי - ניתוב חינמי ללא מפתח. כישלון/timeout מפיל אותנו חזרה לקו אווירי.
TRIP_OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}"
TRIP_ROUTING_TIMEOUT_S = 6.0

TRIP_SEARCH_RADII_KM: tuple[float, ...] = (10.0, 20.0, 40.0)
TRIP_PREFERRED_MIN_POWER_KW = 150.0
TRIP_POWER_FALLBACK_FLOOR_KW = 1.0


class TripRangeError(ValueError):
    """אין בכלל טווח נסיעה זמין (סוללה מתחת למרווח הביטחון) - אי אפשר לתכנן נסיעה."""


# ==============================================================================
# טווחים ואחוזי סוללה
# ==============================================================================


def calculate_available_range_km(
    real_range_km: float,
    battery_percent: float,
    safety_margin_percent: float,
) -> float:
    """טווח הנסיעה עם רמת הסוללה הנתונה: החלק שמעל מרווח הביטחון, מתוך הטווח האמיתי."""
    usable_percent = battery_percent - safety_margin_percent
    if usable_percent <= 0:
        return 0.0
    return real_range_km * (usable_percent / 100.0)


def calculate_recharged_range_km(
    real_range_km: float,
    recharge_target_percent: float = TRIP_DEFAULT_RECHARGE_TARGET_PERCENT,
    safety_margin_percent: float = TRIP_DEFAULT_SAFETY_MARGIN_PERCENT,
) -> float:
    """הטווח שעומד לרשות הנהג *אחרי* עצירת טעינה - לפי רמת הטעינה שאליה הוא טוען.

    זה ההבדל המהותי מהרגל הראשונה: מי שיצא לדרך עם 20% ממשיך אחרי העצירה הראשונה
    עם סוללה מלאה, ולכן הרגליים הבאות ארוכות בהרבה מהראשונה.
    """
    return calculate_available_range_km(real_range_km, recharge_target_percent, safety_margin_percent)


def calculate_stops_needed(distance_km: float, range_km: float) -> int:
    """מספר עצירות הטעינה הנדרשות = ceil(מרחק/טווח) - 1, לא פחות מאפס.

    הערכה גסה לטווח *אחיד*, בשימוש רק כדי לדווח כמה עצירות עוד נדרשו כשהתכנון
    נעצר באמצע (לא נמצאה עמדה בקטע מסוים).
    """
    if distance_km <= 0 or range_km <= 0:
        return 0
    return max(0, math.ceil(distance_km / range_km) - 1)


def battery_percent_after_km(start_percent: float, distance_km: float, real_range_km: float) -> float:
    """אחוז הסוללה אחרי נסיעה של distance_km, בהנחת צריכה אחידה לאורך הטווח האמיתי."""
    if real_range_km <= 0:
        return start_percent
    return max(0.0, start_percent - (distance_km / real_range_km) * 100.0)


# ==============================================================================
# מסלול (ניתוב לפי כבישים, עם נפילה לקו אווירי)
# ==============================================================================


def interpolate_point(
    lat1: float, lng1: float, lat2: float, lng2: float, fraction: float
) -> tuple[float, float]:
    """נקודה על הציר הישר (אינטרפולציה לינארית) בין שתי נקודות, לפי fraction ב-[0,1]."""
    fraction = max(0.0, min(1.0, fraction))
    return lat1 + (lat2 - lat1) * fraction, lng1 + (lng2 - lng1) * fraction


def _cumulative_km(coords: list[tuple[float, float]]) -> list[float]:
    cumulative = [0.0]
    for (lat1, lng1), (lat2, lng2) in zip(coords, coords[1:]):
        cumulative.append(cumulative[-1] + haversine_km(lat1, lng1, lat2, lng2))
    return cumulative


def _make_route(
    coords: list[tuple[float, float]],
    total_km: float,
    source: str,
    duration_hours: Optional[float] = None,
) -> dict:
    """מסלול = רשימת נקודות + מרחק מצטבר בכל נקודה, מנורמל כך שהסוף שווה ל-total_km.

    הנרמול מאפשר להשתמש באותו מבנה גם לגיאומטריה אמיתית של OSRM וגם לקו אווירי
    מוכפל במקדם כביש, בלי שהקוד שמעל יצטרך לדעת מאיפה הגיע המסלול.
    """
    cumulative = _cumulative_km(coords)
    raw_total = cumulative[-1]
    if raw_total > 0 and total_km > 0:
        scale = total_km / raw_total
        cumulative = [c * scale for c in cumulative]
    return {
        "coords": coords,
        "cumulative_km": cumulative,
        "total_km": total_km,
        "source": source,
        "duration_hours": duration_hours,
    }


def build_straight_line_route(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
) -> dict:
    """מסלול גיבוי: קו אווירי בין המוצא ליעד, שאורכו מוכפל במקדם הכביש."""
    coords = [(origin_lat, origin_lng), (dest_lat, dest_lng)]
    straight_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    return _make_route(coords, straight_km * TRIP_ROAD_DISTANCE_FACTOR, "straight_line")


def _parse_osrm_payload(payload: dict) -> Optional[dict]:
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        return None
    routes = payload.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    geometry = (route.get("geometry") or {}).get("coordinates") or []
    # OSRM מחזיר [lng, lat]; אנחנו עובדים ב-(lat, lng) לכל אורך הקוד.
    coords = [(float(point[1]), float(point[0])) for point in geometry if len(point) >= 2]
    if len(coords) < 2:
        return None
    distance_km = float(route.get("distance") or 0.0) / 1000.0
    if distance_km <= 0:
        return None
    duration_s = float(route.get("duration") or 0.0)
    duration_hours = duration_s / 3600.0 if duration_s > 0 else None
    return _make_route(coords, distance_km, "osrm", duration_hours)


def _fetch_osrm_route_sync(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, timeout_s: float
) -> Optional[dict]:
    url = TRIP_OSRM_URL.format(lat1=origin_lat, lng1=origin_lng, lat2=dest_lat, lng2=dest_lng)
    response = requests.get(
        url, params={"overview": "simplified", "geometries": "geojson"}, timeout=timeout_s
    )
    response.raise_for_status()
    return _parse_osrm_payload(response.json())


async def fetch_road_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    timeout_s: float = TRIP_ROUTING_TIMEOUT_S,
) -> Optional[dict]:
    """מסלול לפי כבישים מ-OSRM, או None אם השירות לא זמין/החזיר תשובה לא שמישה.

    תכנון נסיעה הוא לא נתיב קריטי שמותר לו להיכשל בגלל שירות חיצוני, ולכן כל תקלה
    כאן נבלעת בכוונה והקורא נופל לקו האווירי.
    """
    try:
        return await asyncio.to_thread(
            _fetch_osrm_route_sync, origin_lat, origin_lng, dest_lat, dest_lng, timeout_s
        )
    except Exception:
        logger.warning("OSRM routing failed, falling back to straight line", exc_info=True)
        return None


async def build_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    use_routing: bool = True,
) -> dict:
    if use_routing:
        route = await fetch_road_route(origin_lat, origin_lng, dest_lat, dest_lng)
        if route is not None:
            return route
    return build_straight_line_route(origin_lat, origin_lng, dest_lat, dest_lng)


def point_at_km(route: dict, km: float) -> tuple[float, float]:
    """הנקודה על המסלול במרחק km מהמוצא (אינטרפולציה בתוך הקטע המתאים)."""
    coords = route["coords"]
    cumulative = route["cumulative_km"]
    km = max(0.0, min(km, cumulative[-1]))
    for i in range(1, len(cumulative)):
        if cumulative[i] >= km:
            segment_km = cumulative[i] - cumulative[i - 1]
            fraction = (km - cumulative[i - 1]) / segment_km if segment_km > 0 else 0.0
            return interpolate_point(*coords[i - 1], *coords[i], fraction)
    return coords[-1]


def _to_local_xy(lat: float, lng: float, ref_lat: float) -> tuple[float, float]:
    """שיטוח lat/lng לצירי ק"מ סביב קו רוחב ייחוס, כדי לחשב מרחק נקודה-קטע בגאומטריה שטוחה."""
    km_per_deg_lat = 110.574
    km_per_deg_lng = 111.320 * math.cos(math.radians(ref_lat))
    return lng * km_per_deg_lng, lat * km_per_deg_lat


def _segment_index_range(
    route: dict, from_km: float, to_km: float, padding_km: float
) -> tuple[int, int]:
    """טווח האינדקסים של קטעי המסלול שנוגעים ב-[from_km, to_km] בתוספת שוליים.

    הטלת מאות עמדות על מסלול בן אלפי קטעים היא עבודה מיותרת: לכל רגל מספיק להסתכל
    על הקטעים שסביב חלון החיפוש שלה.
    """
    cumulative = route["cumulative_km"]
    low = bisect.bisect_left(cumulative, from_km - padding_km) - 1
    high = bisect.bisect_right(cumulative, to_km + padding_km)
    last = max(0, len(cumulative) - 1)
    return max(0, low), min(high, last)


def project_on_route(
    route: dict, lat: float, lng: float, segment_bounds: Optional[tuple[int, int]] = None
) -> tuple[float, float]:
    """הטלת נקודה על המסלול -> (מרחק מהמוצא לאורך המסלול, מרחק אווירי מהמסלול), בק"מ."""
    coords = route["coords"]
    cumulative = route["cumulative_km"]
    first, last = segment_bounds or (0, len(coords) - 1)
    best_along_km = 0.0
    best_off_km = math.inf

    for i in range(first, min(last, len(coords) - 1)):
        (a_lat, a_lng), (b_lat, b_lng) = coords[i], coords[i + 1]
        px, py = _to_local_xy(lat, lng, a_lat)
        ax, ay = _to_local_xy(a_lat, a_lng, a_lat)
        bx, by = _to_local_xy(b_lat, b_lng, a_lat)
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        t = 0.0 if length_sq == 0 else ((px - ax) * dx + (py - ay) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        off_km = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if off_km < best_off_km:
            best_off_km = off_km
            segment_km = cumulative[i + 1] - cumulative[i]
            best_along_km = cumulative[i] + t * segment_km

    return best_along_km, best_off_km


# ==============================================================================
# בחירת עמדות
# ==============================================================================


def _power_thresholds(min_power_kw: Optional[float]) -> list[float]:
    """סולם ירידה של סף הספק: מהעדפת המשתמש (או ברירת המחדל) ועד רצפה מינימלית."""
    base = min_power_kw if min_power_kw is not None else TRIP_PREFERRED_MIN_POWER_KW
    pool = {t for t in (100.0, 50.0, TRIP_POWER_FALLBACK_FLOOR_KW) if t <= base}
    pool.add(base)
    return sorted(pool, reverse=True)


def _relaxation_steps(
    min_power_kw: Optional[float],
    max_price: Optional[float],
    allowed_providers: Optional[list[str]],
) -> list[dict]:
    """סולם ההקלות, מהמחמיר למקל: קודם מוותרים על המפעילים המועדפים, אחר כך על
    תקרת המחיר, ורק בסוף מורידים את סף ההספק המינימלי."""
    thresholds = _power_thresholds(min_power_kw)
    preferred_power = thresholds[0]
    has_providers = bool(allowed_providers)
    has_price = max_price is not None

    steps = [{"providers": False, "price": False, "power_kw": preferred_power}]
    if has_providers:
        steps.append({"providers": True, "price": False, "power_kw": preferred_power})
    if has_price:
        steps.append({"providers": has_providers, "price": True, "power_kw": preferred_power})
    for power_kw in thresholds[1:]:
        steps.append({"providers": has_providers, "price": has_price, "power_kw": power_kw})
    return steps


def _matches_step(
    station: dict,
    step: dict,
    max_price: Optional[float],
    allowed_providers: Optional[list[str]],
) -> bool:
    if station.get("max_power", 0.0) < step["power_kw"]:
        return False
    if allowed_providers and not step["providers"]:
        if station.get("provider_name") not in allowed_providers:
            return False
    if max_price is not None and not step["price"]:
        price = station.get("max_per_kwh")
        if price is not None and price > max_price:
            return False
    return True


async def find_station_near_point(
    db_path: str,
    lat: float,
    lng: float,
    min_power_kw: Optional[float] = None,
    max_price: Optional[float] = None,
    allowed_providers: Optional[list[str]] = None,
    exclude_ids: Optional[Iterable] = None,
) -> tuple[Optional[dict], dict]:
    """
    מוצא את עמדת הטעינה המתאימה ביותר בסביבת נקודה, תוך כיבוד העדפות המשתמש
    (הספק מינימלי, מחיר מקסימלי, מפעילים מועדפים) ורדיוס חיפוש הולך וגדל.

    אם לא נמצאה עמדה שעומדת בכל ההעדפות, ההעדפות מוקלות בהדרגה לפי _relaxation_steps
    עד שנמצאת עמדה או שאוזלות האפשרויות. exclude_ids מדלג על עמדות שכבר נבחרו
    לעצירה אחרת באותה נסיעה. מחזיר (עמדה או None, dict המתאר אילו הקלות בוצעו).
    """
    excluded = set(exclude_ids or ())
    for step in _relaxation_steps(min_power_kw, max_price, allowed_providers):
        for radius_km in TRIP_SEARCH_RADII_KM:
            stations = await find_nearby(
                db_path, lat, lng, radius_km=radius_km, sort_by="speed", limit=50,
                max_price=None if step["price"] else max_price,
            )
            matches = [
                s for s in stations
                if s.get("id") not in excluded
                and _matches_step(s, step, max_price, allowed_providers)
            ]
            if matches:
                matches.sort(key=lambda s: (-s.get("max_power", 0.0), s.get("distance_km", math.inf)))
                return matches[0], dict(step)
    return None, {"providers": False, "price": False, "power_kw": None}


def _leg_sample_points(from_km: float, to_km: float) -> list[float]:
    """נקודות דגימה על המסלול בתוך קטע, בצפיפות שמבטיחה שרדיוס החיפוש סביב כל נקודה
    מכסה את הקטע כולו בלי חורים."""
    span_km = max(0.0, to_km - from_km)
    count = max(TRIP_STOP_WINDOW_SAMPLES, math.ceil(span_km / TRIP_SAMPLE_SPACING_KM) + 1)
    count = min(count, TRIP_MAX_SAMPLES_PER_LEG)
    if count <= 1 or span_km == 0:
        return [to_km]
    step = span_km / (count - 1)
    return [from_km + step * i for i in range(count)]


async def _collect_leg_candidates(
    db_path: str,
    route: dict,
    from_km: float,
    to_km: float,
    reachable_limit_km: float,
    min_progress_km: float,
    exclude_ids: set,
) -> list[dict]:
    """
    כל העמדות שנמצאות בקרבת קטע המסלול [from_km, to_km], כשלכל אחת מחושב המיקום
    האמיתי שלה *לאורך* המסלול ומרחקה מהמסלול.

    זה הלב של התיקון לעומת הגרסה הקודמת: שם נבחרה עמדה אחת ליד נקודה מחושבת ובלי
    לדעת איפה היא נופלת על הדרך, כך שאפשר היה לקבל עמדה מאחורינו או מחוץ לטווח.
    """
    segment_bounds = _segment_index_range(route, from_km, to_km, TRIP_ROUTE_POOL_RADIUS_KM)
    candidates: dict = {}
    seen: set = set(exclude_ids)

    for sample_km in _leg_sample_points(from_km, to_km):
        lat, lng = point_at_km(route, sample_km)
        _, nearby = await find_nearby(
            db_path, lat, lng, radius_km=TRIP_ROUTE_POOL_RADIUS_KM, return_all=True
        )
        for station in nearby:
            station_id = station.get("id")
            key = station_id if station_id is not None else (station.get("lat"), station.get("lng"))
            if key in seen:
                continue
            seen.add(key)
            along_km, off_route_km = project_on_route(
                route, station["lat"], station["lng"], segment_bounds
            )
            if off_route_km > TRIP_MAX_OFF_ROUTE_KM:
                continue
            if not (min_progress_km <= along_km <= reachable_limit_km):
                continue
            candidates[key] = {
                "station": station,
                "along_km": along_km,
                "off_route_km": off_route_km,
            }
    return list(candidates.values())


def _best_candidate(
    candidates: list[dict],
    min_power_kw: Optional[float],
    max_price: Optional[float],
    allowed_providers: Optional[list[str]],
) -> Optional[dict]:
    """מבין המועמדים בקטע: העמדה שמכבדת הכי הרבה מהעדפות המשתמש, ובין שוות -
    זו שמקדמת אותנו הכי רחוק (כדי לא לבזבז עצירה קרוב מדי)."""
    for step in _relaxation_steps(min_power_kw, max_price, allowed_providers):
        matches = [
            c for c in candidates
            if _matches_step(c["station"], step, max_price, allowed_providers)
        ]
        if matches:
            best = max(matches, key=lambda c: (c["along_km"], -c["off_route_km"]))
            return {**best, "relaxation": dict(step)}
    return None


async def _find_stop_for_leg(
    db_path: str,
    route: dict,
    leg_start_km: float,
    range_km: float,
    *,
    min_power_kw: Optional[float],
    max_price: Optional[float],
    allowed_providers: Optional[list[str]],
    used_station_ids: set,
) -> Optional[dict]:
    """
    העמדה שבה כדאי לעצור בסוף הרגל הנוכחית.

    מחפשים קודם בחלון המועדף [60%, 95%] מהטווח שנותר - רחוק מספיק כדי לא לבזבז
    עצירה, וקרוב מספיק כדי להשאיר מרווח אם העמדה תפוסה. רק אם אין שם כלום מרחיבים
    לכל הקטע שבטווח: עצירה מוקדמת מהרצוי עדיין עדיפה על "לא נמצאה עמדה".
    """
    reachable_limit_km = min(leg_start_km + range_km, route["total_km"])
    min_progress_km = leg_start_km + TRIP_MIN_LEG_PROGRESS_KM
    window_end_km = min(leg_start_km + range_km * TRIP_STOP_WINDOW_MAX_FRACTION, route["total_km"])

    windows = [
        (leg_start_km + range_km * TRIP_STOP_WINDOW_MIN_FRACTION, window_end_km),
        (min_progress_km, window_end_km),
    ]

    for from_km, to_km in windows:
        if to_km < from_km:
            continue
        candidates = await _collect_leg_candidates(
            db_path, route, from_km, to_km,
            reachable_limit_km=reachable_limit_km,
            min_progress_km=min_progress_km,
            exclude_ids=used_station_ids,
        )
        best = _best_candidate(candidates, min_power_kw, max_price, allowed_providers)
        if best is not None:
            return best
    return None


# ==============================================================================
# תכנון הנסיעה
# ==============================================================================


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
    recharge_target_percent: float = TRIP_DEFAULT_RECHARGE_TARGET_PERCENT,
    min_power_kw: Optional[float] = None,
    max_price: Optional[float] = None,
    allowed_providers: Optional[list[str]] = None,
    use_routing: bool = True,
) -> dict:
    """
    מתכנן נסיעה בין מוצא ליעד בשיטת "רגל אחר רגל": בכל פעם נוסעים כמה שאפשר עם
    הסוללה שיש, עוצרים לטעינה קרוב לקצה הטווח, וממשיכים עם הטווח שאחרי הטעינה.

    זה ההבדל מהגרסה הקודמת, שחישבה את *כל* העצירות לפי הטווח ההתחלתי בלבד: מי
    שיוצא לדרך עם 20% קיבל עצירה כל ~20 ק"מ לאורך כל הנסיעה, במקום עצירה אחת
    קצרה בהתחלה ואז רגליים באורך טווח מלא.

    מחזיר dict עם: total_distance_km, straight_line_km, duration_hours, num_stops,
    available_range_km (הרגל הראשונה), recharged_range_km (הרגליים שאחרי טעינה),
    route_source ("osrm"/"straight_line"), arrival_battery_percent (ביעד),
    car_params, stops, missing_segments.
    כל עצירה כוללת גם leg_distance_km, battery_arrival_percent, battery_departure_percent
    ו-off_route_km.
    """
    available_range_km = calculate_available_range_km(real_range_km, battery_percent, safety_margin_percent)
    if available_range_km <= 0:
        raise TripRangeError(
            f"אחוז הסוללה ({battery_percent:.0f}%) אינו מעל מרווח הביטחון "
            f"({safety_margin_percent:.0f}%) - אין טווח נסיעה זמין."
        )
    recharged_range_km = calculate_recharged_range_km(
        real_range_km, recharge_target_percent, safety_margin_percent
    )

    straight_line_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    route = await build_route(origin_lat, origin_lng, dest_lat, dest_lng, use_routing=use_routing)
    total_distance_km = route["total_km"]
    duration_hours = route["duration_hours"] or (total_distance_km / TRIP_AVG_SPEED_KMH)

    stops: list[dict] = []
    missing_segments: list[dict] = []
    used_station_ids: set = set()

    leg_start_km = 0.0
    range_for_leg = available_range_km
    battery_at_leg_start = battery_percent
    unplanned_stops = 0

    while total_distance_km - leg_start_km > range_for_leg:
        if len(stops) >= TRIP_MAX_STOPS:
            unplanned_stops = calculate_stops_needed(total_distance_km - leg_start_km, range_for_leg)
            break

        best = await _find_stop_for_leg(
            db_path, route, leg_start_km, range_for_leg,
            min_power_kw=min_power_kw, max_price=max_price,
            allowed_providers=allowed_providers, used_station_ids=used_station_ids,
        )
        if best is None:
            missing_segments.append({
                "segment_index": len(stops) + 1,
                "distance_km": leg_start_km + range_for_leg * TRIP_STOP_WINDOW_MIN_FRACTION,
            })
            unplanned_stops = calculate_stops_needed(total_distance_km - leg_start_km, range_for_leg)
            break

        leg_distance_km = best["along_km"] - leg_start_km
        station_id = best["station"].get("id")
        if station_id is not None:
            used_station_ids.add(station_id)

        stops.append({
            "segment_index": len(stops) + 1,
            "distance_from_origin_km": best["along_km"],
            "leg_distance_km": leg_distance_km,
            "off_route_km": best["off_route_km"],
            "battery_arrival_percent": battery_percent_after_km(
                battery_at_leg_start, leg_distance_km, real_range_km
            ),
            "battery_departure_percent": recharge_target_percent,
            "station": best["station"],
            "relaxation": best["relaxation"],
        })

        leg_start_km = best["along_km"]
        range_for_leg = recharged_range_km
        battery_at_leg_start = recharge_target_percent

    arrival_battery_percent = battery_percent_after_km(
        battery_at_leg_start, total_distance_km - leg_start_km, real_range_km
    )

    return {
        "origin": {"lat": origin_lat, "lng": origin_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "straight_line_km": straight_line_km,
        "total_distance_km": total_distance_km,
        "duration_hours": duration_hours,
        "route_source": route["source"],
        "num_stops": len(stops) + unplanned_stops,
        "available_range_km": available_range_km,
        "recharged_range_km": recharged_range_km,
        "arrival_battery_percent": arrival_battery_percent,
        "car_params": {
            "real_range_km": real_range_km,
            "battery_percent": battery_percent,
            "safety_margin_percent": safety_margin_percent,
            "consumption_kwh_per_100km": consumption_kwh_per_100km,
            "recharge_target_percent": recharge_target_percent,
            "min_power_kw": min_power_kw,
        },
        "stops": stops,
        "missing_segments": missing_segments,
    }
