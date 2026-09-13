import logging

from telethon import TelegramClient, events

from bot.config import settings as app_settings
from bot.handlers.location import ERROR_GENERIC
from bot.keyboards.inline import (
    connector_keyboard,
    map_format_keyboard,
    price_keyboard,
    range_keyboard,
    settings_main_keyboard,
    speed_keyboard,
    trip_consumption_keyboard,
    trip_margin_keyboard,
    trip_power_keyboard,
    trip_price_keyboard,
    trip_providers_keyboard,
    trip_range_keyboard,
    trip_settings_main_keyboard,
)
from bot.services.station_search import get_distinct_providers
from bot.states import get_session
from bot.services.trip_planner import (
    TRIP_CONSUMPTION_KWH_PER_100KM,
    TRIP_DEFAULT_REAL_RANGE_KM,
    TRIP_DEFAULT_SAFETY_MARGIN_PERCENT,
    TRIP_PREFERRED_MIN_POWER_KW,
)
from bot.storage.users_db import DEFAULT_MAP_FORMAT, get_user_settings, upsert_user

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

MAP_FORMAT_DISPLAY = {
    "interactive": "🗺️ מפה אינטראקטיבית",
    "document": "📄 קובץ (חד, ללא דחיסה)",
    "photo": "🖼️ תמונה (תצוגה ישירה)",
}

