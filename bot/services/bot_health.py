import asyncio
import collections
from datetime import datetime, timezone
import logging
import os
from typing import Optional, Dict, Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# שעת עליית הבוט
START_TIME = datetime.now()

# מאגר שגיאות אחרונות בזיכרון (מוגבל ל-20 רשומות, ללא מידע מזהה)
_recent_errors: collections.deque = collections.deque(maxlen=20)


class ErrorTrackerHandler(logging.Handler):
    """Logging handler שאוסף שגיאות אחרונות (ERROR ומעלה) למעקב בריאות הבוט."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.ERROR:
            msg = record.getMessage()
            # סניטציה קלה: חיתוך אורך והסרת נתונים
            sanitized = msg[:120].replace("\n", " ").strip()
            _recent_errors.append({
                "time": datetime.now().strftime("%d/%m %H:%M:%S"),
                "logger": record.name,
                "msg": sanitized,
            })


_error_handler_installed = False


def setup_error_tracker() -> None:
    """מתקין את handler השגיאות ב-root logger."""
    global _error_handler_installed
    if not _error_handler_installed:
        handler = ErrorTrackerHandler()
        logging.getLogger().addHandler(handler)
        _error_handler_installed = True


def get_uptime_str() -> str:
    """מחשב ומחזיר מחרוזת זמן פעילות (Uptime) בעברית."""
    delta = datetime.now() - START_TIME
    total_seconds = int(delta.total_seconds())

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days} ימים" if days > 1 else "יום 1")
    if hours > 0 or days > 0:
        parts.append(f"{hours} שעות" if hours != 1 else "שעה 1")
    if minutes > 0 or (days == 0 and hours == 0):
        parts.append(f"{minutes} דקות" if minutes != 1 else "דקה 1")
    if days == 0 and hours == 0 and minutes == 0:
        parts.append(f"{seconds} שניות")

    return ", ".join(parts)


def get_start_time_str() -> str:
    """מחזיר תאריך ושעת הפעלה של הבוט בפורמט קריא."""
    return START_TIME.strftime("%d/%m/%Y %H:%M:%S")


def get_recent_errors_summary() -> str:
    """מחזיר סיכום שגיאות אחרונות."""
    count = len(_recent_errors)
    if count == 0:
        return "אין שגיאות מאז ההפעלה 🟢"
    last_err = _recent_errors[-1]
    return f"{count} שגיאות נרשמו (אחרונה ב-{last_err['time']}: {last_err['msg']}) ⚠️"


def format_bytes(size_bytes: int) -> str:
    """ממיר בתים לתצוגה קריאה (KB / MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _check_geoapify_sync(api_key: str) -> str:
    if not api_key.strip():
        return "לא הוגדר (משתמש ב-OSM מקומי) ℹ️"
    url = f"https://maps.geoapify.com/v1/staticmap?apiKey={quote(api_key.strip())}&style=osm-carto&width=10&height=10&center=lonlat:34.78,32.08&zoom=10&format=png"
    try:
        resp = requests.get(url, timeout=3.5)
        if resp.status_code == 200:
            return "תקין ופעיל 🟢 (HTTP 200)"
        elif resp.status_code in (401, 403):
            return f"מפתח שגוי או לא מורשה 🔴 (HTTP {resp.status_code})"
        else:
            return f"מענה לא תקין 🔴 (HTTP {resp.status_code})"
    except requests.Timeout:
        return "פסק זמן בחיבור (Timeout) ⚠️"
    except Exception as exc:
        return f"שגיאת תקשורת ⚠️ ({type(exc).__name__})"


async def check_geoapify_health(api_key: str) -> str:
    """בודק באופן אסינכרוני את תקינות מפתח ה-Geoapify."""
    return await asyncio.to_thread(_check_geoapify_sync, api_key)


def _check_webapp_sync(webapp_url: str) -> str:
    if not webapp_url.strip():
        return "לא הוגדר ⚠️"
    try:
        resp = requests.get(webapp_url.strip(), timeout=4.0, headers={"User-Agent": "ev-charging-bot-health/1.0"})
        if resp.status_code == 200:
            return "זמין ופעיל 🟢 (HTTP 200)"
        else:
            return f"מענה שרת 🔴 (HTTP {resp.status_code})"
    except requests.Timeout:
        return "פסק זמן בחיבור ⚠️"
    except Exception as exc:
        return f"לא זמין 🔴 ({type(exc).__name__})"


async def check_webapp_health(webapp_url: str) -> str:
    """בודק באופן אסינכרוני האם ה-WebApp זמין ומחזיר HTTP 200."""
    return await asyncio.to_thread(_check_webapp_sync, webapp_url)


async def get_database_stats(db_path: str, users_db_path: str) -> Dict[str, Any]:
    """שולף סטטיסטיקות מצב מאגר הנתונים (ev_stations.db)."""
    stats = {
        "locations_count": 0,
        "priced_locations_count": 0,
        "operators_count": 0,
        "total_chargers": 0,
        "db_size": "0 B",
        "users_db_size": "0 B",
        "db_exists": False,
    }

    # גדלי קבצים
    if os.path.exists(db_path):
        stats["db_exists"] = True
        stats["db_size"] = format_bytes(os.path.getsize(db_path))
    else:
        stats["db_size"] = "קובץ לא קיים"

    if os.path.exists(users_db_path):
        stats["users_db_size"] = format_bytes(os.path.getsize(users_db_path))
    else:
        stats["users_db_size"] = "קובץ לא קיים"

    # שליפת נתונים מ-ev_stations.db
    if stats["db_exists"]:
        import aiosqlite
        try:
            async with aiosqlite.connect(db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM locations") as cursor:
                    row = await cursor.fetchone()
                    stats["locations_count"] = row[0] if row else 0

                async with db.execute(
                    "SELECT COUNT(*) FROM locations WHERE has_tariffs = 1 OR max_per_kwh IS NOT NULL"
                ) as cursor:
                    row = await cursor.fetchone()
                    stats["priced_locations_count"] = row[0] if row else 0

                async with db.execute(
                    "SELECT COUNT(DISTINCT provider_name) FROM locations WHERE provider_name IS NOT NULL AND provider_name != ''"
                ) as cursor:
                    row = await cursor.fetchone()
                    stats["operators_count"] = row[0] if row else 0

                async with db.execute("SELECT SUM(stations_count) FROM locations") as cursor:
                    row = await cursor.fetchone()
                    stats["total_chargers"] = row[0] if row and row[0] is not None else 0
        except Exception:
            logger.exception("Failed to query database stats from %s", db_path)

    return stats
