import asyncio
import logging
import re
import time
from typing import Optional

import requests

from bot.config import settings
from bot.services.station_search import haversine_km, is_in_israel

logger = logging.getLogger(__name__)

GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_TIMEOUT_SEC = 5

NOMINATIM_GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "ev-charging-bot/1.0 (Israel EV charging station Telegram bot; contact=bot-admin)"
NOMINATIM_TIMEOUT_SEC = 6

_nominatim_lock = asyncio.Lock()
_nominatim_last_call = 0.0

# מטמון בזיכרון לתוצאות גיאוקודינג (שאילתה -> תוצאות) למניעת קריאות חוזרות
_GEOCODE_CACHE_MAX = 256
_geocode_cache: dict[str, list[dict]] = {}

COORD_REGEX = re.compile(
    r"^(?:geo:)?\s*([+-]?\d{1,2}(?:\.\d+)?)\s*[°NnSs]?\s*[,;\s/]\s*([+-]?\d{1,3}(?:\.\d+)?)\s*[°EeWw]?\s*$"
)
URL_COORD_REGEX = re.compile(
    r"(?:[@\?&](?:q|query|ll|loc)=|@)([+-]?\d{1,2}(?:\.\d+)?)[,;]([+-]?\d{1,3}(?:\.\d+)?)"
)


