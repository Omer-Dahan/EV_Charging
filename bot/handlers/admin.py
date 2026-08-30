import asyncio
from datetime import datetime, timezone
import html
import json
import logging
import re
import sqlite3
from typing import Optional, Tuple
import uuid

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from bot.config import settings, is_admin, WEBAPP_URL
from bot.services.formatter import _connectors_block
from bot.services.geocoder import parse_coordinates
from bot.states import get_session
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

MAX_NAME_LENGTH = 150
MAX_ADDRESS_LENGTH = 200
MAX_CITY_LENGTH = 100
MAX_PROVIDER_LENGTH = 80
MAX_CONNECTORS_LENGTH = 500



def admin_keyboard() -> list[list[Button]]:
    """כפתורי לוח הבקרה למנהל."""
    return [
        [
            Button.inline("🔄 רענן נתונים", data=b"admin:refresh"),
            Button.inline("➕ הוספת עמדה חדשה", data=b"admin:add_station"),
        ]
    ]


def admin_wizard_cancel_keyboard() -> list[list[Button]]:
    """כפתור ביטול inline במהלך ה-wizard."""
    return [
        [Button.inline("❌ ביטול הוספה", data=b"admin:add_cancel")]
    ]


def admin_location_keyboard() -> list[list[Button]]:
    """מקלדת reply לשיתוף מיקום GPS או ביטול."""
    return [
        [Button.request_location("📍 שתף מיקום GPS נוכחי", resize=True, single_use=True)],
        [Button.text("❌ ביטול", resize=True, single_use=True)],
    ]


def admin_confirm_keyboard() -> list[list[Button]]:
    """כפתורי אישור וביטול בסיום ה-wizard."""
    return [
        [
            Button.inline("✅ אישור ושמירה במאגר", data=b"admin:add_confirm"),
            Button.inline("❌ ביטול", data=b"admin:add_cancel"),
        ]
    ]


def is_valid_israel_coord(lat: float, lng: float) -> bool:
    """בדיקת גבולות קואורדינטות בישראל (קו רוחב 29-34, קו אורך 34-36)."""
    return 29.0 <= lat <= 34.0 and 34.0 <= lng <= 36.0


def parse_admin_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """מפענח קואורדינטות מטקסט או קישור מפות."""
    coords = parse_coordinates(text)
    if coords is not None:
        lat, lng = coords
        if is_valid_israel_coord(lat, lng):
            return lat, lng
        if is_valid_israel_coord(lng, lat):
            return lng, lat
        return lat, lng

    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text)
    if len(nums) >= 2:
        try:
            v1 = float(nums[0])
            v2 = float(nums[1])
            if is_valid_israel_coord(v1, v2):
                return v1, v2
            if is_valid_israel_coord(v2, v1):
                return v2, v1
            return v1, v2
        except (ValueError, TypeError):
            return None
    return None


def parse_connectors_input(text: str) -> list[dict]:
    """מפענח מחרוזת מחברים חופשית (לדוגמה 'CCS2 150kW, Type2 22kW') למבנה JSON של עמדה."""
    cleaned = text.strip()
    if len(cleaned) > MAX_CONNECTORS_LENGTH:
        raise ValueError(f"פירוט המחברים ארוך מדי (מקסימום {MAX_CONNECTORS_LENGTH} תווים)")
    if not cleaned or cleaned.lower() in ("-", "דלג", "ללא", "none", "skip"):
        return []

    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    chunks = re.split(r"[,;\n+]+", cleaned)
    connectors = []
    for chunk in chunks:
        c = chunk.strip()
        if not c:
            continue
        c_lower = c.lower()
        if "ccs" in c_lower or "combo" in c_lower:
            standard = "CCS2_COMBO"
            power_type = "DC"
            default_power = 150.0
        elif "type" in c_lower or "ac" in c_lower or "mennekes" in c_lower or "טייפ" in c_lower:
            standard = "TYPE2"
            power_type = "AC"
            default_power = 22.0
        elif "chade" in c_lower or "צ'אדמו" in c_lower or "צדמו" in c_lower:
            standard = "CHADEMO"
            power_type = "DC"
            default_power = 50.0
        else:
            standard = "OTHER"
            power_type = "DC"
            default_power = 50.0

        # Remove standard names like CCS2, Type2 so their '2' is not extracted as power
        temp = re.sub(r"ccs\s*2?|combo\s*2?|type\s*2?|chademo", "", c, flags=re.IGNORECASE)
        match_kw = re.search(r"(\d+(?:\.\d+)?)\s*(?:kw|קווט|קוט|k|w)?", temp, re.IGNORECASE)
        if match_kw and match_kw.group(1):
            try:
                max_power = float(match_kw.group(1))
            except ValueError:
                max_power = default_power
        else:
            max_power = default_power

        connectors.append({
            "standard": standard,
            "powerType": power_type,
            "maxPower": int(max_power) if max_power.is_integer() else max_power,
        })
    return connectors


