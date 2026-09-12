import aiosqlite
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# עמודות שנוספו לטבלת users אחרי היצירה המקורית - כל אחת מטופלת בנפרד
# ב-init_users_db כדי לתמוך במיגרציה של DB קיים בלי לאבד נתונים.
_TRIP_MIGRATION_COLUMNS = (
    ("trip_real_range_km", "REAL DEFAULT NULL"),
    ("trip_battery_percent", "REAL DEFAULT NULL"),
    ("trip_safety_margin_percent", "REAL DEFAULT NULL"),
    ("trip_consumption_kwh_100km", "REAL DEFAULT NULL"),
    ("trip_min_power_kw", "REAL DEFAULT NULL"),
    ("trip_max_price", "REAL DEFAULT NULL"),
    ("trip_allowed_providers", "TEXT DEFAULT NULL"),
)


@dataclass
class UserSettings:
    chat_id: int
    first_name: str = ""
    username: str = ""
    connector_filter: str = "ALL"
    speed_filter: str = "ALL"
    default_radius: int = 10
    max_price: Optional[float] = None
    map_format: str = "document"
    # הגדרות מצב נסיעה (Trip Mode) - None = השתמש בברירת המחדל שמוגדרת ב-trip_planner.
    trip_real_range_km: Optional[float] = None
    trip_battery_percent: Optional[float] = None
    trip_safety_margin_percent: Optional[float] = None
    trip_consumption_kwh_100km: Optional[float] = None
    trip_min_power_kw: Optional[float] = None
    trip_max_price: Optional[float] = None
    trip_allowed_providers: List[str] = field(default_factory=list)


async def init_users_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                connector_filter TEXT DEFAULT 'ALL',
                speed_filter TEXT DEFAULT 'ALL',
                default_radius INTEGER DEFAULT 10,
                max_price REAL DEFAULT NULL,
                map_format TEXT DEFAULT 'document',
                trip_real_range_km REAL DEFAULT NULL,
                trip_battery_percent REAL DEFAULT NULL,
                trip_safety_margin_percent REAL DEFAULT NULL,
                trip_consumption_kwh_100km REAL DEFAULT NULL,
                trip_min_power_kw REAL DEFAULT NULL,
                trip_max_price REAL DEFAULT NULL,
                trip_allowed_providers TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Schema migration: add map_format column if missing in existing DB
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "map_format" not in columns:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN map_format TEXT DEFAULT 'document'")
            except Exception as e:
                logger.warning("Failed to add map_format column during migration: %s", e)

        # Schema migration: add trip-mode personalization columns if missing.
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        for column_name, column_def in _TRIP_MIGRATION_COLUMNS:
            if column_name not in columns:
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
                except Exception as e:
                    logger.warning("Failed to add %s column during migration: %s", column_name, e)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_type TEXT DEFAULT 'search',
                results_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS map_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                success INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # תוכניות נסיעה שהושלמו (Trip Mode) - נשמרות כך שהמשתמש יוכל לפתוח אותן שוב
        # גם אחרי restart של הבוט. ראה save_trip_plan/get_recent_trip_plans/get_trip_plan.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trip_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                origin_lat REAL,
                origin_lng REAL,
                origin_name TEXT,
                destination_lat REAL,
                destination_lng REAL,
                destination_name TEXT,
                total_distance_km REAL,
                battery_percent REAL,
                plan_json TEXT
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_trip_plans_chat_id ON trip_plans (chat_id, created_at DESC)"
        )
        await db.commit()


async def ensure_user(
    chat_id: int,
    first_name: str = "",
    username: str = "",
    db_path: str = "",
) -> None:
    """מוודא שהמשתמש קיים בטבלת users לצורך מניית משתמשים ייחודיים,
    מבלי לדרוס העדפות סינון קיימות.
    """
    if not db_path:
        return
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO users (chat_id, first_name, username, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(chat_id) DO UPDATE SET
                    updated_at = datetime('now'),
                    first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE users.first_name END,
                    username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END
            """, (chat_id, first_name, username))
            await db.commit()
    except Exception:
        logger.exception("Failed to ensure user in db for chat_id=%s", chat_id)


async def record_search_event(
    search_type: str = "search",
    results_count: int = 0,
    db_path: str = "",
) -> None:
    """רושם אירוע חיפוש אנונימי (ללא user_id, ללא מיקום וללא שאילתת טקסט) לצורך סטטיסטיקה."""
    if not db_path:
        return
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO search_events (search_type, results_count)
                VALUES (?, ?)
            """, (search_type, results_count))
            await db.commit()
    except Exception:
        logger.exception("Failed to record search event in db")


