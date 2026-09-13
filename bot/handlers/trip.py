import logging
import os
import time
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import MessageNotModifiedError
from telethon.tl.custom import Button

from bot.config import settings
from bot.handlers import trip_screens as screens
from bot.handlers.location import ERROR_GENERIC, LOCATION_PROMPT_MESSAGE
from bot.keyboards.inline import welcome_keyboard
from bot.keyboards.reply import location_request_keyboard
from bot.services.geocoder import geocode, parse_coordinates
from bot.services.map_renderer import render_trip_map
from bot.services.station_search import is_in_israel
from bot.services.trip_planner import (
    TRIP_CONSUMPTION_KWH_PER_100KM,
    TRIP_DEFAULT_REAL_RANGE_KM,
    TRIP_DEFAULT_SAFETY_MARGIN_PERCENT,
    TripRangeError,
    plan_trip,
)
from bot.states import get_session
from bot.storage.users_db import get_recent_trip_plans, get_trip_plan, get_user_settings, save_trip_plan

logger = logging.getLogger(__name__)

# השלבים שבהם הודעת טקסט של המשתמש שייכת לזרימת הנסיעה. handler הטקסט היחיד
# קורא את ה-state פעם אחת ומפצל לפיו - כך הודעה אחת לא נצרכת בכמה שלבים ברצף.
TRIP_TEXT_STATES = ("awaiting_destination", "awaiting_origin", "awaiting_battery")

# זרימה שננטשה באמצע משתחררת אחרי רבע שעה, כדי שהמשתמש לא ימצא את עצמו עם בוט
# שבולע כל הודעה עד פקיעת ה-session כולו (שעתיים).
TRIP_FLOW_TTL_SECONDS = 900

TRIP_PRIVATE_ONLY_MESSAGE = "🚗 תכנון נסיעה זמין בצ'אט הפרטי עם הבוט."
TRIP_INVALID_BATTERY_MESSAGE = "❌ יש להזין מספר בין 1 ל-100 (אחוזי סוללה)."
TRIP_GPS_PROMPT_MESSAGE = "📍 שתף מיקום מהכפתור שלמטה — ההודעה הזו תיעלם אחר כך."
TRIP_MAP_CAPTION = (
    "🗺️ מפת המסלול: 🔴 המוצא, 🏁 היעד, ועצירות הטעינה ממוספרות לפי סדר הנסיעה."
)


def _reset_trip_state(session) -> None:
    """מנקה את מצב הזרימה. מזהי ההודעות לא נוגעים כאן - הם מנוהלים במקום שבו
    מחליטים אם לערוך את ההודעה הקיימת או לפתוח חדשה."""
    session.trip_state = None
    session.trip_destination = None
    session.trip_origin = None
    session.trip_geocode_candidates = []
    session.trip_started_at = None
    session.trip_busy = False


def _flow_expired(session) -> bool:
    return (
        session.trip_started_at is not None
        and time.monotonic() - session.trip_started_at > TRIP_FLOW_TTL_SECONDS
    )


async def _show_trip_step(event, chat_id: int, session, text: str, buttons=None) -> None:
    """נקודת הפלט היחידה של הזרימה: עורכת את הודעת הזרימה (session.trip_message_id)
    במקום לשלוח הודעה חדשה, כדי שכל התכנון יתנהל בהודעה אחת.

    אם אין עדיין הודעת זרימה, או שהעריכה נכשלת (ההודעה נמחקה/ישנה מדי), נופלים
    לשליחת הודעה חדשה ושומרים את המזהה שלה להמשך.
    """
    if session.trip_message_id is not None:
        try:
            await event.client.edit_message(chat_id, session.trip_message_id, text, buttons=buttons, parse_mode="html")
            return
        except MessageNotModifiedError:
            return
        except Exception:
            logger.warning(
                "trip step edit failed chat_id=%s msg_id=%s - falling back to a new message",
                chat_id, session.trip_message_id, exc_info=True,
            )
    msg = await event.respond(text, buttons=buttons, parse_mode="html")
    session.trip_message_id = msg.id


