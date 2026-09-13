import asyncio
import functools
import logging
import math
import os
import tempfile
import time
from io import BytesIO
from typing import Optional
from urllib.parse import quote, urlencode

import requests
from PIL import Image, ImageDraw, ImageFont

from bot.config import settings
from bot.services.station_search import apply_smart_mix, get_station_max_power, haversine_km
from bot.storage.users_db import record_map_event

logger = logging.getLogger(__name__)

TILE_SIZE = 256
OUTPUT_WIDTH = 1600
OUTPUT_HEIGHT = 1200
MIN_ZOOM = 7
MAX_ZOOM = 19
MAX_MAP_STATIONS = 50
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "ev-charging-bot/1.0 (Telegram bot for EV charging station search in Israel)"
TILE_TIMEOUT_SEC = 5
BBOX_PADDING_RATIO = 0.08
RADIUS_VIEW_FACTOR = 1.15  # המפה מציגה כ-1.15x מהרדיוס שנבחר לזום קרוב וממוקד (למשל 10 ק"מ -> ~11.5 ק"מ רוחב)
# עד כמה תחנות רחוקות מותר למתוח את התיבה מעבר לרדיוס*פקטור (מגן מפני חריגים/נתונים פגומים שמנפחים את המפה)
STATION_EXTRA_RATIO = 0.15

# סף איחוד עמדות קרובות (צבירים) למניעת חפיפת סמנים (מותאם לרזולוציה 1600x1200)
CLUSTER_MIN_DIST_KM = 0.12  # 120 מטרים
CLUSTER_MIN_PIXELS = 36.0   # 36 פיקסלים על גבי התמונה הסופית

USER_MARKER_COLOR = (30, 100, 230)
STATION_MARKER_COLOR = (30, 170, 90)
MARKER_OUTLINE = (255, 255, 255)
PIN_RED = (220, 40, 40)
PIN_RED_DARK = (170, 20, 20)
BOLT_YELLOW = (255, 214, 51)
PIN_DEST = (34, 48, 63)
PIN_DEST_DARK = (18, 27, 38)
ROUTE_BLUE = (31, 95, 208)

# תיבה מינימלית למפת מסלול (במעלות), כדי שנסיעה קצרה מאוד לא תיתן זום קיצוני.
TRIP_MIN_SPAN_DEG = 0.02
TRIP_BBOX_PADDING_RATIO = 0.12
# רוב הנסיעות הארוכות בארץ הן צפון-דרום. בתמונה רחבה כזו המסלול מצטמצם לרצועה
# דקה באמצע, אז גודל התמונה נבחר לפי כיוון המסלול עצמו.
TRIP_PORTRAIT_SIZE = (1000, 1400)
TRIP_LANDSCAPE_SIZE = (1600, 1100)
TRIP_SQUARE_SIZE = (1280, 1280)

# ===== Geoapify Static Maps (ספק איכותי יותר, אופציונלי) =====
# כשיש מפתח חינמי (MAP_PROVIDER_KEY ב-.env), משתמשים ב-Geoapify: אריחי osm-carto
# עם תמיכה מלאה בעברית (RTL תקין ושמות עבריים), רזולוציה גבוהה (1600x1200) וסמנים מותאמים.
# בלי מפתח - נופלים אוטומטית חזרה לרינדור OSM+PIL המקומי (_render_map_sync).
GEOAPIFY_STATIC_URL = "https://maps.geoapify.com/v1/staticmap"
GEOAPIFY_STYLE = "osm-carto"
GEOAPIFY_LANG = "he"
GEOAPIFY_CONNECT_TIMEOUT_SEC = 10
GEOAPIFY_TIMEOUT_SEC = 30  # read timeout (בקשה גדולה ברזולוציה 1600x1200 עם עשרות סמנים)
GEOAPIFY_MAX_RETRIES = 2   # ניסיון ראשון + retry אחד
GEOAPIFY_RETRY_DELAY_SEC = 1.5
GEOAPIFY_USER_COLOR = "#dc2828"
GEOAPIFY_STATION_COLOR = "#1eaa5a"
GEOAPIFY_DESTINATION_COLOR = "#22303f"
GEOAPIFY_ROUTE_COLOR = "#1f5fd0"