async def record_map_event(
    provider: str,
    success: bool = True,
    db_path: str = "",
) -> None:
    """רושם אירוע רינדור מפה אנונימי (Geoapify/OSM/fallback) לצורך סטטיסטיקת API."""
    if not db_path:
        return
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO map_events (provider, success)
                VALUES (?, ?)
            """, (provider, 1 if success else 0))
            await db.commit()
    except Exception:
        logger.exception("Failed to record map event in db")


async def get_usage_stats(db_path: str) -> Dict[str, int]:
    """שולף סטטיסטיקות שימוש מצטברות ואנונימיות מ-users.db."""
    stats = {
        "total_users": 0,
        "total_searches": 0,
        "today_searches": 0,
        "week_searches": 0,
    }
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                row = await cursor.fetchone()
                stats["total_users"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM search_events") as cursor:
                row = await cursor.fetchone()
                stats["total_searches"] = row[0] if row else 0

            async with db.execute(
                "SELECT COUNT(*) FROM search_events WHERE date(created_at, 'localtime') = date('now', 'localtime')"
            ) as cursor:
                row = await cursor.fetchone()
                stats["today_searches"] = row[0] if row else 0

            async with db.execute(
                "SELECT COUNT(*) FROM search_events WHERE created_at >= datetime('now', '-7 days')"
            ) as cursor:
                row = await cursor.fetchone()
                stats["week_searches"] = row[0] if row else 0
    except Exception:
        logger.exception("Failed to get usage stats from users db")
    return stats


async def get_map_stats(db_path: str) -> Dict[str, int]:
    """שולף סטטיסטיקת רינדור מפות מ-users.db."""
    stats = {
        "total_maps": 0,
        "geoapify_maps": 0,
        "fallback_maps": 0,
        "osm_maps": 0,
        "failed_maps": 0,
    }
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM map_events WHERE success = 1") as cursor:
                row = await cursor.fetchone()
                stats["total_maps"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM map_events WHERE provider = 'geoapify' AND success = 1") as cursor:
                row = await cursor.fetchone()
                stats["geoapify_maps"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM map_events WHERE provider = 'osm_fallback'") as cursor:
                row = await cursor.fetchone()
                stats["fallback_maps"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM map_events WHERE provider = 'osm' AND success = 1") as cursor:
                row = await cursor.fetchone()
                stats["osm_maps"] = row[0] if row else 0

            async with db.execute("SELECT COUNT(*) FROM map_events WHERE success = 0") as cursor:
                row = await cursor.fetchone()
                stats["failed_maps"] = row[0] if row else 0
    except Exception:
        logger.exception("Failed to get map stats from users db")
    return stats


async def get_user_settings(chat_id: int, db_path: str) -> UserSettings:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                map_format = "document"
                if "map_format" in row.keys() and row["map_format"]:
                    map_format = row["map_format"]
                row_keys = row.keys()
                allowed_providers: List[str] = []
                if "trip_allowed_providers" in row_keys and row["trip_allowed_providers"]:
                    try:
                        allowed_providers = json.loads(row["trip_allowed_providers"])
                    except (json.JSONDecodeError, TypeError):
                        allowed_providers = []
                return UserSettings(
                    chat_id=row["chat_id"],
                    first_name=row["first_name"] or "",
                    username=row["username"] or "",
                    connector_filter=row["connector_filter"] or "ALL",
                    speed_filter=row["speed_filter"] or "ALL",
                    default_radius=row["default_radius"] or 10,
                    max_price=row["max_price"],
                    map_format=map_format,
                    trip_real_range_km=row["trip_real_range_km"] if "trip_real_range_km" in row_keys else None,
                    trip_battery_percent=row["trip_battery_percent"] if "trip_battery_percent" in row_keys else None,
                    trip_safety_margin_percent=(
                        row["trip_safety_margin_percent"] if "trip_safety_margin_percent" in row_keys else None
                    ),
                    trip_consumption_kwh_100km=(
                        row["trip_consumption_kwh_100km"] if "trip_consumption_kwh_100km" in row_keys else None
                    ),
                    trip_min_power_kw=row["trip_min_power_kw"] if "trip_min_power_kw" in row_keys else None,
                    trip_max_price=row["trip_max_price"] if "trip_max_price" in row_keys else None,
                    trip_allowed_providers=allowed_providers,
                )
            return UserSettings(chat_id=chat_id)


async def upsert_user(settings: UserSettings, db_path: str) -> None:
    allowed_providers_json = json.dumps(settings.trip_allowed_providers) if settings.trip_allowed_providers else None
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO users (chat_id, first_name, username,
                connector_filter, speed_filter, default_radius, max_price, map_format,
                trip_real_range_km, trip_battery_percent, trip_safety_margin_percent,
                trip_consumption_kwh_100km, trip_min_power_kw, trip_max_price, trip_allowed_providers,
                updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username,
                connector_filter = excluded.connector_filter,
                speed_filter = excluded.speed_filter,
                default_radius = excluded.default_radius,
                max_price = excluded.max_price,
                map_format = excluded.map_format,
                trip_real_range_km = excluded.trip_real_range_km,
                trip_battery_percent = excluded.trip_battery_percent,
                trip_safety_margin_percent = excluded.trip_safety_margin_percent,
                trip_consumption_kwh_100km = excluded.trip_consumption_kwh_100km,
                trip_min_power_kw = excluded.trip_min_power_kw,
                trip_max_price = excluded.trip_max_price,
                trip_allowed_providers = excluded.trip_allowed_providers,
                updated_at = datetime('now')
        """, (
            settings.chat_id, settings.first_name, settings.username,
            settings.connector_filter, settings.speed_filter,
            settings.default_radius, settings.max_price,
            settings.map_format or "document",
            settings.trip_real_range_km, settings.trip_battery_percent,
            settings.trip_safety_margin_percent, settings.trip_consumption_kwh_100km,
            settings.trip_min_power_kw, settings.trip_max_price, allowed_providers_json,
        ))
        await db.commit()


