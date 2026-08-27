import html
import logging
import os
import re
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from bot.config import settings
from bot.keyboards.inline import (
    geocode_selection_keyboard,
    no_results_keyboard,
    station_card_keyboard,
    welcome_keyboard,
)
from bot.keyboards.reply import location_request_keyboard
from bot.services.formatter import format_station_card
from bot.services.geocoder import geocode, parse_coordinates
from bot.services.map_renderer import render_map
from bot.services.station_search import find_nearby, is_in_israel
from bot.states import get_session
from bot.storage.users_db import get_user_settings

logger = logging.getLogger(__name__)

SEARCHING_MESSAGE = '🔍 מחפש עמדות טעינה ברדיוס {radius} ק"מ...'
SEARCHING_GEO_MESSAGE = '🔍 מחפש עמדות טעינה סביב <b>{name}</b> (ברדיוס {radius} ק"מ)...'
SEARCHING_LOCATION_MESSAGE = '🔍 מאתר את המיקום "<b>{query}</b>"...'
NO_RESULTS_MESSAGE = (
    '😕 <b>לא נמצאו עמדות טעינה ברדיוס {radius} ק"מ.</b>\n\n'
    "💡 אפשר להרחיב את טווח החיפוש בכפתורים למטה, או לעדכן את אפשרויות הסינון ב-⚙️ הגדרות."
)
NO_GEOCODE_RESULTS = (
    '❌ <b>לא מצאנו את המיקום "<i>{query}</i>"</b>\n\n'
    '💡 <b>טיפים לחיפוש:</b>\n'
    '• כתבו רחוב או שכונה, ואז פסיק ועיר (למשל: <i>רוטשילד 1, תל אביב</i>, <i>ביאליק, חיפה</i>)\n'
    '• שלח קואורדינטות GPS (למשל: <code>32.0853, 34.7818</code>)\n'
    '• שתף מיקום נוכחי באמצעות הכפתור למטה'
)
GEOCODE_CHOICE_MESSAGE = (
    '📍 <b>נמצאו מספר מיקומים עבור "<i>{query}</i>":</b>\n'
    'בחר את המיקום הרצוי לחיפוש:'
)
LOCATION_PROMPT_MESSAGE = (
    "📍 <b>איך תרצה לחפש עמדות טעינה?</b>\n\n"
    "1️⃣ שתף מיקום נוכחי בכפתור למטה\n"
    "2️⃣ שלח רחוב או שכונה ועיר מופרדים בפסיק (למשל: <i>הרצל 7, חיפה</i>)\n"
    "3️⃣ שלח קואורדינטות (למשל: <code>32.0853, 34.7818</code>)"
)
MISSING_CITY_MESSAGE = (
    '📍 כדי למצוא מיקום מדויק, כתבו רחוב או שכונה וגם עיר, מופרדים בפסיק.\n'
    'לדוגמה: <i>הרצל 7, חיפה</i> או <i>ביאליק, תל אביב</i>\n\n'
    'אפשר גם לשלוח קואורדינטות GPS (למשל: <code>32.0853, 34.7818</code>) או לשתף מיקום נוכחי.'
)
ERROR_GENERIC = "❌ אירעה שגיאה. כדאי לנסות שוב בעוד מספר רגעים."
ERROR_OUTSIDE_ISRAEL = "❌ המיקום שנשלח נמצא מחוץ לישראל. המאגר מכיל עמדות בארץ בלבד."


def render_station_card(session) -> tuple[str, list]:
    total = len(session.results)
    idx = session.current_idx
    station = session.results[idx]
    text = format_station_card(
        station,
        station["distance_km"],
        idx + 1,
        total,
        session.current_radius,
        location_name=session.location_name,
    )
    buttons = station_card_keyboard(
        station["id"], idx, total, station["lat"], station["lng"]
    )
    return text, buttons


