import asyncio
import logging
import math
import os
import tempfile
from io import BytesIO
from typing import Optional
from urllib.parse import quote, urlencode

import requests
from PIL import Image, ImageDraw, ImageFont

from bot.config import settings

logger = logging.getLogger(__name__)

TILE_SIZE = 256
OUTPUT_WIDTH = 800
OUTPUT_HEIGHT = 600
MIN_ZOOM = 8  # מוריד מ-10: טווח 100 ק"מ עם RADIUS_VIEW_FACTOR צריך זום נמוך יותר כדי להיכנס לפריים בלי חיתוך
MAX_ZOOM = 17
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "ev-charging-bot/1.0 (Telegram bot for EV charging station search in Israel)"
TILE_TIMEOUT_SEC = 5
BBOX_PADDING_RATIO = 0.08
RADIUS_VIEW_FACTOR = 1.15  # המפה מציגה כ-1.15x מהרדיוס שנבחר לזום קרוב וממוקד (למשל 10 ק"מ -> ~11.5 ק"מ רוחב)
# עד כמה תחנות רחוקות מותר למתוח את התיבה מעבר לרדיוס*פקטור (מגן מפני חריגים/נתונים פגומים שמנפחים את המפה)
STATION_EXTRA_RATIO = 0.15

USER_MARKER_COLOR = (30, 100, 230)
STATION_MARKER_COLOR = (30, 170, 90)
MARKER_OUTLINE = (255, 255, 255)
PIN_RED = (220, 40, 40)
PIN_RED_DARK = (170, 20, 20)
BOLT_YELLOW = (255, 214, 51)

# ===== Geoapify Static Maps (ספק איכותי יותר, אופציונלי) =====
# כשיש מפתח חינמי (MAP_PROVIDER_KEY ב-.env), משתמשים ב-Geoapify: אריחי osm-carto
# עם תמיכה מלאה בעברית (RTL תקין ושמות עבריים), רזולוציה גבוהה וסמנים מותאמים.
# בלי מפתח - נופלים אוטומטית חזרה לרינדור OSM+PIL המקומי (_render_map_sync).
GEOAPIFY_API_KEY = settings.map_provider_key.strip()
GEOAPIFY_STATIC_URL = "https://maps.geoapify.com/v1/staticmap"
GEOAPIFY_STYLE = "osm-carto"
GEOAPIFY_LANG = "he"
GEOAPIFY_TIMEOUT_SEC = 8
GEOAPIFY_USER_COLOR = "#dc2828"
GEOAPIFY_STATION_COLOR = "#1eaa5a"


