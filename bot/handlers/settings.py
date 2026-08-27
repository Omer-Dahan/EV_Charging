import logging

from telethon import TelegramClient, events

from bot.config import settings as app_settings
from bot.handlers.location import ERROR_GENERIC
from bot.keyboards.inline import (
    connector_keyboard,
    price_keyboard,
    range_keyboard,
    settings_main_keyboard,
    speed_keyboard,
)
from bot.storage.users_db import get_user_settings, upsert_user

logger = logging.getLogger(__name__)

CONNECTOR_DISPLAY = {
    "ALL": "הכל (ללא סינון)",
    "CCS2_COMBO": "⚡ CCS2 (מהיר DC)",
    "TYPE2": "🔌 Type 2 (AC)",
    "CHADEMO": "🇯🇵 CHAdeMO",
}

SPEED_DISPLAY = {
    "ALL": "הכל (ללא סינון)",
    "SLOW": "🐢 רגילה (עד 22kW)",
    "FAST": "⚡ מהירה (50–150kW)",
    "ULTRA": "🚀 אולטרה-מהירה (150kW+)",
}

PRICE_DISPLAY = {
    None: "ללא הגבלה",
    1.5: 'עד 1.50 ₪ לקוט"ש',
    2.0: 'עד 2.00 ₪ לקוט"ש',
    2.5: 'עד 2.50 ₪ לקוט"ש',
}

SETTINGS_MAIN_TEMPLATE = (
    "⚙️ <b>הגדרות חיפוש</b>\n\n"
    "🔌 <b>סוג שקע:</b> {connector_display}\n"
    "⚡ <b>מהירות טעינה:</b> {speed_display}\n"
    '📏 <b>רדיוס ברירת מחדל:</b> {default_radius} ק"מ\n'
    "💰 <b>מחיר מקסימלי:</b> {price_display}\n\n"
    "בחר הגדרה לשינוי:"
)

SAVED_TOAST = "✅ ההגדרה נשמרה!"


async def _render_main_text(chat_id: int) -> str:
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    return SETTINGS_MAIN_TEMPLATE.format(
        connector_display=CONNECTOR_DISPLAY.get(user_settings.connector_filter, "הכל (ללא סינון)"),
        speed_display=SPEED_DISPLAY.get(user_settings.speed_filter, "הכל (ללא סינון)"),
        default_radius=user_settings.default_radius,
        price_display=PRICE_DISPLAY.get(user_settings.max_price, "ללא הגבלה"),
    )


async def show_main(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    text = await _render_main_text(chat_id)
    await event.edit(text, buttons=settings_main_keyboard(), parse_mode="html")


async def show_connector(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    await event.edit(
        "🔌 בחר סוג שקע מועדף:",
        buttons=connector_keyboard(user_settings.connector_filter),
    )


async def show_speed(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    await event.edit(
        "⚡ בחר מהירות טעינה מועדפת:",
        buttons=speed_keyboard(user_settings.speed_filter),
    )


async def show_range(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    await event.edit(
        '📏 בחר רדיוס ברירת מחדל לחיפוש:',
        buttons=range_keyboard(user_settings.default_radius),
    )


async def show_price(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    await event.edit(
        '💰 בחר מחיר מקסימלי לקוט"ש:',
        buttons=price_keyboard(user_settings.max_price),
    )



async def _save_and_return(event: events.CallbackQuery.Event, **field) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    sender = await event.get_sender()
    user_settings.first_name = getattr(sender, "first_name", "") or ""
    user_settings.username = getattr(sender, "username", "") or ""
    for key, value in field.items():
        setattr(user_settings, key, value)
    await upsert_user(user_settings, app_settings.users_db_path)
    await event.answer(SAVED_TOAST, alert=False)
    text = await _render_main_text(chat_id)
    await event.edit(text, buttons=settings_main_keyboard(), parse_mode="html")


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.CallbackQuery(pattern=rb"^settings:"))
    async def handle_settings(event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        try:
            if data == "settings:main":
                await show_main(event)
            elif data == "settings:connector":
                await show_connector(event)
            elif data == "settings:speed":
                await show_speed(event)
            elif data == "settings:range":
                await show_range(event)
            elif data == "settings:price":
                await show_price(event)
        except Exception:
            logger.exception("error handling settings callback for chat_id=%s", event.chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

    @client.on(events.CallbackQuery(pattern=rb"^filter:"))
    async def handle_filter(event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        # Expect exactly "filter:<type>:<value>" — 3 parts minimum.
        if len(parts) < 3:
            await event.answer(ERROR_GENERIC, alert=True)
            return
        filter_type = parts[1]
        value = parts[2]
        try:
            if filter_type == "connector":
                if value not in ("ALL", "CCS2_COMBO", "TYPE2", "CHADEMO"):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return(event, connector_filter=value)
            elif filter_type == "speed":
                if value not in ("ALL", "SLOW", "FAST", "ULTRA"):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return(event, speed_filter=value)
            elif filter_type == "range":
                try:
                    radius = int(value)
                except ValueError:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                if not (1 <= radius <= 200):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return(event, default_radius=radius)
            elif filter_type == "price":
                if value == "NONE":
                    max_price = None
                else:
                    try:
                        max_price = float(value)
                    except ValueError:
                        await event.answer(ERROR_GENERIC, alert=True)
                        return
                    if max_price < 0:
                        await event.answer(ERROR_GENERIC, alert=True)
                        return
                await _save_and_return(event, max_price=max_price)
            else:
                # Unknown filter type — ignore silently (defensive).
                await event.answer(ERROR_GENERIC, alert=True)
        except Exception:
            logger.exception("error handling filter callback for chat_id=%s", event.chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

