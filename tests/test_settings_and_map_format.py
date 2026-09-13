import os
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from telethon.tl.types import KeyboardButtonWebView

from bot.config import WEBAPP_URL

from bot.handlers.location import execute_search, send_map_image
from bot.handlers.settings import _render_main_text, register_handlers as register_settings_handlers
from bot.keyboards.inline import (
    interactive_map_keyboard,
    map_format_keyboard,
    settings_main_keyboard,
    trip_map_keyboard,
    webapp_map_url,
    webapp_trip_url,
)
from bot.states import get_session
from bot.storage.users_db import (
    UserSettings,
    ensure_user,
    get_user_settings,
    init_users_db,
    upsert_user,
)


class TestMapFormatDB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        await init_users_db(self.users_db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_default_map_format_for_new_user(self):
        settings = await get_user_settings(1001, self.users_db_path)
        self.assertEqual(settings.map_format, "interactive")

    async def test_ensure_user_default_map_format(self):
        await ensure_user(1002, "Alice", "alice_u", self.users_db_path)
        settings = await get_user_settings(1002, self.users_db_path)
        self.assertEqual(settings.first_name, "Alice")
        self.assertEqual(settings.map_format, "interactive")

    async def test_upsert_and_retrieve_interactive_format(self):
        await upsert_user(UserSettings(chat_id=1005, map_format="interactive"), self.users_db_path)

        retrieved = await get_user_settings(1005, self.users_db_path)
        self.assertEqual(retrieved.map_format, "interactive")

    async def test_upsert_and_retrieve_photo_format(self):
        user = UserSettings(chat_id=1003, map_format="photo")
        await upsert_user(user, self.users_db_path)

        retrieved = await get_user_settings(1003, self.users_db_path)
        self.assertEqual(retrieved.map_format, "photo")

    async def test_upsert_and_retrieve_document_format(self):
        user = UserSettings(chat_id=1004, map_format="document")
        await upsert_user(user, self.users_db_path)

        retrieved = await get_user_settings(1004, self.users_db_path)
        self.assertEqual(retrieved.map_format, "document")

    async def test_db_migration_adds_column_to_existing_db(self):
        mig_db_path = os.path.join(self.temp_dir.name, "old_users.db")
        conn = sqlite3.connect(mig_db_path)
        conn.execute("""
            CREATE TABLE users (
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
        conn.execute("INSERT INTO users (chat_id, first_name) VALUES (777, 'OldUser')")
        conn.commit()
        conn.close()

        # Run init_users_db to execute migration
        await init_users_db(mig_db_path)

        # Verify column exists and defaults properly
        conn = sqlite3.connect(mig_db_path)
        cursor = conn.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cursor.fetchall()]
        self.assertIn("map_format", cols)
        conn.close()

        # למשתמש הישן לא הייתה העדפה כלל (העמודה לא קיימת), ולכן הוא מקבל את החדשה.
        user_777 = await get_user_settings(777, mig_db_path)
        self.assertEqual(user_777.map_format, "interactive")

    async def test_migration_keeps_existing_static_preference(self):
        """משתמש שכבר בחר photo/document לא נדרס ע"י ברירת המחדל החדשה."""
        mig_db_path = os.path.join(self.temp_dir.name, "pref_users.db")
        await init_users_db(mig_db_path)
        await upsert_user(UserSettings(chat_id=881, map_format="document"), mig_db_path)
        await upsert_user(UserSettings(chat_id=882, map_format="photo"), mig_db_path)

        await init_users_db(mig_db_path)

        self.assertEqual((await get_user_settings(881, mig_db_path)).map_format, "document")
        self.assertEqual((await get_user_settings(882, mig_db_path)).map_format, "photo")

    async def test_db_migration_warning_logged_on_failure(self):
        mig_db_path = os.path.join(self.temp_dir.name, "fail_mig_users.db")
        conn = sqlite3.connect(mig_db_path)
        conn.execute("CREATE TABLE users (chat_id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        import aiosqlite
        orig_execute = aiosqlite.Connection.execute

        async def fake_execute(self, sql, *args, **kwargs):
            if "ALTER TABLE users ADD COLUMN map_format" in sql:
                raise Exception("database is locked")
            return await orig_execute(self, sql, *args, **kwargs)

        with patch("bot.storage.users_db.logger.warning") as mock_logger_warning, \
             patch.object(aiosqlite.Connection, "execute", new=fake_execute):
            await init_users_db(mig_db_path)
            mock_logger_warning.assert_called_once()
            self.assertIn("Failed to add map_format column", mock_logger_warning.call_args[0][0])


class TestTripSettingsDB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        await init_users_db(self.users_db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_default_trip_settings_for_new_user(self):
        settings = await get_user_settings(2001, self.users_db_path)
        self.assertIsNone(settings.trip_real_range_km)
        self.assertIsNone(settings.trip_battery_percent)
        self.assertIsNone(settings.trip_safety_margin_percent)
        self.assertIsNone(settings.trip_consumption_kwh_100km)
        self.assertIsNone(settings.trip_min_power_kw)
        self.assertIsNone(settings.trip_max_price)
        self.assertEqual(settings.trip_allowed_providers, [])

    async def test_upsert_and_retrieve_trip_settings_roundtrip(self):
        user = UserSettings(
            chat_id=2002,
            trip_real_range_km=300.0,
            trip_battery_percent=75.0,
            trip_safety_margin_percent=15.0,
            trip_consumption_kwh_100km=20.0,
            trip_min_power_kw=100.0,
            trip_max_price=2.0,
            trip_allowed_providers=["Tesla", "Ev4u"],
        )
        await upsert_user(user, self.users_db_path)

        retrieved = await get_user_settings(2002, self.users_db_path)
        self.assertEqual(retrieved.trip_real_range_km, 300.0)
        self.assertEqual(retrieved.trip_battery_percent, 75.0)
        self.assertEqual(retrieved.trip_safety_margin_percent, 15.0)
        self.assertEqual(retrieved.trip_consumption_kwh_100km, 20.0)
        self.assertEqual(retrieved.trip_min_power_kw, 100.0)
        self.assertEqual(retrieved.trip_max_price, 2.0)
        self.assertEqual(retrieved.trip_allowed_providers, ["Tesla", "Ev4u"])

    async def test_upsert_with_empty_provider_list_clears_restriction(self):
        user = UserSettings(chat_id=2003, trip_allowed_providers=["Tesla"])
        await upsert_user(user, self.users_db_path)

        user.trip_allowed_providers = []
        await upsert_user(user, self.users_db_path)

        retrieved = await get_user_settings(2003, self.users_db_path)
        self.assertEqual(retrieved.trip_allowed_providers, [])

    async def test_db_migration_adds_trip_columns_to_existing_db(self):
        mig_db_path = os.path.join(self.temp_dir.name, "old_users_trip.db")
        conn = sqlite3.connect(mig_db_path)
        conn.execute("""
            CREATE TABLE users (
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
        conn.execute("INSERT INTO users (chat_id, first_name) VALUES (778, 'OldUser')")
        conn.commit()
        conn.close()

        await init_users_db(mig_db_path)

        conn = sqlite3.connect(mig_db_path)
        cursor = conn.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cursor.fetchall()]
        conn.close()
        for col in (
            "trip_real_range_km", "trip_battery_percent", "trip_safety_margin_percent",
            "trip_consumption_kwh_100km", "trip_min_power_kw", "trip_max_price", "trip_allowed_providers",
        ):
            self.assertIn(col, cols)

        user_778 = await get_user_settings(778, mig_db_path)
        self.assertIsNone(user_778.trip_real_range_km)
        self.assertEqual(user_778.trip_allowed_providers, [])


class TestSettingsKeyboardsAndHandlers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        await init_users_db(self.users_db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    def test_settings_main_keyboard_has_map_format_button(self):
        kb = settings_main_keyboard()
        button_texts = [btn.text for row in kb for btn in row]
        button_datas = [btn.data for row in kb for btn in row]
        self.assertTrue(any("מפה" in text for text in button_texts))
        self.assertIn(b"settings:mapfmt", button_datas)

    def test_map_format_keyboard_marking(self):
        kb_doc = map_format_keyboard("document")
        interactive_btn, doc_btn, photo_btn = kb_doc[0][0], kb_doc[1][0], kb_doc[2][0]
        self.assertTrue(doc_btn.text.startswith("✅"))
        self.assertFalse(interactive_btn.text.startswith("✅"))
        self.assertFalse(photo_btn.text.startswith("✅"))

        kb_photo = map_format_keyboard("photo")
        self.assertTrue(kb_photo[2][0].text.startswith("✅"))
        self.assertFalse(kb_photo[1][0].text.startswith("✅"))

        kb_interactive = map_format_keyboard("interactive")
        self.assertTrue(kb_interactive[0][0].text.startswith("✅"))
        self.assertFalse(kb_interactive[1][0].text.startswith("✅"))
        self.assertEqual(kb_interactive[0][0].data, b"settings:mapfmt:interactive")

    async def test_render_main_text_shows_map_format(self):
        with patch("bot.config.settings.users_db_path", self.users_db_path):
            await upsert_user(UserSettings(chat_id=123, map_format="document"), self.users_db_path)
            text_doc = await _render_main_text(123)
            self.assertIn("תצוגת מפה", text_doc)
            self.assertIn("קובץ", text_doc)

            await upsert_user(UserSettings(chat_id=123, map_format="photo"), self.users_db_path)
            text_photo = await _render_main_text(123)
            self.assertIn("תצוגת מפה", text_photo)
            self.assertIn("תמונה", text_photo)

            await upsert_user(UserSettings(chat_id=123, map_format="interactive"), self.users_db_path)
            text_interactive = await _render_main_text(123)
            self.assertIn("מפה אינטראקטיבית", text_interactive)

    async def test_settings_callbacks_switch_format(self):
        mock_client = MagicMock()
        registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                registered_handlers.append((event_builder, f))
                return f
            return decorator

        mock_client.on = mock_on
        register_settings_handlers(mock_client)

        cb_settings_handler = registered_handlers[0][1]
        cb_filter_handler = registered_handlers[1][1]

        chat_id = 999
        sender = MagicMock(first_name="Test", username="testuser")

        with patch("bot.config.settings.users_db_path", self.users_db_path):
            # 1. Open map format submenu
            event_open = AsyncMock()
            event_open.chat_id = chat_id
            event_open.data = b"settings:mapfmt"
            await cb_settings_handler(event_open)
            event_open.edit.assert_called_once()
            self.assertIn("איך לקבל את המפה", event_open.edit.call_args[0][0])

            # 2. Select photo via settings:mapfmt:photo
            event_photo = AsyncMock()
            event_photo.chat_id = chat_id
            event_photo.data = b"settings:mapfmt:photo"
            event_photo.get_sender = AsyncMock(return_value=sender)
            await cb_settings_handler(event_photo)

            saved = await get_user_settings(chat_id, self.users_db_path)
            self.assertEqual(saved.map_format, "photo")
            event_photo.answer.assert_called_with("✅ ההגדרה נשמרה!", alert=False)

            # 3. Select document via settings:mapfmt:document
            event_doc = AsyncMock()
            event_doc.chat_id = chat_id
            event_doc.data = b"settings:mapfmt:document"
            event_doc.get_sender = AsyncMock(return_value=sender)
            await cb_settings_handler(event_doc)

            saved_doc = await get_user_settings(chat_id, self.users_db_path)
            self.assertEqual(saved_doc.map_format, "document")

            # 4. Select photo via filter:mapfmt:photo
            event_filter = AsyncMock()
            event_filter.chat_id = chat_id
            event_filter.data = b"filter:mapfmt:photo"
            event_filter.get_sender = AsyncMock(return_value=sender)
            await cb_filter_handler(event_filter)

            saved_filter = await get_user_settings(chat_id, self.users_db_path)
            self.assertEqual(saved_filter.map_format, "photo")

            # 5. Back to the interactive map
            event_interactive = AsyncMock()
            event_interactive.chat_id = chat_id
            event_interactive.data = b"settings:mapfmt:interactive"
            event_interactive.get_sender = AsyncMock(return_value=sender)
            await cb_settings_handler(event_interactive)

            saved_interactive = await get_user_settings(chat_id, self.users_db_path)
            self.assertEqual(saved_interactive.map_format, "interactive")


class TestMapSendingFormat(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        self.stations_db_path = os.path.join(self.temp_dir.name, "test_stations.db")
        await init_users_db(self.users_db_path)

        conn = sqlite3.connect(self.stations_db_path)
        conn.execute("""
            CREATE TABLE locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cello_id TEXT UNIQUE,
                name TEXT,
                address TEXT,
                city TEXT,
                lat REAL,
                lng REAL,
                provider_id TEXT,
                provider_name TEXT,
                max_per_kwh REAL,
                has_tariffs INTEGER,
                payment_options TEXT,
                facilities TEXT,
                status_summary TEXT,
                connectors TEXT,
                stations_count INTEGER,
                updated_at TEXT,
                sources TEXT,
                is_gov_official INTEGER
            )
        """)
        conn.execute("INSERT INTO locations (cello_id, name, lat, lng, stations_count) VALUES ('1', 'Station 1', 32.0853, 34.7818, 2)")
        conn.commit()
        conn.close()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_send_map_image_force_document_true_for_document(self):
        event = AsyncMock()
        event.chat_id = 111

        with patch("bot.handlers.location.render_map", AsyncMock(return_value="/tmp/dummy_map.png")), \
             patch("bot.handlers.location.os.remove") as mock_remove:
            await send_map_image(event, 32.0853, 34.7818, 10, [], map_format="document")
            event.respond.assert_called_once()
            self.assertEqual(event.respond.call_args[1]["force_document"], True)
            mock_remove.assert_called_once_with("/tmp/dummy_map.png")

    async def test_send_map_image_force_document_false_for_photo(self):
        event = AsyncMock()
        event.chat_id = 222

        with patch("bot.handlers.location.render_map", AsyncMock(return_value="/tmp/dummy_map.png")), \
             patch("bot.handlers.location.os.remove") as mock_remove:
            await send_map_image(event, 32.0853, 34.7818, 10, [], map_format="photo")
            event.respond.assert_called_once()
            self.assertEqual(event.respond.call_args[1]["force_document"], False)
            mock_remove.assert_called_once_with("/tmp/dummy_map.png")

    async def test_send_map_image_reads_db_setting_when_map_format_omitted(self):
        chat_id = 333
        await upsert_user(UserSettings(chat_id=chat_id, map_format="photo"), self.users_db_path)

        event = AsyncMock()
        event.chat_id = chat_id

        with patch("bot.config.settings.users_db_path", self.users_db_path), \
             patch("bot.handlers.location.render_map", AsyncMock(return_value="/tmp/dummy_map.png")), \
             patch("bot.handlers.location.os.remove"):
            await send_map_image(event, 32.0853, 34.7818, 10, [])
            event.respond.assert_called_once()
            self.assertEqual(event.respond.call_args[1]["force_document"], False)

    async def test_send_map_image_skips_rendering_for_interactive(self):
        event = AsyncMock()
        event.chat_id = 555

        with patch("bot.handlers.location.render_map", AsyncMock()) as mock_render:
            await send_map_image(event, 32.0853, 34.7818, 10, [], map_format="interactive")
            mock_render.assert_not_called()
            event.respond.assert_not_called()

    async def test_send_map_image_skips_rendering_when_db_says_interactive(self):
        chat_id = 556
        await upsert_user(UserSettings(chat_id=chat_id, map_format="interactive"), self.users_db_path)

        event = AsyncMock()
        event.chat_id = chat_id

        with patch("bot.config.settings.users_db_path", self.users_db_path), \
             patch("bot.handlers.location.render_map", AsyncMock()) as mock_render:
            await send_map_image(event, 32.0853, 34.7818, 10, [])
            mock_render.assert_not_called()
            event.respond.assert_not_called()

    async def test_execute_search_sends_link_instead_of_image_for_interactive(self):
        chat_id = 557
        await upsert_user(UserSettings(chat_id=chat_id, map_format="interactive"), self.users_db_path)

        event = AsyncMock()
        event.chat_id = chat_id
        event.is_private = True
        event.respond.side_effect = [AsyncMock(), AsyncMock(), MagicMock(id=99)]

        with patch("bot.config.settings.users_db_path", self.users_db_path), \
             patch("bot.config.settings.db_path", self.stations_db_path), \
             patch("bot.handlers.location.render_map", AsyncMock()) as mock_render, \
             patch("bot.handlers.location.send_map_image", AsyncMock()) as mock_send_map:
            await execute_search(event, chat_id, 32.0853, 34.7818)

        mock_send_map.assert_not_called()
        mock_render.assert_not_called()
        # ההודעה השנייה היא קישור המפה (הראשונה היא "מחפש...", השלישית כרטיס העמדה)
        map_msg_text = event.respond.call_args_list[1][0][0]
        self.assertIn("מפת העמדות באזור", map_msg_text)
        map_buttons = event.respond.call_args_list[1][1]["buttons"]
        self.assertIn("lat=32.0853", map_buttons[0][0].url)

    async def test_execute_search_respects_user_map_format(self):
        chat_id = 444
        await upsert_user(UserSettings(chat_id=chat_id, map_format="photo"), self.users_db_path)

        event = AsyncMock()
        event.chat_id = chat_id
        event.is_private = True

        searching_msg = AsyncMock()
        result_msg = MagicMock(id=99)
        event.respond.side_effect = [searching_msg, result_msg]

        with patch("bot.config.settings.users_db_path", self.users_db_path), \
             patch("bot.config.settings.db_path", self.stations_db_path), \
             patch("bot.handlers.location.send_map_image", AsyncMock()) as mock_send_map:
            await execute_search(event, chat_id, 32.0853, 34.7818)
            mock_send_map.assert_called_once()
            call_kwargs = mock_send_map.call_args[1]
            self.assertEqual(call_kwargs.get("map_format"), "photo")


class TestInteractiveMapLink(unittest.TestCase):
    def test_webapp_map_url_includes_coordinates(self):
        url = webapp_map_url(32.0853, 34.7818)
        self.assertTrue(url.startswith(WEBAPP_URL + "?"))
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["lat"], ["32.0853"])
        self.assertEqual(query["lng"], ["34.7818"])

    def test_webapp_map_url_without_coordinates(self):
        self.assertEqual(webapp_map_url(), WEBAPP_URL)
        self.assertEqual(webapp_map_url(32.0853, None), WEBAPP_URL)

    def test_interactive_map_keyboard_is_webview_in_private(self):
        button = interactive_map_keyboard(32.0853, 34.7818, is_private=True)[0][0]
        self.assertIsInstance(button, KeyboardButtonWebView)
        self.assertIn("lng=34.7818", button.url)

    def test_interactive_map_keyboard_falls_back_to_url_in_groups(self):
        """טלגרם דוחה כפתורי web_app בקבוצות, ולכן שם נשלח כפתור URL רגיל."""
        button = interactive_map_keyboard(32.0853, 34.7818, is_private=False)[0][0]
        self.assertNotIsInstance(button, KeyboardButtonWebView)
        self.assertIn("lat=32.0853", button.url)


class TestTripMapLink(unittest.TestCase):
    origin = (32.0853, 34.7818)
    destination = (29.5577, 34.9519)

    def test_webapp_trip_url_carries_origin_and_destination(self):
        url = webapp_trip_url(self.origin, self.destination)
        self.assertTrue(url.startswith(WEBAPP_URL + "?"))
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["from_lat"], ["32.0853"])
        self.assertEqual(query["from_lng"], ["34.7818"])
        self.assertEqual(query["to_lat"], ["29.5577"])
        self.assertEqual(query["to_lng"], ["34.9519"])

    def test_trip_map_keyboard_is_webview_in_private(self):
        button = trip_map_keyboard(self.origin, self.destination, is_private=True)[0][0]
        self.assertIsInstance(button, KeyboardButtonWebView)
        self.assertIn("from_lat=32.0853", button.url)

    def test_trip_map_keyboard_falls_back_to_url_in_groups(self):
        button = trip_map_keyboard(self.origin, self.destination, is_private=False)[0][0]
        self.assertNotIsInstance(button, KeyboardButtonWebView)
        self.assertIn("to_lat=29.5577", button.url)


if __name__ == "__main__":
    unittest.main()
