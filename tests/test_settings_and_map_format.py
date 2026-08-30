import os
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers.location import execute_search, send_map_image
from bot.handlers.settings import _render_main_text, register_handlers as register_settings_handlers
from bot.keyboards.inline import map_format_keyboard, settings_main_keyboard
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
        self.assertEqual(settings.map_format, "document")

    async def test_ensure_user_default_map_format(self):
        await ensure_user(1002, "Alice", "alice_u", self.users_db_path)
        settings = await get_user_settings(1002, self.users_db_path)
        self.assertEqual(settings.first_name, "Alice")
        self.assertEqual(settings.map_format, "document")

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

        user_777 = await get_user_settings(777, mig_db_path)
        self.assertEqual(user_777.map_format, "document")

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
        doc_btn = kb_doc[0][0]
        photo_btn = kb_doc[1][0]
        self.assertTrue(doc_btn.text.startswith("✅"))
        self.assertFalse(photo_btn.text.startswith("✅"))

        kb_photo = map_format_keyboard("photo")
        doc_btn2 = kb_photo[0][0]
        photo_btn2 = kb_photo[1][0]
        self.assertFalse(doc_btn2.text.startswith("✅"))
        self.assertTrue(photo_btn2.text.startswith("✅"))

    async def test_render_main_text_shows_map_format(self):
        with patch("bot.config.settings.users_db_path", self.users_db_path):
            await upsert_user(UserSettings(chat_id=123, map_format="document"), self.users_db_path)
            text_doc = await _render_main_text(123)
            self.assertIn("פורמט מפה", text_doc)
            self.assertIn("קובץ", text_doc)

            await upsert_user(UserSettings(chat_id=123, map_format="photo"), self.users_db_path)
            text_photo = await _render_main_text(123)
            self.assertIn("פורמט מפה", text_photo)
            self.assertIn("תמונה", text_photo)

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
            self.assertIn("בחר פורמט", event_open.edit.call_args[0][0])

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


if __name__ == "__main__":
    unittest.main()
