from typing import Optional
from urllib.parse import urlencode

from telethon.tl.custom import Button
from telethon.tl.types import KeyboardButtonWebView

from bot.config import WEBAPP_URL


def _webapp_button(text: str, lat: float = None, lng: float = None, is_private: bool = True):
    """כפתור אינליין שפותח את מפת העמדות.

    בצ'אט פרטי - כפתור web_app (KeyboardButtonWebView) שפותח את המפה בתוך טלגרם.
    בקבוצות - טלגרם אוסרת כפתורי web_app (BUTTON_TYPE_INVALID), אז נופלים לכפתור
    URL רגיל שפותח את אותה מפה בדפדפן החיצוני.
    """
    url = WEBAPP_URL
    if lat is not None and lng is not None:
        url = f"{WEBAPP_URL}?{urlencode({'lat': lat, 'lng': lng})}"
    if is_private:
        return KeyboardButtonWebView(text, url)
    return Button.url(text, url)


def station_card_keyboard(
    station_id: int,
    idx: int,          # 0-based
    total: int,
    lat: float,
    lng: float,
    sort_by: str = "distance",
    user_lat: float = None,
    user_lng: float = None,
    is_private: bool = True,
) -> list:
    waze_url = f"https://waze.com/ul?ll={lat},{lng}&navigate=yes"
    gmap_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"

    prev_disabled = idx == 0
    next_disabled = idx == total - 1

    dist_btn_text = "📏 לפי מרחק ✅" if sort_by == "distance" else "📏 לפי מרחק"
    speed_btn_text = "⚡ לפי מהירות ✅" if sort_by == "speed" else "⚡ לפי מהירות"

    rows = [
        [
            Button.inline(
                "◀ הקודמת" if not prev_disabled else "·",
                data=b"nav:prev" if not prev_disabled else b"nav:noop",
            ),
            Button.inline(
                f"{idx + 1} / {total}",
                data=b"nav:noop",
            ),
            Button.inline(
                "הבאה ▶" if not next_disabled else "·",
                data=b"nav:next" if not next_disabled else b"nav:noop",
            ),
        ],
        [
            Button.inline(dist_btn_text, data=b"sort:distance"),
            Button.inline(speed_btn_text, data=b"sort:speed"),
        ],
        [
            Button.url("🚗 ניווט ב-Waze", url=waze_url),
            Button.url("🗺️ Google Maps", url=gmap_url),
        ],
        [
            Button.inline("🔄 חיפוש חדש", data=b"nav:new_search"),
            Button.inline("⚙️ הגדרות", data=b"settings:main"),
        ],
    ]
    rows.insert(
        3,
        [_webapp_button("🗺️ מפת עמדות", lat=user_lat, lng=user_lng, is_private=is_private)],
    )
    return rows


def welcome_keyboard(is_private: bool = True) -> list:
    rows = [
        [Button.inline("📍 שיתוף מיקום GPS", data=b"loc:request")],
    ]
    rows.append([_webapp_button("🗺️ מפת עמדות", is_private=is_private)])
    rows.append([Button.inline("⚙️ הגדרות", data=b"settings:main")])
    rows.append([
        Button.url("📢 ערוץ עדכונים", "https://t.me/YD_IL_BOTS"),
        Button.inline("ℹ️ איך הבוט עובד?", data=b"info:how"),
    ])
    return rows


def no_results_keyboard(current_radius: int) -> list:
    rows = []
    if current_radius < 20:
        rows.append([Button.inline('🔍 הרחב ל-20 ק"מ', data=b"range:20")])
    if current_radius < 40:
        rows.append([Button.inline('🔍 הרחב ל-40 ק"מ', data=b"range:40")])
    if current_radius < 100:
        rows.append([Button.inline('🔍 הרחב ל-100 ק"מ', data=b"range:100")])
    rows.append([
        Button.inline("⚙️ הגדרות סינון", data=b"settings:main"),
        Button.inline("🔄 חיפוש חדש", data=b"nav:new_search"),
    ])
    return rows


def geocode_selection_keyboard(candidates: list[dict]) -> list:
    """מקלדת בחירה כאשר נמצאו מספר תוצאות עבור חיפוש כתובת טקסטואלי."""
    rows = []
    for i, item in enumerate(candidates):
        lat = item["lat"]
        lng = item["lng"]
        name = item["name"]
        btn_text = f"📍 {name}"
        if len(btn_text) > 42:
            btn_text = btn_text[:39] + "..."
        # קידוד אינדקס וקואורדינטות ב-callback data (עד 64 בתים בטלגרם)
        data = f"geo:{i}:{lat:.5f}:{lng:.5f}".encode("utf-8")
        rows.append([Button.inline(btn_text, data=data)])
    rows.append([Button.inline("❌ ביטול", data=b"nav:new_search")])
    return rows