def parse_coordinates(text: str) -> Optional[tuple[float, float]]:
    """
    מזהה קואורדינטות בטקסט (לדוגמה: '32.0853, 34.7818' או לינק גוגל מפות/וויז).
    מחזיר (lat, lng) כ-float, או None אם הטקסט אינו קואורדינטות.
    מזהה אוטומטית אם המשתמש הפך בין קווי רוחב לאורך בישראל.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    val1: Optional[float] = None
    val2: Optional[float] = None

    # בדיקת regex רגיל של שני מספרים
    m = COORD_REGEX.match(cleaned)
    if m:
        try:
            val1 = float(m.group(1))
            val2 = float(m.group(2))
        except ValueError:
            return None
    else:
        # בדיקה אם נשלח קישור שמכיל קואורדינטות
        m_url = URL_COORD_REGEX.search(cleaned)
        if m_url:
            try:
                val1 = float(m_url.group(1))
                val2 = float(m_url.group(2))
            except ValueError:
                return None

    if val1 is None or val2 is None:
        return None

    # אם הקואורדינטות הן lat, lng תקינות לישראל
    if is_in_israel(val1, val2):
        return val1, val2

    # אם המשתמש הפך אותן בטעות (lng, lat)
    if is_in_israel(val2, val1):
        return val2, val1

    # אם הקואורדינטות בטווח הגיוני בעולם אך מחוץ לישראל
    if -90.0 <= val1 <= 90.0 and -180.0 <= val2 <= 180.0:
        return val1, val2

    return None


def _clean_address_text(formatted: str, props: Optional[dict] = None) -> str:
    """מנקה ומקצר מחרוזת כתובת כך שתהיה קריאה ותמציתית (הסרת מיקודים, 'ישראל' וכו')."""
    props = props or {}
    line1 = props.get("address_line1") or props.get("name") or props.get("street")
    city = props.get("city")

    if line1 and city and city not in line1:
        text = f"{line1}, {city}"
    elif formatted:
        text = formatted
    else:
        text = line1 or city or "מיקום בישראל"

    # הסרת ", ישראל" / "ישראל" מסוף המחרוזת
    text = re.sub(r",?\s*ישראל\s*$", "", text).strip()
    # הסרת מיקוד (5-7 ספרות)
    text = re.sub(r"\b\d{5,7}\b", "", text).strip()
    # ניקוי פסיקים כפולים ורווחים עודפים
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,-")


def _deduplicate_results(results: list[dict]) -> list[dict]:
    """מסנן תוצאות מחוץ לישראל ומאחד תוצאות קרובות מאוד או זהות."""
    valid = [r for r in results if is_in_israel(r.get("lat", 0), r.get("lng", 0))]
    unique: list[dict] = []

    for item in valid:
        duplicate = False
        for u in unique:
            dist = haversine_km(item["lat"], item["lng"], u["lat"], u["lng"])
            # אם המרחק פחות מ-500 מטר, או שם זהה ומרחק פחות מ-2 ק"מ - מדובר באותו אתר/רחוב
            if dist < 0.5:
                duplicate = True
                break
            if item["name"] == u["name"] and dist < 2.0:
                duplicate = True
                break
        if not duplicate:
            unique.append(item)
        if len(unique) >= 5:
            break

    return unique


def _geocode_geoapify_sync(text: str, api_key: str) -> list[dict]:
    """גיאוקודינג באמצעות Geoapify Geocoding API."""
    params = {
        "text": text,
        "apiKey": api_key,
        "filter": "countrycode:il",
        "lang": "he",
        "limit": 5,
    }
    try:
        resp = requests.get(GEOAPIFY_GEOCODE_URL, params=params, timeout=GEOAPIFY_TIMEOUT_SEC)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        raw_results = []
        for feat in features:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            lng, lat = float(coords[0]), float(coords[1])
            props = feat.get("properties", {})
            formatted = props.get("formatted", "")
            name = _clean_address_text(formatted, props)
            raw_results.append({"name": name, "lat": lat, "lng": lng})
        return _deduplicate_results(raw_results)
    except Exception:
        logger.warning("Geoapify geocoding failed for query=%r", text, exc_info=True)
        return []


def _geocode_nominatim_sync(text: str) -> list[dict]:
    """גיאוקודינג באמצעות OpenStreetMap Nominatim (fallback)."""
    params = {
        "q": text,
        "format": "json",
        "countrycodes": "il",
        "accept-language": "he",
        "addressdetails": 1,
        "limit": 5,
    }
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
    }
    try:
        resp = requests.get(
            NOMINATIM_GEOCODE_URL,
            params=params,
            headers=headers,
            timeout=NOMINATIM_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_results = []
        for item in data:
            lat = float(item["lat"])
            lng = float(item["lon"])
            addr = item.get("address", {})
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb")
            road = addr.get("road") or item.get("name")
            display_name = item.get("display_name", "")
            props = {"address_line1": road, "city": city}
            name = _clean_address_text(display_name, props)
            raw_results.append({"name": name, "lat": lat, "lng": lng})
        return _deduplicate_results(raw_results)
    except Exception:
        logger.warning("Nominatim geocoding failed for query=%r", text, exc_info=True)
        return []


async def _nominatim_rate_limit() -> None:
    """הבטחת מרווח של לפחות שנייה אחת בין קריאות ל-Nominatim (מדיניות OSM)."""
    global _nominatim_last_call
    async with _nominatim_lock:
        now = time.monotonic()
        elapsed = now - _nominatim_last_call
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _nominatim_last_call = time.monotonic()


async def geocode(text: str) -> list[dict]:
    """
    מקבל מחרוזת טקסט חופשי (שם רחוב, עיר, אתר וכו') ומחזיר רשימה של עד 5 תוצאות.
    מבנה כל תוצאה: {'name': str, 'lat': float, 'lng': float}
    
    סדר עדיפויות:
    1. Geoapify Geocoding API (אם מוגדר מפתח MAP_PROVIDER_KEY).
    2. OSM Nominatim כגיבוי אוטומטי (עם rate limit של 1 שניה ו-User-Agent ייעודי).
    """
    cleaned_query = text.strip()
    if not cleaned_query:
        return []

    # בדיקת מטמון (מנורמל לאותיות קטנות) - חוסך קריאות רשת חוזרות
    cache_key = cleaned_query.lower()
    cached = _geocode_cache.get(cache_key)
    if cached is not None:
        logger.info("geocode cache hit query=%r results=%d", cleaned_query, len(cached))
        return cached

    # 1. ניסיון ב-Geoapify כספק ראשי
    api_key = settings.map_provider_key.strip()
    if api_key:
        results = await asyncio.to_thread(_geocode_geoapify_sync, cleaned_query, api_key)
        if results:
            logger.info("geocoded via Geoapify query=%r results=%d", cleaned_query, len(results))
            _store_in_cache(cache_key, results)
            return results

    # 2. נפילה ל-Nominatim אם Geoapify נכשל או לא הוגדר מפתח
    await _nominatim_rate_limit()
    results = await asyncio.to_thread(_geocode_nominatim_sync, cleaned_query)
    logger.info("geocoded via Nominatim query=%r results=%d", cleaned_query, len(results))
    if results:
        _store_in_cache(cache_key, results)
    return results


def _store_in_cache(cache_key: str, results: list[dict]) -> None:
    """שמירת תוצאות במטמון הזיכרון עם הגבלת גודל (FIFO)."""
    if len(_geocode_cache) >= _GEOCODE_CACHE_MAX:
        _geocode_cache.pop(next(iter(_geocode_cache)))
    _geocode_cache[cache_key] = results