async def _delete_user_input(event) -> None:
    """מוחק את הודעת המשתמש כדי שהזרימה תיראה כהודעה אחת. בקבוצות אין הרשאה
    למחוק הודעות של אחרים, ולכן מוחקים רק בצ'אט פרטי."""
    if not event.is_private:
        return
    try:
        await event.delete()
    except Exception:
        logger.debug("could not delete user input in chat_id=%s", event.chat_id, exc_info=True)


async def _clear_trip_map(event, chat_id: int, session) -> None:
    if session.trip_map_msg_id is None:
        return
    try:
        await event.client.delete_messages(chat_id, session.trip_map_msg_id)
    except Exception:
        logger.debug("could not delete trip map message in chat_id=%s", chat_id, exc_info=True)
    session.trip_map_msg_id = None


async def _send_trip_map(
    event,
    chat_id: int,
    session,
    origin: tuple[float, float],
    destination: tuple[float, float],
    stops: list[tuple[float, float]],
) -> None:
    """שולח את מפת המסלול כהודעה נפרדת (טלגרם לא הופכת הודעת טקסט להודעת מדיה
    בעריכה), ומוחק קודם מפה קודמת של הזרימה כדי שלא יצטברו תמונות בצ'אט.

    כשלון ברינדור/שליחה לא אמור להפיל את התוכנית עצמה - היא כבר מוצגת בטקסט.
    """
    await _clear_trip_map(event, chat_id, session)
    try:
        map_path = await render_trip_map(origin, destination, stops)
        if map_path is None:
            return
        try:
            user_settings = await get_user_settings(chat_id, settings.users_db_path)
            msg = await event.respond(
                file=map_path,
                message=TRIP_MAP_CAPTION,
                force_document=user_settings.map_format != "photo",
            )
            session.trip_map_msg_id = msg.id
        finally:
            try:
                os.remove(map_path)
            except OSError:
                logger.warning("failed to remove temp trip map file %s", map_path)
    except Exception:
        logger.exception("failed to send trip map for chat_id=%s", chat_id)


def _plan_points(plan: dict) -> tuple[tuple[float, float], tuple[float, float], list[tuple[float, float]]]:
    origin = (plan["origin"]["lat"], plan["origin"]["lng"])
    destination = (plan["destination"]["lat"], plan["destination"]["lng"])
    stops = [(s["station"]["lat"], s["station"]["lng"]) for s in plan.get("stops") or []]
    return origin, destination, stops


async def _clear_gps_prompt(event, chat_id: int, session) -> None:
    """מוחק את הודעת בקשת ה-GPS הזמנית ומסיר את מקלדת התשובה שהיא נשאה.

    טלגרם מסירה reply keyboard רק בהודעה נשלחת ולא בעריכה, ולכן שולחים הודעה
    זניחה עם Button.clear() ומוחקים אותה מיד - ההסרה כבר חלה אצל הלקוח.
    """
    if session.trip_gps_prompt_msg_id is None:
        return
    prompt_id = session.trip_gps_prompt_msg_id
    session.trip_gps_prompt_msg_id = None
    try:
        await event.client.delete_messages(chat_id, prompt_id)
    except Exception:
        logger.debug("could not delete gps prompt in chat_id=%s", chat_id, exc_info=True)
    try:
        cleanup = await event.respond("👌", buttons=Button.clear())
        await cleanup.delete()
    except Exception:
        logger.debug("could not clear reply keyboard in chat_id=%s", chat_id, exc_info=True)


async def _start_trip_flow(event, chat_id: int, fresh_message: bool) -> None:
    """fresh_message=True כשהמשתמש הקליד /trip - אז נשלחת הודעת זרימה חדשה ותוכנית
    קודמת שכבר על המסך נשארת שלמה. מ-callback עורכים את ההודעה שנלחצה."""
    session = get_session(chat_id)
    _reset_trip_state(session)
    if fresh_message:
        # ההודעה הקודמת (ואם יש - המפה שלה) נשארות בצ'אט כהיסטוריה, כבר לא שלנו.
        session.trip_message_id = None
        session.trip_map_msg_id = None
    else:
        await _clear_trip_map(event, chat_id, session)
    session.trip_state = "awaiting_destination"
    session.trip_started_at = time.monotonic()
    await _show_trip_step(event, chat_id, session, *screens.render_ask_destination())


