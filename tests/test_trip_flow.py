"""בדיקות זרימה של מצב הנסיעה מול לקוח טלגרם מזויף.

הבדיקה המרכזית כאן משחזרת את הבאג שבגללו הודעה אחת של המשתמש נצרכה על ידי שלושה
handlers ברצף ("❌ יש להזין מספר בין 1 ל-100" מיד אחרי /trip). לכן ה-FakeClient
מחקה את הסמנטיקה שגרמה לזה: telethon מחשב את הפילטר של כל handler בתוך לולאת
ה-dispatch, כלומר *אחרי* שה-handler הקודם כבר שינה את ה-session.
"""
import ast
import asyncio
import contextlib
import inspect
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telethon import events

from bot import main
from bot.handlers import callbacks, location, trip
from bot.states import UserSession, user_states


class FakeClient:
    """אוסף handlers לפי סדר הרישום ומריץ אותם כמו telethon.client.updates._dispatch_update."""

    def __init__(self):
        self.handlers: list = []

    def on(self, builder):
        def decorator(callback):
            self.handlers.append((builder, callback))
            return callback
        return decorator

    @staticmethod
    def _matches(builder, event) -> bool:
        is_callback = getattr(event, "is_callback", False)
        if isinstance(builder, events.CallbackQuery):
            if not is_callback:
                return False
            if builder.match is not None and not builder.match(event.data):
                return False
        elif isinstance(builder, events.NewMessage):
            if is_callback:
                return False
            if builder.pattern is not None and not builder.pattern(event.text or ""):
                return False
        else:
            return False
        return builder.func is None or builder.func(event)

    async def dispatch(self, event) -> list[str]:
        """מחזיר את שמות ה-handlers שרצו בפועל על האירוע."""
        ran = []
        for builder, callback in self.handlers:
            if not self._matches(builder, event):
                continue
            ran.append(callback.__name__)
            try:
                await callback(event)
            except events.StopPropagation:
                break
        return ran


class FakeMessageEvent:
    is_callback = False

    def __init__(self, chat_id: int = 500, text: str = "", geo=None, is_private: bool = True):
        self.chat_id = chat_id
        self.text = text
        self.raw_text = text
        self.geo = geo
        self.is_private = is_private
        self.client = AsyncMock()
        self.delete = AsyncMock()
        self.respond = AsyncMock(return_value=MagicMock(id=100))
        self.get_sender = AsyncMock(return_value=MagicMock(first_name="דני", username="danny"))


class FakeCallbackEvent:
    is_callback = True

    def __init__(self, data: bytes, chat_id: int = 500, message_id: int = 100, is_private: bool = True):
        self.chat_id = chat_id
        self.data = data
        self.message_id = message_id
        self.is_private = is_private
        self.client = AsyncMock()
        self.answer = AsyncMock()
        self.edit = AsyncMock()
        self.delete = AsyncMock()
        self.respond = AsyncMock(return_value=MagicMock(id=101))