def trip_geocode_selection_keyboard(candidates: list[dict]) -> list:
    """מקלדת בחירה כאשר נמצאו מספר תוצאות עבור יעד/מוצא במצב נסיעה (Trip Mode)."""
    rows = []
    for i, item in enumerate(candidates):
        lat = item["lat"]
        lng = item["lng"]
        name = item["name"]
        btn_text = f"📍 {name}"
        if len(btn_text) > 42:
            btn_text = btn_text[:39] + "..."
        data = f"tripgeo:{i}:{lat:.5f}:{lng:.5f}".encode("utf-8")
        rows.append([Button.inline(btn_text, data=data)])
    rows.append([Button.inline("❌ ביטול", data=b"nav:new_search")])
    return rows


def trip_battery_choice_keyboard(default_percent: float) -> list:
    """מקלדת לבחירת אחוז סוללה בתחילת תכנון נסיעה, כשקיימת ברירת מחדל אישית שמורה."""
    return [
        [Button.inline(f"🔋 המשך עם {default_percent:.0f}% (ברירת מחדל)", data=b"tripbatt:default")],
        [Button.inline("✏️ הזן אחוז אחר לנסיעה זו", data=b"tripbatt:custom")],
    ]


def trip_plan_keyboard(stops: list[dict]) -> list:
    """מקלדת עם כפתור ניווט ב-Waze לכל עצירת טעינה בתוכנית הנסיעה."""
    rows = []
    for stop in stops:
        station = stop["station"]
        lat, lng = station["lat"], station["lng"]
        idx = stop["segment_index"]
        waze_url = f"https://waze.com/ul?ll={lat},{lng}&navigate=yes"
        rows.append([Button.url(f"🚗 ניווט לעצירה {idx}", url=waze_url)])
    rows.append([
        Button.inline("🔄 חיפוש חדש", data=b"nav:new_search"),
        Button.inline("⚙️ הגדרות נסיעה", data=b"settings:trip"),
    ])
    return rows


def settings_main_keyboard() -> list:
    return [
        [
            Button.inline("🔌 סוג שקע", data=b"settings:connector"),
            Button.inline("⚡ מהירות טעינה", data=b"settings:speed"),
        ],
        [
            Button.inline("📏 רדיוס ברירת מחדל", data=b"settings:range"),
            Button.inline("💰 מחיר מקסימלי", data=b"settings:price"),
        ],
        [
            Button.inline("🗺️ מפה: קובץ / תמונה", data=b"settings:mapfmt"),
        ],
        [
            Button.inline("🚗 הגדרות נסיעה", data=b"settings:trip"),
        ],
        [
            Button.inline("↩️ חזרה לתוצאות", data=b"nav:back_to_results"),
        ],
    ]


def trip_settings_main_keyboard() -> list:
    return [
        [
            Button.inline("🔋 טווח רכב אמיתי", data=b"settings:trip:range"),
            Button.inline("🔌 אחוז סוללה", data=b"settings:trip:battery"),
        ],
        [
            Button.inline("🛡️ מרווח ביטחון", data=b"settings:trip:margin"),
            Button.inline("🔢 צריכת חשמל", data=b"settings:trip:consumption"),
        ],
        [
            Button.inline("⚡ הספק מינימלי", data=b"settings:trip:power"),
            Button.inline("💰 מחיר מקסימלי", data=b"settings:trip:price"),
        ],
        [
            Button.inline("🏭 מפעילים מועדפים", data=b"settings:trip:providers"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:main"),
        ],
    ]


def trip_range_keyboard(current: float) -> list:
    def mark(val: float, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(250.0, '250 ק"מ'), data=b"filter:triprange:250"),
            Button.inline(mark(300.0, '300 ק"מ'), data=b"filter:triprange:300"),
            Button.inline(mark(350.0, '350 ק"מ'), data=b"filter:triprange:350"),
        ],
        [
            Button.inline(mark(400.0, '400 ק"מ'), data=b"filter:triprange:400"),
            Button.inline(mark(450.0, '450 ק"מ'), data=b"filter:triprange:450"),
            Button.inline(mark(500.0, '500 ק"מ'), data=b"filter:triprange:500"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:trip"),
        ],
    ]


def trip_battery_keyboard(current: Optional[float]) -> list:
    def mark(val: Optional[float], label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(60.0, "60%"), data=b"filter:tripbattery:60"),
            Button.inline(mark(70.0, "70%"), data=b"filter:tripbattery:70"),
            Button.inline(mark(80.0, "80%"), data=b"filter:tripbattery:80"),
        ],
        [
            Button.inline(mark(90.0, "90%"), data=b"filter:tripbattery:90"),
            Button.inline(mark(100.0, "100%"), data=b"filter:tripbattery:100"),
        ],
        [
            Button.inline(mark(None, "🔄 ישאל בכל תכנון"), data=b"filter:tripbattery:ASK"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:trip"),
        ],
    ]


def trip_margin_keyboard(current: float) -> list:
    def mark(val: float, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(5.0, "5%"), data=b"filter:tripmargin:5"),
            Button.inline(mark(10.0, "10%"), data=b"filter:tripmargin:10"),
            Button.inline(mark(15.0, "15%"), data=b"filter:tripmargin:15"),
        ],
        [
            Button.inline(mark(20.0, "20%"), data=b"filter:tripmargin:20"),
            Button.inline(mark(25.0, "25%"), data=b"filter:tripmargin:25"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:trip"),
        ],
    ]


