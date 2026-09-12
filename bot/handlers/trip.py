import html
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import MessageNotModifiedError
from telethon.tl.custom import Button

from bot.config import settings
from bot.handlers.location import ERROR_GENERIC, LOCATION_PROMPT_MESSAGE, send_map_image
from bot.keyboards.inline import (
    trip_battery_choice_keyboard,
    trip_geocode_selection_keyboard,
    trip_myplans_keyboard,
    trip_plan_keyboard,
    welcome_keyboard,
)
from bot.keyboards.reply import location_request_keyboard
from bot.services.formatter import format_trip_plan
from bot.services.geocoder import geocode, parse_coordinates
from bot.services.station_search import is_in_israel
from bot.services.trip_planner import (
    TRIP_CONSUMPTION_KWH_PER_100KM,
    TRIP_DEFAULT_REAL_RANGE_KM,
    TRIP_DEFAULT_SAFETY_MARGIN_PERCENT,
    plan_trip,
)
from bot.states import get_session
from bot.storage.users_db import get_recent_trip_plans, get_trip_plan, get_user_settings, save_trip_plan

logger = logging.getLogger(__name__)

TRIP_ASK_DESTINATION_MESSAGE = (
    "🚗 <b>מצב נסיעה</b>\n\n"
    "לאן נוסעים? שלח עיר, כתובת או קואורדינטות "
    "(לדוגמה: <i>אילת</i> או <code>29.557, 34.952</code>).\n\n"
    "לביטול - שלח \"ביטול\"."
)
TRIP_ASK_ORIGIN_MESSAGE = (
    "📍 מאיפה יוצאים לדרך?\n\n"
    "שתף מיקום נוכחי בכפתור למטה, או שלח עיר/כתובת/קואורדינטות.\n\n"
    "לביטול - שלח \"ביטול\"."
)
TRIP_MISSING_CITY_MESSAGE = (
    '📍 כדי למצוא מיקום מדויק, כתבו רחוב או שכונה וגם עיר, מופרדים בפסיק.\n'
    'לדוגמה: <i>הרצל 7, חיפה</i> או <i>ביאליק, תל אביב</i>\n\n'
    'אפשר גם לשלוח קואורדינטות GPS (למשל: <code>32.0853, 34.7818</code>).'
)
TRIP_NO_GEOCODE_RESULTS = (
    '❌ <b>לא מצאנו את המיקום "<i>{query}</i>"</b>\n\n'
    "נסו לנסח מחדש, או שלחו קואורדינטות GPS."
)
TRIP_GEOCODE_CHOICE_MESSAGE = (
    '📍 <b>נמצאו מספר מיקומים עבור "<i>{query}</i>":</b>\n'
    'בחר את המיקום הרצוי:'
)
TRIP_PLANNING_MESSAGE = "🧭 מתכנן את מסלול הנסיעה ובוחר עמדות טעינה לאורך הדרך..."
TRIP_ERROR_OUTSIDE_ISRAEL = "❌ מוצא ו/או יעד הנסיעה נמצאים מחוץ לישראל. המאגר מכיל עמדות בארץ בלבד."
TRIP_MAP_CAPTION = (
    "🗺️ מפת המסלול: מוצא הנסיעה מסומן באדום 🔴. "
    "עמדות הטעינה שנבחרו לאורך הדרך מסומנות בירוק ⚡."
)
TRIP_SETTINGS_HINT_MESSAGE = "💡 אפשר להתאים את פרמטרי הרכב ואת העדפות הטעינה שלך לפני התכנון."
TRIP_ASK_BATTERY_MESSAGE = (
    "🔋 מה אחוז הסוללה הנוכחי שלך?\n\n"
    "שלח מספר בין 1 ל-100.\n\n"
    "לביטול - שלח \"ביטול\"."
)
TRIP_BATTERY_CHOICE_MESSAGE = "🔋 באיזה אחוז סוללה יוצאים לדרך?"
TRIP_INVALID_BATTERY_MESSAGE = "❌ יש להזין מספר בין 1 ל-100 (אחוזי סוללה)."
TRIP_LOW_BATTERY_MESSAGE = (
    "❌ אחוז הסוללה שהזנת נמוך מדי ביחס למרווח הביטחון שהוגדר ({margin:.0f}%). "
    "טענו קצת לפני היציאה ונסו שוב עם /trip."
)
TRIP_NO_SAVED_PLANS_MESSAGE = (
    "🕘 עדיין אין לך תוכניות נסיעה שמורות.\n\n"
    "תכננו נסיעה ראשונה עם /trip!"
)
TRIP_PLANS_LIST_MESSAGE = "🕘 <b>התוכניות האחרונות שלך:</b>\n\nבחר תוכנית כדי לפתוח אותה שוב:"
TRIP_PLAN_NOT_FOUND_MESSAGE = "❌ התוכנית המבוקשת לא נמצאה (יתכן שנמחקה)."