@contextlib.contextmanager
def temp_map_file():
    """קובץ מפה מדומה. הקוד הנבדק מוחק אותו אחרי השליחה, אז הניקוי כאן סלחני."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def make_plan(stops: int = 1) -> dict:
    """תוכנית מינימלית בפורמט של trip_planner.plan_trip, לשימוש במקום תכנון אמיתי."""
    return {
        "origin": {"lat": 32.0, "lng": 34.8},
        "destination": {"lat": 29.5, "lng": 34.9},
        "straight_line_km": 264.0,
        "total_distance_km": 330.0,
        "duration_hours": 3.6,
        "num_stops": stops,
        "available_range_km": 245.0,
        "car_params": {
            "real_range_km": 350.0, "battery_percent": 80.0,
            "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
            "min_power_kw": None,
        },
        "stops": [
            {
                "segment_index": i + 1,
                "distance_from_origin_km": 208.0,
                "station": {
                    "id": i + 1, "name": f"עמדה {i + 1}", "lat": 31.0, "lng": 35.0,
                    "max_power": 150.0, "provider_name": "EVI", "max_per_kwh": 1.8,
                },
                "relaxation": {"providers": False, "price": False, "power_kw": 150.0},
            }
            for i in range(stops)
        ],
        "missing_segments": [],
    }


def fake_user_settings(**overrides):
    defaults = {
        "trip_real_range_km": None,
        "trip_battery_percent": None,
        "trip_safety_margin_percent": None,
        "trip_consumption_kwh_100km": None,
        "trip_min_power_kw": None,
        "trip_max_price": None,
        "trip_allowed_providers": None,
        "map_format": "photo",
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


class TripFlowTestCase(unittest.IsolatedAsyncioTestCase):
    """בסיס משותף: session נקי, handlers רשומים, ו-get_user_settings מנוטרל מה-DB."""

    chat_id = 500

    async def asyncSetUp(self):
        user_states.clear()
        self.session = UserSession()
        user_states[self.chat_id] = self.session

        self.client = FakeClient()
        trip.register_handlers(self.client)

        self.settings_patch = patch.object(
            trip, "get_user_settings", AsyncMock(return_value=fake_user_settings())
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    async def asyncTearDown(self):
        user_states.clear()


class TestSingleHandlerPerMessage(TripFlowTestCase):
    async def test_coordinates_as_destination_run_exactly_one_handler(self):
        """הודעת טקסט אחת = handler אחד. זה הבאג המרכזי: קואורדינטות שנשלחו כיעד
        נצרכו שוב כמוצא ושוב כאחוז סוללה, והמשתמש קיבל שגיאת סוללה משום מקום."""
        self.session.trip_state = "awaiting_destination"
        event = FakeMessageEvent(self.chat_id, "29.557, 34.952")

        ran = await self.client.dispatch(event)

        self.assertEqual(len(ran), 1, f"רצו {len(ran)} handlers על אותה הודעה: {ran}")
        self.assertNotEqual(self.session.trip_state, "awaiting_battery")
    async def test_address_as_destination_stops_at_the_origin_step(self):
        """גם כתובת עם פסיק (תוצאה יחידה מהגיאוקודר) לא ממשיכה לשלב הסוללה לבדה."""
        self.session.trip_state = "awaiting_destination"
        self.session.trip_message_id = 10
        event = FakeMessageEvent(self.chat_id, "תל אביב, ישראל")

        with patch.object(trip, "geocode", AsyncMock(return_value=[{"lat": 32.08, "lng": 34.78, "name": "תל אביב"}])):
            ran = await self.client.dispatch(event)

        self.assertEqual(ran, ["handle_trip_text"])
        self.assertEqual(self.session.trip_state, "awaiting_origin")

    async def test_shared_location_is_not_consumed_by_the_regular_search(self):
        """הודעת מיקום בזרימת נסיעה חייבת לעצור את ההפצה, אחרת החיפוש הרגיל רץ אחריה."""
        location.register_handlers(self.client)
        self.session.trip_state = "awaiting_origin"
        self.session.trip_message_id = 10
        event = FakeMessageEvent(self.chat_id, geo=MagicMock(lat=32.0, long=34.8))

        ran = await self.client.dispatch(event)

        self.assertEqual(ran, ["handle_trip_location"])
        self.assertEqual(self.session.trip_state, "awaiting_battery")


class TestAbandonedFlowReleasesTheBot(TripFlowTestCase):
    async def test_expired_flow_falls_back_to_regular_search(self):
        """זרימה נטושה משתחררת, וההודעה הבאה נתפסת ע"י חיפוש העמדות הרגיל."""
        location.register_handlers(self.client)
        self.session.trip_state = "awaiting_destination"
        self.session.trip_started_at = time.monotonic() - trip.TRIP_FLOW_TTL_SECONDS - 60
        event = FakeMessageEvent(self.chat_id, "32.0853, 34.7818")

        with patch.object(location, "execute_search", AsyncMock()), \
             patch.object(location, "ensure_user", AsyncMock()):
            ran = await self.client.dispatch(event)

        self.assertIsNone(self.session.trip_state)
        self.assertEqual(ran, ["handle_text_query"])

    async def test_fresh_flow_is_not_released(self):
        self.session.trip_state = "awaiting_destination"
        self.session.trip_started_at = time.monotonic() - 60
        self.assertTrue(trip._is_trip_text(FakeMessageEvent(self.chat_id, "אילת")))