async def perform_search(
    chat_id: int,
    lat: float,
    lng: float,
    radius_km: int,
    location_name: Optional[str] = None,
) -> list[dict]:
    user_settings = await get_user_settings(chat_id, settings.users_db_path)
    results = await find_nearby(
        settings.db_path,
        lat,
        lng,
        radius_km=radius_km,
        connector_filter=user_settings.connector_filter,
        speed_filter=user_settings.speed_filter,
        max_price=user_settings.max_price,
    )
    session = get_session(chat_id)
    session.results = results
    session.current_idx = 0
    session.user_lat = lat
    session.user_lng = lng
    session.current_radius = radius_km
    if location_name is not None:
        session.location_name = location_name

    logger.info(
        "search chat_id=%s lat=%.3f lng=%.3f radius=%s results=%d loc=%s",
        chat_id, lat, lng, radius_km, len(results), session.location_name,
    )
    return results


async def send_map_image(
    event,
    lat: float,
    lng: float,
    radius_km: int,
    results: list[dict],
) -> None:
    """שולח תמונת מפה בנפרד מכרטיסיית העמדה. כשלון כאן (רשת, שגיאת רינדור וכו')
    לא אמור לחסום את החיפוש - לכן נבלע ונרשם ללוג בלבד."""
    try:
        map_path = await render_map(lat, lng, radius_km, results)
        if map_path is None:
            return
        try:
            await event.respond(
                file=map_path,
                message="🗺️ מפת האזור: המיקום המבוקש מסומן באדום 🔴, עמדות הטעינה בירוק 🟢.",
            )
        finally:
            try:
                os.remove(map_path)
            except OSError:
                logger.warning("failed to remove temp map file %s", map_path)
    except Exception:
        logger.exception("failed to send map image")


async def execute_search(
    event,
    chat_id: int,
    lat: float,
    lng: float,
    location_name: Optional[str] = None,
) -> None:
    """מריץ את תהליך החיפוש המלא: הצגת הודעת טעינה, שליפת נתונים, שליחת מפה וכרטיס עמדה."""
    if not is_in_israel(lat, lng):
        await event.respond(ERROR_OUTSIDE_ISRAEL, buttons=Button.clear())
        return

    try:
        user_settings = await get_user_settings(chat_id, settings.users_db_path)
        radius_km = user_settings.default_radius

        if location_name:
            searching_text = SEARCHING_GEO_MESSAGE.format(
                name=html.escape(location_name), radius=radius_km
            )
        else:
            searching_text = SEARCHING_MESSAGE.format(radius=radius_km)

        searching_msg = await event.respond(
            searching_text,
            buttons=Button.clear(),
            parse_mode="html",
        )

        results = await perform_search(
            chat_id, lat, lng, radius_km, location_name=location_name
        )
        session = get_session(chat_id)

        if not results:
            result_msg = await event.respond(
                NO_RESULTS_MESSAGE.format(radius=radius_km),
                buttons=no_results_keyboard(radius_km),
                parse_mode="html",
            )
        else:
            await send_map_image(event, lat, lng, radius_km, results)
            text, buttons = render_station_card(session)
            result_msg = await event.respond(
                text, buttons=buttons, parse_mode="html"
            )

        session.result_msg_id = result_msg.id
        try:
            await searching_msg.delete()
        except Exception:
            pass
    except Exception:
        logger.exception("error executing search for chat_id=%s", chat_id)
        await event.respond(ERROR_GENERIC)