async def _show_expired(event, chat_id: int, session) -> None:
    _reset_trip_state(session)
    await _show_trip_step(event, chat_id, session, *screens.render_expired())


async def _ask_battery(event, chat_id: int, session, error: Optional[str] = None) -> None:
    session.trip_state = "awaiting_battery"
    await _show_trip_step(event, chat_id, session, *screens.render_ask_battery(error))


async def _origin_resolved(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    """נקרא ברגע שמוצא הנסיעה ידוע - ממשיך לשלב אחוז הסוללה."""
    session = get_session(chat_id)
    session.trip_origin = {"lat": lat, "lng": lng, "name": name}
    session.trip_geocode_candidates = []
    await _clear_gps_prompt(event, chat_id, session)
    await _ask_battery(event, chat_id, session)


async def _set_trip_destination(event, chat_id: int, lat: float, lng: float, name: Optional[str]) -> None:
    session = get_session(chat_id)
    session.trip_destination = {"lat": lat, "lng": lng, "name": name}
    session.trip_geocode_candidates = []

    # אם המשתמש כבר חיפש עמדות בסשן הזה, המיקום שלו ידוע ואין טעם לשאול שוב.
    if session.user_lat is not None and session.user_lng is not None:
        await _origin_resolved(event, chat_id, session.user_lat, session.user_lng, session.location_name)
        return

    session.trip_state = "awaiting_origin"
    dest_label = name or f"{lat:.4f}, {lng:.4f}"
    await _show_trip_step(
        event, chat_id, session,
        *screens.render_ask_origin(dest_label, event.is_private),
    )


async def _handle_free_text_location(event, raw_text: str, on_resolved) -> None:
    """פענוח טקסט חופשי (יעד או מוצא) לקואורדינטות, כולל בחירה בין כמה תוצאות."""
    chat_id = event.chat_id
    session = get_session(chat_id)

    coords = parse_coordinates(raw_text)
    if coords is not None:
        lat, lng = coords
        await on_resolved(event, chat_id, lat, lng, f"{lat:.4f}, {lng:.4f}")
        return

    if "," not in raw_text:
        await _show_trip_step(event, chat_id, session, *screens.render_missing_city())
        return

    candidates = await geocode(raw_text)
    if not candidates:
        await _show_trip_step(event, chat_id, session, *screens.render_no_geocode_results(raw_text))
        return

    if len(candidates) == 1:
        chosen = candidates[0]
        await on_resolved(event, chat_id, chosen["lat"], chosen["lng"], chosen["name"])
        return

    session.trip_geocode_candidates = candidates
    await _show_trip_step(event, chat_id, session, *screens.render_geocode_choice(raw_text, candidates))


def _parse_battery_percent(raw: str) -> Optional[float]:
    """מקבל גם "85%" וגם "85,5". מחזיר None לכל קלט שאינו אחוז תקין."""
    try:
        percent = float(raw.replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None
    if not (1.0 <= percent <= 100.0):
        return None
    return percent


async def _finalize_trip(
    event, chat_id: int, origin_lat: float, origin_lng: float, origin_name: Optional[str], battery_percent: float
) -> None:
    session = get_session(chat_id)
    destination = session.trip_destination
    if destination is None:
        await _show_expired(event, chat_id, session)
        return

    dest_lat, dest_lng = destination["lat"], destination["lng"]
    dest_name = destination.get("name") or f"{dest_lat:.4f}, {dest_lng:.4f}"
    origin_name = origin_name or f"{origin_lat:.4f}, {origin_lng:.4f}"

    if not is_in_israel(origin_lat, origin_lng) or not is_in_israel(dest_lat, dest_lng):
        session.trip_destination = None
        session.trip_state = "awaiting_destination"
        await _show_trip_step(event, chat_id, session, *screens.render_outside_israel())
        return

    user_settings = await get_user_settings(chat_id, settings.users_db_path)
    real_range_km = user_settings.trip_real_range_km or TRIP_DEFAULT_REAL_RANGE_KM
    safety_margin_percent = user_settings.trip_safety_margin_percent or TRIP_DEFAULT_SAFETY_MARGIN_PERCENT
    consumption_kwh_per_100km = user_settings.trip_consumption_kwh_100km or TRIP_CONSUMPTION_KWH_PER_100KM

    if battery_percent <= safety_margin_percent:
        session.trip_state = "awaiting_battery"
        await _show_trip_step(
            event, chat_id, session,
            *screens.render_low_battery(battery_percent, safety_margin_percent),
        )
        return

    session.trip_state = "planning"
    await _show_trip_step(event, chat_id, session, *screens.render_planning())
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
    except TripRangeError:
        # רשת ביטחון: אותו מצב שהבדיקה למעלה חוסמת, אבל אם הגדרות המשתמש השתנו
        # בינתיים עדיף להחזיר אותו למסך הסוללה מאשר ל"שגיאה כללית".
        logger.info("trip planning blocked by range for chat_id=%s", chat_id)
        session.trip_state = "awaiting_battery"
        await _show_trip_step(
            event, chat_id, session,
            *screens.render_low_battery(battery_percent, safety_margin_percent),
        )
        return
    except Exception:
        logger.exception("error planning trip for chat_id=%s", chat_id)
        session.trip_state = None
        await _show_trip_step(event, chat_id, session, *screens.render_generic_error())
        return

    _reset_trip_state(session)

    # שומרים לפני התצוגה כדי שכפתור "פירוט מלא" יוכל להצביע על התוכנית ב-DB
    # (וכך ימשיך לעבוד גם אחרי restart של הבוט).
    plan_id = None
    try:
        plan_id = await save_trip_plan(
            chat_id,
            origin={"lat": origin_lat, "lng": origin_lng, "name": origin_name},
            destination={"lat": dest_lat, "lng": dest_lng, "name": dest_name},
            battery_percent=battery_percent,
            plan=plan,
            db_path=settings.users_db_path,
        )
    except Exception:
        logger.exception("failed to save trip plan for chat_id=%s", chat_id)

    await _show_trip_step(event, chat_id, session, *screens.render_plan(plan, origin_name, dest_name, plan_id))
    await _send_trip_map(event, chat_id, session, *_plan_points(plan))


async def _show_trip_plans_list(event, chat_id: int) -> None:
    session = get_session(chat_id)
    plans = await get_recent_trip_plans(chat_id, settings.users_db_path, limit=5)
    if not plans:
        await _show_trip_step(event, chat_id, session, *screens.render_no_plans())
        return
    await _show_trip_step(event, chat_id, session, *screens.render_plans_list(plans))


async def _show_saved_trip_plan(event, chat_id: int, plan_id: int, detailed: bool = False) -> None:
    session = get_session(chat_id)
    row = await get_trip_plan(plan_id, chat_id, settings.users_db_path)
    if row is None:
        await _show_trip_step(event, chat_id, session, *screens.render_plan_not_found())
        return

    plan = row["plan"]
    origin_name = row.get("origin_name") or f"{row['origin_lat']:.4f}, {row['origin_lng']:.4f}"
    dest_name = row.get("destination_name") or f"{row['destination_lat']:.4f}, {row['destination_lng']:.4f}"

    if detailed:
        await _show_trip_step(
            event, chat_id, session,
            *screens.render_plan_details(plan, origin_name, dest_name, plan_id),
        )
        return

    await _show_trip_step(event, chat_id, session, *screens.render_plan(plan, origin_name, dest_name, plan_id))
    await _send_trip_map(event, chat_id, session, *_plan_points(plan))


async def _resume_current_step(event, chat_id: int, session) -> None:
    """מצייר מחדש את המסך של השלב הנוכחי - למשל בחזרה מהגדרות הנסיעה."""
    state = session.trip_state
    if state == "awaiting_destination":
        await _show_trip_step(event, chat_id, session, *screens.render_ask_destination())
    elif state == "awaiting_origin":
        destination = session.trip_destination or {}
        dest_label = destination.get("name") or "היעד שנבחר"
        await _show_trip_step(event, chat_id, session, *screens.render_ask_origin(dest_label, event.is_private))
    elif state == "awaiting_battery":
        await _ask_battery(event, chat_id, session)
    else:
        await _show_expired(event, chat_id, session)


async def _send_gps_prompt(event, chat_id: int, session) -> None:
    """מסלול ה-GPS בלחיצה אחת: הודעה זמנית נפרדת עם מקלדת בקשת מיקום.

    אי אפשר לצרף בקשת מיקום ל-inline keyboard או לעריכת הודעה, ולכן זו הודעה
    משלה - הודעת הזרימה עצמה לא זזה, וההודעה הזו נמחקת ברגע שהמיקום מגיע.
    """
    if session.trip_state != "awaiting_origin":
        await event.answer()
        await _show_expired(event, chat_id, session)
        return
    await event.answer()
    if session.trip_gps_prompt_msg_id is not None:
        return
    prompt = await event.respond(
        TRIP_GPS_PROMPT_MESSAGE,
        buttons=location_request_keyboard(),
        parse_mode="html",
    )
    session.trip_gps_prompt_msg_id = prompt.id


def _is_trip_text(e: events.NewMessage.Event) -> bool:
    if bool(e.geo):
        return False
    text = (e.text or "").strip()
    if not text or text.startswith("/"):
        return False
    if text in ("❌ ביטול", "ביטול"):
        return False
    session = get_session(e.chat_id)
    if session.trip_state not in TRIP_TEXT_STATES:
        return False
    if _flow_expired(session):
        # הזרימה נזנחה מזמן: משחררים אותה כאן כדי שההודעה תיפול ל-handler החיפוש הרגיל.
        _reset_trip_state(session)
        return False
    return True


def _is_trip_location(e: events.NewMessage.Event) -> bool:
    if not bool(e.geo):
        return False
    session = get_session(e.chat_id)
    if session.trip_state != "awaiting_origin":
        return False
    if _flow_expired(session):
        _reset_trip_state(session)
        return False
    return True


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(pattern=r"^/trip"))
    async def handle_trip_command(event: events.NewMessage.Event) -> None:
        # בקבוצה אין טעם בזרימה: היא מבוססת על עריכת הודעה אחת ועל מחיקת הודעות
        # המשתמש, ושתיהן לא עובדות שם כמו שצריך.
        if not event.is_private:
            await event.respond(TRIP_PRIVATE_ONLY_MESSAGE)
            return
        await _delete_user_input(event)
        await _start_trip_flow(event, event.chat_id, fresh_message=True)

    @client.on(events.NewMessage(func=_is_trip_text))
    async def handle_trip_text(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        session = get_session(chat_id)
        state = session.trip_state          # נקרא פעם אחת, לפני כל await
        raw_text = event.text.strip()

        if session.trip_busy:
            # הקלט הקודם עדיין בטיפול (גיאוקוד/תכנון לוקחים שניות) - מתעלמים
            # מהשני כדי שלא ייווצרו שני מסלולים במקביל על אותה הודעה.
            await _delete_user_input(event)
            raise events.StopPropagation

        session.trip_busy = True
        try:
            await _delete_user_input(event)
            if state == "awaiting_destination":
                await _handle_free_text_location(event, raw_text, _set_trip_destination)
            elif state == "awaiting_origin":
                await _handle_free_text_location(event, raw_text, _origin_resolved)
            elif state == "awaiting_battery":
                percent = _parse_battery_percent(raw_text)
                if percent is None:
                    await _ask_battery(event, chat_id, session, error=TRIP_INVALID_BATTERY_MESSAGE)
                elif session.trip_origin is None:
                    await _show_expired(event, chat_id, session)
                else:
                    origin = session.trip_origin
                    await _finalize_trip(event, chat_id, origin["lat"], origin["lng"], origin.get("name"), percent)
        except Exception:
            logger.exception("trip text step failed chat_id=%s state=%s", chat_id, state)
            await _show_trip_step(event, chat_id, session, *screens.render_generic_error())
        finally:
            session.trip_busy = False
        raise events.StopPropagation

    @client.on(events.NewMessage(func=_is_trip_location))
    async def handle_trip_location(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        session = get_session(chat_id)
        if session.trip_busy:
            raise events.StopPropagation
        session.trip_busy = True
        try:
            await _delete_user_input(event)
            if session.trip_state == "awaiting_origin":
                await _origin_resolved(event, chat_id, event.geo.lat, event.geo.long, None)
        except Exception:
            logger.exception("trip location step failed chat_id=%s", chat_id)
            await _show_trip_step(event, chat_id, session, *screens.render_generic_error())
        finally:
            session.trip_busy = False
        raise events.StopPropagation

    @client.on(events.CallbackQuery(pattern=rb"^tripbatt:"))
    async def handle_trip_battery_choice(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        session = get_session(chat_id)
        session.trip_message_id = event.message_id
        try:
            if session.trip_state != "awaiting_battery" or session.trip_origin is None:
                await event.answer()
                await _show_expired(event, chat_id, session)
                return

            try:
                battery_percent = float(data.rsplit(":", 1)[1])
            except (ValueError, IndexError):
                battery_percent = None

            if battery_percent is None:
                await event.answer(ERROR_GENERIC, alert=True)
                return

            origin = session.trip_origin
            await event.answer()
            await _finalize_trip(event, chat_id, origin["lat"], origin["lng"], origin.get("name"), battery_percent)
        except Exception:
            logger.exception("error handling trip battery choice for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^tripgeo:"))
    async def handle_trip_geo_selection(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        session = get_session(chat_id)
        session.trip_message_id = event.message_id
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

            name = None
            if session.trip_geocode_candidates and 0 <= idx < len(session.trip_geocode_candidates):
                name = session.trip_geocode_candidates[idx].get("name")

            await event.answer()

            if session.trip_state == "awaiting_destination":
                await _set_trip_destination(event, chat_id, lat, lng, name)
            elif session.trip_state == "awaiting_origin":
                await _origin_resolved(event, chat_id, lat, lng, name)
            else:
                # כפתור מתוך זרימה ישנה (restart של הבוט או session שפג).
                await _show_expired(event, chat_id, session)
        except Exception:
            logger.exception("error handling trip geo selection for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^trip:"))
    async def handle_trip_menu(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        session = get_session(chat_id)
        # ההודעה שעליה נלחץ הכפתור היא מעתה הודעת הזרימה, גם אם ה-session נמחק
        # או שהבוט עלה מחדש - כך אף פעם לא נשלחת הודעה חדשה במקומה.
        session.trip_message_id = event.message_id
        try:
            if not event.is_private:
                await event.answer(TRIP_PRIVATE_ONLY_MESSAGE, alert=True)
                return

            if data == "trip:new":
                await event.answer()
                await _start_trip_flow(event, chat_id, fresh_message=False)
            elif data == "trip:cancel":
                await event.answer()
                _reset_trip_state(session)
                await _clear_trip_map(event, chat_id, session)
                await event.edit(
                    LOCATION_PROMPT_MESSAGE,
                    buttons=welcome_keyboard(is_private=event.is_private),
                    parse_mode="html",
                )
                session.trip_message_id = None
            elif data == "trip:redest":
                await event.answer()
                session.trip_destination = None
                session.trip_state = "awaiting_destination"
                await _show_trip_step(event, chat_id, session, *screens.render_ask_destination())
            elif data == "trip:battery":
                await event.answer()
                if session.trip_origin is None:
                    await _show_expired(event, chat_id, session)
                else:
                    await _ask_battery(event, chat_id, session)
            elif data == "trip:gps":
                await _send_gps_prompt(event, chat_id, session)
            elif data == "trip:resume":
                await event.answer()
                await _resume_current_step(event, chat_id, session)
            elif data == "trip:myplans":
                await event.answer()
                await _show_trip_plans_list(event, chat_id)
            elif data.startswith("trip:plan:") or data.startswith("trip:details:"):
                try:
                    plan_id = int(data.rsplit(":", 1)[1])
                except (ValueError, IndexError):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await event.answer()
                await _show_saved_trip_plan(event, chat_id, plan_id, detailed=data.startswith("trip:details:"))
            else:
                await event.answer(ERROR_GENERIC, alert=True)
        except Exception:
            logger.exception("error handling trip menu callback for chat_id=%s data=%r", chat_id, data)
            await event.answer(ERROR_GENERIC, alert=True)