def _deg_to_pixel(lat: float, lng: float, zoom: int) -> tuple[float, float]:
    lat_rad = math.radians(lat)
    n = 2.0**zoom
    x = (lng + 180.0) / 360.0 * n * TILE_SIZE
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def _select_map_stations(
    stations: list[dict],
    user_lat: float,
    user_lng: float,
    limit: int = MAX_MAP_STATIONS,
) -> list[dict]:
    """מגביל את מספר העמדות המוצגות על המפה ל-limit (ברירת מחדל 50) באמצעות Smart Mix:

    אם יש יותר מ-limit עמדות:
    - 25 העמדות הקרובות ביותר (ממוינות לפי מרחק)
    - 25 העמדות המהירות ביותר מתוך היתר (ללא כפילויות, ממוינות לפי הספק)
    כך המפה נשארת ממוקדת וקריאה, תוך שימור עמדות קרובות ועמדות מהירות מרוחקות.
    """
    if not stations or len(stations) <= limit:
        return stations

    prepared: list[dict] = []
    for s in stations:
        if s.get("lat") is None or s.get("lng") is None:
            continue
        item = dict(s)
        if item.get("distance_km") is None:
            item["distance_km"] = haversine_km(user_lat, user_lng, item["lat"], item["lng"])
        if item.get("max_power") is None:
            item["max_power"] = get_station_max_power(item.get("connectors"))
        prepared.append(item)

    return apply_smart_mix(prepared, limit=limit, sort_by="distance")