def _is_text_search(e: events.NewMessage.Event) -> bool:
    if bool(e.geo):
        return False
    text = (e.text or "").strip()
    if not text or text.startswith("/"):
        return False
    if re.match(r"^(?:❌\s*)?ביטול$", text):
        return False
    return True


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(func=lambda e: bool(e.geo)))
    async def handle_location(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        session = get_session(chat_id)
        session.location_name = None
        await execute_search(event, chat_id, event.geo.lat, event.geo.long, location_name=None)

    @client.on(events.NewMessage(func=_is_text_search))
    async def handle_text_query(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        raw_text = event.text.strip()

        # 1. בדיקה אם נשלחו קואורדינטות ישירות או לינק מפות
        coords = parse_coordinates(raw_text)
        if coords is not None:
            lat, lng = coords
            session = get_session(chat_id)
            session.location_name = f"{lat:.4f}, {lng:.4f}"
            await execute_search(event, chat_id, lat, lng, location_name=session.location_name)
            return

        # 2. טקסט ללא פסיק — בקשה להוסיף עיר (גיאוקודינג לא אמין בלי יישוב)
        if "," not in raw_text:
            await event.respond(
                MISSING_CITY_MESSAGE,
                buttons=welcome_keyboard(),
                parse_mode="html",
            )
            return

        # 3. חיפוש טקסטואלי חופשי באמצעות גיאוקודינג
        searching_msg = None
        try:
            searching_msg = await event.respond(
                SEARCHING_LOCATION_MESSAGE.format(query=html.escape(raw_text)),
                buttons=Button.clear(),
                parse_mode="html",
            )

            candidates = await geocode(raw_text)

            if not candidates:
                try:
                    await searching_msg.delete()
                except Exception:
                    pass
                await event.respond(
                    NO_GEOCODE_RESULTS.format(query=html.escape(raw_text)),
                    buttons=welcome_keyboard(),
                    parse_mode="html",
                )
                return

            if len(candidates) == 1:
                try:
                    await searching_msg.delete()
                except Exception:
                    pass
                chosen = candidates[0]
                await execute_search(
                    event, chat_id, chosen["lat"], chosen["lng"], location_name=chosen["name"]
                )
                return

            # מספר תוצאות — הצגת תפריט בחירה
            try:
                await searching_msg.delete()
            except Exception:
                pass
            session = get_session(chat_id)
            session.geocode_candidates = candidates
            await event.respond(
                GEOCODE_CHOICE_MESSAGE.format(query=html.escape(raw_text)),
                buttons=geocode_selection_keyboard(candidates),
                parse_mode="html",
            )
        except Exception:
            logger.exception("error handling text query for chat_id=%s query=%r", chat_id, raw_text)
            if searching_msg:
                try:
                    await searching_msg.delete()
                except Exception:
                    pass
            await event.respond(ERROR_GENERIC)

    @client.on(events.CallbackQuery(pattern=rb"^geo:"))
    async def handle_geo_selection(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        parts = data.split(":")
        try:
            if len(parts) < 4:
                raise ValueError(f"malformed geo callback data: {data!r}")
            idx = int(parts[1])
            lat = float(parts[2])
            lng = float(parts[3])

            # Validate that the coordinates are within a reasonable world range.
            # execute_search also checks is_in_israel, but this guards against
            # obviously bad/tampered callback data before we touch the session.
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                await event.answer(ERROR_GENERIC, alert=True)
                return

            session = get_session(chat_id)
            location_name = None
            if session.geocode_candidates and 0 <= idx < len(session.geocode_candidates):
                location_name = session.geocode_candidates[idx].get("name")

            await event.answer()
            try:
                await event.delete()
            except Exception:
                # If delete fails (e.g. message too old), at least clear the keyboard.
                try:
                    await event.edit(buttons=None)
                except Exception:
                    pass

            await execute_search(event, chat_id, lat, lng, location_name=location_name)
        except Exception:
            logger.exception("error handling geo selection callback for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.NewMessage(pattern=r"^(?:❌\s*)?ביטול$"))
    async def handle_cancel(event: events.NewMessage.Event) -> None:
        await event.respond(LOCATION_PROMPT_MESSAGE, buttons=Button.clear(), parse_mode="html")

    @client.on(events.CallbackQuery(pattern=rb"^loc:request"))
    async def handle_loc_request(event: events.CallbackQuery.Event) -> None:
        await event.answer()
        await event.respond(LOCATION_PROMPT_MESSAGE, buttons=location_request_keyboard(), parse_mode="html")
