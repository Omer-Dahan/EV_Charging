import html
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from bot.config import settings
from bot.handlers.location import ERROR_GENERIC, LOCATION_PROMPT_MESSAGE, send_map_image
from bot.keyboards.inline import trip_geocode_selection_keyboard, trip_plan_keyboard, welcome_keyboard
from bot.keyboards.reply import location_request_keyboard
from bot.services.formatter import format_trip_plan
from bot.services.geocoder import geocode, parse_coordinates
from bot.services.station_search import is_in_israel
from bot.services.trip_planner import plan_trip
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


def _reset_trip_state(session) -> None:
    session.trip_state = None
    session.trip_destination = None
    session.trip_geocode_candidates = []


async def _finalize_trip(event, chat_id: int, origin_lat: float, origin_lng: float, origin_name: Optional[str]) -> None:
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

    planning_msg = await event.respond(TRIP_PLANNING_MESSAGE, buttons=Button.clear())
    try:
        plan = await plan_trip(origin_lat, origin_lng, dest_lat, dest_lng, settings.db_path)
        text = format_trip_plan(plan, origin_name, dest_name)

        if plan["stops"]:
            buttons = trip_plan_keyboard(plan["stops"])
        else:
            buttons = welcome_keyboard(is_private=event.is_private)

        if plan["stops"]:
            user_settings = await get_user_settings(chat_id, settings.users_db_path)
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


async def _set_trip_destination(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    session = get_session(chat_id)
    session.trip_destination = {"lat": lat, "lng": lng, "name": name}
    session.trip_geocode_candidates = []

    if session.user_lat is not None and session.user_lng is not None:
        session.trip_state = None
        await _finalize_trip(event, chat_id, session.user_lat, session.user_lng, session.location_name)
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

        async def on_resolved(ev, chat_id, lat, lng, name):
            get_session(chat_id).trip_state = None
            await _finalize_trip(ev, chat_id, lat, lng, name)

        try:
            await _handle_free_text_location(event, raw_text, on_resolved)
        except Exception:
            logger.exception("error handling trip origin text for chat_id=%s", event.chat_id)
            await event.respond(ERROR_GENERIC)

    @client.on(events.NewMessage(func=_is_trip_origin_location))
    async def handle_trip_origin_location(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        try:
            get_session(chat_id).trip_state = None
            await _finalize_trip(event, chat_id, event.geo.lat, event.geo.long, None)
        except Exception:
            logger.exception("error handling trip origin location for chat_id=%s", chat_id)
            await event.respond(ERROR_GENERIC)

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
                session.trip_state = None
                await _finalize_trip(event, chat_id, lat, lng, name)
            else:
                await event.respond(LOCATION_PROMPT_MESSAGE, buttons=Button.clear(), parse_mode="html")
        except Exception:
            logger.exception("error handling trip geo selection for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)