TRIP_START_KEYBOARD = [
    [Button.inline("⚙️ הגדרות נסיעה", data=b"settings:trip")],
    [Button.inline("🕘 התוכניות שלי", data=b"trip:myplans")],
]


def _reset_trip_state(session) -> None:
    session.trip_state = None
    session.trip_destination = None
    session.trip_origin = None
    session.trip_geocode_candidates = []


async def _show_trip_step(event, chat_id: int, session, text: str, buttons=None) -> None:
    """מציג שלב בזרימת מצב הנסיעה - עורך את הודעת הזרימה הקיימת של המשתמש (session.trip_message_id)
    במקום לשלוח הודעה חדשה, כדי שהצ'אט לא יתמלא בהודעות על כל שלב.

    אם אין עדיין הודעת זרימה, או שהעריכה נכשלת (ההודעה נמחקה/ישנה מדי מכדי לערוך) - נופלים
    לשליחת הודעה חדשה ושומרים את המזהה שלה להמשך הזרימה.
    """
    if session.trip_message_id is not None:
        try:
            await event.client.edit_message(chat_id, session.trip_message_id, text, buttons=buttons, parse_mode="html")
            return
        except MessageNotModifiedError:
            return
        except Exception:
            pass
    msg = await event.respond(text, buttons=buttons, parse_mode="html")
    session.trip_message_id = msg.id


async def _clear_location_reply_keyboard(event, chat_id: int, session) -> None:
    """מסיר את מקלדת התשובה (ReplyKeyboardMarkup) של בקשת מיקום GPS.

    טלגרם לא מאפשרת לצרף/להסיר reply keyboard בעריכת הודעה קיימת - רק sendMessage חדש
    יכול לעשות זאת. שולחים הודעה זניחה עם Button.clear() ומוחקים אותה מיד; הסרת המקלדת
    כבר חלה אצל הלקוח גם אם ההודעה שנשאה אותה נעלמת.
    """
    if not session.trip_reply_keyboard_active:
        return
    session.trip_reply_keyboard_active = False
    try:
        msg = await event.respond("⏳", buttons=Button.clear())
        await msg.delete()
    except Exception:
        pass


async def _start_trip_flow(event, chat_id: int) -> None:
    session = get_session(chat_id)
    _reset_trip_state(session)
    session.trip_state = "awaiting_destination"
    text = f"{TRIP_ASK_DESTINATION_MESSAGE}\n\n{TRIP_SETTINGS_HINT_MESSAGE}"
    await _show_trip_step(event, chat_id, session, text, buttons=TRIP_START_KEYBOARD)


