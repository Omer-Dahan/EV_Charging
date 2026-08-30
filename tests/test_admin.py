import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.config import Settings, is_admin
from bot.services.bot_health import (
    ErrorTrackerHandler,
    check_geoapify_health,
    check_webapp_health,
    format_bytes,
    get_database_stats,
    get_recent_errors_summary,
    get_start_time_str,
    get_uptime_str,
    setup_error_tracker,
)
from bot.storage.users_db import (
    UserSettings,
    ensure_user,
    get_map_stats,
    get_usage_stats,
    get_user_settings,
    init_users_db,
    record_map_event,
    record_search_event,
    upsert_user,
)
from bot.handlers.admin import build_admin_report, admin_keyboard, UNAUTHORIZED_MESSAGE


class TestAdminConfig(unittest.TestCase):
    def test_is_admin_check(self):
        with patch("bot.config.settings.admin_id", 123456789), patch(
            "bot.config.settings.admin_chat_id", None
        ):
            self.assertTrue(is_admin(123456789))
            self.assertFalse(is_admin(987654321))
            self.assertFalse(is_admin(None))

        with patch("bot.config.settings.admin_id", None), patch(
            "bot.config.settings.admin_chat_id", 999888777
        ):
            self.assertTrue(is_admin(999888777))
            self.assertFalse(is_admin(123456789))
            self.assertFalse(is_admin(None))

        with patch("bot.config.settings.admin_id", None), patch(
            "bot.config.settings.admin_chat_id", None
        ):
            self.assertFalse(is_admin(123456789))
            self.assertFalse(is_admin(None))

    def test_pydantic_admin_id_parsing(self):
        # Empty string handling
        s = Settings(
            TELEGRAM_API_ID=123,
            TELEGRAM_API_HASH="hash",
            BOT_TOKEN="token",
            DB_PATH="/dummy/stations.db",
            USERS_DB_PATH="/dummy/users.db",
            ADMIN_ID="",
            ADMIN_CHAT_ID="",
        )
        self.assertIsNone(s.admin_id)
        self.assertIsNone(s.admin_chat_id)

        # Valid string int
        s2 = Settings(
            TELEGRAM_API_ID=123,
            TELEGRAM_API_HASH="hash",
            BOT_TOKEN="token",
            DB_PATH="/dummy/stations.db",
            USERS_DB_PATH="/dummy/users.db",
            ADMIN_ID="1234567",
            ADMIN_CHAT_ID="7654321",
        )
        self.assertEqual(s2.admin_id, 1234567)
        self.assertEqual(s2.admin_chat_id, 7654321)


