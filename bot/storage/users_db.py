import aiosqlite
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserSettings:
    chat_id: int
    first_name: str = ""
    username: str = ""
    connector_filter: str = "ALL"
    speed_filter: str = "ALL"
    default_radius: int = 10
    max_price: Optional[float] = None


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
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


async def get_user_settings(chat_id: int, db_path: str) -> UserSettings:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserSettings(
                    chat_id=row["chat_id"],
                    first_name=row["first_name"] or "",
                    username=row["username"] or "",
                    connector_filter=row["connector_filter"] or "ALL",
                    speed_filter=row["speed_filter"] or "ALL",
                    default_radius=row["default_radius"] or 10,
                    max_price=row["max_price"],
                )
            return UserSettings(chat_id=chat_id)


async def upsert_user(settings: UserSettings, db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO users (chat_id, first_name, username,
                connector_filter, speed_filter, default_radius, max_price, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username,
                connector_filter = excluded.connector_filter,
                speed_filter = excluded.speed_filter,
                default_radius = excluded.default_radius,
                max_price = excluded.max_price,
                updated_at = datetime('now')
        """, (
            settings.chat_id, settings.first_name, settings.username,
            settings.connector_filter, settings.speed_filter,
            settings.default_radius, settings.max_price,
        ))
        await db.commit()
