import aiosqlite
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


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
            except Exception:
                pass
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
                return UserSettings(
                    chat_id=row["chat_id"],
                    first_name=row["first_name"] or "",
                    username=row["username"] or "",
                    connector_filter=row["connector_filter"] or "ALL",
                    speed_filter=row["speed_filter"] or "ALL",
                    default_radius=row["default_radius"] or 10,
                    max_price=row["max_price"],
                    map_format=map_format,
                )
            return UserSettings(chat_id=chat_id)


async def upsert_user(settings: UserSettings, db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO users (chat_id, first_name, username,
                connector_filter, speed_filter, default_radius, max_price, map_format, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username,
                connector_filter = excluded.connector_filter,
                speed_filter = excluded.speed_filter,
                default_radius = excluded.default_radius,
                max_price = excluded.max_price,
                map_format = excluded.map_format,
                updated_at = datetime('now')
        """, (
            settings.chat_id, settings.first_name, settings.username,
            settings.connector_filter, settings.speed_filter,
            settings.default_radius, settings.max_price,
            settings.map_format or "document",
        ))
        await db.commit()