def _bbox(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> tuple[float, float, float, float]:
    """תיבה תוחמת סביב המשתמש, בגודל פרופורציונלי לקוטר החיפוש (2 * radius_km * RADIUS_VIEW_FACTOR).

    מבטיח שכל העמדות בטווח החיפוש ייכנסו לפריים גם בציר האורך וגם בציר הרוחב של התמונה (4:3),
    עם מתיחה קלה במקרה של עמדות בקצה הטווח.
    """
    target_height_km = 2 * radius_km * RADIUS_VIEW_FACTOR / (1 + 2 * BBOX_PADDING_RATIO)
    target_width_km = target_height_km * (OUTPUT_WIDTH / OUTPUT_HEIGHT)
    lat_delta = (target_height_km / 2) / 111.32
    lon_delta = (target_width_km / 2) / (111.32 * math.cos(math.radians(user_lat)))
    lat_min, lat_max = user_lat - lat_delta, user_lat + lat_delta
    lon_min, lon_max = user_lng - lon_delta, user_lng + lon_delta

    # מתיחה קלה כדי לכלול תחנות שנופלות ממש על קצה התיבה, אך מוגבלת בתקרה קשיחה
    max_lat_delta = lat_delta * (1 + STATION_EXTRA_RATIO)
    max_lon_delta = lon_delta * (1 + STATION_EXTRA_RATIO)
    for s in stations:
        lat = s.get("lat")
        lng = s.get("lng")
        if lat is None or lng is None:
            continue
        lat_min = max(min(lat_min, lat), user_lat - max_lat_delta)
        lat_max = min(max(lat_max, lat), user_lat + max_lat_delta)
        lon_min = max(min(lon_min, lng), user_lng - max_lon_delta)
        lon_max = min(max(lon_max, lng), user_lng + max_lon_delta)

    pad_lat = (lat_max - lat_min) * BBOX_PADDING_RATIO
    pad_lon = (lon_max - lon_min) * BBOX_PADDING_RATIO
    return lat_min - pad_lat, lon_min - pad_lon, lat_max + pad_lat, lon_max + pad_lon


def _cluster_stations(
    stations: list[dict],
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
    min_dist_km: float = CLUSTER_MIN_DIST_KM,
    min_px: float = CLUSTER_MIN_PIXELS,
) -> list[dict]:
    """מאחד עמדות טעינה קרובות (באותו מתחם או סמוכות על המפה) לצביר אחד עם מונה.

    עמדה תצורף לצביר קיים אם המרחק הגיאוגרפי בינה לבין מרכז הצביר קטן מ-min_dist_km (למשל 120 מ'),
    או אם המרחק בפיקסלים על גבי תמונת המפה קטן מ-min_px (למניעת חפיפת סמנים במפות רחבות).
    """
    clusters: list[dict] = []

    def to_px(lat: float, lng: float) -> tuple[float, float]:
        if lon_max == lon_min or lat_max == lat_min:
            return width / 2, height / 2
        x = (lng - lon_min) / (lon_max - lon_min) * width
        y = (lat_max - lat) / (lat_max - lat_min) * height
        return x, y

    for s in stations:
        lat = s.get("lat")
        lng = s.get("lng")
        if lat is None or lng is None:
            continue
        sx, sy = to_px(lat, lng)
        best_cluster = None
        min_d = float("inf")

        for c in clusters:
            g_dist = haversine_km(c["lat"], c["lng"], lat, lng)
            cx, cy = to_px(c["lat"], c["lng"])
            p_dist = math.hypot(sx - cx, sy - cy)

            if g_dist <= min_dist_km or p_dist <= min_px:
                if p_dist < min_d:
                    min_d = p_dist
                    best_cluster = c

        if best_cluster is not None:
            best_cluster["stations"].append(s)
            best_cluster["lat"] = sum(x["lat"] for x in best_cluster["stations"]) / len(best_cluster["stations"])
            best_cluster["lng"] = sum(x["lng"] for x in best_cluster["stations"]) / len(best_cluster["stations"])
            best_cluster["count"] = len(best_cluster["stations"])
        else:
            clusters.append({
                "lat": lat,
                "lng": lng,
                "count": 1,
                "stations": [s],
            })

    return clusters


def _pixel_bbox_at_zoom(lat_min: float, lon_min: float, lat_max: float, lon_max: float, zoom: int):
    px_min, py_min = _deg_to_pixel(lat_max, lon_min, zoom)  # top-left
    px_max, py_max = _deg_to_pixel(lat_min, lon_max, zoom)  # bottom-right
    return px_min, py_min, px_max, py_max


def _continuous_zoom(
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
) -> float:
    """זום 'רציף' (לא שלם) שבו התיבה התוחמת ממלאת בדיוק את מימדי הפלט.

    אריחי OSM זמינים רק בזום שלם, ולכן זהו רק שלב ביניים: _render_map_sync
    מוריד אריחים בזום שלם קרוב (ceil) ואז מכווץ את התמונה חזרה לגודל היעד,
    כדי לקבל התאמה מדויקת לרדיוס החיפוש בלי "קפיצה" של רמת זום שלמה.
    """
    px_min0, py_min0, px_max0, py_max0 = _pixel_bbox_at_zoom(lat_min, lon_min, lat_max, lon_max, 0)
    width0 = max(px_max0 - px_min0, 1e-9)
    height0 = max(py_max0 - py_min0, 1e-9)
    zoom = min(math.log2(width / width0), math.log2(height / height0))
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


def _draw_user_pin(
    draw: ImageDraw.ImageDraw,
    px: float,
    py: float,
    radius: int = 18,
    tail: int = 22,
    fill=PIN_RED,
    tail_fill=PIN_RED_DARK,
) -> None:
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
        fill=tail_fill,
    )
    draw.ellipse(
        [px - radius, head_cy - radius, px + radius, head_cy + radius],
        fill=fill,
        outline=MARKER_OUTLINE,
        width=3,
    )
    inner_r = radius * 0.4
    draw.ellipse(
        [px - inner_r, head_cy - inner_r, px + inner_r, head_cy + inner_r],
        fill=MARKER_OUTLINE,
    )


