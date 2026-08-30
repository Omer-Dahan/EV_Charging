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
from bot.states import get_session
from bot.handlers.admin import (
    build_admin_report,
    admin_keyboard,
    admin_confirm_keyboard,
    admin_wizard_cancel_keyboard,
    is_valid_israel_coord,
    parse_admin_coordinates,
    parse_connectors_input,
    parse_price_input,
    insert_manual_station,
    register_handlers,
)


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
        mock_client = MagicMock()
        registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                registered_handlers.append((event_builder, f))
                return f
            return decorator

        mock_client.on = mock_on
        register_handlers(mock_client)

        self.assertEqual(len(registered_handlers), 3)
        msg_builder, msg_handler = registered_handlers[0]
        cb_builder, cb_handler = registered_handlers[1]

        # Case 1: Unauthorized user sends /adminpanel, /admin, /stats -> Silent ignore (0 messages sent)
        for cmd in ["/adminpanel", "/admin", "/stats"]:
            unauth_event = AsyncMock()
            unauth_event.sender_id = 111222333
            unauth_event.chat_id = 111222333
            unauth_event.text = cmd

            with patch("bot.config.settings.admin_id", 999999999), patch(
                "bot.config.settings.admin_chat_id", None
            ):
                await msg_handler(unauth_event)
                unauth_event.respond.assert_not_called()
                unauth_event.reply.assert_not_called()

        # Case 2: Authorized admin sends /adminpanel
        auth_event = AsyncMock()
        auth_event.sender_id = 999999999
        auth_event.chat_id = 999999999
        auth_event.text = "/adminpanel"

        with patch("bot.config.settings.admin_id", 999999999), patch(
            "bot.config.settings.admin_chat_id", None
        ), patch("bot.handlers.admin.build_admin_report", AsyncMock(return_value="Admin Report OK")):
            await msg_handler(auth_event)
            auth_event.respond.assert_called_once()
            call_args = auth_event.respond.call_args
            self.assertEqual(call_args[0][0], "Admin Report OK")
            self.assertEqual(call_args[1]["parse_mode"], "html")

        # Case 3: Unauthorized callback query -> Silent ignore
        unauth_cb = AsyncMock()
        unauth_cb.sender_id = 111222333
        unauth_cb.chat_id = 111222333
        unauth_cb.data = b"admin:refresh"

        with patch("bot.config.settings.admin_id", 999999999), patch(
            "bot.config.settings.admin_chat_id", None
        ):
            await cb_handler(unauth_cb)
            unauth_cb.edit.assert_not_called()
            unauth_cb.respond.assert_not_called()

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


