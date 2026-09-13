"""המסכים של זרימת הנסיעה: טקסט + כפתורים, בלי שום תלות בטלגרם.

כל הזרימה מתנהלת בהודעה אחת שנערכת שוב ושוב (session.trip_message_id), ולכן כל
שלב מיוצג כאן כפונקציה טהורה שמחזירה (טקסט, כפתורים). זה גם מה שמאפשר לבדוק
בטסט רגיל שאין מסך שמשאיר את המשתמש בלי כפתור המשך.
"""
import html
from typing import Optional

from telethon.tl.custom import Button

from bot.keyboards.inline import trip_geocode_selection_keyboard, trip_myplans_keyboard
from bot.services.formatter import format_duration, format_trip_plan
from bot.services.station_search import get_station_max_power

# אחוזי הסוללה שמוצעים כגריד כפתורים. ההקלדה נשארה אפשרית כקיצור, אבל היא כבר
# לא הדרך היחידה להתקדם (זה מה שהשאיר מסכים בלי כפתורים).
BATTERY_CHOICES = (20, 40, 50, 60, 70, 80, 90, 100)

# מספור העצירות בטקסט תואם למספור הסמנים על המפה.
STOP_DIGITS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")


def stop_label(index: int) -> str:
    return STOP_DIGITS[index - 1] if 1 <= index <= len(STOP_DIGITS) else f"{index}."


def _cancel_row() -> list:
    return [Button.inline("❌ ביטול", data=b"trip:cancel")]


def _restart_row() -> list:
    return [
        Button.inline("🚗 תכנון נסיעה חדשה", data=b"trip:new"),
        Button.inline("🕘 התוכניות שלי", data=b"trip:myplans"),
    ]


def _stops_phrase(num_stops: int) -> str:
    if num_stops == 0:
        return "בלי עצירות טעינה"
    if num_stops == 1:
        return "עצירת טעינה אחת"
    return f"{num_stops} עצירות טעינה"


def render_ask_destination() -> tuple[str, list]:
    text = (
        "🚗 <b>תכנון נסיעה</b>\n\n"
        "לאן נוסעים? שלח עיר, כתובת (רחוב ופסיק ועיר) או קואורדינטות — "
        "לדוגמה <i>אילת</i> או <code>29.557, 34.952</code>.\n\n"
        "💡 כדאי לוודא שפרמטרי הרכב והעדפות הטעינה מעודכנים לפני התכנון."
    )
    buttons = [
        [
            Button.inline("⚙️ הגדרות נסיעה", data=b"settings:trip"),
            Button.inline("🕘 התוכניות שלי", data=b"trip:myplans"),
        ],
        _cancel_row(),
    ]
    return text, buttons


def render_ask_origin(dest_name: str, is_private: bool) -> tuple[str, list]:
    text = (
        f"🏁 <b>היעד:</b> {html.escape(dest_name)}\n\n"
        "📍 מאיפה יוצאים? שלח עיר, כתובת או קואורדינטות.\n"
        "אפשר גם לצרף מיקום דרך 📎 ← מיקום."
    )
    rows = [[Button.inline("🔄 יעד אחר", data=b"trip:redest")]]
    if is_private:
        # בקשת GPS בלחיצה אחת מחייבת ReplyKeyboard, שאי אפשר לצרף לעריכת הודעה -
        # ולכן היא מסלול אופציונלי (הודעה זמנית שנמחקת) ולא חלק מהזרימה עצמה.
        rows.append([Button.inline("📡 שיתוף מיקום GPS", data=b"trip:gps")])
    rows.append(_cancel_row())
    return text, rows