def trip_consumption_keyboard(current: Optional[float]) -> list:
    def mark(val: Optional[float], label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(14.0, "14"), data=b"filter:tripconsumption:14"),
            Button.inline(mark(16.0, "16"), data=b"filter:tripconsumption:16"),
            Button.inline(mark(18.0, "18"), data=b"filter:tripconsumption:18"),
        ],
        [
            Button.inline(mark(20.0, "20"), data=b"filter:tripconsumption:20"),
            Button.inline(mark(22.0, "22"), data=b"filter:tripconsumption:22"),
        ],
        [
            Button.inline(mark(None, "🔄 ברירת מחדל (18)"), data=b"filter:tripconsumption:DEFAULT"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:trip"),
        ],
    ]


def trip_power_keyboard(current: Optional[float]) -> list:
    def mark(val: Optional[float], label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(50.0, "50kW"), data=b"filter:trippower:50"),
            Button.inline(mark(100.0, "100kW"), data=b"filter:trippower:100"),
        ],
        [
            Button.inline(mark(150.0, "150kW"), data=b"filter:trippower:150"),
            Button.inline(mark(200.0, "200kW"), data=b"filter:trippower:200"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:trip"),
        ],
    ]


def trip_price_keyboard(current) -> list:
    def mark(val, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(None, "ללא הגבלה"), data=b"filter:tripprice:NONE"),
            Button.inline(mark(1.5, "עד 1.50 ₪"), data=b"filter:tripprice:1.5"),
        ],
        [
            Button.inline(mark(2.0, "עד 2.00 ₪"), data=b"filter:tripprice:2.0"),
            Button.inline(mark(2.5, "עד 2.50 ₪"), data=b"filter:tripprice:2.5"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:trip"),
        ],
    ]


def trip_providers_keyboard(all_providers: list[str], selected: list[str]) -> list:
    """מקלדת בחירה מרובה של מפעילים מועדפים למצב נסיעה, לפי אינדקס ברשימה הממוינת מה-DB."""
    rows = []
    row: list = []
    for i, provider in enumerate(all_providers):
        label = f"✅ {provider}" if provider in selected else provider
        if len(label) > 28:
            label = label[:25] + "..."
        row.append(Button.inline(label, data=f"filter:tripprov:{i}".encode("utf-8")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("🔄 איפוס (הכל)", data=b"filter:tripprovreset:1")])
    rows.append([Button.inline("↩️ חזרה", data=b"settings:trip")])
    return rows


def connector_keyboard(current: str) -> list:
    def mark(val: str, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark("CCS2_COMBO", "⚡ CCS2 (מהיר DC)"), data=b"filter:connector:CCS2_COMBO"),
            Button.inline(mark("TYPE2", "🔌 Type 2 (AC)"), data=b"filter:connector:TYPE2"),
        ],
        [
            Button.inline(mark("CHADEMO", "🇯🇵 CHAdeMO"), data=b"filter:connector:CHADEMO"),
            Button.inline(mark("ALL", "הכל (ללא סינון)"), data=b"filter:connector:ALL"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:main"),
        ],
    ]


def speed_keyboard(current: str) -> list:
    def mark(val: str, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [Button.inline(mark("SLOW", "🐢 רגילה (עד 22kW)"), data=b"filter:speed:SLOW")],
        [Button.inline(mark("FAST", "⚡ מהירה (50–150kW)"), data=b"filter:speed:FAST")],
        [Button.inline(mark("ULTRA", "🚀 אולטרה-מהירה (150kW+)"), data=b"filter:speed:ULTRA")],
        [Button.inline(mark("ALL", "הכל (ללא סינון)"), data=b"filter:speed:ALL")],
        [Button.inline("↩️ חזרה", data=b"settings:main")],
    ]


def range_keyboard(current: int) -> list:
    def mark(val: int, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(10, '10 ק"מ'), data=b"filter:range:10"),
            Button.inline(mark(20, '20 ק"מ'), data=b"filter:range:20"),
            Button.inline(mark(40, '40 ק"מ'), data=b"filter:range:40"),
            Button.inline(mark(100, '100 ק"מ'), data=b"filter:range:100"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:main"),
        ],
    ]


def price_keyboard(current) -> list:
    def mark(val, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(None, "ללא הגבלה"), data=b"filter:price:NONE"),
            Button.inline(mark(1.5, "עד 1.50 ₪"), data=b"filter:price:1.5"),
        ],
        [
            Button.inline(mark(2.0, "עד 2.00 ₪"), data=b"filter:price:2.0"),
            Button.inline(mark(2.5, "עד 2.50 ₪"), data=b"filter:price:2.5"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:main"),
        ],
    ]


def map_format_keyboard(current: str) -> list:
    def mark(val: str, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark("document", "📄 קובץ (חד, ללא דחיסה)"), data=b"settings:mapfmt:document"),
        ],
        [
            Button.inline(mark("photo", "🖼️ תמונה (תצוגה ישירה בצ'אט)"), data=b"settings:mapfmt:photo"),
        ],
        [
            Button.inline("↩️ חזרה", data=b"settings:main"),
        ],
    ]