def parse_price_input(text: str) -> Optional[float]:
    """מפענח מחיר לקוט\"ש מטקסט חופשי או None אם דולג."""
    cleaned = text.strip()
    if not cleaned or cleaned.lower() in ("-", "דלג", "ללא", "none", "skip"):
        return None
    if cleaned.lower() in ("חינם", "free", "0"):
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def format_admin_station_summary(data: dict) -> str:
    """מעצב סיכום פרטי עמדה חדשה לקראת אישור המנהל."""
    name = data.get("name", "לא צוין")
    address = data.get("address", "לא צוין")
    lat = data.get("lat", 0.0)
    lng = data.get("lng", 0.0)
    provider = data.get("provider", "ידני")
    connectors = data.get("connectors", [])
    price = data.get("price")

    if connectors:
        conn_str = _connectors_block(connectors)
    else:
        conn_str = "לא צוין"

    price_str = f"{price:.2f} ₪ לקוט\"ש" if price is not None else "לא צוין"

    return (
        "📋 <b>סיכום פרטי העמדה החדשה:</b>\n"
        "──────────────────\n"
        f"🏢 <b>שם העמדה:</b> {html.escape(name)}\n"
        f"📍 <b>כתובת:</b> {html.escape(address)}\n"
        f"🌐 <b>קואורדינטות:</b> <code>{lat:.5f}, {lng:.5f}</code>\n"
        f"🏭 <b>מפעיל:</b> {html.escape(provider)}\n"
        f"🔌 <b>מחברים:</b> {conn_str}\n"
        f"💰 <b>מחיר:</b> {price_str}\n"
        f"🏷️ <b>מקור:</b> <code>manual</code>\n"
        "──────────────────\n"
        "האם לאשר ולהוסיף את העמדה למאגר?"
    )


def _insert_manual_station_sync(db_path: str, data: dict) -> int:
    """הכנסת עמדה חדשה לטבלת locations ב-SQLite באופן סינכרוני."""
    cello_id = data.get("cello_id") or f"MANUAL_{uuid.uuid4().hex[:12].upper()}"
    name = (data.get("name") or "").strip()
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"השם ארוך מדי (מקסימום {MAX_NAME_LENGTH} תווים)")

    address = (data.get("address") or "").strip()
    if len(address) > MAX_ADDRESS_LENGTH:
        raise ValueError(f"הכתובת ארוכה מדי (מקסימום {MAX_ADDRESS_LENGTH} תווים)")

    city = (data.get("city") or "").strip()
    if not city and address:
        parts = [p.strip() for p in address.split(",") if p.strip()]
        if len(parts) > 1:
            city = parts[-1]
        else:
            city = parts[0]
        if len(city) > MAX_CITY_LENGTH:
            city = city[:MAX_CITY_LENGTH]
    elif len(city) > MAX_CITY_LENGTH:
        raise ValueError(f"שם העיר ארוך מדי (מקסימום {MAX_CITY_LENGTH} תווים)")

    lat = float(data["lat"])
    lng = float(data["lng"])
    provider = (data.get("provider") or "ידני").strip() or "ידני"
    if len(provider) > MAX_PROVIDER_LENGTH:
        raise ValueError(f"שם המפעיל ארוך מדי (מקסימום {MAX_PROVIDER_LENGTH} תווים)")

    max_per_kwh = data.get("price")
    if max_per_kwh is not None:
        try:
            max_per_kwh = float(max_per_kwh)
        except (ValueError, TypeError):
            max_per_kwh = None
    has_tariffs = 1 if max_per_kwh is not None else 0

    connectors = data.get("connectors", [])
    if isinstance(connectors, str):
        connectors_json = connectors
    else:
        connectors_json = json.dumps(connectors, ensure_ascii=False)

    stations_count = len(connectors) if isinstance(connectors, list) and connectors else 1
    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    sql = """
        INSERT INTO locations (
            cello_id, name, address, city, lat, lng,
            provider_id, provider_name, max_per_kwh, has_tariffs,
            payment_options, facilities, status_summary, connectors,
            stations_count, updated_at, sources, is_gov_official
        ) VALUES (
            :cello_id, :name, :address, :city, :lat, :lng,
            :provider_id, :provider_name, :max_per_kwh, :has_tariffs,
            :payment_options, :facilities, :status_summary, :connectors,
            :stations_count, :updated_at, :sources, :is_gov_official
        )
    """
    params = {
        "cello_id": cello_id,
        "name": name,
        "address": address,
        "city": city,
        "lat": lat,
        "lng": lng,
        "provider_id": provider,
        "provider_name": provider,
        "max_per_kwh": max_per_kwh,
        "has_tariffs": has_tariffs,
        "payment_options": '["CREDIT_CARD", "APP"]',
        "facilities": '[]',
        "status_summary": f'{{"AVAILABLE": {stations_count}}}',
        "connectors": connectors_json,
        "stations_count": stations_count,
        "updated_at": updated_at,
        "sources": "manual",
        "is_gov_official": 0,
    }
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