class TestBatteryStep(TripFlowTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.session.trip_state = "awaiting_battery"
        self.session.trip_message_id = 10
        self.session.trip_origin = {"lat": 32.0, "lng": 34.8, "name": "תל אביב"}
        self.session.trip_destination = {"lat": 29.5, "lng": 34.9, "name": "אילת"}

    def _edited_text(self) -> str:
        return self.client_edits()[-1]

    def client_edits(self) -> list[str]:
        return [call.args[2] for call in self.edit_mock.call_args_list]

    async def test_invalid_input_keeps_the_step_and_its_buttons(self):
        event = FakeMessageEvent(self.chat_id, "abc")
        self.edit_mock = event.client.edit_message

        await self.client.dispatch(event)

        self.assertEqual(self.session.trip_state, "awaiting_battery")
        text = self._edited_text()
        self.assertIn(trip.TRIP_INVALID_BATTERY_MESSAGE, text)
        buttons = self.edit_mock.call_args_list[-1].kwargs["buttons"]
        self.assertTrue(buttons)
        event.respond.assert_not_called()

    async def test_out_of_range_percent_is_rejected(self):
        event = FakeMessageEvent(self.chat_id, "150")
        self.edit_mock = event.client.edit_message

        await self.client.dispatch(event)

        self.assertIn(trip.TRIP_INVALID_BATTERY_MESSAGE, self._edited_text())

    async def test_percent_sign_and_comma_are_accepted(self):
        self.assertEqual(trip._parse_battery_percent("85%"), 85.0)
        self.assertEqual(trip._parse_battery_percent("85,5"), 85.5)
        self.assertIsNone(trip._parse_battery_percent("abc"))
        self.assertIsNone(trip._parse_battery_percent("0"))

    async def test_battery_button_plans_the_trip(self):
        event = FakeCallbackEvent(b"tripbatt:set:80", self.chat_id, message_id=10)
        with patch.object(trip, "plan_trip", AsyncMock(return_value=make_plan())) as planner, \
             patch.object(trip, "save_trip_plan", AsyncMock(return_value=7)), \
             patch.object(trip, "render_trip_map", AsyncMock(return_value=None)):
            await self.client.dispatch(event)

        self.assertEqual(planner.await_args.kwargs["battery_percent"], 80.0)
        self.assertIsNone(self.session.trip_state)

    async def test_battery_below_safety_margin_offers_a_way_out(self):
        """מסך "סוללה נמוכה" השאיר את המשתמש בלי כפתורים ובלי דרך חזרה."""
        event = FakeCallbackEvent(b"tripbatt:set:20", self.chat_id, message_id=10)
        self.settings_patch.stop()
        with patch.object(trip, "get_user_settings", AsyncMock(return_value=fake_user_settings(
            trip_safety_margin_percent=25.0
        ))):
            await self.client.dispatch(event)
        self.settings_patch.start()

        self.assertEqual(self.session.trip_state, "awaiting_battery")
        text, buttons = event.client.edit_message.call_args.args[2], event.client.edit_message.call_args.kwargs["buttons"]
        self.assertIn("מרווח הביטחון", text)
        self.assertTrue(buttons)


class TestDeadEndScreens(TripFlowTestCase):
    """כל שגיאה בזרימה חייבת להשאיר מסלול המשך - זו הייתה התקיעה המרכזית בממשק."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.session.trip_state = "awaiting_battery"
        self.session.trip_message_id = 10
        self.session.trip_origin = {"lat": 32.0, "lng": 34.8, "name": "תל אביב"}

    async def test_destination_outside_israel_returns_to_the_destination_step(self):
        self.session.trip_destination = {"lat": 48.85, "lng": 2.35, "name": "פריז"}
        event = FakeCallbackEvent(b"tripbatt:set:80", self.chat_id, message_id=10)

        await self.client.dispatch(event)

        self.assertEqual(self.session.trip_state, "awaiting_destination")
        self.assertIsNone(self.session.trip_destination)
        self.assertTrue(event.client.edit_message.call_args.kwargs["buttons"])

    async def test_missing_city_keeps_the_user_in_the_flow(self):
        self.session.trip_state = "awaiting_destination"
        event = FakeMessageEvent(self.chat_id, "הרצל")

        await self.client.dispatch(event)

        self.assertEqual(self.session.trip_state, "awaiting_destination")
        self.assertTrue(event.client.edit_message.call_args.kwargs["buttons"])

    async def test_planner_failure_offers_a_retry(self):
        self.session.trip_destination = {"lat": 29.5, "lng": 34.9, "name": "אילת"}
        event = FakeCallbackEvent(b"tripbatt:set:80", self.chat_id, message_id=10)

        with patch.object(trip, "plan_trip", AsyncMock(side_effect=RuntimeError("db is gone"))):
            await self.client.dispatch(event)

        data = [b.data for row in event.client.edit_message.call_args.kwargs["buttons"] for b in row]
        self.assertIn(b"trip:new", data)
        self.assertIn(b"trip:cancel", data)


class TestCancelAndRebind(TripFlowTestCase):
    async def test_cancel_releases_the_regular_search(self):
        self.session.trip_state = "awaiting_origin"
        self.session.trip_message_id = 10
        event = FakeCallbackEvent(b"trip:cancel", self.chat_id, message_id=10)

        await self.client.dispatch(event)

        self.assertIsNone(self.session.trip_state)
        self.assertIsNone(self.session.trip_message_id)
        event.edit.assert_awaited_once()
        self.assertTrue(location._is_text_search(FakeMessageEvent(self.chat_id, "הרצל 7, חיפה")))

    async def test_new_search_callback_also_clears_the_flow(self):
        self.session.trip_state = "awaiting_origin"
        nav_client = FakeClient()
        callbacks.register_handlers(nav_client)
        await nav_client.dispatch(FakeCallbackEvent(b"nav:new_search", self.chat_id, message_id=10))
        self.assertIsNone(self.session.trip_state)

    async def test_callback_rebinds_the_flow_message(self):
        """כפתור מהודעה ישנה (אחרי restart) עורך את ההודעה שנלחצה, לא שולח חדשה."""
        self.session.trip_message_id = None
        event = FakeCallbackEvent(b"trip:myplans", self.chat_id, message_id=77)

        with patch.object(trip, "get_recent_trip_plans", AsyncMock(return_value=[])):
            await self.client.dispatch(event)

        self.assertEqual(event.client.edit_message.call_args.args[1], 77)
        event.respond.assert_not_called()

    async def test_stale_geo_callback_shows_the_expired_screen(self):
        event = FakeCallbackEvent(b"tripgeo:0:32.0:34.0", self.chat_id, message_id=77)

        await self.client.dispatch(event)

        text = event.client.edit_message.call_args.args[2]
        data = [b.data for row in event.client.edit_message.call_args.kwargs["buttons"] for b in row]
        self.assertIn("פעילה", text)
        self.assertIn(b"trip:new", data)
        self.assertIn(b"trip:myplans", data)


class TestOriginStepSendsNoNewMessage(TripFlowTestCase):
    async def test_destination_step_edits_instead_of_sending(self):
        """זו הייתה ההודעה הנוספת: שלב המוצא נשלח בהודעה חדשה בגלל מקלדת ה-GPS."""
        self.session.trip_state = "awaiting_destination"
        self.session.trip_message_id = 10
        event = FakeMessageEvent(self.chat_id, "29.557, 34.952")

        await self.client.dispatch(event)

        event.respond.assert_not_called()
        event.client.edit_message.assert_awaited_once()
        self.assertEqual(self.session.trip_message_id, 10)
        self.assertEqual(self.session.trip_state, "awaiting_origin")

    async def test_gps_button_sends_a_prompt_that_the_location_removes(self):
        self.session.trip_state = "awaiting_origin"
        self.session.trip_message_id = 10
        self.session.trip_destination = {"lat": 29.5, "lng": 34.9, "name": "אילת"}

        press = FakeCallbackEvent(b"trip:gps", self.chat_id, message_id=10)
        press.respond = AsyncMock(return_value=MagicMock(id=55))
        await self.client.dispatch(press)
        self.assertEqual(self.session.trip_gps_prompt_msg_id, 55)

        location_event = FakeMessageEvent(self.chat_id, geo=MagicMock(lat=32.0, long=34.8))
        await self.client.dispatch(location_event)

        self.assertIsNone(self.session.trip_gps_prompt_msg_id)
        location_event.client.delete_messages.assert_awaited_with(self.chat_id, 55)

    async def test_no_gps_prompt_without_asking_for_it(self):
        self.session.trip_state = "awaiting_destination"
        self.session.trip_message_id = 10
        event = FakeMessageEvent(self.chat_id, "29.557, 34.952")

        await self.client.dispatch(event)

        event.respond.assert_not_called()
        self.assertIsNone(self.session.trip_gps_prompt_msg_id)


class TestConcurrentInput(TripFlowTestCase):
    async def test_second_message_is_ignored_while_the_first_is_running(self):
        """גיאוקוד לוקח שניות. לחיצה/שליחה כפולה לא אמורה לפתוח שני מסלולים."""
        self.session.trip_state = "awaiting_destination"
        self.session.trip_message_id = 10
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def slow_geocode(query):
            calls.append(query)
            started.set()
            await release.wait()
            return [{"lat": 32.08, "lng": 34.78, "name": "תל אביב"}]

        with patch.object(trip, "geocode", slow_geocode):
            first = asyncio.create_task(self.client.dispatch(FakeMessageEvent(self.chat_id, "תל אביב, ישראל")))
            await started.wait()
            await self.client.dispatch(FakeMessageEvent(self.chat_id, "חיפה, ישראל"))
            release.set()
            await first

        self.assertEqual(calls, ["תל אביב, ישראל"])


class TestTripCommandAndMap(TripFlowTestCase):
    async def test_trip_command_opens_a_new_message_and_keeps_the_old_plan(self):
        self.session.trip_message_id = 5
        event = FakeMessageEvent(self.chat_id, "/trip")
        event.respond = AsyncMock(return_value=MagicMock(id=60))

        await self.client.dispatch(event)

        event.respond.assert_awaited_once()
        event.client.edit_message.assert_not_called()
        self.assertEqual(self.session.trip_message_id, 60)
        event.delete.assert_awaited_once()

    async def test_trip_command_in_a_group_answers_once_and_stops(self):
        event = FakeMessageEvent(self.chat_id, "/trip", is_private=False)

        await self.client.dispatch(event)

        event.respond.assert_awaited_once_with(trip.TRIP_PRIVATE_ONLY_MESSAGE)
        self.assertIsNone(self.session.trip_state)

    async def test_trip_new_callback_edits_the_message_in_place(self):
        self.session.trip_message_id = 5
        event = FakeCallbackEvent(b"trip:new", self.chat_id, message_id=5)

        await self.client.dispatch(event)

        event.client.edit_message.assert_awaited_once()
        self.assertEqual(event.client.edit_message.call_args.args[1], 5)
        event.respond.assert_not_called()

    async def test_reopening_a_plan_replaces_the_previous_map_message(self):
        self.session.trip_message_id = 10
        self.session.trip_map_msg_id = 41
        row = {
            "plan": make_plan(), "origin_lat": 32.0, "origin_lng": 34.8,
            "destination_lat": 29.5, "destination_lng": 34.9,
            "origin_name": "תל אביב", "destination_name": "אילת",
        }
        event = FakeCallbackEvent(b"trip:plan:7", self.chat_id, message_id=10)
        event.respond = AsyncMock(return_value=MagicMock(id=42))

        with temp_map_file() as map_path, \
             patch.object(trip, "get_trip_plan", AsyncMock(return_value=row)), \
             patch.object(trip, "render_trip_map", AsyncMock(return_value=map_path)):
            await self.client.dispatch(event)

        event.client.delete_messages.assert_awaited_once_with(self.chat_id, 41)
        self.assertEqual(self.session.trip_map_msg_id, 42)

    async def test_map_is_sent_with_the_plan_and_numbers_every_stop(self):
        self.session.trip_state = "awaiting_battery"
        self.session.trip_message_id = 10
        self.session.trip_origin = {"lat": 32.0, "lng": 34.8, "name": "תל אביב"}
        self.session.trip_destination = {"lat": 29.5, "lng": 34.9, "name": "אילת"}
        event = FakeCallbackEvent(b"tripbatt:set:80", self.chat_id, message_id=10)
        event.respond = AsyncMock(return_value=MagicMock(id=42))

        with temp_map_file() as map_path, \
             patch.object(trip, "plan_trip", AsyncMock(return_value=make_plan())), \
             patch.object(trip, "save_trip_plan", AsyncMock(return_value=7)), \
             patch.object(trip, "render_trip_map", AsyncMock(return_value=map_path)) as renderer:
            await self.client.dispatch(event)

        origin, destination, stops = renderer.await_args.args
        self.assertEqual(origin, (32.0, 34.8))
        self.assertEqual(destination, (29.5, 34.9))
        self.assertEqual(stops, [(31.0, 35.0)])
        self.assertEqual(event.respond.await_args.kwargs["file"], map_path)


class TestOneMessageEndToEnd(TripFlowTestCase):
    async def test_the_reported_scenario_produces_one_flow_message(self):
        """התרחיש מהתלונה: /trip ואז קואורדינטות - בלי "יש להזין מספר בין 1 ל-100"."""
        self.session.user_lat, self.session.user_lng = 32.0853, 34.7818
        self.session.location_name = "תל אביב"

        start = FakeMessageEvent(self.chat_id, "/trip")
        start.respond = AsyncMock(return_value=MagicMock(id=60))
        await self.client.dispatch(start)

        destination = FakeMessageEvent(self.chat_id, "29.557, 34.952")
        await self.client.dispatch(destination)

        battery = FakeCallbackEvent(b"tripbatt:set:80", self.chat_id, message_id=60)
        battery.respond = AsyncMock(return_value=MagicMock(id=61))
        with temp_map_file() as map_path, \
             patch.object(trip, "plan_trip", AsyncMock(return_value=make_plan())), \
             patch.object(trip, "save_trip_plan", AsyncMock(return_value=7)), \
             patch.object(trip, "render_trip_map", AsyncMock(return_value=map_path)):
            await self.client.dispatch(battery)

        start.respond.assert_awaited_once()          # הודעת הזרימה, ביוזמת המשתמש
        destination.respond.assert_not_called()
        self.assertEqual(destination.client.edit_message.await_count, 1)
        self.assertGreaterEqual(battery.client.edit_message.await_count, 2)
        self.assertEqual(len(battery.respond.await_args_list), 1)  # רק המפה
        self.assertIn("file", battery.respond.await_args.kwargs)

        edited = [c.args[2] for c in destination.client.edit_message.call_args_list]
        edited += [c.args[2] for c in battery.client.edit_message.call_args_list]
        for text in edited:
            self.assertNotIn(trip.TRIP_INVALID_BATTERY_MESSAGE, text)


class TestHandlerRegistrationOrder(unittest.TestCase):
    def test_trip_is_registered_before_location(self):
        """הפילטרים נבדקים לפי סדר הרישום. אם location יירשם קודם, הודעה של זרימה
        שכבר פגה תיבלע במקום ליפול חזרה לחיפוש העמדות הרגיל."""
        source = inspect.getsource(main)
        self.assertLess(
            source.index("trip.register_handlers"),
            source.index("location.register_handlers"),
        )


class TestNoStrayMessagesInTripModule(unittest.TestCase):
    """שומר מפני רגרסיה: רק שלוש הפונקציות האלה רשאיות לשלוח הודעה חדשה בזרימה.

    _show_trip_step - נקודת הפלט היחידה (עם fallback כשהעריכה נכשלת);
    _send_trip_map / _clear_gps_prompt / _send_gps_prompt - הודעות שטלגרם מחייבת
    שיהיו נפרדות (מדיה, ומקלדת תשובה שאי אפשר לצרף לעריכה);
    handle_trip_command - ההודעה שהמשתמש עצמו יזם עם /trip.
    """

    ALLOWED = {
        "_show_trip_step",
        "_send_trip_map",
        "_send_gps_prompt",
        "_clear_gps_prompt",
        "handle_trip_command",
    }

    def test_new_messages_only_come_from_the_allowed_helpers(self):
        tree = ast.parse(inspect.getsource(trip))
        functions = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        def enclosing(lineno: int) -> str:
            candidates = [f for f in functions if f.lineno <= lineno <= f.end_lineno]
            return min(candidates, key=lambda f: f.end_lineno - f.lineno).name

        senders = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in ("respond", "send_message", "send_file"):
                senders.add(enclosing(node.lineno))

        self.assertEqual(senders - self.ALLOWED, set())


if __name__ == "__main__":
    unittest.main()
