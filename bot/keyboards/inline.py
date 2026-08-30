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
            Button.inline("↩️ חזרה לתוצאות", data=b"nav:back_to_results"),
        ],
    ]


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

