import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telethon import events

from bot.services.rate_limiter import (
    RateLimiter,
    RateLimitResult,
    check_rate_limit,
    register_handlers as register_rate_limit_handlers,
)


class TestRateLimiterCore(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            window_seconds=60,
            max_per_window=20,
            daily_limit=200,
            cleanup_interval=300,
            max_idle_seconds=3600,
            warn_cooldown=60,
        )

    def test_20_requests_allowed_21st_blocked(self):
        """משתמש שולח 21 הודעות מהר -> ה-21 נחסמת."""
        user_id = 12345
        t0 = 100000.0

        for i in range(20):
            res = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + i * 0.1)
            self.assertTrue(res.allowed, f"Request {i+1} should be allowed")
            self.assertEqual(res.retry_after_seconds, 0)
            self.assertEqual(res.daily_remaining, 200 - (i + 1))

        # The 21st request at rapid succession should be blocked
        res_21 = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + 2.1)
        self.assertFalse(res_21.allowed, "21st request within 60s window must be blocked")
        self.assertGreater(res_21.retry_after_seconds, 0)
        self.assertEqual(res_21.reason, "window_limit")
        self.assertEqual(res_21.daily_remaining, 180)

    def test_window_resets_after_60_seconds(self):
        """חלון זמן מתאפס אחרי 60 שניות."""
        user_id = 23456
        t0 = 100000.0

        # Send 20 requests at t0
        for _ in range(20):
            res = self.limiter.check(user_id, is_admin_override=False, current_time=t0)
            self.assertTrue(res.allowed)

        # 21st request at t0 is blocked
        res_blocked = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + 1.0)
        self.assertFalse(res_blocked.allowed)
        self.assertEqual(res_blocked.retry_after_seconds, 59)

        # Advance time by 61 seconds (past the 60s window)
        res_after_window = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + 61.0)
        self.assertTrue(res_after_window.allowed, "Request after 60s window must be allowed")
        self.assertEqual(res_after_window.retry_after_seconds, 0)

    def test_sliding_window_partial_expiry(self):
        """בדיקת חלון מתגלגל (sliding window) - פינוי חלקי של הודעות ישנות."""
        user_id = 34567
        t0 = 100000.0

        # 10 requests at t=0
        for _ in range(10):
            self.assertTrue(self.limiter.check(user_id, is_admin_override=False, current_time=t0).allowed)

        # 10 requests at t=30
        for _ in range(10):
            self.assertTrue(self.limiter.check(user_id, is_admin_override=False, current_time=t0 + 30.0).allowed)

        # Request at t=35 is blocked (20 in last 60s)
        res_blocked = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + 35.0)
        self.assertFalse(res_blocked.allowed)

        # At t=61: first 10 requests expired, 10 remain from t=30
        res_allowed = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + 61.0)
        self.assertTrue(res_allowed.allowed)

    def test_admin_is_exempt(self):
        """המנהל פטור מכל הגבלה."""
        admin_id = 99999
        t0 = 100000.0

        with patch("bot.services.rate_limiter.is_admin", return_value=True):
            # Admin sends 100 requests in 1 second
            for i in range(100):
                res = self.limiter.check(admin_id, current_time=t0)
                self.assertTrue(res.allowed, f"Admin request {i+1} must be allowed")
                self.assertEqual(res.retry_after_seconds, 0)

        # Also test with explicit is_admin_override=True
        for i in range(50):
            res = self.limiter.check(1234, is_admin_override=True, current_time=t0)
            self.assertTrue(res.allowed)

    def test_daily_limit(self):
        """בדיקת המגבלה היומית (200 הודעות ליום)."""
        user_id = 45678
        t0 = 100000.0  # arbitrary timestamp

        # Distribute 200 requests across time (e.g. 10 requests every 2 minutes = no window violation)
        for i in range(200):
            req_time = t0 + (i * 70.0)  # 70s between requests -> never hits 20/60s window
            res = self.limiter.check(user_id, is_admin_override=False, current_time=req_time)
            self.assertTrue(res.allowed, f"Daily request {i+1} should be allowed")
            self.assertEqual(res.daily_remaining, 200 - (i + 1))

        # 201st request on same day must be blocked by daily limit
        res_201 = self.limiter.check(user_id, is_admin_override=False, current_time=t0 + (200 * 70.0))
        self.assertFalse(res_201.allowed, "201st daily request must be blocked")
        self.assertEqual(res_201.reason, "daily_limit")
        self.assertEqual(res_201.daily_remaining, 0)
        self.assertGreater(res_201.retry_after_seconds, 0)

        # Next day (advance timestamp by 86400s from t0): limit resets
        next_day_time = t0 + 86400.0 + 10.0
        res_next_day = self.limiter.check(user_id, is_admin_override=False, current_time=next_day_time)
        self.assertTrue(res_next_day.allowed, "Request on next day should be allowed after daily reset")
        self.assertEqual(res_next_day.daily_remaining, 199)

    def test_memory_cleanup_removes_idle_entries(self):
        """ניקוי entries ישנים עובד (ללא memory leak)."""
        t0 = 100000.0

        # Create 50 distinct users at t0
        for uid in range(1000, 1050):
            self.limiter.check(uid, is_admin_override=False, current_time=t0)

        self.assertEqual(len(self.limiter._records), 50)

        # User 1000 makes a request at t0 + 4000 (active)
        t_active = t0 + 4000.0
        self.limiter.check(1000, is_admin_override=False, current_time=t_active)

        # Run cleanup with max_idle_seconds=3600
        # Users 1001..1049 were last active at t0 (4000s ago > 3600s), user 1000 active at t_active (0s ago)
        deleted = self.limiter.cleanup(max_idle_seconds=3600, now=t_active)
        self.assertEqual(deleted, 49)
        self.assertEqual(len(self.limiter._records), 1)
        self.assertIn(1000, self.limiter._records)

    def test_automatic_cleanup_triggered_on_check(self):
        """ניקוי תקופתי מופעל אוטומטית לפי מרווח זמן ב-check."""
        t0 = 100000.0
        self.limiter._last_cleanup = t0

        # Add user at t0
        self.limiter.check(5001, is_admin_override=False, current_time=t0)

        # After cleanup_interval (300s) + max_idle_seconds (3600s), next check triggers automatic cleanup
        t_future = t0 + 4000.0
        self.limiter.check(5002, is_admin_override=False, current_time=t_future)

        # User 5001 should have been cleaned up automatically, leaving only 5002
        self.assertEqual(len(self.limiter._records), 1)
        self.assertIn(5002, self.limiter._records)

    def test_should_notify_user_cooldown(self):
        """בדיקת מניעת הצפת אזהרות למשתמש (warn cooldown)."""
        user_id = 77777
        t0 = 100000.0

        # Fill window
        for _ in range(20):
            self.limiter.check(user_id, is_admin_override=False, current_time=t0)

        # First violation -> should notify
        self.assertTrue(self.limiter.should_notify_user(user_id, current_time=t0))

        # Immediately subsequent violations during spam burst -> should NOT notify (silent drop)
        self.assertFalse(self.limiter.should_notify_user(user_id, current_time=t0 + 5.0))
        self.assertFalse(self.limiter.should_notify_user(user_id, current_time=t0 + 30.0))

        # After warn_cooldown (60s) -> should notify again
        self.assertTrue(self.limiter.should_notify_user(user_id, current_time=t0 + 61.0))

    def test_result_structure_and_unpacking(self):
        """בדיקת תאימות מבנה RateLimitResult לפירוק כ-tuple ולשמות שדות."""
        user_id = 88888
        t0 = 100000.0

        result = self.limiter.check(user_id, is_admin_override=False, current_time=t0)

        # 1. Tuple unpacking
        allowed, retry_after, remaining = result
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)
        self.assertEqual(remaining, 199)

        # 2. Named attributes
        self.assertTrue(result.allowed)
        self.assertEqual(result.retry_after_seconds, 0)
        self.assertEqual(result.daily_remaining, 199)

        # 3. Tuple equality and indexing
        self.assertEqual(result, (True, 0, 199))
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], 0)
        self.assertEqual(result[2], 199)
        self.assertEqual(len(result), 3)

    def test_none_sender_id_allowed(self):
        """sender_id שהוא None תמיד מורשה."""
        res = self.limiter.check(None)
        self.assertTrue(res.allowed)
        self.assertEqual(res.retry_after_seconds, 0)


