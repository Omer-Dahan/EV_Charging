import logging

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from bot.handlers.location import (
    ERROR_GENERIC,
    LOCATION_PROMPT_MESSAGE,
    NO_RESULTS_MESSAGE,
    perform_search,
    render_station_card,
)
from bot.handlers.start import WELCOME_MESSAGE
from bot.keyboards.inline import no_results_keyboard, welcome_keyboard
from bot.services.station_search import sort_stations
from bot.states import get_session

logger = logging.getLogger(__name__)

INFO_HOW_MESSAGE = (
    "ℹ️ <b>איך הבוט עובד?</b>\n\n"
    "📍 <b>דרכי חיפוש:</b>\n"
    "• <b>טקסט:</b> שלח רחוב או שכונה ועיר מופרדים בפסיק (לדוגמה: <i>הרצל 7, חיפה</i>)\n"
    "• <b>קואורדינטות:</b> שלח קואורדינטות GPS (לדוגמה: <code>32.0853, 34.7818</code>)\n"
    "• <b>מיקום נוכחי:</b> שיתוף GPS ישיר מהמכשיר\n\n"
    "🔒 <b>פרטיות:</b>\n"
    "המיקום שלך משמש אך ורק לחיפוש העמדות הקרובות ברגע הבקשה, ולא נשמר בשום מאגר נתונים.\n\n"
    "📊 <b>מאגר הנתונים ורמת העדכון:</b>\n"
    "הבוט מאחד כ-3,400 אתרי טעינה ממספר מקורות: המאגר הלאומי של משרד האנרגיה (CelloCharge), data.gov.il ומקורות נוספים. "
    "הסריקה מתבצעת מחדש מדי כמה חודשים באופן תקופתי — הנתונים מעודכנים, אך אינם מוצגים בזמן אמת (ללא סטטוס תפוס/פנוי חי).\n\n"
    "💻 <b>קוד פתוח:</b>\n"
    "הפרויקט הוא קוד פתוח ומפותח ב-Python 3.11 🐍"
)


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.CallbackQuery(pattern=rb"^nav:"))
    async def handle_nav(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        action = data.split(":", 1)[1]

        try:
            if action == "noop":
                await event.answer()
                return

            session = get_session(chat_id)

            if action == "next":
                if not session.results:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                if session.current_idx < len(session.results) - 1:
                    session.current_idx += 1
                text, buttons = render_station_card(session)
                await event.edit(text, buttons=buttons, parse_mode="html")

            elif action == "prev":
                if not session.results:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                if session.current_idx > 0:
                    session.current_idx -= 1
                text, buttons = render_station_card(session)
                await event.edit(text, buttons=buttons, parse_mode="html")

            elif action == "back_to_results":
                if session.results:
                    text, buttons = render_station_card(session)
                    await event.edit(text, buttons=buttons, parse_mode="html")
                else:
                    await event.edit(LOCATION_PROMPT_MESSAGE, buttons=welcome_keyboard(), parse_mode="html")

            elif action == "new_search":
                await event.edit(LOCATION_PROMPT_MESSAGE, buttons=welcome_keyboard(), parse_mode="html")

            elif action == "back_to_welcome":
                await event.edit(WELCOME_MESSAGE, buttons=welcome_keyboard(), parse_mode="html")
        except Exception:
            logger.exception("error handling nav callback for chat_id=%s", chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^info:how$"))
    async def handle_info_how(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        try:
            await event.edit(
                INFO_HOW_MESSAGE,
                buttons=[[Button.inline("↩️ חזרה", data=b"nav:back_to_welcome")]],
                parse_mode="html",
            )
        except Exception:
            logger.exception("error handling info:how callback for chat_id=%s", chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^range:"))
    async def handle_range(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")

        try:
            radius_km = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await event.answer(ERROR_GENERIC, alert=True)
            return
        # Reject unreasonable radius values to prevent DB/map abuse.
        if not (1 <= radius_km <= 200):
            await event.answer(ERROR_GENERIC, alert=True)
            return

        try:
            session = get_session(chat_id)
            if session.user_lat is None or session.user_lng is None:
                await event.answer(ERROR_GENERIC, alert=True)
                return

            results = await perform_search(
                chat_id, session.user_lat, session.user_lng, radius_km, location_name=session.location_name
            )

            if not results:
                await event.edit(
                    NO_RESULTS_MESSAGE.format(radius=radius_km),
                    buttons=no_results_keyboard(radius_km),
                    parse_mode="html",
                )
                return

            text, buttons = render_station_card(session)
            await event.edit(text, buttons=buttons, parse_mode="html")
        except Exception:
            logger.exception("error handling range callback for chat_id=%s", chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^sort:"))
    async def handle_sort(event: events.CallbackQuery.Event) -> None:
        chat_id = event.chat_id
        data = event.data.decode("utf-8")
        sort_by = data.split(":", 1)[1]

        try:
            session = get_session(chat_id)
            if not session.results:
                await event.answer("אין תוצאות להצגה", alert=False)
                return

            if session.sort_by == sort_by:
                await event.answer(
                    f"כבר ממוין לפי {'מהירות' if sort_by == 'speed' else 'מרחק'}"
                )
                return

            session.sort_by = sort_by
            session.results = sort_stations(session.results, sort_by=sort_by)
            session.current_idx = 0

            text, buttons = render_station_card(session)
            await event.answer()
            await event.edit(text, buttons=buttons, parse_mode="html")
        except Exception:
            logger.exception("error handling sort callback for chat_id=%s", chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