class TestStatsAndUsersDB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        self.stations_db_path = os.path.join(self.temp_dir.name, "test_stations.db")

        # Initialize users db schema
        await init_users_db(self.users_db_path)

        # Create dummy stations db schema & data
        conn = sqlite3.connect(self.stations_db_path)
        conn.execute("""
            CREATE TABLE locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cello_id TEXT UNIQUE,
                name TEXT,
                provider_name TEXT,
                has_tariffs INTEGER,
                max_per_kwh REAL,
                stations_count INTEGER
            )
        """)
        conn.execute("INSERT INTO locations (cello_id, name, provider_name, has_tariffs, max_per_kwh, stations_count) VALUES ('1', 'Loc1', 'OpA', 1, 1.5, 2)")
        conn.execute("INSERT INTO locations (cello_id, name, provider_name, has_tariffs, max_per_kwh, stations_count) VALUES ('2', 'Loc2', 'OpA', 0, NULL, 4)")
        conn.execute("INSERT INTO locations (cello_id, name, provider_name, has_tariffs, max_per_kwh, stations_count) VALUES ('3', 'Loc3', 'OpB', 1, 2.0, 1)")
        conn.commit()
        conn.close()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_ensure_user_and_usage_stats(self):
        # Initial stats
        stats = await get_usage_stats(self.users_db_path)
        self.assertEqual(stats["total_users"], 0)
        self.assertEqual(stats["total_searches"], 0)

        # Ensure user 1
        await ensure_user(1001, "Dan", "dan_user", self.users_db_path)
        # Ensure user 2
        await ensure_user(1002, "Sarah", "sarah_user", self.users_db_path)
        # Ensure user 1 again (should not duplicate)
        await ensure_user(1001, "Dan", "dan_user", self.users_db_path)

        stats = await get_usage_stats(self.users_db_path)
        self.assertEqual(stats["total_users"], 2)

        # Record searches
        await record_search_event("location", 5, self.users_db_path)
        await record_search_event("geocode", 10, self.users_db_path)

        stats = await get_usage_stats(self.users_db_path)
        self.assertEqual(stats["total_searches"], 2)
        self.assertEqual(stats["today_searches"], 2)
        self.assertEqual(stats["week_searches"], 2)

    async def test_ensure_user_preserves_preferences(self):
        # User sets custom radius and filter
        custom = UserSettings(chat_id=5000, connector_filter="CCS", default_radius=25, max_price=1.8)
        await upsert_user(custom, self.users_db_path)

        # ensure_user is called (e.g. on search)
        await ensure_user(5000, "John", "johnny", self.users_db_path)

        saved = await get_user_settings(5000, self.users_db_path)
        self.assertEqual(saved.connector_filter, "CCS")
        self.assertEqual(saved.default_radius, 25)
        self.assertEqual(saved.max_price, 1.8)
        self.assertEqual(saved.first_name, "John")

    async def test_map_events_tracking(self):
        map_stats = await get_map_stats(self.users_db_path)
        self.assertEqual(map_stats["total_maps"], 0)

        await record_map_event("geoapify", success=True, db_path=self.users_db_path)
        await record_map_event("geoapify", success=True, db_path=self.users_db_path)
        await record_map_event("osm_fallback", success=True, db_path=self.users_db_path)
        await record_map_event("none", success=False, db_path=self.users_db_path)

        map_stats = await get_map_stats(self.users_db_path)
        self.assertEqual(map_stats["total_maps"], 3)
        self.assertEqual(map_stats["geoapify_maps"], 2)
        self.assertEqual(map_stats["fallback_maps"], 1)
        self.assertEqual(map_stats["failed_maps"], 1)

    async def test_database_stats(self):
        db_stats = await get_database_stats(self.stations_db_path, self.users_db_path)
        self.assertTrue(db_stats["db_exists"])
        self.assertEqual(db_stats["locations_count"], 3)
        self.assertEqual(db_stats["priced_locations_count"], 2)
        self.assertEqual(db_stats["operators_count"], 2)
        self.assertEqual(db_stats["total_chargers"], 7)


class TestBotHealthAndPrivacy(unittest.IsolatedAsyncioTestCase):
    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1536), "1.5 KB")
        self.assertEqual(format_bytes(5 * 1024 * 1024), "5.00 MB")

    def test_uptime_str(self):
        uptime = get_uptime_str()
        self.assertIsInstance(uptime, str)
        self.assertTrue(len(uptime) > 0)
        start_str = get_start_time_str()
        self.assertIn("/", start_str)

    def test_error_tracking(self):
        setup_error_tracker()
        import logging
        test_logger = logging.getLogger("test_error_tracker")
        test_logger.error("Something went wrong with test calculation")
        summary = get_recent_errors_summary()
        self.assertIn("שגיאות", summary)
        self.assertIn("Something went wrong", summary)

    async def test_admin_report_privacy_no_leakage(self):
        # Setup dummy DB with user private info
        temp_dir = tempfile.TemporaryDirectory()
        users_path = os.path.join(temp_dir.name, "users.db")
        stations_path = os.path.join(temp_dir.name, "stations.db")

        await init_users_db(users_path)
        conn = sqlite3.connect(stations_path)
        conn.execute("CREATE TABLE locations (id INT, cello_id TEXT, name TEXT, provider_name TEXT, has_tariffs INT, max_per_kwh REAL, stations_count INT)")
        conn.commit()
        conn.close()

        # Insert user with private sensitive details
        await ensure_user(999999, "SecretPerson", "secret_username", users_path)
        await record_search_event("location", 3, users_path)

        with patch("bot.config.settings.users_db_path", users_path), \
             patch("bot.config.settings.db_path", stations_path), \
             patch("bot.config.settings.map_provider_key", ""), \
             patch("bot.services.bot_health.check_webapp_health", AsyncMock(return_value="זמין 🟢")):
            report = await build_admin_report()

            # Ensure privacy: NO user id, NO secret name, NO secret username
            self.assertNotIn("999999", report)
            self.assertNotIn("SecretPerson", report)
            self.assertNotIn("secret_username", report)

            # Ensure aggregated counts are present
            self.assertIn("משתמשים ייחודיים: <b>1</b>", report)
            self.assertIn("סה\"כ חיפושים שבוצעו: <b>1</b>", report)
            self.assertIn("📊 <b>לוח בקרה וניהול", report)

        temp_dir.cleanup()