class TestAdminAddStationWizard(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.stations_db_path = os.path.join(self.temp_dir.name, "test_stations.db")

        # Initialize SQLite DB schema with locations table
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
        conn.commit()
        conn.close()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    def test_coordinate_validation_israel(self):
        # Valid Israel coordinates
        self.assertTrue(is_valid_israel_coord(32.0853, 34.7818))  # Tel Aviv
        self.assertTrue(is_valid_israel_coord(29.5581, 34.9482))  # Eilat
        self.assertTrue(is_valid_israel_coord(33.0, 35.5))        # North

        # Outside Israel bounds (lat 29-34, lng 34-36)
        self.assertFalse(is_valid_israel_coord(51.5074, -0.1278)) # London
        self.assertFalse(is_valid_israel_coord(40.7128, -74.0060)) # NY
        self.assertFalse(is_valid_israel_coord(28.5, 34.5))       # Too far south
        self.assertFalse(is_valid_israel_coord(34.5, 35.0))       # Too far north
        self.assertFalse(is_valid_israel_coord(32.0, 33.5))       # Too far west (sea)
        self.assertFalse(is_valid_israel_coord(32.0, 36.5))       # Too far east

    def test_parse_connectors_input(self):
        # Free text parsing
        res = parse_connectors_input("CCS2 150kW, Type2 22kW")
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["standard"], "CCS2_COMBO")
        self.assertEqual(res[0]["powerType"], "DC")
        self.assertEqual(res[0]["maxPower"], 150)
        self.assertEqual(res[1]["standard"], "TYPE2")
        self.assertEqual(res[1]["powerType"], "AC")
        self.assertEqual(res[1]["maxPower"], 22)

        # CHAdeMO and multiple
        res2 = parse_connectors_input("CCS 300, Type 2 11, CHAdeMO 50")
        self.assertEqual(len(res2), 3)
        self.assertEqual(res2[0]["maxPower"], 300)
        self.assertEqual(res2[1]["maxPower"], 11)
        self.assertEqual(res2[2]["standard"], "CHADEMO")
        self.assertEqual(res2[2]["maxPower"], 50)

        # Empty / Skip
        self.assertEqual(parse_connectors_input("-"), [])
        self.assertEqual(parse_connectors_input("דלג"), [])
        self.assertEqual(parse_connectors_input(""), [])

    def test_parse_price_input(self):
        self.assertEqual(parse_price_input("1.85"), 1.85)
        self.assertEqual(parse_price_input("2.10 ₪"), 2.10)
        self.assertEqual(parse_price_input("0"), 0.0)
        self.assertEqual(parse_price_input("חינם"), 0.0)
        self.assertIsNone(parse_price_input("-"))
        self.assertIsNone(parse_price_input("דלג"))
        self.assertIsNone(parse_price_input("ללא"))

    async def test_full_wizard_flow_and_db_insert(self):
        mock_client = MagicMock()
        registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                registered_handlers.append((event_builder, f))
                return f
            return decorator

        mock_client.on = mock_on
        register_handlers(mock_client)

        cb_handler = registered_handlers[1][1]
        wizard_handler = registered_handlers[2][1]

        admin_id = 999999999
        session = get_session(admin_id)
        session.admin_add_state = None
        session.admin_add_data = {}

        with patch("bot.config.settings.admin_id", admin_id), \
             patch("bot.config.settings.db_path", self.stations_db_path):

            # Step 0: Click "➕ הוספת עמדה חדשה"
            cb_event = AsyncMock()
            cb_event.sender_id = admin_id
            cb_event.chat_id = admin_id
            cb_event.data = b"admin:add_station"
            await cb_handler(cb_event)
            self.assertEqual(session.admin_add_state, "name")
            cb_event.respond.assert_called_once()
            self.assertIn("שם העמדה", cb_event.respond.call_args[0][0])

            # Step 1: Send station name
            msg1 = AsyncMock()
            msg1.sender_id = admin_id
            msg1.chat_id = admin_id
            msg1.text = "עמדת בדיקה ראשית תל אביב"
            msg1.geo = None
            await wizard_handler(msg1)
            self.assertEqual(session.admin_add_state, "address")
            self.assertEqual(session.admin_add_data["name"], "עמדת בדיקה ראשית תל אביב")
            msg1.respond.assert_called_once()
            self.assertIn("כתובת", msg1.respond.call_args[0][0])

            # Step 2: Send address
            msg2 = AsyncMock()
            msg2.sender_id = admin_id
            msg2.chat_id = admin_id
            msg2.text = "דיזנגוף 50, תל אביב"
            msg2.geo = None
            await wizard_handler(msg2)
            self.assertEqual(session.admin_add_state, "coords")
            self.assertEqual(session.admin_add_data["address"], "דיזנגוף 50, תל אביב")
            msg2.respond.assert_called_once()
            self.assertIn("קואורדינטות", msg2.respond.call_args[0][0])

            # Step 3 (failure): Send coordinates outside Israel
            msg3_bad = AsyncMock()
            msg3_bad.sender_id = admin_id
            msg3_bad.chat_id = admin_id
            msg3_bad.text = "51.5074, -0.1278"  # London
            msg3_bad.geo = None
            await wizard_handler(msg3_bad)
            self.assertEqual(session.admin_add_state, "coords")  # Should remain in coords
            msg3_bad.respond.assert_called_once()
            self.assertIn("מחוץ לגבולות ישראל", msg3_bad.respond.call_args[0][0])

            # Step 3 (success): Send valid coordinates
            msg3_good = AsyncMock()
            msg3_good.sender_id = admin_id
            msg3_good.chat_id = admin_id
            msg3_good.text = "32.0745, 34.7915"
            msg3_good.geo = None
            await wizard_handler(msg3_good)
            self.assertEqual(session.admin_add_state, "provider")
            self.assertAlmostEqual(session.admin_add_data["lat"], 32.0745)
            self.assertAlmostEqual(session.admin_add_data["lng"], 34.7915)
            msg3_good.respond.assert_called_once()
            self.assertIn("מפעיל", msg3_good.respond.call_args[0][0])

            # Step 4: Send provider name
            msg4 = AsyncMock()
            msg4.sender_id = admin_id
            msg4.chat_id = admin_id
            msg4.text = "EV-Edge"
            msg4.geo = None
            await wizard_handler(msg4)
            self.assertEqual(session.admin_add_state, "connectors")
            self.assertEqual(session.admin_add_data["provider"], "EV-Edge")
            msg4.respond.assert_called_once()
            self.assertIn("מחברים", msg4.respond.call_args[0][0])

            # Step 5: Send connectors
            msg5 = AsyncMock()
            msg5.sender_id = admin_id
            msg5.chat_id = admin_id
            msg5.text = "CCS2 150kW, Type2 22kW"
            msg5.geo = None
            await wizard_handler(msg5)
            self.assertEqual(session.admin_add_state, "price")
            self.assertEqual(len(session.admin_add_data["connectors"]), 2)
            msg5.respond.assert_called_once()
            self.assertIn("מחיר", msg5.respond.call_args[0][0])

            # Step 6: Send price
            msg6 = AsyncMock()
            msg6.sender_id = admin_id
            msg6.chat_id = admin_id
            msg6.text = "1.85"
            msg6.geo = None
            await wizard_handler(msg6)
            self.assertEqual(session.admin_add_state, "confirm")
            self.assertEqual(session.admin_add_data["price"], 1.85)
            msg6.respond.assert_called_once()
            self.assertIn("סיכום פרטי העמדה", msg6.respond.call_args[0][0])

            # Step 7: Confirm and save to DB
            confirm_cb = AsyncMock()
            confirm_cb.sender_id = admin_id
            confirm_cb.chat_id = admin_id
            confirm_cb.data = b"admin:add_confirm"
            await cb_handler(confirm_cb)

            # Check session cleaned up
            self.assertIsNone(session.admin_add_state)
            self.assertEqual(session.admin_add_data, {})
            confirm_cb.edit.assert_called_once()
            self.assertIn("נוספה בהצלחה", confirm_cb.edit.call_args[0][0])

            # Verify record in DB
            conn = sqlite3.connect(self.stations_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM locations WHERE name = ?", ("עמדת בדיקה ראשית תל אביב",)).fetchone()
            self.assertIsNotNone(row)
            row_dict = dict(row)
            self.assertEqual(row_dict["name"], "עמדת בדיקה ראשית תל אביב")
            self.assertEqual(row_dict["address"], "דיזנגוף 50, תל אביב")
            self.assertEqual(row_dict["city"], "תל אביב")
            self.assertAlmostEqual(row_dict["lat"], 32.0745)
            self.assertAlmostEqual(row_dict["lng"], 34.7915)
            self.assertEqual(row_dict["provider_name"], "EV-Edge")
            self.assertEqual(row_dict["max_per_kwh"], 1.85)
            self.assertEqual(row_dict["has_tariffs"], 1)
            self.assertEqual(row_dict["sources"], "manual")
            self.assertIn("CCS2_COMBO", row_dict["connectors"])
            self.assertEqual(row_dict["stations_count"], 2)
            conn.close()

    async def test_wizard_with_geo_message_and_skipped_fields(self):
        mock_client = MagicMock()
        registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                registered_handlers.append((event_builder, f))
                return f
            return decorator

        mock_client.on = mock_on
        register_handlers(mock_client)

        cb_handler = registered_handlers[1][1]
        wizard_handler = registered_handlers[2][1]

        admin_id = 999999999
        session = get_session(admin_id)
        session.admin_add_state = None
        session.admin_add_data = {}

        with patch("bot.config.settings.admin_id", admin_id), \
             patch("bot.config.settings.db_path", self.stations_db_path):

            # Start wizard
            cb_event = AsyncMock()
            cb_event.sender_id = admin_id
            cb_event.chat_id = admin_id
            cb_event.data = b"admin:add_station"
            await cb_handler(cb_event)

            # 1. Name
            msg1 = AsyncMock(sender_id=admin_id, chat_id=admin_id, text="עמדת פז ירושלים", geo=None)
            await wizard_handler(msg1)

            # 2. Address
            msg2 = AsyncMock(sender_id=admin_id, chat_id=admin_id, text="יפו 200, ירושלים", geo=None)
            await wizard_handler(msg2)

            # 3. Coordinates via GPS Geo object
            geo_mock = MagicMock()
            geo_mock.lat = 31.7850
            geo_mock.long = 35.2050
            msg3 = AsyncMock(sender_id=admin_id, chat_id=admin_id, text="", geo=geo_mock)
            await wizard_handler(msg3)
            self.assertEqual(session.admin_add_state, "provider")
            self.assertAlmostEqual(session.admin_add_data["lat"], 31.7850)
            self.assertAlmostEqual(session.admin_add_data["lng"], 35.2050)

            # 4. Provider
            msg4 = AsyncMock(sender_id=admin_id, chat_id=admin_id, text="Paz Charge", geo=None)
            await wizard_handler(msg4)

            # 5. Connectors - Skip using "דלג"
            msg5 = AsyncMock(sender_id=admin_id, chat_id=admin_id, text="דלג", geo=None)
            await wizard_handler(msg5)
            self.assertEqual(session.admin_add_state, "price")
            self.assertEqual(session.admin_add_data["connectors"], [])

            # 6. Price - Skip using "-"
            msg6 = AsyncMock(sender_id=admin_id, chat_id=admin_id, text="-", geo=None)
            await wizard_handler(msg6)
            self.assertEqual(session.admin_add_state, "confirm")
            self.assertIsNone(session.admin_add_data["price"])

            # 7. Confirm
            confirm_cb = AsyncMock(sender_id=admin_id, chat_id=admin_id, data=b"admin:add_confirm")
            await cb_handler(confirm_cb)

            # Verify in DB
            conn = sqlite3.connect(self.stations_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM locations WHERE name = ?", ("עמדת פז ירושלים",)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["city"], "ירושלים")
            self.assertIsNone(row["max_per_kwh"])
            self.assertEqual(row["has_tariffs"], 0)
            self.assertEqual(row["connectors"], "[]")
            self.assertEqual(row["stations_count"], 1)
            conn.close()

    async def test_wizard_cancellation(self):
        mock_client = MagicMock()
        registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                registered_handlers.append((event_builder, f))
                return f
            return decorator

        mock_client.on = mock_on
        register_handlers(mock_client)

        cb_handler = registered_handlers[1][1]
        wizard_handler = registered_handlers[2][1]

        admin_id = 999999999
        session = get_session(admin_id)

        with patch("bot.config.settings.admin_id", admin_id), \
             patch("bot.config.settings.db_path", self.stations_db_path):

            # Start wizard
            cb_event = AsyncMock()
            cb_event.sender_id = admin_id
            cb_event.chat_id = admin_id
            cb_event.data = b"admin:add_station"
            await cb_handler(cb_event)
            self.assertEqual(session.admin_add_state, "name")

            # Cancel via text "ביטול"
            cancel_msg = AsyncMock()
            cancel_msg.sender_id = admin_id
            cancel_msg.chat_id = admin_id
            cancel_msg.text = "ביטול"
            cancel_msg.geo = None
            await wizard_handler(cancel_msg)
            self.assertIsNone(session.admin_add_state)
            self.assertEqual(session.admin_add_data, {})
            cancel_msg.respond.assert_called_once()
            self.assertIn("בוטלה", cancel_msg.respond.call_args[0][0])

            # Start again and cancel via callback
            await cb_handler(cb_event)
            self.assertEqual(session.admin_add_state, "name")

            cancel_cb = AsyncMock()
            cancel_cb.sender_id = admin_id
            cancel_cb.chat_id = admin_id
            cancel_cb.data = b"admin:add_cancel"
            await cb_handler(cancel_cb)
            self.assertIsNone(session.admin_add_state)
            self.assertEqual(session.admin_add_data, {})
            cancel_cb.edit.assert_called_once()
            self.assertIn("בוטלה", cancel_cb.edit.call_args[0][0])


if __name__ == "__main__":
    unittest.main()