def render_ask_battery(error: Optional[str]) -> tuple[str, list]:
    """מסך אחוז הסוללה. האחוז משתנה בכל נסיעה, ולכן תמיד נשאל מחדש בלי ברירת מחדל.

    שגיאת קלט נכנסת כשורה מעל אותו מסך - לא מחליפה אותו."""
    lines = []
    if error:
        lines.extend([error, ""])
    lines.append("🔋 <b>באיזה אחוז סוללה יוצאים לדרך?</b>")
    lines.append("בחר מהכפתורים, או פשוט שלח מספר בין 1 ל-100.")

    rows = []
    for start in range(0, len(BATTERY_CHOICES), 4):
        rows.append([
            Button.inline(f"{p}%", data=f"tripbatt:set:{p}".encode("utf-8"))
            for p in BATTERY_CHOICES[start:start + 4]
        ])
    rows.append([Button.inline("⚙️ הגדרות נסיעה", data=b"settings:trip")])
    rows.append(_cancel_row())
    return "\n".join(lines), rows


def render_geocode_choice(query: str, candidates: list[dict]) -> tuple[str, list]:
    text = (
        f'📍 <b>נמצאו כמה מיקומים עבור "<i>{html.escape(query)}</i>":</b>\n'
        "בחר את המיקום הנכון:"
    )
    return text, trip_geocode_selection_keyboard(candidates)


def render_planning() -> tuple[str, list]:
    text = "🧭 מחשב מסלול ובוחר עמדות טעינה לאורך הדרך..."
    return text, [_cancel_row()]


def render_missing_city() -> tuple[str, list]:
    text = (
        "📍 בלי שם יישוב קשה לאתר כתובת במדויק. כתוב רחוב או שכונה, פסיק, ואז עיר —\n"
        "למשל <i>הרצל 7, חיפה</i>.\n\n"
        "אפשר גם לשלוח קואורדינטות (<code>32.0853, 34.7818</code>)."
    )
    return text, [_cancel_row()]


def render_no_geocode_results(query: str) -> tuple[str, list]:
    text = (
        f'❌ <b>לא מצאנו את "<i>{html.escape(query)}</i>"</b>\n\n'
        "נסה ניסוח אחר, או שלח קואורדינטות."
    )
    return text, [_cancel_row()]


def render_outside_israel() -> tuple[str, list]:
    text = (
        "❌ <b>המסלול חורג מגבולות ישראל</b>\n\n"
        "המאגר מכיל עמדות טעינה בארץ בלבד. שלח יעד אחר כדי להמשיך."
    )
    return text, [_cancel_row()]


def render_low_battery(battery_percent: float, safety_margin_percent: float) -> tuple[str, list]:
    text = (
        f"🪫 <b>{battery_percent:.0f}% זה מתחת למרווח הביטחון שהגדרת ({safety_margin_percent:.0f}%)</b>\n\n"
        "בחר אחוז גבוה יותר, או הקטן את מרווח הביטחון בהגדרות הנסיעה."
    )
    buttons = [
        [Button.inline("🔋 אחוז אחר", data=b"trip:battery")],
        [Button.inline("⚙️ הגדרות נסיעה", data=b"settings:trip")],
        _cancel_row(),
    ]
    return text, buttons


def render_expired() -> tuple[str, list]:
    text = (
        "⌛ <b>הזרימה הזו כבר לא פעילה</b>\n\n"
        "אפשר להתחיל תכנון חדש או לפתוח תוכנית שכבר שמורה."
    )
    return text, [_restart_row()]


def render_generic_error() -> tuple[str, list]:
    text = "❌ משהו השתבש בדרך. אפשר לנסות שוב בעוד רגע."
    buttons = [
        [Button.inline("🔄 נסה שוב", data=b"trip:new")],
        _cancel_row(),
    ]
    return text, buttons


def render_plan_not_found() -> tuple[str, list]:
    text = "❌ התוכנית לא נמצאה — ייתכן שנמחקה (תוכניות נשמרות 30 יום)."
    return text, [_restart_row()]


def render_no_plans() -> tuple[str, list]:
    text = (
        "🕘 <b>אין עדיין תוכניות שמורות</b>\n\n"
        "כל נסיעה שתתכנן תישמר כאן ל-30 יום."
    )
    return text, [[Button.inline("🚗 תכנון נסיעה חדשה", data=b"trip:new")]]


