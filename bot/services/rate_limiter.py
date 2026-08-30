import collections
import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

from telethon import TelegramClient, events

from bot.config import is_admin, settings

logger = logging.getLogger(__name__)

# ברירות מחדל למגבלות קצב
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MAX_PER_WINDOW = 20
DEFAULT_DAILY_LIMIT = 200
DEFAULT_CLEANUP_INTERVAL = 300  # 5 דקות בין ניקויים תקופתיים
DEFAULT_MAX_IDLE_SECONDS = 3600  # שעה של חוסר פעילות לפני מחיקת רשומה
DEFAULT_WARN_COOLDOWN_SECONDS = 60  # מרווח מינימלי בין שליחת אזהרות לספאמר פעיל


class RateLimitResult:
    """מייצג את תוצאת בדיקת ה-Rate Limit.

    תומך בפירוק כ-tuple: allowed, retry_after_seconds, daily_remaining = result
    וגם בגישה ישירה לתכונות: result.allowed, result.retry_after_seconds, result.daily_remaining, result.reason
    """

    __slots__ = ("allowed", "retry_after_seconds", "daily_remaining", "reason")

    def __init__(
        self,
        allowed: bool,
        retry_after_seconds: int,
        daily_remaining: int,
        reason: Optional[str] = None,
    ):
        self.allowed = allowed
        self.retry_after_seconds = retry_after_seconds
        self.daily_remaining = daily_remaining
        self.reason = reason

    def __iter__(self):
        yield self.allowed
        yield self.retry_after_seconds
        yield self.daily_remaining

    def __getitem__(self, item: int) -> Any:
        return (self.allowed, self.retry_after_seconds, self.daily_remaining)[item]

    def __len__(self) -> int:
        return 3

    def __repr__(self) -> str:
        return (
            f"RateLimitResult(allowed={self.allowed}, "
            f"retry_after_seconds={self.retry_after_seconds}, "
            f"daily_remaining={self.daily_remaining}, "
            f"reason={self.reason!r})"
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, tuple):
            return (self.allowed, self.retry_after_seconds, self.daily_remaining) == other[:3]
        if isinstance(other, RateLimitResult):
            return (
                self.allowed,
                self.retry_after_seconds,
                self.daily_remaining,
                self.reason,
            ) == (
                other.allowed,
                other.retry_after_seconds,
                other.daily_remaining,
                other.reason,
            )
        return False


class UserRecord:
    """רשומת מעקב עבור משתמש בודד בזיכרון."""

    __slots__ = ("timestamps", "daily_count", "day", "last_active", "last_warned")

    def __init__(self, current_day: int, now: float):
        self.timestamps: collections.deque[float] = collections.deque()
        self.daily_count: int = 0
        self.day: int = current_day
        self.last_active: float = now
        self.last_warned: float = 0.0