async def _finalize_trip(
    event, chat_id: int, origin_lat: float, origin_lng: float, origin_name: Optional[str], battery_percent: float
) -> None:
    session = get_session(chat_id)
    destination = session.trip_destination
    _reset_trip_state(session)

    if destination is None:
        await _show_trip_step(event, chat_id, session, ERROR_GENERIC)
        return

    dest_lat, dest_lng = destination["lat"], destination["lng"]
    dest_name = destination.get("name") or f"{dest_lat:.4f}, {dest_lng:.4f}"
    origin_name = origin_name or f"{origin_lat:.4f}, {origin_lng:.4f}"

    if not is_in_israel(origin_lat, origin_lng) or not is_in_israel(dest_lat, dest_lng):
        await _show_trip_step(event, chat_id, session, TRIP_ERROR_OUTSIDE_ISRAEL)
        return

    user_settings = await get_user_settings(chat_id, settings.users_db_path)
    real_range_km = user_settings.trip_real_range_km or TRIP_DEFAULT_REAL_RANGE_KM
    safety_margin_percent = user_settings.trip_safety_margin_percent or TRIP_DEFAULT_SAFETY_MARGIN_PERCENT
    consumption_kwh_per_100km = user_settings.trip_consumption_kwh_100km or TRIP_CONSUMPTION_KWH_PER_100KM

    if battery_percent <= safety_margin_percent:
        await _show_trip_step(event, chat_id, session, TRIP_LOW_BATTERY_MESSAGE.format(margin=safety_margin_percent))
        return

    await _show_trip_step(event, chat_id, session, TRIP_PLANNING_MESSAGE)
    try:
        plan = await plan_trip(
            origin_lat, origin_lng, dest_lat, dest_lng, settings.db_path,
            real_range_km=real_range_km,
            battery_percent=battery_percent,
            safety_margin_percent=safety_margin_percent,
            consumption_kwh_per_100km=consumption_kwh_per_100km,
            min_power_kw=user_settings.trip_min_power_kw,
            max_price=user_settings.trip_max_price,
            allowed_providers=user_settings.trip_allowed_providers or None,
        )
        text = format_trip_plan(plan, origin_name, dest_name)

        if plan["stops"]:
            buttons = trip_plan_keyboard(plan["stops"])
        else:
            buttons = welcome_keyboard(is_private=event.is_private)

        if plan["stops"]:
            stop_stations = [stop["station"] for stop in plan["stops"]]
            map_radius_km = max(1, round(plan["total_distance_km"]))
            await send_map_image(
                event,
                origin_lat,
                origin_lng,
                map_radius_km,
                stop_stations,
                map_format=user_settings.map_format,
                caption=TRIP_MAP_CAPTION,
            )

        await _show_trip_step(event, chat_id, session, text, buttons=buttons)

        try:
            await save_trip_plan(
                chat_id,
                origin={"lat": origin_lat, "lng": origin_lng, "name": origin_name},
                destination={"lat": dest_lat, "lng": dest_lng, "name": dest_name},
                battery_percent=battery_percent,
                plan=plan,
                db_path=settings.users_db_path,
            )
        except Exception:
            logger.exception("failed to save trip plan for chat_id=%s", chat_id)
    except Exception:
        logger.exception("error planning trip for chat_id=%s", chat_id)
        await _show_trip_step(event, chat_id, session, ERROR_GENERIC)