def render_plans_list(plans: list[dict]) -> tuple[str, list]:
    text = "🕘 <b>התוכניות האחרונות שלך</b>\n\nבחר תוכנית כדי לפתוח אותה שוב:"
    return text, trip_myplans_keyboard(plans)


def _stop_lines(plan: dict) -> list[str]:
    """שורה תמציתית לכל עצירה, ממוספרת בדיוק כמו הסמנים על המפה."""
    min_power_kw = (plan.get("car_params") or {}).get("min_power_kw")
    lines = []
    for stop in plan.get("stops") or []:
        station = stop["station"]
        idx = stop["segment_index"]
        name = station.get("name") or "עמדת טעינה"
        provider = station.get("provider_name") or "מפעיל לא ידוע"
        power = station.get("max_power")
        if power is None:
            power = get_station_max_power(station.get("connectors"))
        details = [provider, f"{power:.0f}kW"]
        price = station.get("max_per_kwh")
        if price is not None:
            details.append(f'{price:.2f} ₪ לקוט"ש')
        lines.append(
            f'{stop_label(idx)} <b>{html.escape(name)}</b> — אחרי {stop["distance_from_origin_km"]:.0f} ק"מ'
        )
        lines.append(f"     {' · '.join(details)}")
        relaxation = stop.get("relaxation") or {}
        if relaxation.get("providers") or relaxation.get("price") or (
            min_power_kw is not None
            and relaxation.get("power_kw") is not None
            and relaxation["power_kw"] < min_power_kw
        ):
            lines.append("     ⚠️ נבחרה בהקלת ההעדפות")
    return lines


def render_plan(plan: dict, origin_name: str, dest_name: str, plan_id: Optional[int]) -> tuple[str, list]:
    """תקציר התוכנית - נועד להיקרא במבט אחד לצד מפת המסלול שנשלחת מתחתיו."""
    num_stops = plan["num_stops"]
    lines = [
        f"🚗 <b>{html.escape(origin_name)} ← {html.escape(dest_name)}</b>",
        f'📏 {plan["total_distance_km"]:.0f} ק"מ · ⏱️ {format_duration(plan["duration_hours"])} · '
        f"🔋 {_stops_phrase(num_stops)}",
        "",
    ]
    if num_stops == 0:
        lines.append("✅ הטווח מספיק להגעה ישירה, בלי לעצור בדרך.")
    else:
        lines.extend(_stop_lines(plan))

    missing = plan.get("missing_segments") or []
    if missing:
        lines.append("")
        for segment in missing:
            lines.append(f'⚠️ לא נמצאה עמדה מתאימה אחרי {segment["distance_km"]:.0f} ק"מ מהמוצא.')

    lines.append("")
    lines.append("🗺️ המסלול והעצירות מסומנים במפה שמתחת.")

    rows = []
    for stop in plan.get("stops") or []:
        station = stop["station"]
        rows.append([Button.url(
            f'🚗 ניווט לעצירה {stop["segment_index"]}',
            url=f'https://waze.com/ul?ll={station["lat"]},{station["lng"]}&navigate=yes',
        )])
    if plan_id is not None:
        rows.append([Button.inline("📋 פירוט מלא", data=f"trip:details:{plan_id}".encode("utf-8"))])
    rows.append(_restart_row())
    return "\n".join(lines), rows


def render_plan_details(plan: dict, origin_name: str, dest_name: str, plan_id: Optional[int]) -> tuple[str, list]:
    """הטקסט המלא של התוכנית (הנחות החישוב, פרמטרי הרכב, הערות הקלה)."""
    rows = []
    if plan_id is not None:
        rows.append([Button.inline("↩️ חזרה לתקציר", data=f"trip:plan:{plan_id}".encode("utf-8"))])
    rows.append(_restart_row())
    return format_trip_plan(plan, origin_name, dest_name), rows