class TestRateLimiterHandlers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.limiter = RateLimiter(
            window_seconds=60,
            max_per_window=20,
            daily_limit=200,
            cleanup_interval=300,
            max_idle_seconds=3600,
            warn_cooldown=60,
        )

        self.mock_client = MagicMock()
        self.registered_handlers = []

        def mock_on(event_builder):
            def decorator(f):
                self.registered_handlers.append((event_builder, f))
                return f
            return decorator

        self.mock_client.on = mock_on
        register_rate_limit_handlers(self.mock_client, limiter=self.limiter)

        self.message_handler = self.registered_handlers[0][1]
        self.callback_handler = self.registered_handlers[1][1]

    async def test_normal_message_allowed(self):
        event = AsyncMock()
        event.out = False
        event.sender_id = 1111
        event.chat_id = 1111

        with patch("bot.services.rate_limiter.is_admin", return_value=False):
            # Normal message: should complete without raising StopPropagation
            await self.message_handler(event)
            event.respond.assert_not_called()

    async def test_spammer_message_blocked_and_stopped(self):
        event = AsyncMock()
        event.out = False
        event.sender_id = 2222
        event.chat_id = 2222

        with patch("bot.services.rate_limiter.is_admin", return_value=False):
            # Send 20 allowed messages
            for _ in range(20):
                await self.message_handler(event)

            # 21st message: should send 1 warning and raise StopPropagation
            with self.assertRaises(events.StopPropagation):
                await self.message_handler(event)

            event.respond.assert_called_once()
            self.assertIn("אתה שולח הודעות מהר מדי", event.respond.call_args[0][0])

            # 22nd message (spam continuation): should NOT send second response (silent), but still raise StopPropagation
            event.respond.reset_mock()
            with self.assertRaises(events.StopPropagation):
                await self.message_handler(event)
            event.respond.assert_not_called()

    async def test_callback_rate_limited(self):
        event = AsyncMock()
        event.sender_id = 3333
        event.chat_id = 3333

        with patch("bot.services.rate_limiter.is_admin", return_value=False):
            for _ in range(20):
                await self.callback_handler(event)

            # 21st callback query: should alert and raise StopPropagation
            with self.assertRaises(events.StopPropagation):
                await self.callback_handler(event)

            event.answer.assert_called_once()
            self.assertIn("פעולה מהירה מדי", event.answer.call_args[0][0])
            self.assertTrue(event.answer.call_args[1].get("alert"))

    async def test_admin_never_blocked_in_handlers(self):
        event = AsyncMock()
        event.out = False
        event.sender_id = 9999
        event.chat_id = 9999

        with patch("bot.services.rate_limiter.is_admin", return_value=True):
            # 50 messages from admin: none raise StopPropagation
            for _ in range(50):
                await self.message_handler(event)
            event.respond.assert_not_called()


if __name__ == "__main__":
    unittest.main()