class TestAdminHandlerAuthorization(unittest.IsolatedAsyncioTestCase):
    async def test_admin_authorized_and_unauthorized_events(self):
        from bot.handlers.admin import register_handlers
        from telethon.events import NewMessage, CallbackQuery

        mock_client = MagicMock()
        registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                registered_handlers.append((event_builder, f))
                return f
            return decorator

        mock_client.on = mock_on
        register_handlers(mock_client)

        self.assertEqual(len(registered_handlers), 2)
        msg_builder, msg_handler = registered_handlers[0]
        cb_builder, cb_handler = registered_handlers[1]

        # Case 1: Unauthorized user sends /admin
        unauth_event = AsyncMock()
        unauth_event.sender_id = 111222333
        unauth_event.chat_id = 111222333
        unauth_event.text = "/admin"

        with patch("bot.config.settings.admin_id", 999999999), patch(
            "bot.config.settings.admin_chat_id", None
        ):
            await msg_handler(unauth_event)
            unauth_event.respond.assert_called_once_with(UNAUTHORIZED_MESSAGE, parse_mode="html")

        # Case 2: Authorized admin sends /admin
        auth_event = AsyncMock()
        auth_event.sender_id = 999999999
        auth_event.chat_id = 999999999
        auth_event.text = "/admin"

        with patch("bot.config.settings.admin_id", 999999999), patch(
            "bot.config.settings.admin_chat_id", None
        ), patch("bot.handlers.admin.build_admin_report", AsyncMock(return_value="Admin Report OK")):
            await msg_handler(auth_event)
            auth_event.respond.assert_called_once()
            call_args = auth_event.respond.call_args
            self.assertEqual(call_args[0][0], "Admin Report OK")
            self.assertEqual(call_args[1]["parse_mode"], "html")

        # Case 3: Unauthorized callback query
        unauth_cb = AsyncMock()
        unauth_cb.sender_id = 111222333
        unauth_cb.chat_id = 111222333
        unauth_cb.data = b"admin:refresh"

        with patch("bot.config.settings.admin_id", 999999999), patch(
            "bot.config.settings.admin_chat_id", None
        ):
            await cb_handler(unauth_cb)
            unauth_cb.answer.assert_called_once_with("⛔ אין לך הרשאה לבצע פעולה זו.", alert=True)

        # Case 4: Authorized callback query
        auth_cb = AsyncMock()
        auth_cb.sender_id = 999999999
        auth_cb.chat_id = 999999999
        auth_cb.data = b"admin:refresh"

        with patch("bot.config.settings.admin_id", 999999999), patch(
            "bot.config.settings.admin_chat_id", None
        ), patch("bot.handlers.admin.build_admin_report", AsyncMock(return_value="Refreshed Report")):
            await cb_handler(auth_cb)
            auth_cb.edit.assert_called_once()
            call_args = auth_cb.edit.call_args
            self.assertEqual(call_args[0][0], "Refreshed Report")
            self.assertEqual(call_args[1]["parse_mode"], "html")


if __name__ == "__main__":
    unittest.main()