class RateLimiter:
    """מנגנון בקרת קצב בזיכרון (In-Memory Rate Limiter) לכל משתמש לפי sender_id.

    כולל חלון זמן קצר (rolling window של N שניות) ומגבלה יומית מצטברת,
    עם ניקוי תקופתי למניעת דליפות זיכרון.
    """

    def __init__(
        self,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_per_window: int = DEFAULT_MAX_PER_WINDOW,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
        max_idle_seconds: int = DEFAULT_MAX_IDLE_SECONDS,
        warn_cooldown: int = DEFAULT_WARN_COOLDOWN_SECONDS,
    ):
        self.window_seconds = window_seconds
        self.max_per_window = max_per_window
        self.daily_limit = daily_limit
        self.cleanup_interval = cleanup_interval
        self.max_idle_seconds = max_idle_seconds
        self.warn_cooldown = warn_cooldown

        self._records: Dict[int, UserRecord] = {}
        self._last_cleanup: float = time.time()

    def check(
        self,
        sender_id: Optional[int],
        is_admin_override: Optional[bool] = None,
        current_time: Optional[float] = None,
    ) -> RateLimitResult:
        """בודק האם בקשה מ-sender_id מורשית לפי ה-Rate Limit.

        מנהל המערכת (Admin) פטור תמיד מכל הגבלה.
        """
        if sender_id is None:
            return RateLimitResult(
                allowed=True,
                retry_after_seconds=0,
                daily_remaining=self.daily_limit,
            )

        # פטור מלא למנהל המערכת
        if is_admin_override is True or (is_admin_override is None and is_admin(sender_id)):
            return RateLimitResult(
                allowed=True,
                retry_after_seconds=0,
                daily_remaining=self.daily_limit,
            )

        now = current_time if current_time is not None else time.time()

        # ניקוי תקופתי של רשומות ישנות למניעת memory leak
        if (now - self._last_cleanup) >= self.cleanup_interval:
            self.cleanup(now=now)

        current_day = int(now // 86400)
        record = self._records.get(sender_id)
        if record is None:
            record = UserRecord(current_day, now)
            self._records[sender_id] = record
        elif record.day != current_day:
            # איפוס יומי ביום חדש
            record.day = current_day
            record.daily_count = 0

        # סילוק חותמות זמן ישנות מחוץ לחלון המתגלגל
        cutoff = now - self.window_seconds
        while record.timestamps and record.timestamps[0] <= cutoff:
            record.timestamps.popleft()

        # 1. בדיקת חריגה מהמגבלה היומית
        if record.daily_count >= self.daily_limit:
            record.last_active = now
            # שניות עד חצות UTC
            seconds_until_midnight = max(1, int(math.ceil(86400 - (now % 86400))))
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=seconds_until_midnight,
                daily_remaining=0,
                reason="daily_limit",
            )

        # 2. בדיקת חריגה ממגבלת חלון הזמן הקצר
        if len(record.timestamps) >= self.max_per_window:
            record.last_active = now
            oldest_ts = record.timestamps[0]
            retry_after = max(1, int(math.ceil(self.window_seconds - (now - oldest_ts))))
            daily_rem = max(0, self.daily_limit - record.daily_count)
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=retry_after,
                daily_remaining=daily_rem,
                reason="window_limit",
            )

        # הבקשה מאושרת: רישום חותמת זמן והגדלת מונה יומי
        record.timestamps.append(now)
        record.daily_count += 1
        record.last_active = now
        daily_rem = max(0, self.daily_limit - record.daily_count)

        return RateLimitResult(
            allowed=True,
            retry_after_seconds=0,
            daily_remaining=daily_rem,
        )

    def should_notify_user(
        self,
        sender_id: int,
        current_time: Optional[float] = None,
    ) -> bool:
        """בודק האם לשלוח הודעת אזהרה למשתמש החסום (מונע הצפת צ'אט במקרה של ספאם רצוף)."""
        now = current_time if current_time is not None else time.time()
        record = self._records.get(sender_id)
        if record is None:
            return True

        if (now - record.last_warned) >= self.warn_cooldown:
            record.last_warned = now
            return True
        return False

    def cleanup(
        self,
        max_idle_seconds: Optional[int] = None,
        now: Optional[float] = None,
    ) -> int:
        """מנקה רשומות של משתמשים שלא היו פעילים זמן רב."""
        current_ts = now if now is not None else time.time()
        max_idle = max_idle_seconds if max_idle_seconds is not None else self.max_idle_seconds
        current_day = int(current_ts // 86400)

        to_delete = []
        for uid, rec in self._records.items():
            is_idle = (current_ts - rec.last_active) >= max_idle
            is_old_day_empty = (rec.day != current_day and not rec.timestamps)
            if is_idle or is_old_day_empty:
                to_delete.append(uid)

        for uid in to_delete:
            del self._records[uid]

        self._last_cleanup = current_ts
        if to_delete:
            logger.debug(
                "Cleaned up %d idle rate limit records (remaining: %d)",
                len(to_delete),
                len(self._records),
            )
        return len(to_delete)

    def reset(self) -> None:
        """איפוס כל הרשומות בזיכרון (עבור בדיקות)."""
        self._records.clear()
        self._last_cleanup = time.time()


# מופע ברירת מחדל של ה-RateLimiter
default_rate_limiter = RateLimiter(
    window_seconds=DEFAULT_WINDOW_SECONDS,
    max_per_window=getattr(settings, "rate_limit_per_minute", DEFAULT_MAX_PER_WINDOW),
    daily_limit=getattr(settings, "rate_limit_daily", DEFAULT_DAILY_LIMIT),
)


def check_rate_limit(
    sender_id: Optional[int],
    is_admin_override: Optional[bool] = None,
    current_time: Optional[float] = None,
) -> RateLimitResult:
    """פונקציית בדיקה ראשית עבור sender_id."""
    return default_rate_limiter.check(
        sender_id=sender_id,
        is_admin_override=is_admin_override,
        current_time=current_time,
    )


def register_handlers(
    client: TelegramClient,
    limiter: Optional[RateLimiter] = None,
) -> None:
    """רושם handlers לבדיקת rate limit לפני כל שאר ה-handlers בבוט."""
    rl = limiter or default_rate_limiter

    @client.on(events.NewMessage)
    async def rate_limit_message_handler(event: events.NewMessage.Event) -> None:
        if getattr(event, "out", False):
            return

        sender_id = event.sender_id or event.chat_id
        if sender_id is None:
            return

        result = rl.check(sender_id)
        if not result.allowed:
            logger.warning(
                "Rate limit exceeded for NewMessage sender_id=%s (retry_after=%ss, daily_remaining=%s, reason=%s)",
                sender_id,
                result.retry_after_seconds,
                result.daily_remaining,
                result.reason,
            )
            if rl.should_notify_user(sender_id):
                try:
                    if result.reason == "daily_limit":
                        msg = (
                            "⚠️ <b>הגעת למגבלת ההודעות היומית של הבוט.</b>\n\n"
                            "כדי למנוע עומס והתעללות, השימוש מוגבל ל-200 הודעות ביום. המגבלה תתאפס בחצות (UTC)."
                        )
                    else:
                        msg = (
                            "⚠️ <b>אתה שולח הודעות מהר מדי.</b>\n\n"
                            f"אנא המתן <b>{result.retry_after_seconds}</b> שניות לפני שליחת הודעה נוספת."
                        )
                    await event.respond(msg, parse_mode="html")
                except Exception:
                    pass
            raise events.StopPropagation

    @client.on(events.CallbackQuery)
    async def rate_limit_callback_handler(event: events.CallbackQuery.Event) -> None:
        sender_id = event.sender_id or event.chat_id
        if sender_id is None:
            return

        result = rl.check(sender_id)
        if not result.allowed:
            logger.warning(
                "Rate limit exceeded for CallbackQuery sender_id=%s (retry_after=%ss, daily_remaining=%s, reason=%s)",
                sender_id,
                result.retry_after_seconds,
                result.daily_remaining,
                result.reason,
            )
            try:
                if result.reason == "daily_limit":
                    await event.answer("⚠️ הגעת למגבלת הבקשות היומית. נסה שוב מחר.", alert=True)
                else:
                    await event.answer(
                        f"⚠️ פעולה מהירה מדי. אנא המתן {result.retry_after_seconds} שניות.",
                        alert=True,
                    )
            except Exception:
                pass
            raise events.StopPropagation