SETTINGS_MAIN_TEMPLATE = (
    "⚙️ <b>הגדרות חיפוש</b>\n\n"
    "🔌 <b>סוג שקע:</b> {connector_display}\n"
    "⚡ <b>מהירות טעינה:</b> {speed_display}\n"
    '📏 <b>רדיוס ברירת מחדל:</b> {default_radius} ק"מ\n'
    "💰 <b>מחיר מקסימלי:</b> {price_display}\n"
    "🗺️ <b>תצוגת מפה:</b> {map_format_display}\n\n"
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
        map_format_display=MAP_FORMAT_DISPLAY.get(user_settings.map_format, MAP_FORMAT_DISPLAY[DEFAULT_MAP_FORMAT]),
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


async def show_map_format(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    await event.edit(
        "🗺️ <b>איך לקבל את המפה אחרי חיפוש?</b>\n\n"
        "• <b>מפה אינטראקטיבית:</b> קישור למפה חיה עם כל העמדות, סינון, חיפוש ותכנון נסיעה. "
        "נפתחת ממורכזת על אזור החיפוש (מומלץ).\n"
        "• <b>קובץ (Document):</b> תמונת מפה סטטית ללא דחיסה, באיכות וחדות מקסימלית (קובץ להורדה/פתיחה).\n"
        "• <b>תמונה (Photo):</b> תמונת מפה סטטית שמוצגת מיד בצ'אט (נדחסת מעט ע\"י טלגרם).",
        buttons=map_format_keyboard(user_settings.map_format),
        parse_mode="html",
    )


TRIP_SETTINGS_TEMPLATE = (
    "🚗 <b>הגדרות מצב נסיעה</b>\n\n"
    '🔋 <b>טווח רכב אמיתי:</b> {range_km:.0f} ק"מ\n'
    "🛡️ <b>מרווח ביטחון:</b> {margin:.0f}%\n"
    "🔢 <b>צריכת חשמל:</b> {consumption:.0f} kWh/100 ק\"מ\n"
    "⚡ <b>הספק מינימלי מועדף:</b> {power:.0f}kW\n"
    "💰 <b>מחיר מקסימלי לטעינה:</b> {price_display}\n"
    "🏭 <b>מפעילים מועדפים:</b> {providers_display}\n\n"
    "בחר הגדרה לשינוי:"
)


def _trip_providers_display(providers: list) -> str:
    if not providers:
        return "הכל (ללא הגבלה)"
    shown = ", ".join(providers[:3])
    if len(providers) > 3:
        shown += f" ועוד {len(providers) - 3}"
    return shown


async def _render_trip_main_text(chat_id: int) -> str:
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    return TRIP_SETTINGS_TEMPLATE.format(
        range_km=user_settings.trip_real_range_km or TRIP_DEFAULT_REAL_RANGE_KM,
        margin=user_settings.trip_safety_margin_percent or TRIP_DEFAULT_SAFETY_MARGIN_PERCENT,
        consumption=user_settings.trip_consumption_kwh_100km or TRIP_CONSUMPTION_KWH_PER_100KM,
        power=user_settings.trip_min_power_kw or TRIP_PREFERRED_MIN_POWER_KW,
        price_display=PRICE_DISPLAY.get(user_settings.trip_max_price, "ללא הגבלה"),
        providers_display=_trip_providers_display(user_settings.trip_allowed_providers),
    )


def _trip_settings_keyboard(chat_id: int) -> list:
    """כשמגיעים להגדרות מתוך תכנון פעיל, כפתור החזרה מחזיר לשלב שבו המשתמש היה."""
    return trip_settings_main_keyboard(in_trip_flow=get_session(chat_id).trip_state is not None)


async def show_trip_main(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    text = await _render_trip_main_text(chat_id)
    await event.edit(text, buttons=_trip_settings_keyboard(chat_id), parse_mode="html")


async def show_trip_range(event: events.CallbackQuery.Event) -> None:
    user_settings = await get_user_settings(event.chat_id, app_settings.users_db_path)
    await event.edit(
        '🔋 בחר טווח נסיעה אמיתי של הרכב (לא הטווח המוצהר):',
        buttons=trip_range_keyboard(user_settings.trip_real_range_km or TRIP_DEFAULT_REAL_RANGE_KM),
    )


async def show_trip_margin(event: events.CallbackQuery.Event) -> None:
    user_settings = await get_user_settings(event.chat_id, app_settings.users_db_path)
    await event.edit(
        "🛡️ בחר מרווח ביטחון (אחוז סוללה שיישאר בהגעה, גם לעמדת טעינה וגם ליעד הסופי):",
        buttons=trip_margin_keyboard(user_settings.trip_safety_margin_percent or TRIP_DEFAULT_SAFETY_MARGIN_PERCENT),
    )


async def show_trip_consumption(event: events.CallbackQuery.Event) -> None:
    user_settings = await get_user_settings(event.chat_id, app_settings.users_db_path)
    await event.edit(
        '🔢 בחר צריכת חשמל משוערת (kWh ל-100 ק"מ):',
        buttons=trip_consumption_keyboard(user_settings.trip_consumption_kwh_100km),
    )


async def show_trip_power(event: events.CallbackQuery.Event) -> None:
    user_settings = await get_user_settings(event.chat_id, app_settings.users_db_path)
    await event.edit(
        "⚡ בחר הספק טעינה מינימלי מועדף לעצירות בדרך:",
        buttons=trip_power_keyboard(user_settings.trip_min_power_kw or TRIP_PREFERRED_MIN_POWER_KW),
    )


async def show_trip_price(event: events.CallbackQuery.Event) -> None:
    user_settings = await get_user_settings(event.chat_id, app_settings.users_db_path)
    await event.edit(
        '💰 בחר מחיר מקסימלי לקוט"ש לעצירות טעינה בדרך:',
        buttons=trip_price_keyboard(user_settings.trip_max_price),
    )


async def show_trip_providers(event: events.CallbackQuery.Event) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    all_providers = await get_distinct_providers(app_settings.db_path)
    await event.edit(
        "🏭 בחר מפעילים מועדפים (בחירה מרובה). ללא בחירה - כל המפעילים מותרים:",
        buttons=trip_providers_keyboard(all_providers, user_settings.trip_allowed_providers),
    )


async def _save_and_return_to_trip(event: events.CallbackQuery.Event, **field) -> None:
    chat_id = event.chat_id
    user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
    sender = await event.get_sender()
    user_settings.first_name = getattr(sender, "first_name", "") or ""
    user_settings.username = getattr(sender, "username", "") or ""
    for key, value in field.items():
        setattr(user_settings, key, value)
    await upsert_user(user_settings, app_settings.users_db_path)
    await event.answer(SAVED_TOAST, alert=False)
    text = await _render_trip_main_text(chat_id)
    await event.edit(text, buttons=_trip_settings_keyboard(chat_id), parse_mode="html")


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
            elif data == "settings:mapfmt":
                await show_map_format(event)
            elif data.startswith("settings:mapfmt:"):
                fmt_val = data.split(":", 2)[2]
                if fmt_val not in ("interactive", "document", "photo"):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return(event, map_format=fmt_val)
            elif data == "settings:trip":
                await show_trip_main(event)
            elif data == "settings:trip:range":
                await show_trip_range(event)
            elif data == "settings:trip:margin":
                await show_trip_margin(event)
            elif data == "settings:trip:consumption":
                await show_trip_consumption(event)
            elif data == "settings:trip:power":
                await show_trip_power(event)
            elif data == "settings:trip:price":
                await show_trip_price(event)
            elif data == "settings:trip:providers":
                await show_trip_providers(event)
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
            elif filter_type == "mapfmt":
                if value not in ("interactive", "document", "photo"):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return(event, map_format=value)
            elif filter_type == "triprange":
                try:
                    range_km = float(value)
                except ValueError:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                if not (100.0 <= range_km <= 800.0):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return_to_trip(event, trip_real_range_km=range_km)
            elif filter_type == "tripmargin":
                try:
                    margin = float(value)
                except ValueError:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                if not (0.0 <= margin <= 50.0):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return_to_trip(event, trip_safety_margin_percent=margin)
            elif filter_type == "tripconsumption":
                if value == "DEFAULT":
                    consumption = None
                else:
                    try:
                        consumption = float(value)
                    except ValueError:
                        await event.answer(ERROR_GENERIC, alert=True)
                        return
                    if not (5.0 <= consumption <= 50.0):
                        await event.answer(ERROR_GENERIC, alert=True)
                        return
                await _save_and_return_to_trip(event, trip_consumption_kwh_100km=consumption)
            elif filter_type == "trippower":
                try:
                    power_kw = float(value)
                except ValueError:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                if not (1.0 <= power_kw <= 400.0):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                await _save_and_return_to_trip(event, trip_min_power_kw=power_kw)
            elif filter_type == "tripprice":
                if value == "NONE":
                    trip_max_price = None
                else:
                    try:
                        trip_max_price = float(value)
                    except ValueError:
                        await event.answer(ERROR_GENERIC, alert=True)
                        return
                    if trip_max_price < 0:
                        await event.answer(ERROR_GENERIC, alert=True)
                        return
                await _save_and_return_to_trip(event, trip_max_price=trip_max_price)
            elif filter_type == "tripprov":
                try:
                    idx = int(value)
                except ValueError:
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                all_providers = await get_distinct_providers(app_settings.db_path)
                if not (0 <= idx < len(all_providers)):
                    await event.answer(ERROR_GENERIC, alert=True)
                    return
                provider = all_providers[idx]
                chat_id = event.chat_id
                user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
                selected = list(user_settings.trip_allowed_providers)
                if provider in selected:
                    selected.remove(provider)
                else:
                    selected.append(provider)
                sender = await event.get_sender()
                user_settings.first_name = getattr(sender, "first_name", "") or ""
                user_settings.username = getattr(sender, "username", "") or ""
                user_settings.trip_allowed_providers = selected
                await upsert_user(user_settings, app_settings.users_db_path)
                await event.answer(SAVED_TOAST, alert=False)
                await event.edit(
                    "🏭 בחר מפעילים מועדפים (בחירה מרובה). ללא בחירה - כל המפעילים מותרים:",
                    buttons=trip_providers_keyboard(all_providers, selected),
                )
            elif filter_type == "tripprovreset":
                chat_id = event.chat_id
                user_settings = await get_user_settings(chat_id, app_settings.users_db_path)
                user_settings.trip_allowed_providers = []
                await upsert_user(user_settings, app_settings.users_db_path)
                await event.answer(SAVED_TOAST, alert=False)
                all_providers = await get_distinct_providers(app_settings.db_path)
                await event.edit(
                    "🏭 בחר מפעילים מועדפים (בחירה מרובה). ללא בחירה - כל המפעילים מותרים:",
                    buttons=trip_providers_keyboard(all_providers, []),
                )
            else:
                # Unknown filter type — ignore silently (defensive).
                await event.answer(ERROR_GENERIC, alert=True)
        except Exception:
            logger.exception("error handling filter callback for chat_id=%s", event.chat_id)
            await event.answer(ERROR_GENERIC, alert=True)