def _draw_charger_icon(draw: ImageDraw.ImageDraw, px: float, py: float, radius: int = 16) -> None:
    """סמל עמדת טעינה יחידה: עיגול ירוק עם ברק צהוב במרכז."""
    draw.ellipse(
        [px - radius, py - radius, px + radius, py + radius],
        fill=STATION_MARKER_COLOR,
        outline=MARKER_OUTLINE,
        width=3,
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


def _draw_cluster_icon(
    draw: ImageDraw.ImageDraw,
    px: float,
    py: float,
    count: int,
    radius: int = 20,
    font: Optional[ImageFont.FreeTypeFont] = None,
) -> None:
    """סמל צביר עמדות טעינה: עיגול ירוק עם מספר העמדות בלבן במרכז."""
    draw.ellipse(
        [px - radius, py - radius, px + radius, py + radius],
        fill=STATION_MARKER_COLOR,
        outline=MARKER_OUTLINE,
        width=3,
    )
    text = str(count) if count <= 99 else "99+"
    if font is not None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (px - tw / 2 - bbox[0], py - th / 2 - bbox[1]),
            text,
            fill=(255, 255, 255),
            font=font,
        )


@functools.lru_cache(maxsize=8)
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a font with Hebrew glyph support."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
    return ImageFont.load_default()


def _build_basemap(
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
):
    """מוריד אריחי OSM לתיבה נתונה ומחזיר (תמונת פלט בגודל מלא, המרת lat/lng לפיקסל).

    אריחי OSM קיימים רק בזום שלם, אז מורידים אריחים בזום השלם הקרוב ביותר שעדיין
    נותן רזולוציה מספקת (ceil), ואז מכווצים בדיוק לגודל הפלט - כך מקבלים התאמה
    חלקה לתיבה המבוקשת בלי "קפיצות" גסות של רמת זום.
    """
    z_cont = _continuous_zoom(lat_min, lon_min, lat_max, lon_max, width, height)
    zoom = min(MAX_ZOOM, math.ceil(z_cont))
    n_tiles = 2**zoom
    resize_factor = 2 ** (zoom - z_cont)  # >= 1

    px_min, py_min, px_max, py_max = _pixel_bbox_at_zoom(lat_min, lon_min, lat_max, lon_max, zoom)
    cx, cy = (px_min + px_max) / 2, (py_min + py_max) / 2
    window_w = width * resize_factor
    window_h = height * resize_factor
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
    final = cropped.resize((width, height), Image.LANCZOS)
    scale_x = width / window_w
    scale_y = height / window_h

    def to_final_px(lat: float, lng: float) -> tuple[float, float]:
        px, py = _deg_to_pixel(lat, lng, zoom)
        return (px - crop_left) * scale_x, (py - crop_top) * scale_y

    return final, to_final_px


def _draw_attribution(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
) -> None:
    attribution = "© OpenStreetMap contributors"
    attr_bbox = draw.textbbox((0, 0), attribution, font=font)
    attr_w, attr_h = attr_bbox[2] - attr_bbox[0], attr_bbox[3] - attr_bbox[1]
    pad = 8
    draw.rectangle(
        [width - attr_w - 2 * pad, height - attr_h - 2 * pad, width, height],
        fill=(255, 255, 255, 180),
    )
    draw.text((width - attr_w - pad, height - attr_h - pad), attribution, fill=(60, 60, 60), font=font)


def _save_png(image: Image.Image) -> str:
    fd, path = tempfile.mkstemp(prefix="ev_map_", suffix=".png")
    os.close(fd)
    image.save(path, "PNG")
    return path