def _deg_to_pixel(lat: float, lng: float, zoom: int) -> tuple[float, float]:
    lat_rad = math.radians(lat)
    n = 2.0**zoom
    x = (lng + 180.0) / 360.0 * n * TILE_SIZE
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def _bbox(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> tuple[float, float, float, float]:
    """תיבה תוחמת סביב המשתמש, בגודל פרופורציונלי לרדיוס החיפוש (RADIUS_VIEW_FACTOR),
    ולא לפי הפיזור בפועל של התחנות - כדי שבחירת טווח קטנה (למשל 20 ק"מ) תמיד תיתן
    מפה "צמודה" ולא תישאב על ידי תחנה חריגה/נתון פגום למרחק ארץ-ישראלי."""
    # התיבה נבנית ביחס-רוחב/גובה של תמונת הפלט (OUTPUT_WIDTH:OUTPUT_HEIGHT) כבר בשלב הזה,
    # אחרת _continuous_zoom "מותח" את הממד הקצר יותר כדי למלא את הפריים ומייצר מפה רחבה בהרבה מהמיועד.
    # מחולק ב-(1 + 2*BBOX_PADDING_RATIO) כדי שהרוחב הסופי המוצג (אחרי הריפוד למטה) יתקרב בפועל
    # ל-radius_km * RADIUS_VIEW_FACTOR, ולא יחרוג ממנו משמעותית.
    target_width_km = radius_km * RADIUS_VIEW_FACTOR / (1 + 2 * BBOX_PADDING_RATIO)
    target_height_km = target_width_km * (OUTPUT_HEIGHT / OUTPUT_WIDTH)
    lat_delta = (target_height_km / 2) / 111.32
    lon_delta = (target_width_km / 2) / (111.32 * math.cos(math.radians(user_lat)))
    lat_min, lat_max = user_lat - lat_delta, user_lat + lat_delta
    lon_min, lon_max = user_lng - lon_delta, user_lng + lon_delta

    # מתיחה קלה כדי לכלול תחנות שנופלות ממש על קצה התיבה, אך מוגבלת בתקרה קשיחה
    max_lat_delta = lat_delta * (1 + STATION_EXTRA_RATIO)
    max_lon_delta = lon_delta * (1 + STATION_EXTRA_RATIO)
    for s in stations:
        lat_min = max(min(lat_min, s["lat"]), user_lat - max_lat_delta)
        lat_max = min(max(lat_max, s["lat"]), user_lat + max_lat_delta)
        lon_min = max(min(lon_min, s["lng"]), user_lng - max_lon_delta)
        lon_max = min(max(lon_max, s["lng"]), user_lng + max_lon_delta)

    pad_lat = (lat_max - lat_min) * BBOX_PADDING_RATIO
    pad_lon = (lon_max - lon_min) * BBOX_PADDING_RATIO
    return lat_min - pad_lat, lon_min - pad_lon, lat_max + pad_lat, lon_max + pad_lon


def _pixel_bbox_at_zoom(lat_min: float, lon_min: float, lat_max: float, lon_max: float, zoom: int):
    px_min, py_min = _deg_to_pixel(lat_max, lon_min, zoom)  # top-left
    px_max, py_max = _deg_to_pixel(lat_min, lon_max, zoom)  # bottom-right
    return px_min, py_min, px_max, py_max


def _continuous_zoom(lat_min: float, lon_min: float, lat_max: float, lon_max: float) -> float:
    """זום 'רציף' (לא שלם) שבו התיבה התוחמת ממלאת בדיוק את מימדי הפלט.

    אריחי OSM זמינים רק בזום שלם, ולכן זהו רק שלב ביניים: _render_map_sync
    מוריד אריחים בזום שלם קרוב (ceil) ואז מכווץ את התמונה חזרה לגודל היעד,
    כדי לקבל התאמה מדויקת לרדיוס החיפוש בלי "קפיצה" של רמת זום שלמה.
    """
    px_min0, py_min0, px_max0, py_max0 = _pixel_bbox_at_zoom(lat_min, lon_min, lat_max, lon_max, 0)
    width0 = max(px_max0 - px_min0, 1e-9)
    height0 = max(py_max0 - py_min0, 1e-9)
    zoom = min(math.log2(OUTPUT_WIDTH / width0), math.log2(OUTPUT_HEIGHT / height0))
    return max(MIN_ZOOM, min(MAX_ZOOM, zoom))


def _fetch_tile(session: requests.Session, zoom: int, x: int, y: int, n_tiles: int) -> Optional[Image.Image]:
    if not (0 <= x < n_tiles and 0 <= y < n_tiles):
        return None
    try:
        resp = session.get(
            TILE_URL.format(z=zoom, x=x, y=y),
            headers={"User-Agent": USER_AGENT},
            timeout=TILE_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception:
        logger.warning("failed to fetch tile z=%s x=%s y=%s", zoom, x, y, exc_info=True)
        return None


def _draw_user_pin(draw: ImageDraw.ImageDraw, px: float, py: float, radius: int = 10, tail: int = 12) -> None:
    """סיכת מיקום קלאסית (עיגול + זנב משולש) עם החוד בדיוק על הקואורדינטה של המשתמש.

    ראש המשולש חופף לתחתית העיגול בכוונה (כדי שיתמזג חלק אליו), ורק הזנב שמתחת
    לתחתית העיגול חייב להישאר גלוי - לכן העיגול מצויר אחרי המשולש ומעליו."""
    head_cy = py - radius - tail
    draw.polygon(
        [
            (px - radius * 0.45, head_cy + radius * 0.3),
            (px + radius * 0.45, head_cy + radius * 0.3),
            (px, py),
        ],
        fill=PIN_RED_DARK,
    )
    draw.ellipse(
        [px - radius, head_cy - radius, px + radius, head_cy + radius],
        fill=PIN_RED,
        outline=MARKER_OUTLINE,
        width=2,
    )
    inner_r = radius * 0.4
    draw.ellipse(
        [px - inner_r, head_cy - inner_r, px + inner_r, head_cy + inner_r],
        fill=MARKER_OUTLINE,
    )


def _draw_charger_icon(draw: ImageDraw.ImageDraw, px: float, py: float, radius: int = 9) -> None:
    """סמל עמדת טעינה: עיגול ירוק עם ברק צהוב במרכז."""
    draw.ellipse(
        [px - radius, py - radius, px + radius, py + radius],
        fill=STATION_MARKER_COLOR,
        outline=MARKER_OUTLINE,
        width=2,
    )
    bolt = [
        (px + 0.10 * radius, py - 0.80 * radius),
        (px - 0.50 * radius, py + 0.10 * radius),
        (px - 0.05 * radius, py + 0.10 * radius),
        (px - 0.25 * radius, py + 0.80 * radius),
        (px + 0.50 * radius, py - 0.15 * radius),
        (px + 0.05 * radius, py - 0.15 * radius),
    ]
    draw.polygon(bolt, fill=BOLT_YELLOW)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    # DejaVu Sans Bold כולל גליפים עבריים (בניגוד לפונט ברירת המחדל של PIL),
    # דרוש כדי שהתוויות א/ב על הסמנים לא יוצגו כריבועי "תו חסר".
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def _render_map_sync(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> Optional[str]:
    lat_min, lon_min, lat_max, lon_max = _bbox(user_lat, user_lng, radius_km, stations)

    # אריחי OSM קיימים רק בזום שלם, אז מורידים אריחים בזום השלם הקרוב ביותר
    # שעדיין נותן רזולוציה מספקת (ceil), ואז מכווצים בדיוק לגודל הפלט -
    # כדי לקבל התאמה חלקה לרדיוס החיפוש בלי "קפיצות" גסות של רמת זום.
    z_cont = _continuous_zoom(lat_min, lon_min, lat_max, lon_max)
    zoom = min(MAX_ZOOM, math.ceil(z_cont))
    n_tiles = 2**zoom
    resize_factor = 2 ** (zoom - z_cont)  # >= 1

    px_min, py_min, px_max, py_max = _pixel_bbox_at_zoom(lat_min, lon_min, lat_max, lon_max, zoom)
    cx, cy = (px_min + px_max) / 2, (py_min + py_max) / 2
    window_w = OUTPUT_WIDTH * resize_factor
    window_h = OUTPUT_HEIGHT * resize_factor
    crop_left = cx - window_w / 2
    crop_top = cy - window_h / 2
    crop_right = crop_left + window_w
    crop_bottom = crop_top + window_h

    tile_x_min = math.floor(crop_left / TILE_SIZE)
    tile_x_max = math.floor((crop_right - 1) / TILE_SIZE)
    tile_y_min = math.floor(crop_top / TILE_SIZE)
    tile_y_max = math.floor((crop_bottom - 1) / TILE_SIZE)

    canvas_w = (tile_x_max - tile_x_min + 1) * TILE_SIZE
    canvas_h = (tile_y_max - tile_y_min + 1) * TILE_SIZE
    canvas = Image.new("RGB", (canvas_w, canvas_h), color=(224, 222, 216))

    with requests.Session() as session:
        for tx in range(tile_x_min, tile_x_max + 1):
            for ty in range(tile_y_min, tile_y_max + 1):
                tile = _fetch_tile(session, zoom, tx, ty, n_tiles)
                if tile is not None:
                    canvas.paste(tile, ((tx - tile_x_min) * TILE_SIZE, (ty - tile_y_min) * TILE_SIZE))

    canvas_crop_left = crop_left - tile_x_min * TILE_SIZE
    canvas_crop_top = crop_top - tile_y_min * TILE_SIZE
    cropped = canvas.crop((
        int(round(canvas_crop_left)),
        int(round(canvas_crop_top)),
        int(round(canvas_crop_left)) + int(round(window_w)),
        int(round(canvas_crop_top)) + int(round(window_h)),
    ))
    final = cropped.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.LANCZOS)
    scale_x = OUTPUT_WIDTH / window_w
    scale_y = OUTPUT_HEIGHT / window_h

    draw = ImageDraw.Draw(final)
    font = _load_font(14)

    def to_final_px(lat: float, lng: float) -> tuple[float, float]:
        px, py = _deg_to_pixel(lat, lng, zoom)
        return (px - crop_left) * scale_x, (py - crop_top) * scale_y

    for s in stations:
        fx, fy = to_final_px(s["lat"], s["lng"])
        _draw_charger_icon(draw, fx, fy, radius=9)

    ux, uy = to_final_px(user_lat, user_lng)
    _draw_user_pin(draw, ux, uy)

    attribution = "© OpenStreetMap contributors"
    attr_bbox = draw.textbbox((0, 0), attribution, font=font)
    attr_w, attr_h = attr_bbox[2] - attr_bbox[0], attr_bbox[3] - attr_bbox[1]
    pad = 4
    draw.rectangle(
        [OUTPUT_WIDTH - attr_w - 2 * pad, OUTPUT_HEIGHT - attr_h - 2 * pad, OUTPUT_WIDTH, OUTPUT_HEIGHT],
        fill=(255, 255, 255, 180),
    )
    draw.text((OUTPUT_WIDTH - attr_w - pad, OUTPUT_HEIGHT - attr_h - pad), attribution, fill=(60, 60, 60), font=font)

    fd, path = tempfile.mkstemp(prefix="ev_map_", suffix=".png")
    os.close(fd)
    final.save(path, "PNG")
    return path


def _geoapify_marker_param(lat: float, lng: float, *, icon: str, color: str, size: int) -> str:
    value = f"lonlat:{lng},{lat};type:awesome;color:{color};icon:{icon};icontype:awesome;size:{size}"
    return quote(value, safe=":;,")


def _render_map_geoapify_sync(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> Optional[str]:
    """מרנדר מפה דרך Geoapify Static Maps (אריחי וקטור איכותיים + סמנים מצד השרת).

    מחזיר None בכל כשלון (מפתח לא תקף, בעיית רשת, תגובה לא תקינה) כדי ש-render_map
    יפול חזרה אוטומטית לרינדור ה-OSM/PIL המקומי."""
    lat_min, lon_min, lat_max, lon_max = _bbox(user_lat, user_lng, radius_km, stations)

    markers = [_geoapify_marker_param(user_lat, user_lng, icon="map-marker-alt", color=GEOAPIFY_USER_COLOR, size=46)]
    for s in stations:
        markers.append(_geoapify_marker_param(s["lat"], s["lng"], icon="bolt", color=GEOAPIFY_STATION_COLOR, size=34))

    params = {
        "apiKey": GEOAPIFY_API_KEY,
        "style": GEOAPIFY_STYLE,
        "lang": GEOAPIFY_LANG,
        "width": OUTPUT_WIDTH,
        "height": OUTPUT_HEIGHT,
        "area": f"rect:{lon_min},{lat_max},{lon_max},{lat_min}",
        "format": "png",
    }
    url = f"{GEOAPIFY_STATIC_URL}?{urlencode(params)}&" + "&".join(f"marker={m}" for m in markers)

    try:
        resp = requests.get(url, timeout=GEOAPIFY_TIMEOUT_SEC)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise ValueError(f"unexpected content-type from Geoapify: {content_type!r}")
        img = Image.open(BytesIO(resp.content))
        img.load()  # מכריח דקודינג מיידי כדי לתפוס תוכן פגום/חלקי כאן ולא בהמשך
        fd, path = tempfile.mkstemp(prefix="ev_map_", suffix=".png")
        os.close(fd)
        img.convert("RGB").save(path, "PNG")
        return path
    except Exception:
        logger.warning("Geoapify static map request failed, falling back to OSM rendering", exc_info=True)
        return None


async def render_map(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> Optional[str]:
    """מרנדר מפה עם מיקום הנהג (סיכה אדומה) ועמדות הטעינה (סמל ברק).

    אם הוגדר MAP_PROVIDER_KEY (מפתח חינמי ל-Geoapify) - משתמשים בו לאיכות ומיקוד גבוהים
    יותר. אחרת, או אם הבקשה ל-Geoapify נכשלה, נופלים חזרה לרינדור אריחי OSM+PIL המקומי.

    מחזיר נתיב לקובץ PNG זמני, או None אם שתי הדרכים נכשלו (למשל אין רשת) - במקרה כזה
    הבוט צריך להמשיך ולשלוח את כרטיסיית העמדה גם בלי תמונה.
    """
    try:
        if GEOAPIFY_API_KEY:
            path = await asyncio.to_thread(_render_map_geoapify_sync, user_lat, user_lng, radius_km, stations)
            if path is not None:
                return path
        return await asyncio.to_thread(_render_map_sync, user_lat, user_lng, radius_km, stations)
    except Exception:
        logger.exception("failed to render map for lat=%.4f lng=%.4f radius=%s", user_lat, user_lng, radius_km)
        return None
