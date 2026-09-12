import os
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from telethon.errors import MessageNotModifiedError

from bot.handlers.trip import _show_trip_step
from bot.states import UserSession
from bot.storage.users_db import (
    cleanup_old_trip_plans,
    get_recent_trip_plans,
    get_trip_plan,
    init_users_db,
    save_trip_plan,
)

SAMPLE_PLAN = {
    "total_distance_km": 330.0,
    "straight_line_km": 264.0,
    "duration_hours": 3.6,
    "num_stops": 1,
    "available_range_km": 245.0,
    "car_params": {
        "real_range_km": 350.0, "battery_percent": 80.0,
        "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
        "min_power_kw": None,
    },
    "stops": [
        {
            "segment_index": 1,
            "distance_from_origin_km": 280.0,
            "station": {"id": 1, "name": "עמדת דוגמה", "lat": 31.5, "lng": 34.9, "max_power": 150.0},
            "relaxation": {"providers": False, "price": False, "power_kw": 150.0},
        }
    ],
    "missing_segments": [],
}


class TestTripPlanPersistence(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        await init_users_db(self.users_db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_save_and_retrieve_round_trip(self):
        plan_id = await save_trip_plan(
            chat_id=555,
            origin={"lat": 32.0853, "lng": 34.7818, "name": "תל אביב"},
            destination={"lat": 29.557, "lng": 34.952, "name": "אילת"},
            battery_percent=80.0,
            plan=SAMPLE_PLAN,
            db_path=self.users_db_path,
        )
        self.assertIsNotNone(plan_id)

        row = await get_trip_plan(plan_id, 555, self.users_db_path)
        self.assertIsNotNone(row)
        self.assertEqual(row["origin_name"], "תל אביב")
        self.assertEqual(row["destination_name"], "אילת")
        self.assertAlmostEqual(row["battery_percent"], 80.0)
        self.assertEqual(row["plan"]["stops"][0]["station"]["name"], "עמדת דוגמה")

    async def test_recent_plans_ordered_newest_first(self):
        for name in ("חיפה", "ירושלים", "אילת"):
            await save_trip_plan(
                chat_id=777,
                origin={"lat": 32.0, "lng": 34.7},
                destination={"lat": 31.7, "lng": 35.2, "name": name},
                battery_percent=70.0,
                plan=SAMPLE_PLAN,
                db_path=self.users_db_path,
            )
        plans = await get_recent_trip_plans(777, self.users_db_path, limit=5)
        self.assertEqual(len(plans), 3)
        self.assertEqual(plans[0]["destination_name"], "אילת")

    async def test_recent_plans_respects_limit(self):
        for i in range(7):
            await save_trip_plan(
                chat_id=888,
                origin={"lat": 32.0, "lng": 34.7},
                destination={"lat": 31.7, "lng": 35.2, "name": f"יעד {i}"},
                battery_percent=70.0,
                plan=SAMPLE_PLAN,
                db_path=self.users_db_path,
            )
        plans = await get_recent_trip_plans(888, self.users_db_path, limit=5)
        self.assertEqual(len(plans), 5)

    async def test_plan_scoped_to_owner_chat_id(self):
        plan_id = await save_trip_plan(
            chat_id=111,
            origin={"lat": 32.0, "lng": 34.7},
            destination={"lat": 31.7, "lng": 35.2, "name": "יעד פרטי"},
            battery_percent=70.0,
            plan=SAMPLE_PLAN,
            db_path=self.users_db_path,
        )
        # משתמש אחר לא יכול לשלוף את התוכנית ע"י ניחוש ה-id שלה.
        other_users_view = await get_trip_plan(plan_id, 222, self.users_db_path)
        self.assertIsNone(other_users_view)

        owner_view = await get_trip_plan(plan_id, 111, self.users_db_path)
        self.assertIsNotNone(owner_view)

    async def test_missing_plan_returns_none(self):
        row = await get_trip_plan(99999, 111, self.users_db_path)
        self.assertIsNone(row)


class TestCleanupOldTripPlans(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_db_path = os.path.join(self.temp_dir.name, "test_users.db")
        await init_users_db(self.users_db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    def _insert_with_age(self, chat_id: int, days_old: int, destination_name: str) -> None:
        conn = sqlite3.connect(self.users_db_path)
        conn.execute(
            """
            INSERT INTO trip_plans (chat_id, created_at, origin_lat, origin_lng, destination_lat,
                destination_lng, destination_name, total_distance_km, battery_percent, plan_json)
            VALUES (?, datetime('now', ?), 32.0, 34.7, 31.7, 35.2, ?, 300.0, 80.0, '{}')
            """,
            (chat_id, f"-{days_old} days", destination_name),
        )
        conn.commit()
        conn.close()

    async def test_deletes_only_plans_older_than_30_days(self):
        self._insert_with_age(1, 45, "ישן מדי")
        self._insert_with_age(1, 10, "עדיין רלוונטי")
        self._insert_with_age(1, 1, "חדש")

        deleted = await cleanup_old_trip_plans(self.users_db_path, days=30)
        self.assertEqual(deleted, 1)

        remaining = await get_recent_trip_plans(1, self.users_db_path, limit=10)
        names = {p["destination_name"] for p in remaining}
        self.assertEqual(names, {"עדיין רלוונטי", "חדש"})

    async def test_keeps_plans_at_least_10_days_old(self):
        self._insert_with_age(2, 10, "בן 10 ימים")
        deleted = await cleanup_old_trip_plans(self.users_db_path, days=30)
        self.assertEqual(deleted, 0)
        remaining = await get_recent_trip_plans(2, self.users_db_path, limit=10)
        self.assertEqual(len(remaining), 1)

    async def test_no_plans_to_delete_returns_zero(self):
        deleted = await cleanup_old_trip_plans(self.users_db_path, days=30)
        self.assertEqual(deleted, 0)


class TestShowTripStep(unittest.IsolatedAsyncioTestCase):
    def _make_event(self):
        event = AsyncMock()
        event.client = AsyncMock()
        return event

    async def test_sends_new_message_when_no_trip_message_id_yet(self):
        event = self._make_event()
        sent_msg = MagicMock(id=42)
        event.respond = AsyncMock(return_value=sent_msg)
        session = UserSession()

        await _show_trip_step(event, chat_id=1, session=session, text="שלום")

        event.respond.assert_called_once()
        event.client.edit_message.assert_not_called()
        self.assertEqual(session.trip_message_id, 42)

    async def test_edits_existing_trip_message_when_present(self):
        event = self._make_event()
        session = UserSession()
        session.trip_message_id = 10

        await _show_trip_step(event, chat_id=1, session=session, text="שלב הבא")

        event.client.edit_message.assert_called_once_with(1, 10, "שלב הבא", buttons=None, parse_mode="html")
        event.respond.assert_not_called()
        self.assertEqual(session.trip_message_id, 10)

    async def test_falls_back_to_new_message_when_edit_fails(self):
        """אם ההודעה הישנה נמחקה/ישנה מדי - client.edit_message נכשל, אז שולחים הודעה חדשה."""
        event = self._make_event()
        event.client.edit_message = AsyncMock(side_effect=Exception("MESSAGE_ID_INVALID"))
        sent_msg = MagicMock(id=99)
        event.respond = AsyncMock(return_value=sent_msg)
        session = UserSession()
        session.trip_message_id = 10

        await _show_trip_step(event, chat_id=1, session=session, text="שלב הבא")

        event.client.edit_message.assert_called_once()
        event.respond.assert_called_once()
        self.assertEqual(session.trip_message_id, 99)

    async def test_message_not_modified_is_treated_as_success_no_duplicate_send(self):
        event = self._make_event()
        event.client.edit_message = AsyncMock(side_effect=MessageNotModifiedError(MagicMock()))
        event.respond = AsyncMock()
        session = UserSession()
        session.trip_message_id = 10

        await _show_trip_step(event, chat_id=1, session=session, text="שלב הבא")

        event.respond.assert_not_called()
        self.assertEqual(session.trip_message_id, 10)


if __name__ == "__main__":
    unittest.main()