def _render_map_sync(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> Optional[str]:
    stations = _select_map_stations(stations, user_lat, user_lng, MAX_MAP_STATIONS)
    lat_min, lon_min, lat_max, lon_max = _bbox(user_lat, user_lng, radius_km, stations)
    clusters = _cluster_stations(stations, lat_min, lon_min, lat_max, lon_max)

    final, to_final_px = _build_basemap(lat_min, lon_min, lat_max, lon_max)
    draw = ImageDraw.Draw(final)
    font = _load_font(22)
    cluster_font = _load_font(18)

    for c in clusters:
        fx, fy = to_final_px(c["lat"], c["lng"])
        if c["count"] == 1:
            _draw_charger_icon(draw, fx, fy, radius=16)
        else:
            _draw_cluster_icon(draw, fx, fy, c["count"], radius=20, font=cluster_font)

    ux, uy = to_final_px(user_lat, user_lng)
    _draw_user_pin(draw, ux, uy, radius=18, tail=22)

    _draw_attribution(draw, font)
    return _save_png(final)


def _geoapify_marker_param(
    lat: float,
    lng: float,
    *,
    icon: Optional[str] = None,
    text: Optional[str] = None,
    color: str,
    size,
) -> str:
    parts = [f"lonlat:{lng},{lat}", "type:awesome", f"color:{color}"]
    if text:
        parts.append(f"text:{text}")
    elif icon:
        parts.append(f"icon:{icon}")
        parts.append("icontype:awesome")
    parts.append(f"size:{size}")
    return quote(";".join(parts), safe=":;,")


def _render_map_geoapify_sync(
    user_lat: float,
    user_lng: float,
    radius_km: float,
    stations: list[dict],
    api_key: str,
) -> Optional[str]:
    """מרנדר מפה דרך Geoapify Static Maps (אריחי וקטור איכותיים + סמנים מצד השרת).

    מחזיר None בכל כשלון (מפתח לא תקף, בעיית רשת, תגובה לא תקינה) כדי ש-render_map
    יפול חזרה אוטומטית לרינדור ה-OSM/PIL המקומי."""
    stations = _select_map_stations(stations, user_lat, user_lng, MAX_MAP_STATIONS)
    lat_min, lon_min, lat_max, lon_max = _bbox(user_lat, user_lng, radius_km, stations)
    clusters = _cluster_stations(stations, lat_min, lon_min, lat_max, lon_max)

    markers = []
    for c in clusters:
        if c["count"] == 1:
            markers.append(_geoapify_marker_param(c["lat"], c["lng"], icon="bolt", color=GEOAPIFY_STATION_COLOR, size=40))
        else:
            text = str(c["count"]) if c["count"] <= 99 else "99+"
            markers.append(_geoapify_marker_param(c["lat"], c["lng"], text=text, color=GEOAPIFY_STATION_COLOR, size=40))

    # סיכת המשתמש האדומה מתווספת אחרונה כדי שתצויר מעל סמני עמדות במקרה של חפיפה
    markers.append(_geoapify_marker_param(user_lat, user_lng, icon="map-marker-alt", color=GEOAPIFY_USER_COLOR, size=52))

    params = {
        "apiKey": api_key,
        "style": GEOAPIFY_STYLE,
        "lang": GEOAPIFY_LANG,
        "width": OUTPUT_WIDTH,
        "height": OUTPUT_HEIGHT,
        "area": f"rect:{lon_min},{lat_max},{lon_max},{lat_min}",
        "format": "png",
    }
    url = f"{GEOAPIFY_STATIC_URL}?{urlencode(params)}&" + "&".join(f"marker={m}" for m in markers)
    return _fetch_geoapify_png(url)


def _fetch_geoapify_png(url: str) -> Optional[str]:
    """מוריד תמונת PNG מ-Geoapify עם retry, ומחזיר נתיב לקובץ זמני (או None בכשלון)."""
    t_start = time.time()
    for attempt in range(1, GEOAPIFY_MAX_RETRIES + 1):
        req_start = time.time()
        try:
            resp = requests.get(
                url,
                timeout=(GEOAPIFY_CONNECT_TIMEOUT_SEC, GEOAPIFY_TIMEOUT_SEC),
            )
            req_elapsed = time.time() - req_start
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                raise ValueError(f"unexpected content-type from Geoapify: {content_type!r}")
            img = Image.open(BytesIO(resp.content))
            img.load()  # מכריח דקודינג מיידי כדי לתפוס תוכן פגום/חלקי כאן ולא בהמשך
            path = _save_png(img.convert("RGB"))
            total_elapsed = time.time() - t_start
            logger.info(
                "Geoapify static map rendered successfully in %.2fs (request: %.2fs, attempt: %d/%d)",
                total_elapsed,
                req_elapsed,
                attempt,
                GEOAPIFY_MAX_RETRIES,
            )
            return path
        except Exception as exc:
            req_elapsed = time.time() - req_start
            if attempt < GEOAPIFY_MAX_RETRIES:
                logger.warning(
                    "Geoapify static map attempt %d/%d failed in %.2fs (%s). Retrying in %.1fs...",
                    attempt,
                    GEOAPIFY_MAX_RETRIES,
                    req_elapsed,
                    exc,
                    GEOAPIFY_RETRY_DELAY_SEC,
                )
                time.sleep(GEOAPIFY_RETRY_DELAY_SEC)
            else:
                logger.warning(
                    "Geoapify static map request failed after %d attempts (last took %.2fs, total %.2fs), falling back to OSM rendering: %s",
                    GEOAPIFY_MAX_RETRIES,
                    req_elapsed,
                    time.time() - t_start,
                    exc,
                    exc_info=True,
                )
                return None


def _route_spans(points: list[tuple[float, float]]) -> tuple[float, float, float, float, float]:
    """מרכז המסלול והמרחקים שהוא תופס. ציר האורך מומר ליחידות של ציר הרוחב
    (מעלת אורך מתכווצת עם קו הרוחב) כדי שאפשר יהיה להשוות בין הצירים."""
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    center_lat = (min(lats) + max(lats)) / 2
    center_lng = (min(lngs) + max(lngs)) / 2
    lat_span = max(max(lats) - min(lats), TRIP_MIN_SPAN_DEG)
    lon_span = max(max(lngs) - min(lngs), TRIP_MIN_SPAN_DEG)
    lon_scale = math.cos(math.radians(center_lat)) or 1.0
    return center_lat, center_lng, lat_span, lon_span, lon_scale


def _trip_canvas_size(points: list[tuple[float, float]]) -> tuple[int, int]:
    """גודל התמונה לפי כיוון המסלול: מסלול צפון-דרום מקבל תמונה לאורך."""
    _, _, lat_span, lon_span, lon_scale = _route_spans(points)
    ratio = (lon_span * lon_scale) / lat_span
    if ratio < 0.7:
        return TRIP_PORTRAIT_SIZE
    if ratio > 1.4:
        return TRIP_LANDSCAPE_SIZE
    return TRIP_SQUARE_SIZE


def _route_bbox(points: list[tuple[float, float]], width: int, height: int) -> tuple[float, float, float, float]:
    """תיבה תוחמת לכל נקודות המסלול, מתוחה ליחס התמונה ועם שוליים מסביב.

    בלי המתיחה ליחס, המסלול היה נצמד לשוליים בציר אחד ומצטמצם לרצועה דקה בשני.
    """
    center_lat, center_lng, lat_span, lon_span, lon_scale = _route_spans(points)

    aspect = width / height
    if (lon_span * lon_scale) / lat_span < aspect:
        lon_span = lat_span * aspect / lon_scale
    else:
        lat_span = lon_span * lon_scale / aspect

    lat_pad = lat_span * TRIP_BBOX_PADDING_RATIO
    lon_pad = lon_span * TRIP_BBOX_PADDING_RATIO
    return (
        center_lat - lat_span / 2 - lat_pad,
        center_lng - lon_span / 2 - lon_pad,
        center_lat + lat_span / 2 + lat_pad,
        center_lng + lon_span / 2 + lon_pad,
    )


def _draw_stop_marker(
    draw: ImageDraw.ImageDraw,
    px: float,
    py: float,
    number: int,
    radius: int = 22,
    font: Optional[ImageFont.FreeTypeFont] = None,
) -> None:
    """עצירת טעינה ממוספרת: עיגול ירוק עם מספר העצירה, בסדר הנסיעה."""
    draw.ellipse(
        [px - radius, py - radius, px + radius, py + radius],
        fill=STATION_MARKER_COLOR,
        outline=MARKER_OUTLINE,
        width=4,
    )
    if font is None:
        return
    text = str(number)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((px - tw / 2 - bbox[0], py - th / 2 - bbox[1]), text, fill=MARKER_OUTLINE, font=font)


def _render_trip_map_sync(
    origin: tuple[float, float],
    destination: tuple[float, float],
    stops: list[tuple[float, float]],
) -> Optional[str]:
    points = [origin, *stops, destination]
    width, height = _trip_canvas_size(points)
    lat_min, lon_min, lat_max, lon_max = _route_bbox(points, width, height)
    final, to_final_px = _build_basemap(lat_min, lon_min, lat_max, lon_max, width, height)

    draw = ImageDraw.Draw(final)
    font = _load_font(22)
    stop_font = _load_font(28)

    line = [to_final_px(lat, lng) for lat, lng in points]
    # מעטפת לבנה מתחת לקו המסלול כדי שיישאר קריא גם מעל כבישים כהים.
    draw.line(line, fill=MARKER_OUTLINE, width=11, joint="curve")
    draw.line(line, fill=ROUTE_BLUE, width=6, joint="curve")

    for i, (lat, lng) in enumerate(stops, start=1):
        sx, sy = to_final_px(lat, lng)
        _draw_stop_marker(draw, sx, sy, i, font=stop_font)

    dx, dy = to_final_px(*destination)
    _draw_user_pin(draw, dx, dy, radius=18, tail=22, fill=PIN_DEST, tail_fill=PIN_DEST_DARK)
    ox, oy = to_final_px(*origin)
    _draw_user_pin(draw, ox, oy, radius=18, tail=22)

    _draw_attribution(draw, font, width, height)
    return _save_png(final)


def _render_trip_map_geoapify_sync(
    origin: tuple[float, float],
    destination: tuple[float, float],
    stops: list[tuple[float, float]],
    api_key: str,
) -> Optional[str]:
    """מפת מסלול דרך Geoapify: קו בין הנקודות, סיכות מוצא/יעד וסמן ממוספר לכל עצירה."""
    points = [origin, *stops, destination]
    width, height = _trip_canvas_size(points)
    lat_min, lon_min, lat_max, lon_max = _route_bbox(points, width, height)

    # רק ב-size:x-large המספר בתוך הסמן יוצא קריא; גדלים מספריים מקטינים את הטקסט.
    markers = [
        _geoapify_marker_param(lat, lng, text=str(i), color=GEOAPIFY_STATION_COLOR, size="x-large")
        for i, (lat, lng) in enumerate(stops, start=1)
    ]
    markers.append(
        _geoapify_marker_param(*destination, icon="flag", color=GEOAPIFY_DESTINATION_COLOR, size="x-large")
    )
    # המוצא אחרון כדי שייצייר מעל השאר אם נקודות חופפות.
    markers.append(
        _geoapify_marker_param(*origin, icon="map-marker-alt", color=GEOAPIFY_USER_COLOR, size="x-large")
    )

    polyline = ",".join(f"{lng},{lat}" for lat, lng in points)
    # ה-# של צבע הקו חייב להיות מקודד (%23), אחרת הוא נחשב לתחילת fragment וה-URL נחתך.
    geometry = quote(
        f"polyline:{polyline};linecolor:{GEOAPIFY_ROUTE_COLOR};linewidth:6;lineopacity:0.9",
        safe=":;,",
    )

    params = {
        "apiKey": api_key,
        "style": GEOAPIFY_STYLE,
        "lang": GEOAPIFY_LANG,
        "width": width,
        "height": height,
        "area": f"rect:{lon_min},{lat_max},{lon_max},{lat_min}",
        "format": "png",
    }
    url = (
        f"{GEOAPIFY_STATIC_URL}?{urlencode(params)}"
        f"&geometry={geometry}&" + "&".join(f"marker={m}" for m in markers)
    )
    return _fetch_geoapify_png(url)


async def _record_map_metric(event_name: str, success: bool = True) -> None:
    """מדד תפעולי בלבד - כשלון ברישום שלו לא אמור להפיל שליחת מפה למשתמש."""
    try:
        await record_map_event(event_name, success=success, db_path=settings.users_db_path)
    except Exception:
        pass


async def _render_with_fallback(geoapify_render, osm_render) -> Optional[str]:
    """מריץ קודם את Geoapify (אם הוגדר מפתח) ונופל לרינדור OSM+PIL המקומי."""
    api_key = settings.map_provider_key.strip()
    if api_key:
        path = await asyncio.to_thread(geoapify_render, api_key)
        if path is not None:
            await _record_map_metric("geoapify")
            return path
        await _record_map_metric("osm_fallback")
    else:
        await _record_map_metric("osm")

    path = await asyncio.to_thread(osm_render)
    if path is None:
        await _record_map_metric("failed", success=False)
    return path


async def render_map(user_lat: float, user_lng: float, radius_km: float, stations: list[dict]) -> Optional[str]:
    """מרנדר מפה עם מיקום הנהג (סיכה אדומה) ועמדות הטעינה (סמל ברק).

    מגביל את מספר העמדות על המפה ל-50 (Smart Mix) כדי למנוע עומס ויזואלי.
    אם הוגדר MAP_PROVIDER_KEY (מפתח חינמי ל-Geoapify) - משתמשים בו לאיכות ומיקוד גבוהים
    ברזולוציה 1600x1200. אחרת, או אם הבקשה ל-Geoapify נכשלה, נופלים חזרה לרינדור
    אריחי OSM+PIL המקומי.

    מחזיר נתיב לקובץ PNG זמני, או None אם שתי הדרכים נכשלו (למשל אין רשת) - במקרה כזה
    הבוט צריך להמשיך ולשלוח את כרטיסיית העמדה גם בלי תמונה.
    """
    try:
        filtered_stations = _select_map_stations(stations, user_lat, user_lng, MAX_MAP_STATIONS)
        return await _render_with_fallback(
            lambda key: _render_map_geoapify_sync(user_lat, user_lng, radius_km, filtered_stations, key),
            lambda: _render_map_sync(user_lat, user_lng, radius_km, filtered_stations),
        )
    except Exception:
        logger.exception("failed to render map for lat=%.4f lng=%.4f radius=%s", user_lat, user_lng, radius_km)
        await _record_map_metric("failed", success=False)
        return None


async def render_trip_map(
    origin: tuple[float, float],
    destination: tuple[float, float],
    stops: list[tuple[float, float]],
) -> Optional[str]:
    """מפת מסלול לתוכנית נסיעה: מוצא, יעד, וכל עצירת טעינה ממוספרת לפי סדר הנסיעה.

    המספור על המפה תואם למספור בתקציר התוכנית, כדי שמבט אחד על התמונה יראה את כל
    הנסיעה. מחזיר נתיב ל-PNG זמני, או None אם הרינדור נכשל (אז שולחים רק טקסט).
    """
    try:
        return await _render_with_fallback(
            lambda key: _render_trip_map_geoapify_sync(origin, destination, stops, key),
            lambda: _render_trip_map_sync(origin, destination, stops),
        )
    except Exception:
        logger.exception("failed to render trip map origin=%s destination=%s stops=%d", origin, destination, len(stops))
        await _record_map_metric("failed", success=False)
        return None