async def save_trip_plan(
    chat_id: int,
    origin: Dict[str, Any],
    destination: Dict[str, Any],
    battery_percent: float,
    plan: Dict[str, Any],
    db_path: str,
) -> Optional[int]:
    """שומר תוכנית נסיעה שהושלמה, כדי שהמשתמש יוכל לפתוח אותה שוב מ"התוכניות שלי"
    גם אחרי restart של הבוט (בניגוד לזיכרון ה-session שנמחק בכל הפעלה מחדש)."""
    if not db_path:
        return None
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                INSERT INTO trip_plans (
                    chat_id, origin_lat, origin_lng, origin_name,
                    destination_lat, destination_lng, destination_name,
                    total_distance_km, battery_percent, plan_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat_id, origin["lat"], origin["lng"], origin.get("name"),
                destination["lat"], destination["lng"], destination.get("name"),
                plan.get("total_distance_km"), battery_percent, json.dumps(plan),
            ))
            await db.commit()
            return cursor.lastrowid
    except Exception:
        logger.exception("Failed to save trip plan for chat_id=%s", chat_id)
        return None


async def get_recent_trip_plans(chat_id: int, db_path: str, limit: int = 5) -> List[Dict[str, Any]]:
    """שולף את תוכניות הנסיעה השמורות האחרונות של המשתמש, מהחדשה לישנה (בלי plan_json המלא)."""
    if not db_path:
        return []
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, created_at, origin_name, destination_name, total_distance_km, battery_percent
                FROM trip_plans WHERE chat_id = ?
                ORDER BY created_at DESC, id DESC LIMIT ?
            """, (chat_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to fetch recent trip plans for chat_id=%s", chat_id)
        return []


async def get_trip_plan(plan_id: int, chat_id: int, db_path: str) -> Optional[Dict[str, Any]]:
    """שולף תוכנית נסיעה שמורה בודדת, כולל plan_json המלא (מפוענח ל-dict תחת המפתח "plan").

    השאילתה מסוננת גם לפי chat_id כדי שמשתמש לא יוכל לצפות בתוכנית של מישהו אחר
    ע"י ניחוש מזהה (id) בכפתור callback.
    """
    if not db_path:
        return None
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM trip_plans WHERE id = ? AND chat_id = ?", (plan_id, chat_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                result = dict(row)
                try:
                    result["plan"] = json.loads(result["plan_json"])
                except (json.JSONDecodeError, TypeError):
                    return None
                return result
    except Exception:
        logger.exception("Failed to fetch trip plan id=%s for chat_id=%s", plan_id, chat_id)
        return None


async def cleanup_old_trip_plans(db_path: str, days: int = 30) -> int:
    """מוחק תוכניות נסיעה ישנות יותר מ-days ימים (ברירת מחדל 30).

    נקרא פעם אחת בכל עליית בוט (main.py) כדי שהטבלה לא תגדל ללא גבול - לא רץ ברקע
    ולא דורש תזמון נפרד. תוכניות בנות 10-29 ימים נשארות; רק ה-DB לא גדל ללא סוף.
    """
    if not db_path:
        return 0
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "DELETE FROM trip_plans WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            await db.commit()
            return cursor.rowcount
    except Exception:
        logger.exception("Failed to cleanup old trip plans")
        return 0
