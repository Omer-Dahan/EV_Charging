import html
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from bot.config import settings
from bot.handlers.location import ERROR_GENERIC, LOCATION_PROMPT_MESSAGE, send_map_image
from bot.keyboards.inline import (
    trip_battery_choice_keyboard,
    trip_geocode_selection_keyboard,
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
from bot.storage.users_db import get_user_settings

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


def _reset_trip_state(session) -> None:
    session.trip_state = None
    session.trip_destination = None
    session.trip_origin = None
    session.trip_geocode_candidates = []


async def _finalize_trip(
    event, chat_id: int, origin_lat: float, origin_lng: float, origin_name: Optional[str], battery_percent: float
) -> None:
    session = get_session(chat_id)
    destination = session.trip_destination
    _reset_trip_state(session)

    if destination is None:
        await event.respond(ERROR_GENERIC)
        return

    dest_lat, dest_lng = destination["lat"], destination["lng"]
    dest_name = destination.get("name") or f"{dest_lat:.4f}, {dest_lng:.4f}"
    origin_name = origin_name or f"{origin_lat:.4f}, {origin_lng:.4f}"

    if not is_in_israel(origin_lat, origin_lng) or not is_in_israel(dest_lat, dest_lng):
        await event.respond(TRIP_ERROR_OUTSIDE_ISRAEL, buttons=Button.clear())
        return

    user_settings = await get_user_settings(chat_id, settings.users_db_path)
    real_range_km = user_settings.trip_real_range_km or TRIP_DEFAULT_REAL_RANGE_KM
    safety_margin_percent = user_settings.trip_safety_margin_percent or TRIP_DEFAULT_SAFETY_MARGIN_PERCENT
    consumption_kwh_per_100km = user_settings.trip_consumption_kwh_100km or TRIP_CONSUMPTION_KWH_PER_100KM

    if battery_percent <= safety_margin_percent:
        await event.respond(
            TRIP_LOW_BATTERY_MESSAGE.format(margin=safety_margin_percent),
            buttons=Button.clear(),
            parse_mode="html",
        )
        return

    planning_msg = await event.respond(TRIP_PLANNING_MESSAGE, buttons=Button.clear())
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

        await event.respond(text, buttons=buttons, parse_mode="html")
    except Exception:
        logger.exception("error planning trip for chat_id=%s", chat_id)
        await event.respond(ERROR_GENERIC)
    finally:
        try:
            await planning_msg.delete()
        except Exception:
            pass


async def _origin_resolved(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    """נקרא ברגע שמקור הנסיעה ידוע - שואל אחוז סוללה (או מציע את ברירת המחדל השמורה)."""
    session = get_session(chat_id)
    session.trip_origin = {"lat": lat, "lng": lng, "name": name}

    user_settings = await get_user_settings(chat_id, settings.users_db_path)
    default_battery = user_settings.trip_battery_percent
    if default_battery is not None:
        session.trip_state = "awaiting_battery_choice"
        await event.respond(
            TRIP_BATTERY_CHOICE_MESSAGE,
            buttons=trip_battery_choice_keyboard(default_battery),
            parse_mode="html",
        )
    else:
        session.trip_state = "awaiting_battery_input"
        await event.respond(TRIP_ASK_BATTERY_MESSAGE, buttons=Button.clear(), parse_mode="html")


async def _set_trip_destination(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    session = get_session(chat_id)
    session.trip_destination = {"lat": lat, "lng": lng, "name": name}
    session.trip_geocode_candidates = []

    if session.user_lat is not None and session.user_lng is not None:
        await _origin_resolved(event, chat_id, session.user_lat, session.user_lng, session.location_name)
    else:
        session.trip_state = "awaiting_origin"
        await event.respond(TRIP_ASK_ORIGIN_MESSAGE, buttons=location_request_keyboard(), parse_mode="html")


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
        await event.respond(TRIP_MISSING_CITY_MESSAGE, parse_mode="html")
        return

    candidates = await geocode(raw_text)
    if not candidates:
        await event.respond(TRIP_NO_GEOCODE_RESULTS.format(query=html.escape(raw_text)), parse_mode="html")
        return

    if len(candidates) == 1:
        chosen = candidates[0]
        await on_resolved(event, chat_id, chosen["lat"], chosen["lng"], chosen["name"])
        return

    session.trip_geocode_candidates = candidates
    await event.respond(
        TRIP_GEOCODE_CHOICE_MESSAGE.format(query=html.escape(raw_text)),
        buttons=trip_geocode_selection_keyboard(candidates),
        parse_mode="html",
    )


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(pattern=r"^/trip"))
    async def handle_trip_command(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        session = get_session(chat_id)
        _reset_trip_state(session)
        session.trip_state = "awaiting_destination"
        await event.respond(TRIP_ASK_DESTINATION_MESSAGE, buttons=Button.clear(), parse_mode="html")
        await event.respond(
            TRIP_SETTINGS_HINT_MESSAGE,
            buttons=[[Button.inline("⚙️ הגדרות נסיעה", data=b"settings:trip")]],
        )

    @client.on(events.NewMessage(func=_is_trip_destination_text))
    async def handle_trip_destination_text(event: events.NewMessage.Event) -> None:
        raw_text = event.text.strip()
        try:
            await _handle_free_text_location(event, raw_text, _set_trip_destination)
        except Exception:
            logger.exception("error handling trip destination text for chat_id=%s", event.chat_id)
            await event.respond(ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_origin_text))
    async def handle_trip_origin_text(event: events.NewMessage.Event) -> None:
        raw_text = event.text.strip()
        try:
            await _handle_free_text_location(event, raw_text, _origin_resolved)
        except Exception:
            logger.exception("error handling trip origin text for chat_id=%s", event.chat_id)
            await event.respond(ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_origin_location))
    async def handle_trip_origin_location(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        try:
            await _origin_resolved(event, chat_id, event.geo.lat, event.geo.long, None)
        except Exception:
            logger.exception("error handling trip origin location for chat_id=%s", chat_id)
            await event.respond(ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_battery_text))
    async def handle_trip_battery_text(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        raw = event.text.strip().replace("%", "").replace(",", ".")
        try:
            percent = float(raw)
        except ValueError:
            await event.respond(TRIP_INVALID_BATTERY_MESSAGE, parse_mode="html")
            return
        if not (1.0 <= percent <= 100.0):
            await event.respond(TRIP_INVALID_BATTERY_MESSAGE, parse_mode="html")
            return

        session = get_session(chat_id)
        origin = session.trip_origin
        if origin is None:
            session.trip_state = None
            await event.respond(ERROR_GENERIC)
            return
        session.trip_state = None
        try:
            await _finalize_trip(event, chat_id, origin["lat"], origin["lng"], origin.get("name"), percent)
        except Exception:
            logger.exception("error finalizing trip after battery input for chat_id=%s", chat_id)
            await event.respond(ERROR_GENERIC)

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
                try:
                    await event.delete()
                except Exception:
                    try:
                        await event.edit(buttons=None)
                    except Exception:
                        pass
                await _finalize_trip(event, chat_id, origin["lat"], origin["lng"], origin.get("name"), battery_percent)
            elif data == "tripbatt:custom":
                session.trip_state = "awaiting_battery_input"
                await event.answer()
                try:
                    await event.edit(TRIP_ASK_BATTERY_MESSAGE, buttons=None, parse_mode="html")
                except Exception:
                    await event.respond(TRIP_ASK_BATTERY_MESSAGE, parse_mode="html")
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
            try:
                await event.delete()
            except Exception:
                try:
                    await event.edit(buttons=None)
                except Exception:
                    pass

            if session.trip_state == "awaiting_destination":
                await _set_trip_destination(event, chat_id, lat, lng, name)
            elif session.trip_state == "awaiting_origin":
                await _origin_resolved(event, chat_id, lat, lng, name)
            else:
                await event.respond(LOCATION_PROMPT_MESSAGE, buttons=Button.clear(), parse_mode="html")
        except Exception:
            logger.exception("error handling trip geo selection for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)