async def _origin_resolved(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    """נקרא ברגע שמקור הנסיעה ידוע - שואל אחוז סוללה (או מציע את ברירת המחדל השמורה)."""
    session = get_session(chat_id)
    session.trip_origin = {"lat": lat, "lng": lng, "name": name}
    await _clear_location_reply_keyboard(event, chat_id, session)

    user_settings = await get_user_settings(chat_id, settings.users_db_path)
    default_battery = user_settings.trip_battery_percent
    if default_battery is not None:
        session.trip_state = "awaiting_battery_choice"
        await _show_trip_step(
            event, chat_id, session, TRIP_BATTERY_CHOICE_MESSAGE, buttons=trip_battery_choice_keyboard(default_battery)
        )
    else:
        session.trip_state = "awaiting_battery_input"
        await _show_trip_step(event, chat_id, session, TRIP_ASK_BATTERY_MESSAGE)


async def _set_trip_destination(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    session = get_session(chat_id)
    session.trip_destination = {"lat": lat, "lng": lng, "name": name}
    session.trip_geocode_candidates = []

    if session.user_lat is not None and session.user_lng is not None:
        await _origin_resolved(event, chat_id, session.user_lat, session.user_lng, session.location_name)
    else:
        session.trip_state = "awaiting_origin"
        # Telegram אינה מאפשרת לצרף ReplyKeyboardMarkup (בקשת מיקום GPS) בעריכת הודעה -
        # זו החריגה היחידה בזרימה שחייבת הודעה חדשה.
        msg = await event.respond(TRIP_ASK_ORIGIN_MESSAGE, buttons=location_request_keyboard(), parse_mode="html")
        session.trip_message_id = msg.id
        session.trip_reply_keyboard_active = True


def _is_trip_destination_text(e: events.NewMessage.Event) -> bool:
    if bool(e.geo):
        return False
    text = (e.text or "").strip()
    if not text or text.startswith("/"):
        return False
    if text in ("❌ ביטול", "ביטול"):
        return False
    return get_session(e.chat_id).trip_state == "awaiting_destination"


def _is_trip_origin_text(e: events.NewMessage.Event) -> bool:
    if bool(e.geo):
        return False
    text = (e.text or "").strip()
    if not text or text.startswith("/"):
        return False
    if text in ("❌ ביטול", "ביטול"):
        return False
    return get_session(e.chat_id).trip_state == "awaiting_origin"


def _is_trip_origin_location(e: events.NewMessage.Event) -> bool:
    return bool(e.geo) and get_session(e.chat_id).trip_state == "awaiting_origin"


def _is_trip_battery_text(e: events.NewMessage.Event) -> bool:
    if bool(e.geo):
        return False
    text = (e.text or "").strip()
    if not text or text.startswith("/"):
        return False
    if text in ("❌ ביטול", "ביטול"):
        return False
    return get_session(e.chat_id).trip_state == "awaiting_battery_input"


async def _handle_free_text_location(
    event: events.NewMessage.Event,
    raw_text: str,
    on_resolved,
) -> None:
    """לוגיקה משותפת לפענוח טקסט חופשי (יעד/מוצא) לקואורדינטות, כולל בחירה מרובה."""
    chat_id = event.chat_id
    session = get_session(chat_id)

    coords = parse_coordinates(raw_text)
    if coords is not None:
        lat, lng = coords
        await on_resolved(event, chat_id, lat, lng, f"{lat:.4f}, {lng:.4f}")
        return

    if "," not in raw_text:
        await _show_trip_step(event, chat_id, session, TRIP_MISSING_CITY_MESSAGE)
        return

    candidates = await geocode(raw_text)
    if not candidates:
        await _show_trip_step(event, chat_id, session, TRIP_NO_GEOCODE_RESULTS.format(query=html.escape(raw_text)))
        return

    if len(candidates) == 1:
        chosen = candidates[0]
        await on_resolved(event, chat_id, chosen["lat"], chosen["lng"], chosen["name"])
        return

    session.trip_geocode_candidates = candidates
    await _show_trip_step(
        event, chat_id, session,
        TRIP_GEOCODE_CHOICE_MESSAGE.format(query=html.escape(raw_text)),
        buttons=trip_geocode_selection_keyboard(candidates),
    )


async def _show_trip_plans_list(event, chat_id: int) -> None:
    session = get_session(chat_id)
    plans = await get_recent_trip_plans(chat_id, settings.users_db_path, limit=5)
    if not plans:
        await _show_trip_step(
            event, chat_id, session, TRIP_NO_SAVED_PLANS_MESSAGE,
            buttons=[[Button.inline("🚗 תכנון נסיעה חדשה", data=b"trip:new")]],
        )
        return
    await _show_trip_step(event, chat_id, session, TRIP_PLANS_LIST_MESSAGE, buttons=trip_myplans_keyboard(plans))


async def _show_saved_trip_plan(event, chat_id: int, plan_id: int) -> None:
    session = get_session(chat_id)
    row = await get_trip_plan(plan_id, chat_id, settings.users_db_path)
    if row is None:
        await _show_trip_step(
            event, chat_id, session, TRIP_PLAN_NOT_FOUND_MESSAGE,
            buttons=[[Button.inline("🕘 התוכניות שלי", data=b"trip:myplans")]],
        )
        return

    plan = row["plan"]
    origin_name = row.get("origin_name") or f"{row['origin_lat']:.4f}, {row['origin_lng']:.4f}"
    destination_name = row.get("destination_name") or f"{row['destination_lat']:.4f}, {row['destination_lng']:.4f}"
    text = format_trip_plan(plan, origin_name, destination_name)

    stops = plan.get("stops") or []
    if stops:
        buttons = trip_plan_keyboard(stops)
        stop_stations = [stop["station"] for stop in stops]
        map_radius_km = max(1, round(plan.get("total_distance_km") or 1))
        user_settings = await get_user_settings(chat_id, settings.users_db_path)
        await send_map_image(
            event, row["origin_lat"], row["origin_lng"], map_radius_km, stop_stations,
            map_format=user_settings.map_format,
            caption=TRIP_MAP_CAPTION,
        )
    else:
        buttons = [[Button.inline("🕘 התוכניות שלי", data=b"trip:myplans")]]

    await _show_trip_step(event, chat_id, session, text, buttons=buttons)


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(pattern=r"^/trip"))
    async def handle_trip_command(event: events.NewMessage.Event) -> None:
        await _start_trip_flow(event, event.chat_id)

    @client.on(events.NewMessage(func=_is_trip_destination_text))
    async def handle_trip_destination_text(event: events.NewMessage.Event) -> None:
        raw_text = event.text.strip()
        try:
            await event.delete()
        except Exception:
            pass
        try:
            await _handle_free_text_location(event, raw_text, _set_trip_destination)
        except Exception:
            logger.exception("error handling trip destination text for chat_id=%s", event.chat_id)
            await _show_trip_step(event, event.chat_id, get_session(event.chat_id), ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_origin_text))
    async def handle_trip_origin_text(event: events.NewMessage.Event) -> None:
        raw_text = event.text.strip()
        try:
            await event.delete()
        except Exception:
            pass
        try:
            await _handle_free_text_location(event, raw_text, _origin_resolved)
        except Exception:
            logger.exception("error handling trip origin text for chat_id=%s", event.chat_id)
            await _show_trip_step(event, event.chat_id, get_session(event.chat_id), ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_origin_location))
    async def handle_trip_origin_location(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        try:
            await event.delete()
        except Exception:
            pass
        try:
            await _origin_resolved(event, chat_id, event.geo.lat, event.geo.long, None)
        except Exception:
            logger.exception("error handling trip origin location for chat_id=%s", chat_id)
            await _show_trip_step(event, chat_id, get_session(chat_id), ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_battery_text))
    async def handle_trip_battery_text(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        raw = event.text.strip().replace("%", "").replace(",", ".")
        try:
            await event.delete()
        except Exception:
            pass

        session = get_session(chat_id)
        try:
            percent = float(raw)
        except ValueError:
            await _show_trip_step(event, chat_id, session, TRIP_INVALID_BATTERY_MESSAGE)
            return
        if not (1.0 <= percent <= 100.0):
            await _show_trip_step(event, chat_id, session, TRIP_INVALID_BATTERY_MESSAGE)
            return

        origin = session.trip_origin
        if origin is None:
            session.trip_state = None
            await _show_trip_step(event, chat_id, session, ERROR_GENERIC)
            return
        session.trip_state = None
        try:
            await _finalize_trip(event, chat_id, origin["lat"], origin["lng"], origin.get("name"), percent)
        except Exception:
            logger.exception("error finalizing trip after battery input for chat_id=%s", chat_id)
            await _show_trip_step(event, chat_id, session, ERROR_GENERIC)

    @client.on(events.CallbackQuery(pattern=rb"^tripbatt:"))
    async def handle_trip_battery_choice(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        session = get_session(chat_id)
        data = event.data.decode("utf-8")
        try:
            if session.trip_state != "awaiting_battery_choice" or session.trip_origin is None:
                await event.answer(ERROR_GENERIC, alert=True)
                return

            if data == "tripbatt:default":
                user_settings = await get_user_settings(chat_id, settings.users_db_path)
                battery_percent = user_settings.trip_battery_percent
                if battery_percent is None:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                origin = session.trip_origin
                session.trip_state = None
                await event.answer()
                await _finalize_trip(event, chat_id, origin["lat"], origin["lng"], origin.get("name"), battery_percent)
            elif data == "tripbatt:custom":
                session.trip_state = "awaiting_battery_input"
                await event.answer()
                await _show_trip_step(event, chat_id, session, TRIP_ASK_BATTERY_MESSAGE)
            else:
                await event.answer(ERROR_GENERIC, alert=True)
        except Exception:
            logger.exception("error handling trip battery choice for chat_id=%s", chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^tripgeo:"))
    async def handle_trip_geo_selection(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        try:
            parts = data.split(":")
            if len(parts) < 4:
                raise ValueError(f"malformed tripgeo callback data: {data!r}")
            idx = int(parts[1])
            lat = float(parts[2])
            lng = float(parts[3])

            if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                await event.answer(ERROR_GENERIC, alert=True)
                return

            session = get_session(chat_id)
            name = None
            if session.trip_geocode_candidates and 0 <= idx < len(session.trip_geocode_candidates):
                name = session.trip_geocode_candidates[idx].get("name")

            await event.answer()

            if session.trip_state == "awaiting_destination":
                await _set_trip_destination(event, chat_id, lat, lng, name)
            elif session.trip_state == "awaiting_origin":
                await _origin_resolved(event, chat_id, lat, lng, name)
            else:
                await _show_trip_step(event, chat_id, session, LOCATION_PROMPT_MESSAGE)
        except Exception:
            logger.exception("error handling trip geo selection for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^trip:"))
    async def handle_trip_menu(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        try:
            if data == "trip:new":
                await event.answer()
                await _start_trip_flow(event, chat_id)
            elif data == "trip:myplans":
                await event.answer()
                await _show_trip_plans_list(event, chat_id)
            elif data.startswith("trip:plan:"):
                try:
                    plan_id = int(data.split(":", 2)[2])
                except (ValueError, IndexError):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await event.answer()
                await _show_saved_trip_plan(event, chat_id, plan_id)
            else:
                await event.answer(ERROR_GENERIC, alert=True)
        except Exception:
            logger.exception("error handling trip menu callback for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)