async def insert_manual_station(db_path: str, data: dict) -> int:
    """הכנסת עמדה חדשה לטבלת locations באופן א-סינכרוני."""
    return await asyncio.to_thread(_insert_manual_station_sync, db_path, data)


def reset_admin_wizard_state(chat_id: int) -> None:
    """איפוס מצב ה-wizard עבור הצ'אט."""
    session = get_session(chat_id)
    session.admin_add_state = None
    session.admin_add_data = {}


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

    @client.on(events.NewMessage(pattern=r'^/(adminpanel|admin|stats)(\s|$)'))
    async def handle_admin_command(event: events.NewMessage.Event) -> None:
        sender_id = event.sender_id or event.chat_id
        if not is_admin(sender_id):
            logger.warning("Unauthorized access attempt to admin command from sender_id=%s", sender_id)
            return

        chat_id = event.chat_id
        reset_admin_wizard_state(chat_id)

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

    @client.on(events.CallbackQuery(pattern=rb"^admin:"))
    async def handle_admin_callback(event: events.CallbackQuery.Event) -> None:
        sender_id = event.sender_id or event.chat_id
        if not is_admin(sender_id):
            logger.warning("Unauthorized callback attempt to admin from sender_id=%s", sender_id)
            return

        chat_id = event.chat_id
        data = event.data

        if data == b"admin:refresh":
            reset_admin_wizard_state(chat_id)
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

        elif data == b"admin:add_station":
            session = get_session(chat_id)
            session.admin_add_state = "name"
            session.admin_add_data = {}
            await event.answer()
            await event.respond(
                "➕ <b>הוספת עמדת טעינה חדשה למאגר (1/6)</b>\n\n"
                "אנא הזן את <b>שם העמדה</b> (לדוגמה: <i>קניון עזריאלי תל אביב</i>):",
                buttons=admin_wizard_cancel_keyboard(),
                parse_mode="html",
            )

        elif data == b"admin:add_confirm":
            session = get_session(chat_id)
            if session.admin_add_state != "confirm" or not session.admin_add_data:
                await event.answer("הפעולה אינה בתוקף.", alert=True)
                return

            try:
                row_id = await insert_manual_station(settings.db_path, session.admin_add_data)
                name = session.admin_add_data.get("name", "")
                reset_admin_wizard_state(chat_id)
                await event.answer("העמדה נשמרה בהצלחה! ✅")
                await event.edit(
                    f"✅ <b>העמדה \"{html.escape(name)}\" נוספה בהצלחה למאגר!</b> 🎉\n\n"
                    f"🔢 מזהה במאגר: <code>{row_id}</code>\n"
                    "העמדה זמינה כעת בחיפוש ובמפת העמדות.",
                    buttons=admin_keyboard(),
                    parse_mode="html",
                )
            except ValueError as e:
                logger.warning("Validation error saving new manual station for sender_id=%s: %s", sender_id, e)
                await event.answer(f"❌ {e}", alert=True)
            except Exception:
                logger.exception("Error saving new manual station for sender_id=%s", sender_id)
                await event.answer("❌ אירעה שגיאה בעת שמירת העמדה במאגר.", alert=True)

        elif data == b"admin:add_cancel":
            reset_admin_wizard_state(chat_id)
            await event.answer("ההוספה בוטלה")
            await event.edit(
                "❌ <b>הוספת העמדה בוטלה.</b>",
                buttons=admin_keyboard(),
                parse_mode="html",
            )

    @client.on(events.NewMessage())
    async def handle_admin_wizard_messages(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        session = get_session(chat_id)
        if getattr(session, "admin_add_state", None) is None:
            return

        sender_id = event.sender_id or chat_id
        if not is_admin(sender_id):
            return

        raw_text = (event.text or "").strip()

        # Handle cancel command or text
        if raw_text.startswith("/cancel") or re.match(r"^(?:❌\s*)?ביטול$", raw_text):
            reset_admin_wizard_state(chat_id)
            await event.respond("❌ <b>הוספת העמדה בוטלה.</b>", buttons=Button.clear(), parse_mode="html")
            return

        # If admin types /adminpanel, /admin or /stats, let handle_admin_command take care of it
        if re.match(r"^/(adminpanel|admin|stats)(\s|$)", raw_text):
            return

        state = session.admin_add_state

        if state == "name":
            if not raw_text:
                await event.respond("❌ אנא הזן שם עמדה תקין:", buttons=admin_wizard_cancel_keyboard(), parse_mode="html")
                return
            if len(raw_text) > MAX_NAME_LENGTH:
                await event.respond(
                    f"❌ <b>השם ארוך מדי</b> (מקסימום {MAX_NAME_LENGTH} תווים).\n"
                    "אנא הזן שם קצר יותר:",
                    buttons=admin_wizard_cancel_keyboard(),
                    parse_mode="html",
                )
                return
            session.admin_add_data["name"] = raw_text
            session.admin_add_state = "address"
            await event.respond(
                "📍 <b>הוספת עמדת טעינה (2/6)</b>\n\n"
                "אנא הזן <b>כתובת או עיר</b> (לדוגמה: <i>מנחם בגין 132, תל אביב</i>):",
                buttons=admin_wizard_cancel_keyboard(),
                parse_mode="html",
            )

        elif state == "address":
            if not raw_text:
                await event.respond("❌ אנא הזן כתובת תקינה:", buttons=admin_wizard_cancel_keyboard(), parse_mode="html")
                return
            if len(raw_text) > MAX_ADDRESS_LENGTH:
                await event.respond(
                    f"❌ <b>הכתובת ארוכה מדי</b> (מקסימום {MAX_ADDRESS_LENGTH} תווים).\n"
                    "אנא הזן כתובת קצרה יותר:",
                    buttons=admin_wizard_cancel_keyboard(),
                    parse_mode="html",
                )
                return
            session.admin_add_data["address"] = raw_text
            session.admin_add_state = "coords"
            await event.respond(
                "🌐 <b>הוספת עמדת טעינה (3/6)</b>\n\n"
                "אנא שלח <b>קואורדינטות (lat, lng)</b> או שתף מיקום GPS 📍:\n"
                "(לדוגמה: <code>32.0745, 34.7915</code>)",
                buttons=admin_location_keyboard(),
                parse_mode="html",
            )

        elif state == "coords":
            lat: Optional[float] = None
            lng: Optional[float] = None

            if bool(event.geo):
                lat = float(event.geo.lat)
                lng = float(event.geo.long)
            else:
                coords = parse_admin_coordinates(raw_text)
                if coords is not None:
                    lat, lng = coords

            if lat is None or lng is None:
                await event.respond(
                    "❌ <b>לא זוהו קואורדינטות תקינות.</b>\n"
                    "אנא שלח קואורדינטות בפורמט <code>32.0745, 34.7915</code> או שתף מיקום GPS:",
                    buttons=admin_location_keyboard(),
                    parse_mode="html",
                )
                return

            if not is_valid_israel_coord(lat, lng):
                await event.respond(
                    f"❌ <b>הקואורדינטות ({lat:.4f}, {lng:.4f}) מחוץ לגבולות ישראל.</b>\n"
                    "הטווח המותר: קו רוחב 29–34, קו אורך 34–36.\n"
                    "אנא נסה שוב או שתף מיקום GPS:",
                    buttons=admin_location_keyboard(),
                    parse_mode="html",
                )
                return

            session.admin_add_data["lat"] = lat
            session.admin_add_data["lng"] = lng
            session.admin_add_state = "provider"
            await event.respond(
                "🏭 <b>הוספת עמדת טעינה (4/6)</b>\n\n"
                "אנא הזן את <b>שם המפעיל</b> (לדוגמה: <i>EV-Edge, Sonol EVI, Afcon, Tesla, Paz Charge</i>):",
                buttons=Button.clear(),
                parse_mode="html",
            )

        elif state == "provider":
            if not raw_text:
                await event.respond("❌ אנא הזן שם מפעיל:", buttons=admin_wizard_cancel_keyboard(), parse_mode="html")
                return
            if len(raw_text) > MAX_PROVIDER_LENGTH:
                await event.respond(
                    f"❌ <b>שם המפעיל ארוך מדי</b> (מקסימום {MAX_PROVIDER_LENGTH} תווים).\n"
                    "אנא הזן שם מפעיל קצר יותר:",
                    buttons=admin_wizard_cancel_keyboard(),
                    parse_mode="html",
                )
                return
            session.admin_add_data["provider"] = raw_text
            session.admin_add_state = "connectors"
            await event.respond(
                "🔌 <b>הוספת עמדת טעינה (5/6)</b>\n\n"
                "אנא הזן <b>סוגי מחברים והספקים</b> (אופציונלי):\n"
                "לדוגמה: <code>CCS2 150kW, Type2 22kW</code>\n"
                "או שלח <code>-</code> / <code>דלג</code> להמשך ללא פירוט מחברים:",
                buttons=admin_wizard_cancel_keyboard(),
                parse_mode="html",
            )

        elif state == "connectors":
            if len(raw_text) > MAX_CONNECTORS_LENGTH:
                await event.respond(
                    f"❌ <b>פירוט המחברים ארוך מדי</b> (מקסימום {MAX_CONNECTORS_LENGTH} תווים).\n"
                    "אנא הזן פירוט קצר יותר או שלח <code>-</code> / <code>דלג</code>:",
                    buttons=admin_wizard_cancel_keyboard(),
                    parse_mode="html",
                )
                return
            try:
                connectors = parse_connectors_input(raw_text)
            except ValueError as e:
                await event.respond(
                    f"❌ <b>{html.escape(str(e))}</b>\nאנא נסה שוב:",
                    buttons=admin_wizard_cancel_keyboard(),
                    parse_mode="html",
                )
                return
            session.admin_add_data["connectors"] = connectors
            session.admin_add_state = "price"
            await event.respond(
                "💰 <b>הוספת עמדת טעינה (6/6)</b>\n\n"
                "אנא הזן <b>מחיר לקוט\"ש</b> בש\"ח (אופציונלי):\n"
                "לדוגמה: <code>1.85</code> או שלח <code>-</code> / <code>דלג</code>:",
                buttons=admin_wizard_cancel_keyboard(),
                parse_mode="html",
            )

        elif state == "price":
            price = parse_price_input(raw_text)
            session.admin_add_data["price"] = price
            session.admin_add_state = "confirm"
            summary_text = format_admin_station_summary(session.admin_add_data)
            await event.respond(
                summary_text,
                buttons=admin_confirm_keyboard(),
                parse_mode="html",
            )

        elif state == "confirm":
            await event.respond(
                "אנא לחץ על כפתור <b>✅ אישור ושמירה במאגר</b> לסיום, או על <b>❌ ביטול</b>:",
                buttons=admin_confirm_keyboard(),
                parse_mode="html",
            )
