import asyncio
from datetime import datetime
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from bot.config import settings, is_admin, WEBAPP_URL
from bot.storage.users_db import get_usage_stats, get_map_stats
from bot.services.bot_health import (
    get_uptime_str,
    get_start_time_str,
    get_recent_errors_summary,
    check_geoapify_health,
    check_webapp_health,
    get_database_stats,
)

logger = logging.getLogger(__name__)

UNAUTHORIZED_MESSAGE = "⛔ <b>אין לך הרשאה לגשת לפקודה זו.</b>"


def admin_keyboard() -> list[list[Button]]:
    """כפתורי לוח הבקרה למנהל."""
    return [
        [Button.inline("🔄 רענן נתונים", data=b"admin:refresh")]
    ]


async def build_admin_report() -> str:
    """בונה דו״ח סטטיסטיקה ומצב מערכת מקיף עבור המנהל (מידע מצטבר ואנונימי בלבד)."""
    usage_task = get_usage_stats(settings.users_db_path)
    map_task = get_map_stats(settings.users_db_path)
    db_task = get_database_stats(settings.db_path, settings.users_db_path)
    geoapify_task = check_geoapify_health(settings.map_provider_key)
    webapp_task = check_webapp_health(WEBAPP_URL)

    usage_stats, map_stats, db_stats, geoapify_status, webapp_status = await asyncio.gather(
        usage_task, map_task, db_task, geoapify_task, webapp_task
    )

    uptime_str = get_uptime_str()
    start_time_str = get_start_time_str()
    errors_summary = get_recent_errors_summary()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    locations_count = db_stats.get("locations_count", 0)
    priced_count = db_stats.get("priced_locations_count", 0)
    operators_count = db_stats.get("operators_count", 0)
    price_pct = (priced_count / locations_count * 100) if locations_count > 0 else 0

    return (
        "📊 <b>לוח בקרה וניהול — EV Charging Bot</b>\n"
        "──────────────────\n\n"
        "👥 <b>סטטיסטיקת שימוש (מצטברת ואנונימית):</b>\n"
        f"• משתמשים ייחודיים: <b>{usage_stats.get('total_users', 0):,}</b>\n"
        f"• סה\"כ חיפושים שבוצעו: <b>{usage_stats.get('total_searches', 0):,}</b>\n"
        f"• חיפושים היום: <b>{usage_stats.get('today_searches', 0):,}</b>\n"
        f"• חיפושים השבוע (7 ימים): <b>{usage_stats.get('week_searches', 0):,}</b>\n\n"
        "🗺️ <b>שירות מפות (Geoapify & OSM):</b>\n"
        f"• מצב API של Geoapify: <b>{geoapify_status}</b>\n"
        f"• סה\"כ מפות שרונדרו: <b>{map_stats.get('total_maps', 0):,}</b>\n"
        f"• רינדור דרך Geoapify: <b>{map_stats.get('geoapify_maps', 0):,}</b>\n"
        f"• נפילה ל-OSM מקומי (Fallback): <b>{map_stats.get('fallback_maps', 0):,}</b>\n\n"
        "🗄️ <b>מצב מאגר הנתונים (Database):</b>\n"
        f"• אתרי טעינה במאגר: <b>{locations_count:,}</b>\n"
        f"• אתרים עם מידע על מחירים: <b>{priced_count:,} ({price_pct:.1f}%)</b>\n"
        f"• מפעילים ייחודיים: <b>{operators_count}</b>\n"
        f"• גודל קובץ נתונים: <b>{db_stats.get('db_size', '-')}</b>\n"
        f"• גודל קובץ משתמשים: <b>{db_stats.get('users_db_size', '-')}</b>\n\n"
        "🌐 <b>ממשק WebApp:</b>\n"
        f"• כתובת: <code>{WEBAPP_URL}</code>\n"
        f"• סטטוס זמינות: <b>{webapp_status}</b>\n\n"
        "⏱️ <b>בריאות המערכת (System Health):</b>\n"
        f"• זמן פעילות (Uptime): <b>{uptime_str}</b>\n"
        f"• מועד הפעלה: <b>{start_time_str}</b>\n"
        f"• יומן שגיאות: <b>{errors_summary}</b>\n"
        "──────────────────\n"
        f"🕒 <i>עודכן לאחרונה: {now_str}</i>"
    )


def register_handlers(client: TelegramClient) -> None:
    """רושם את ה-handlers של פיקוד הניהול בבוט."""

    @client.on(events.NewMessage(pattern=r'^/(admin|stats)(\s|$)'))
    async def handle_admin_command(event: events.NewMessage.Event) -> None:
        sender_id = event.sender_id or event.chat_id
        if not is_admin(sender_id):
            logger.warning("Unauthorized access attempt to /admin from sender_id=%s", sender_id)
            await event.respond(UNAUTHORIZED_MESSAGE, parse_mode="html")
            return

        try:
            report_text = await build_admin_report()
            await event.respond(
                report_text,
                buttons=admin_keyboard(),
                parse_mode="html",
            )
        except Exception:
            logger.exception("Error generating admin report for sender_id=%s", sender_id)
            await event.respond("❌ אירעה שגיאה בעת יצירת דו״ח הניהול.")

    @client.on(events.CallbackQuery(pattern=rb"^admin:refresh$"))
    async def handle_admin_refresh(event: events.CallbackQuery.Event) -> None:
        sender_id = event.sender_id or event.chat_id
        if not is_admin(sender_id):
            logger.warning("Unauthorized refresh attempt to admin panel from sender_id=%s", sender_id)
            await event.answer("⛔ אין לך הרשאה לבצע פעולה זו.", alert=True)
            return

        try:
            await event.answer("מרענן נתונים... ⏳")
            report_text = await build_admin_report()
            await event.edit(
                report_text,
                buttons=admin_keyboard(),
                parse_mode="html",
            )
        except Exception:
            logger.exception("Error refreshing admin report for sender_id=%s", sender_id)
            await event.answer("❌ אירעה שגיאה בעת רענון הנתונים.", alert=True)
