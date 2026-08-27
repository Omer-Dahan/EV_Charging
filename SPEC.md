# 📋 SPEC: בוט טלגרם — חיפוש עמדות טעינה לרכב חשמלי בישראל

> **ספרייה: Telethon בלבד (MTProto)** — לא aiogram / python-telegram-bot

**גרסה:** 1.1  
**תאריך:** אוגוסט 2026  
**מסמך:** `/home/vm/projects/ev-charging-bot/SPEC.md`  
**סטטוס:** מוכן לפיתוח ✅  
**Changelog:** v1.1 — החלפת תשתית מ-aiogram ל-Telethon (MTProto)

---

## תוכן עניינים

1. [ארכיטקטורת קבצים](#1-ארכיטקטורת-קבצים)
2. [ספריות ותלויות](#2-ספריות-ותלויות)
3. [זרימות משתמש](#3-זרימות-משתמש)
4. [תוכן הודעות בעברית](#4-תוכן-הודעות-בעברית)
5. [כפתורים — Inline Keyboards](#5-כפתורים--inline-keyboards)
6. [שאילתות חיפוש על ה-DB](#6-שאילתות-חיפוש-על-ה-db)
7. [אחסון משתמשים והגדרות](#7-אחסון-משתמשים-והגדרות)
8. [קונפיגורציה](#8-קונפיגורציה)
9. [תוכנית פיתוח](#9-תוכנית-פיתוח)
10. [דוגמאות הודעה ויזואליות](#10-דוגמאות-הודעה-ויזואליות)

---

## 1. ארכיטקטורת קבצים

### 1.1 עץ קבצים מלא

```
ev-charging-bot/
├── data/
│   ├── ev_stations.db          # DB קיים — טבלת locations (3,379 אתרים, לא לגעת)
│   ├── build_db.py             # סקריפט בנייה רבעוני (לא חלק מהבוט)
│   └── clean_db.py
├── research/                   # דוחות מחקר (לא חלק מהבוט)
├── bot/
│   ├── __init__.py
│   ├── main.py                 # נקודת כניסה: TelegramClient + Event Handlers + run_until_disconnected
│   ├── config.py               # טעינת .env עם pydantic-settings (API_ID, API_HASH, BOT_TOKEN)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py            # /start, /help — ברוכים הבאים + ReplyKeyboard
│   │   ├── location.py         # events.NewMessage(func=...) — קבלת GPS + שאילתת DB + תצוגת תוצאות
│   │   ├── settings.py         # ניהול העדפות משתמש (תפריטי inline)
│   │   └── callbacks.py        # CallbackQuery handler — ניתוב כל לחיצות ה-inline
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── reply.py            # ReplyKeyboard: כפתור שיתוף מיקום (Button.request_location)
│   │   └── inline.py           # InlineKeyboard builders: טווח, תוצאות, ניווט, הגדרות (Button.inline)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── station_search.py   # חיפוש רדיוס Haversine על SQLite + סינון הגדרות
│   │   └── formatter.py        # עיצוב הודעות עברית: station_card(), results_header()
│   ├── storage/
│   │   ├── __init__.py
│   │   └── users_db.py         # aiosqlite — users.db: הגדרות משתמשים, CRUD
│   └── states.py               # ניהול state בזיכרון (UserSession / dict) לכל משתמש
├── users.db                    # DB נפרד לנתוני משתמשים (נוצר אוטומטית בהרצה ראשונה)
├── requirements.txt
├── .env                        # לא ב-git
├── .env.example
├── .gitignore
├── README.md
└── ev-bot.service              # systemd unit file (אופציונלי)
```

### 1.2 תפקיד כל קובץ

| קובץ | תפקיד |
|------|--------|
| `bot/main.py` | יוצר `TelegramClient('bot_session', api_id, api_hash)`, רושם את כל ה-handlers ב-client, מאתחל את ה-DB, מפעיל `await client.start(bot_token=...)` ומריץ `await client.run_until_disconnected()` |
| `bot/config.py` | `class Settings(BaseSettings)` טוענת `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `BOT_TOKEN`, `DB_PATH`, `USERS_DB_PATH`, `ADMIN_CHAT_ID` |
| `bot/handlers/start.py` | Handler לפקודות `/start` ו-`/help` (`events.NewMessage(pattern=r'^/(start|help)')`). שולח הודעת ברוכים הבאים + ReplyKeyboard עם כפתור שיתוף מיקום |
| `bot/handlers/location.py` | Handler לקבלת מיקום (`events.NewMessage` עם בדיקת `event.geo` / `event.media`). קורא `station_search.find_nearby()`, שומר state (רשימת תוצאות + אינדקס נוכחי) ושולח תוצאה ראשונה |
| `bot/handlers/settings.py` | ניהול הגדרות משתמש (מסכי בחירה inline). Entrypoint: callback `settings:main` |
| `bot/handlers/callbacks.py` | Handler מרכזי ל-`events.CallbackQuery`: מנתב כל לחיצה לפי prefix של `data` (למשל `range:`, `station:`, `nav:`, `settings:`, `filter:`) |
| `bot/keyboards/reply.py` | `location_request_keyboard()` — מחזיר רשימת כפתורים עם `Button.request_location("📍 שתף מיקום נוכחי")` ו-`Button.text("❌ ביטול")` |
| `bot/keyboards/inline.py` | כל ה-builders: `range_keyboard()`, `station_card_keyboard()`, `nav_keyboard()`, `settings_main_keyboard()`, `connector_keyboard()` וכו' באמצעות `Button.inline()` ו-`Button.url()` |
| `bot/services/station_search.py` | `find_nearby(lat, lng, radius_km, filters)` — שאילתת Haversine על `data/ev_stations.db` |
| `bot/services/formatter.py` | `format_station_card(station, distance_km, idx, total)` — מחזיר מחרוזת עברית מעוצבת ב-HTML |
| `bot/storage/users_db.py` | `get_user_settings(chat_id)`, `save_user_settings(chat_id, settings)` — aiosqlite על `users.db` |
| `bot/states.py` | `UserSession` / `user_states: dict[int, UserSession]` — ניהול מצב שיחה בזיכרון (חיפוש אחרון, אינדקס עמדה נוכחי, message_id של כרטיסיית התוצאות) |

---

## 2. ספריות ותלויות

### 2.1 requirements.txt

```text
telethon>=1.34.0
aiosqlite==0.20.0
pydantic-settings==2.4.0
python-dotenv==1.0.1
```

### 2.2 נימוק הבחירות

| ספרייה | גרסה | מה היא עושה | למה נבחרה |
|--------|-------|-------------|-----------|
| **Telethon** | >=1.34.0 | מסגרת MTProto אסינכרונית לטלגרם | תקשורת MTProto ישירה ויציבה, מערכת events חזקה (`events.NewMessage`, `events.CallbackQuery`), עבודה טבעית עם `TelegramClient`, תמיכה מלאה בבוט-טוקן רגיל (`client.start(bot_token=...)`) וביוזר-בוט, ביצועים גבוהים ואסינכרוניות מלאה |
| **aiosqlite** | 0.20.0 | wrapper אסינכרוני ל-sqlite3 | users.db נכתב בזמן Handler — חייב להיות non-blocking. ה-DB הראשי (ev_stations.db) נשאל ב-thread pool דרך `asyncio.to_thread()` |
| **pydantic-settings** | 2.4.0 | טעינת `.env` לתוך `Settings` class | קריאת `BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` ועוד בצורה מאובטחת ומטופחת |
| **python-dotenv** | 1.0.1 | תמיכה בקובץ `.env` | נדרש על ידי pydantic-settings |

> **הערות חשובות:**
> - **תשתית MTProto בלבד:** Telethon מתחברת ישירות לפרוטוקול MTProto הבינארי של טלגרם (בניגוד ל-HTTP Bot API), ומאפשרת מהירות תגובה גבוהה, חיבור קבוע ויציב ויכולות מתקדמות.
> - **אין ORM** — ה-DB הראשי (`ev_stations.db`) נשאל דרך `sqlite3` רגיל בתוך `asyncio.to_thread()`.
> - **אין httpx / aiohttp** — אין קריאות API חיצוניות בזמן ריצת הבוט. כל הנתונים ב-DB מקומי.
> - **אין cachetools** — אין צורך ב-TTL cache כי הנתונים מקומיים (sub-10ms). אפשר להוסיף בעתיד.

---

## 3. זרימות משתמש

### 3.1 עיקרון "הודעה מתעדכנת" (Inline Classic Style)

**כלל אחד:** כל מסך לאחר ההתחלה הוא `event.edit()` / `client.edit_message()` על **אותה הודעה**. אין הודעות חדשות על לחיצות — חוץ מהודעת הברוכים הבאים הראשונית ובקשת המיקום.

מבנה ה-State בזיכרון (dict / dataclass בזיכרון של הבוט) לכל משתמש:

```python
# State data structure (נשמר בזיכרון לפי chat_id / user_id):
{
    "results": [...],        # רשימת dict של תוצאות החיפוש הנוכחית
    "current_idx": 0,        # אינדקס התוצאה הנוכחית המוצגת
    "user_lat": 32.085,      # קואורדינטות אחרון שנשלחו
    "user_lng": 34.781,
    "current_radius": 10,    # הרדיוס שנבחר
    "result_msg_id": 12345   # message_id של ההודעה המתעדכנת
}
```

---

### 3.2 זרימה ראשית: /start → מיקום → תוצאות

```
משתמש                          בוט
  │                               │
  │── /start ──────────────────>  │
  │                               │ שולח הודעת WELCOME (חדשה)
  │                               │ + ReplyKeyboard: [📍 שתף מיקום]
  │<── [WELCOME MSG + KEYBOARD] ──│
  │                               │
  │── [לוחץ "שתף מיקום"] ──────>  │
  │   (event.geo / media)         │ 1. קורא get_user_settings(chat_id)
  │                               │ 2. מסיר ReplyKeyboard (buttons=Button.clear())
  │                               │ 3. שולח הודעת "מחפש..." (חדשה → result_msg_id)
  │<── [⏳ מחפש...] ─────────────│
  │                               │ 4. find_nearby(lat, lng, radius=default_radius, filters)
  │                               │ 5. אם יש תוצאות:
  │                               │    event.edit() → הודעת עמדה #1/N
  │                               │    + InlineKeyboard: [◀ ▶] [🚗 Waze] [🗺 Google] [⚙️]
  │<── [STATION CARD #1/N] ──────│
  │                               │ 6. אם אין תוצאות:
  │                               │    event.edit() → "לא נמצאו עמדות"
  │                               │    + InlineKeyboard: [הרחב ל-20 ק"מ] [הרחב ל-40 ק"מ]
  │                               │
  │── [לחיצה ▶] ──────────────>   │ callback_data = b"nav:next"
  │                               │ event.edit() → עמדה #2/N
  │<── [STATION CARD #2/N] ──────│
  │                               │
  │── [לחיצה ◀] ──────────────>   │ callback_data = b"nav:prev"
  │                               │ event.edit() → עמדה #1/N
  │<── [STATION CARD #1/N] ──────│
  │                               │
  │── [🔄 חיפוש חדש] ──────────>  │ callback_data = b"nav:new_search"
  │                               │ event.edit() → "שתף מיקום חדש:"
  │                               │ + ReplyKeyboard: [📍 שתף מיקום]
  │<── [בקשת מיקום חדש] ─────────│
```

---

### 3.3 זרימת בחירת טווח

```
אחרי קבלת מיקום, אם ה-DB ריק בטווח הברירת מחדל:

  בוט: event.edit() → "לא נמצאו עמדות בטווח 10 ק"מ"
       [הרחב ל-20 ק"מ]  [הרחב ל-40 ק"מ]

  משתמש: לוחץ [הרחב ל-20 ק"מ]  → callback_data = b"range:20"
  בוט: עושה חיפוש מחדש ברדיוס 20, event.edit() → תוצאות

אלטרנטיב — מסך בחירת טווח יזום (לחיצת ⚙️ → "שנה טווח"):
  callback_data = b"settings:range"
  event.edit() → "בחר טווח חיפוש:"
  [10 ק"מ ✅]  [20 ק"מ]  [40 ק"מ]
  [↩ חזור]
```

---

### 3.4 זרימת הגדרות מלאה

```
משתמש לוחץ ⚙️ (callback_data = b"settings:main")
  │
  │  event.edit() → מסך הגדרות ראשי
  │  "⚙️ ההגדרות שלך:
  │   🔌 שקע: הכל
  │   ⚡ מהירות: הכל
  │   📏 טווח ברירת מחדל: 10 ק"מ
  │   💰 מחיר מקסימלי: ללא הגבלה"
  │
  │  [🔌 סוג שקע]    [⚡ מהירות טעינה]
  │  [📏 טווח]       [💰 מחיר מקסימלי]
  │  [↩ חזור לתוצאות]
  │
  ├─ לוחץ [🔌 סוג שקע] → callback_data = b"settings:connector"
  │    event.edit() → "בחר סוג שקע מועדף:"
  │    [⚡ CCS2 (מהיר)]    [🔌 Type 2 (רגיל)]
  │    [🇯🇵 CHAdeMO]       [✅ הכל]
  │    [↩ חזור]
  │    → בחירה שומרת ל-users.db + event.edit() חזרה לראשי
  │
  ├─ לוחץ [⚡ מהירות טעינה] → callback_data = b"settings:speed"
  │    event.edit() → "בחר מהירות טעינה מועדפת:"
  │    [🐢 רגילה (AC עד 22kW)]
  │    [⚡ מהירה (DC 50–150kW)]
  │    [🚀 אולטרה-מהירה (DC 150kW+)]
  │    [✅ הכל]
  │    [↩ חזור]
  │
  ├─ לוחץ [📏 טווח] → callback_data = b"settings:range"
  │    event.edit() → "בחר טווח ברירת מחדל:"
  │    [10 ק"מ]  [20 ק"מ]  [40 ק"מ]
  │    [↩ חזור]
  │
  └─ לוחץ [💰 מחיר מקסימלי] → callback_data = b"settings:price"
       event.edit() → "בחר מחיר מקסימלי לקוט\"ש (₪):"
       [ללא הגבלה]  [עד 1.50 ₪]
       [עד 2.00 ₪]  [עד 2.50 ₪]
       [↩ חזור]
```

---

### 3.5 זרימת "לא נמצאו תוצאות"

```
find_nearby() החזיר רשימה ריקה:
  │
  event.edit() → הודעת ריק (ר' סעיף 4.5)
  [🔍 הרחב ל-20 ק"מ]
  [🔍 הרחב ל-40 ק"מ]
  [⚙️ שנה פילטרים]   [🔄 שתף מיקום חדש]
```

---

## 4. תוכן הודעות בעברית

> **כללים:** לשון פנייה זכר. אמוג'ים מתאימים. parse_mode='html' (ב-Telethon ניתן להגדיר `parse_mode='html'` על ה-client או בכל שליחת הודעה / עריכה — פחות בעיות עם תווים עבריים מול Markdown).

### 4.1 הודעת ברוכים הבאים (`/start`)

```
⚡ ברוך הבא לבוט עמדות הטעינה של ישראל!

🔌 המאגר שלנו כולל ~3,400 אתרי טעינה ברחבי הארץ —
   מידע מעודכן ממשרד האנרגיה, CelloCharge ומקורות נוספים.

📍 כדי למצוא עמדות טעינה קרובות אליך, לחץ על הכפתור למטה ושתף את מיקומך.

💡 <b>טיפ:</b> באמצעות ⚙️ תוכל לסנן לפי סוג שקע, מהירות ומחיר.
```

*(לאחר ההודעה — ReplyKeyboard עם כפתור שיתוף מיקום, ר' סעיף 5.1)*

---

### 4.2 הודעת בקשת מיקום (חוזרת)

```
📍 שתף את מיקומך ואמצא לך עמדות טעינה בקרבת מקום.
```

---

### 4.3 הודעת "מחפש..." (זמנית, מוחלפת מיד)

```
🔍 מחפש עמדות טעינה בטווח {radius} ק"מ ממך...
```

---

### 4.4 תבנית כרטיסיית עמדה (`format_station_card()`)

```
⚡ עמדה {idx}/{total} | {radius} ק"מ

🏢 <b>{name}</b>
📍 {address}, {city}
📏 מרחק: <b>{distance:.1f} ק"מ</b>
🏭 מפעיל: {provider_name}

{connectors_block}

{price_block}

{status_block}

{gov_badge}
```

**כללי עיצוב כל בלוק:**

`connectors_block` — מפיק שורה מרוכזת לכל סוגי המחברים:

```python
# connectors = JSON array: [{"standard": "CCS2_COMBO", "powerType": "DC", "maxPower": 150}, ...]
# standard → display name mapping:
CONNECTOR_DISPLAY = {
    "CCS2_COMBO": "⚡ CCS2 (DC)",
    "TYPE2":      "🔌 Type 2 (AC)",
    "CHADEMO":    "🇯🇵 CHAdeMO",
    "OTHER":      "🔌 שקע אחר",
}
# פלט לדוגמה:
# 🔌 מחברים: ⚡ CCS2 (DC) 150kW | 🔌 Type 2 (AC) 22kW
```

`price_block`:
```python
# אם max_per_kwh קיים:
"💰 מחיר: עד {max_per_kwh:.2f} ₪ לקוט\"ש"
# אם None:
"💰 מחיר: לא ידוע"
```

`status_block` — מפרש JSON `status_summary` (`{"AVAILABLE":2, "BUSY":1, "INACTIVE":0}`):
```python
# אם status_summary ריק או {}:
"🔘 סטטוס: לא ידוע"
# אם יש נתונים:
total = sum(status_summary.values())
available = status_summary.get("AVAILABLE", 0)
busy = status_summary.get("BUSY", 0)
# פלט:
"🟢 פנויות: {available} | 🔴 תפוסות: {busy} | סה\"כ: {total}"
```

`gov_badge`:
```python
# אם is_gov_official == 1:
"🏛️ מאומתת במאגר הממשלתי"
# אחרת — שורה ריקה (לא מציגים כלום)
```

**דוגמת פלט מלא:**
```
⚡ עמדה 1/8 | 10 ק"מ

🏢 <b>קניון עזריאלי תל אביב</b>
📍 דרך מנחם בגין 132, תל אביב
📏 מרחק: <b>1.4 ק"מ</b>
🏭 מפעיל: Afcon EV

🔌 מחברים: ⚡ CCS2 (DC) 150kW | 🔌 Type 2 (AC) 22kW

💰 מחיר: עד 2.29 ₪ לקוט"ש

🟢 פנויות: 2 | 🔴 תפוסות: 1 | סה"כ: 6

🏛️ מאומתת במאגר הממשלתי
```

---

### 4.5 הודעת "לא נמצאו עמדות"

```
😕 לא נמצאו עמדות טעינה בטווח {radius} ק"מ ממך.

💡 נסה להרחיב את טווח החיפוש, או לשנות את פילטר השקע/המהירות בהגדרות.
```

---

### 4.6 מסך הגדרות ראשי

```
⚙️ <b>ההגדרות שלך</b>

🔌 סוג שקע מועדף: <b>{connector_display}</b>
⚡ מהירות טעינה: <b>{speed_display}</b>
📏 טווח ברירת מחדל: <b>{default_radius} ק"מ</b>
💰 מחיר מקסימלי: <b>{price_display}</b>

בחר הגדרה לשינוי:
```

---

### 4.7 הודעות שגיאה

```python
# שגיאת DB / exception כללי:
❌ אירעה שגיאה בחיפוש. נסה שוב בעוד מספר שניות.

# מיקום לא תקין (מחוץ לישראל):
❌ המיקום שקיבלתי אינו בתחומי ישראל. שתף מיקום תקין ונסה שוב.

# CallbackQuery toast לאחר שמירת הגדרה ב-Telethon:
await event.answer("✅ ההגדרה נשמרה!", alert=False)
```

---

## 5. כפתורים — Inline Keyboards

### 5.1 ReplyKeyboard — בקשת מיקום

**קובץ:** `bot/keyboards/reply.py`  
**פונקציה:** `location_request_keyboard() -> list`

```python
from telethon.tl.custom import Button

def location_request_keyboard() -> list:
    """
    מחזיר מקלדת Reply עם כפתור שיתוף מיקום וכפתור ביטול.
    ב-Telethon מעבירים את רשימת השורות לפרמטר buttons של send_message.
    """
    return [
        [Button.request_location("📍 שתף מיקום נוכחי", resize=True, single_use=True)],
        [Button.text("❌ ביטול", resize=True, single_use=True)],
    ]
```

> **הסרת מקלדת ב-Telethon:** כדי להסיר את ה-ReplyKeyboard לאחר קבלת המיקום, שולחים הודעה עם `buttons=Button.clear()`.

---

### 5.2 InlineKeyboard — כרטיסיית עמדה (navigation)

**קובץ:** `bot/keyboards/inline.py`  
**פונקציה:** `station_card_keyboard(station_id: int, idx: int, total: int, lat: float, lng: float) -> list`

מבנה (שורות מלמעלה למטה):

```
שורה 1: [◀ הקודמת]  [1 / 8]  [הבאה ▶]
שורה 2: [🚗 נווט ב-Waze]  [🗺️ Google Maps]
שורה 3: [🔄 חיפוש חדש]  [⚙️ הגדרות]
```

```python
from telethon.tl.custom import Button

def station_card_keyboard(
    station_id: int,
    idx: int,          # 0-based
    total: int,
    lat: float,
    lng: float,
) -> list:
    waze_url = f"https://waze.com/ul?ll={lat},{lng}&navigate=yes"
    gmap_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"

    prev_disabled = idx == 0
    next_disabled = idx == total - 1

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
            Button.url("🚗 נווט ב-Waze", url=waze_url),
            Button.url("🗺️ Google Maps", url=gmap_url),
        ],
        [
            Button.inline("🔄 חיפוש חדש", data=b"nav:new_search"),
            Button.inline("⚙️ הגדרות", data=b"settings:main"),
        ],
    ]
    return rows
```

---

### 5.3 InlineKeyboard — לא נמצאו תוצאות

**פונקציה:** `no_results_keyboard(current_radius: int) -> list`

```
שורה 1: [🔍 הרחב ל-20 ק"מ]  (מוצג רק אם current_radius < 20)
שורה 2: [🔍 הרחב ל-40 ק"מ]  (מוצג רק אם current_radius < 40)
שורה 3: [⚙️ שנה פילטרים]  [🔄 שתף מיקום חדש]
```

```python
from telethon.tl.custom import Button

def no_results_keyboard(current_radius: int) -> list:
    rows = []
    if current_radius < 20:
        rows.append([Button.inline("🔍 הרחב ל-20 ק\"מ", data=b"range:20")])
    if current_radius < 40:
        rows.append([Button.inline("🔍 הרחב ל-40 ק\"מ", data=b"range:40")])
    rows.append([
        Button.inline("⚙️ שנה פילטרים", data=b"settings:main"),
        Button.inline("🔄 שתף מיקום חדש", data=b"nav:new_search"),
    ])
    return rows
```

callback_data (בבתים): `b"range:20"`, `b"range:40"`, `b"settings:main"`, `b"nav:new_search"`

---

### 5.4 InlineKeyboard — הגדרות ראשי

**פונקציה:** `settings_main_keyboard() -> list`

```
שורה 1: [🔌 סוג שקע]    [⚡ מהירות טעינה]
שורה 2: [📏 טווח]       [💰 מחיר מקסימלי]
שורה 3: [↩ חזור לתוצאות]
```

```python
from telethon.tl.custom import Button

def settings_main_keyboard() -> list:
    return [
        [
            Button.inline("🔌 סוג שקע", data=b"settings:connector"),
            Button.inline("⚡ מהירות טעינה", data=b"settings:speed"),
        ],
        [
            Button.inline("📏 טווח", data=b"settings:range"),
            Button.inline("💰 מחיר מקסימלי", data=b"settings:price"),
        ],
        [
            Button.inline("↩ חזור לתוצאות", data=b"nav:back_to_results"),
        ],
    ]
```

callback_data (בבתים): `b"settings:connector"`, `b"settings:speed"`, `b"settings:range"`, `b"settings:price"`, `b"nav:back_to_results"`

---

### 5.5 InlineKeyboard — בחירת סוג שקע

**פונקציה:** `connector_keyboard(current: str) -> list`

```
שורה 1: [⚡ CCS2 (מהיר DC)]  [🔌 Type 2 (AC)]
שורה 2: [🇯🇵 CHAdeMO]         [✅ הכל]
שורה 3: [↩ חזור]
```

```python
from telethon.tl.custom import Button

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
            Button.inline(mark("ALL", "הכל"), data=b"filter:connector:ALL"),
        ],
        [
            Button.inline("↩ חזור", data=b"settings:main"),
        ],
    ]
```

| כפתור | callback_data (bytes) |
|-------|-----------------------|
| `⚡ CCS2 (מהיר DC)` | `b"filter:connector:CCS2_COMBO"` |
| `🔌 Type 2 (AC)` | `b"filter:connector:TYPE2"` |
| `🇯🇵 CHAdeMO` | `b"filter:connector:CHADEMO"` |
| `✅ הכל` | `b"filter:connector:ALL"` |
| `↩ חזור` | `b"settings:main"` |

> **סימון נבחר:** הוסף ✅ לתחילת הטקסט של האפשרות הנוכחית.

---

### 5.6 InlineKeyboard — בחירת מהירות טעינה

**פונקציה:** `speed_keyboard(current: str) -> list`

```
שורה 1: [🐢 רגילה (עד 22kW)]
שורה 2: [⚡ מהירה (50–150kW)]
שורה 3: [🚀 אולטרה-מהירה (150kW+)]
שורה 4: [✅ הכל]
שורה 5: [↩ חזור]
```

```python
from telethon.tl.custom import Button

def speed_keyboard(current: str) -> list:
    def mark(val: str, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [Button.inline(mark("SLOW", "🐢 רגילה (עד 22kW)"), data=b"filter:speed:SLOW")],
        [Button.inline(mark("FAST", "⚡ מהירה (50–150kW)"), data=b"filter:speed:FAST")],
        [Button.inline(mark("ULTRA", "🚀 אולטרה-מהירה (150kW+)"), data=b"filter:speed:ULTRA")],
        [Button.inline(mark("ALL", "הכל"), data=b"filter:speed:ALL")],
        [Button.inline("↩ חזור", data=b"settings:main")],
    ]
```

| כפתור | callback_data (bytes) | min_power_kw |
|-------|-----------------------|-------------|
| `🐢 רגילה (עד 22kW)` | `b"filter:speed:SLOW"` | max ≤ 22 |
| `⚡ מהירה (50–150kW)` | `b"filter:speed:FAST"` | 50 ≤ max < 150 |
| `🚀 אולטרה-מהירה (150kW+)` | `b"filter:speed:ULTRA"` | max ≥ 150 |
| `✅ הכל` | `b"filter:speed:ALL"` | — |
| `↩ חזור` | `b"settings:main"` | — |

---

### 5.7 InlineKeyboard — בחירת טווח

**פונקציה:** `range_keyboard(current: int) -> list`

```
שורה 1: [10 ק"מ]  [20 ק"מ]  [40 ק"מ]
שורה 2: [↩ חזור]
```

```python
from telethon.tl.custom import Button

def range_keyboard(current: int) -> list:
    def mark(val: int, label: str) -> str:
        return f"✅ {label}" if current == val else label

    return [
        [
            Button.inline(mark(10, "10 ק\"מ"), data=b"filter:range:10"),
            Button.inline(mark(20, "20 ק\"מ"), data=b"filter:range:20"),
            Button.inline(mark(40, "40 ק\"מ"), data=b"filter:range:40"),
        ],
        [
            Button.inline("↩ חזור", data=b"settings:main"),
        ],
    ]
```

callback_data (bytes): `b"filter:range:10"`, `b"filter:range:20"`, `b"filter:range:40"`

---

### 5.8 InlineKeyboard — בחירת מחיר מקסימלי

**פונקציה:** `price_keyboard(current) -> list`

```
שורה 1: [ללא הגבלה]   [עד 1.50 ₪]
שורה 2: [עד 2.00 ₪]   [עד 2.50 ₪]
שורה 3: [↩ חזור]
```

```python
from telethon.tl.custom import Button

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
            Button.inline("↩ חזור", data=b"settings:main"),
        ],
    ]
```

callback_data (bytes): `b"filter:price:NONE"`, `b"filter:price:1.5"`, `b"filter:price:2.0"`, `b"filter:price:2.5"`

---

### 5.9 טבלת callback_data מלאה

| prefix | ערך | callback_data (bytes) | פעולה |
|--------|-----|----------------------|--------|
| `nav:` | `next` | `b"nav:next"` | הצג עמדה הבאה |
| `nav:` | `prev` | `b"nav:prev"` | הצג עמדה קודמת |
| `nav:` | `noop` | `b"nav:noop"` | answer ריק (כפתור לא פעיל) |
| `nav:` | `new_search` | `b"nav:new_search"` | שלח בקשת מיקום חדשה |
| `nav:` | `back_to_results` | `b"nav:back_to_results"` | חזור לכרטיסיית עמדה אחרונה |
| `range:` | `10` / `20` / `40` | `b"range:10"` / `b"range:20"` / `b"range:40"` | חפש מחדש בטווח זה |
| `settings:` | `main` | `b"settings:main"` | הצג מסך הגדרות ראשי |
| `settings:` | `connector` | `b"settings:connector"` | מסך בחירת שקע |
| `settings:` | `speed` | `b"settings:speed"` | מסך בחירת מהירות |
| `settings:` | `range` | `b"settings:range"` | מסך בחירת טווח |
| `settings:` | `price` | `b"settings:price"` | מסך בחירת מחיר |
| `filter:connector:` | `CCS2_COMBO` / `TYPE2` / `CHADEMO` / `ALL` | `b"filter:connector:..."` | שמור + חזור להגדרות |
| `filter:speed:` | `SLOW` / `FAST` / `ULTRA` / `ALL` | `b"filter:speed:..."` | שמור + חזור להגדרות |
| `filter:range:` | `10` / `20` / `40` | `b"filter:range:..."` | שמור + חזור להגדרות |
| `filter:price:` | `NONE` / `1.5` / `2.0` / `2.5` | `b"filter:price:..."` | שמור + חזור להגדרות |

> **הערה טכנית על Telethon:** ב-Telethon שדה `data` ב-`Button.inline` מצפה ל-`bytes` (למשל `data=b"nav:next"`). בעת תפיסת האירוע ב-`@client.on(events.CallbackQuery())`, `event.data` מתקבל כ-`bytes` וניתן לפענח אותו בעזרת `data_str = event.data.decode('utf-8')`.

---

## 6. שאילתות חיפוש על ה-DB

### 6.1 הסכמה בפועל של `ev_stations.db`

```sql
-- טבלת locations — הסכמה הממשית מ-build_db.py (אומתה):
CREATE TABLE locations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cello_id        TEXT UNIQUE,          -- מזהה CelloCharge (NULL אם מקור אחר)
    name            TEXT,                 -- שם האתר בעברית
    address         TEXT,                 -- כתובת מלאה
    city            TEXT,                 -- עיר
    lat             REAL,                 -- קו רוחב (WGS84)
    lng             REAL,                 -- קו אורך (WGS84)
    provider_id     TEXT,                 -- מזהה מפעיל (מ-CelloCharge)
    provider_name   TEXT,                 -- שם מפעיל (טקסט)
    max_per_kwh     REAL,                 -- מחיר מקסימלי לקוט"ש (NULL = לא ידוע)
    has_tariffs     INTEGER,              -- 1 אם יש תעריף ידוע
    payment_options TEXT,                 -- JSON array
    facilities      TEXT,                 -- JSON array
    status_summary  TEXT,                 -- JSON: {"AVAILABLE":N,"BUSY":N,"INACTIVE":N}
    connectors      TEXT,                 -- JSON: [{"standard":"CCS2_COMBO","powerType":"DC","maxPower":150}]
    stations_count  INTEGER,              -- מספר שקעים/עמדות באתר
    updated_at      TEXT,                 -- ISO timestamp
    sources         TEXT,                 -- רשימת מקורות: "cello,auto_coil,evm,data_gov"
    is_gov_official INTEGER               -- 1 אם מופיע במאגר משרד האנרגיה
);

-- אינדקסים קיימים:
CREATE UNIQUE INDEX idx_locations_cello_id ON locations(cello_id);
CREATE INDEX idx_locations_coords ON locations(lat, lng);
CREATE INDEX idx_locations_provider ON locations(provider_name);
CREATE INDEX idx_locations_city ON locations(city);
CREATE INDEX idx_locations_is_gov ON locations(is_gov_official);
CREATE INDEX idx_locations_sources ON locations(sources);
```

> **חשוב:** אין R*Tree — הסינון המרחבי נעשה דרך Bounding Box על `(lat, lng)` + חישוב Haversine בפייתון. ה-DB קטן (<6MB, 3,379 שורות) — הכל מהיר.

---

### 6.2 פונקציית החיפוש הראשית

**קובץ:** `bot/services/station_search.py`

```python
import sqlite3
import math
import json
import asyncio
from typing import Optional

# --- Haversine (Python) ---
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

# --- סינון connector בפייתון (connectors הוא JSON) ---
def station_matches_connector(connectors_json: str, connector_filter: str) -> bool:
    """connector_filter: 'CCS2_COMBO' | 'TYPE2' | 'CHADEMO' | 'ALL'"""
    if connector_filter == "ALL":
        return True
    try:
        connectors = json.loads(connectors_json or "[]")
        return any(c.get("standard") == connector_filter for c in connectors)
    except (json.JSONDecodeError, TypeError):
        return False

def station_matches_speed(connectors_json: str, speed_filter: str) -> bool:
    """
    SLOW: max_power <= 22 (AC)
    FAST: 50 <= max_power < 150
    ULTRA: max_power >= 150
    ALL: הכל
    """
    if speed_filter == "ALL":
        return True
    try:
        connectors = json.loads(connectors_json or "[]")
        powers = [float(c["maxPower"]) for c in connectors if c.get("maxPower") is not None]
        if not powers:
            return True  # אין מידע הספק → לא מסננים
        max_power = max(powers)
        if speed_filter == "SLOW":
            return max_power <= 22
        elif speed_filter == "FAST":
            return 50 <= max_power < 150
        elif speed_filter == "ULTRA":
            return max_power >= 150
    except (json.JSONDecodeError, TypeError, ValueError):
        return True
    return False

# --- פונקציה ראשית (sync, רצה ב-thread) ---
def _find_nearby_sync(
    db_path: str,
    user_lat: float,
    user_lng: float,
    radius_km: float,
    connector_filter: str = "ALL",
    speed_filter: str = "ALL",
    max_price: Optional[float] = None,
    limit: int = 15,
) -> list[dict]:
    # 1. Bounding Box pre-filter ב-SQL
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * math.cos(math.radians(user_lat)))
    lat_min = user_lat - lat_delta
    lat_max = user_lat + lat_delta
    lon_min = user_lng - lon_delta
    lon_max = user_lng + lon_delta

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            id, cello_id, name, address, city,
            lat, lng, provider_name, max_per_kwh,
            has_tariffs, status_summary, connectors,
            stations_count, is_gov_official, sources
        FROM locations
        WHERE
            lat IS NOT NULL AND lng IS NOT NULL
            AND lat BETWEEN :lat_min AND :lat_max
            AND lng BETWEEN :lon_min AND :lon_max
            AND (:max_price IS NULL OR max_per_kwh IS NULL OR max_per_kwh <= :max_price)
        LIMIT 300
    """
    params = {
        "lat_min": lat_min, "lat_max": lat_max,
        "lon_min": lon_min, "lon_max": lon_max,
        "max_price": max_price,
    }
    rows = conn.execute(query, params).fetchall()
    conn.close()

    # 2. חישוב Haversine מדויק + סינון connector + speed + radius
    results = []
    for row in rows:
        dist = haversine_km(user_lat, user_lng, row["lat"], row["lng"])
        if dist > radius_km:
            continue
        if not station_matches_connector(row["connectors"], connector_filter):
            continue
        if not station_matches_speed(row["connectors"], speed_filter):
            continue
        d = dict(row)
        d["distance_km"] = dist
        results.append(d)

    # 3. מיון לפי מרחק + הגבלה
    results.sort(key=lambda x: x["distance_km"])
    return results[:limit]


async def find_nearby(
    db_path: str,
    user_lat: float,
    user_lng: float,
    radius_km: float = 10.0,
    connector_filter: str = "ALL",
    speed_filter: str = "ALL",
    max_price: Optional[float] = None,
    limit: int = 15,
) -> list[dict]:
    """Async wrapper — מריץ את החיפוש ב-thread pool."""
    return await asyncio.to_thread(
        _find_nearby_sync,
        db_path, user_lat, user_lng, radius_km,
        connector_filter, speed_filter, max_price, limit,
    )
```

---

### 6.3 ולידציה של מיקום

```python
def is_in_israel(lat: float, lng: float) -> bool:
    """Bounding Box גסה של ישראל."""
    return 29.5 <= lat <= 33.3 and 34.2 <= lng <= 35.9
```

---

## 7. אחסון משתמשים והגדרות

### 7.1 סכמת `users.db`

```sql
CREATE TABLE IF NOT EXISTS users (
    chat_id         INTEGER PRIMARY KEY,   -- Telegram chat_id
    first_name      TEXT,                  -- שם פרטי (מהודעת /start)
    username        TEXT,                  -- @username (אופציונלי)
    connector_filter TEXT DEFAULT 'ALL',   -- ALL | CCS2_COMBO | TYPE2 | CHADEMO
    speed_filter    TEXT DEFAULT 'ALL',    -- ALL | SLOW | FAST | ULTRA
    default_radius  INTEGER DEFAULT 10,    -- 10 | 20 | 40
    max_price       REAL DEFAULT NULL,     -- NULL = ללא הגבלה; 1.5 | 2.0 | 2.5
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
```

### 7.2 ערכי ברירת מחדל

| שדה | ברירת מחדל | ערכים חוקיים |
|-----|------------|--------------|
| `connector_filter` | `ALL` | `ALL`, `CCS2_COMBO`, `TYPE2`, `CHADEMO` |
| `speed_filter` | `ALL` | `ALL`, `SLOW`, `FAST`, `ULTRA` |
| `default_radius` | `10` | `10`, `20`, `40` |
| `max_price` | `NULL` | `NULL`, `1.5`, `2.0`, `2.5` |

### 7.3 CRUD functions — `bot/storage/users_db.py`

```python
import aiosqlite
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserSettings:
    chat_id: int
    first_name: str = ""
    username: str = ""
    connector_filter: str = "ALL"
    speed_filter: str = "ALL"
    default_radius: int = 10
    max_price: Optional[float] = None

async def init_users_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                connector_filter TEXT DEFAULT 'ALL',
                speed_filter TEXT DEFAULT 'ALL',
                default_radius INTEGER DEFAULT 10,
                max_price REAL DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()

async def get_user_settings(chat_id: int, db_path: str) -> UserSettings:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserSettings(
                    chat_id=row["chat_id"],
                    first_name=row["first_name"] or "",
                    username=row["username"] or "",
                    connector_filter=row["connector_filter"] or "ALL",
                    speed_filter=row["speed_filter"] or "ALL",
                    default_radius=row["default_radius"] or 10,
                    max_price=row["max_price"],
                )
            return UserSettings(chat_id=chat_id)

async def upsert_user(settings: UserSettings, db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO users (chat_id, first_name, username,
                connector_filter, speed_filter, default_radius, max_price, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username,
                connector_filter = excluded.connector_filter,
                speed_filter = excluded.speed_filter,
                default_radius = excluded.default_radius,
                max_price = excluded.max_price,
                updated_at = datetime('now')
        """, (
            settings.chat_id, settings.first_name, settings.username,
            settings.connector_filter, settings.speed_filter,
            settings.default_radius, settings.max_price,
        ))
        await db.commit()
```

---

## 8. קונפיגורציה

### 8.1 `.env.example`

```dotenv
# ===== TELEGRAM MTProto API (מאתר my.telegram.org) =====
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef

# ===== BOT TOKEN (מ-@BotFather) =====
BOT_TOKEN=1234567890:AABBcc...

# ===== DB PATHS =====
DB_PATH=/home/vm/projects/ev-charging-bot/data/ev_stations.db
USERS_DB_PATH=/home/vm/projects/ev-charging-bot/users.db

# ===== OPTIONAL =====
ADMIN_CHAT_ID=
DEBUG=false
```

> **הערה לגבי API Credentials:** ב-Telethon, החיבור מתבצע ישירות בפרוטוקול MTProto. לשם כך נדרשים `TELEGRAM_API_ID` ו-`TELEGRAM_API_HASH` (שנוצרים בחינם באתר הרשמי https://my.telegram.org תחת "API development tools"), יחד עם ה-`BOT_TOKEN` הרגיל שנוצר ב-@BotFather.

### 8.2 `bot/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    api_id: int = Field(..., alias="TELEGRAM_API_ID")
    api_hash: str = Field(..., alias="TELEGRAM_API_HASH")
    bot_token: str = Field(..., alias="BOT_TOKEN")
    db_path: str = Field(
        default="/home/vm/projects/ev-charging-bot/data/ev_stations.db",
        alias="DB_PATH",
    )
    users_db_path: str = Field(
        default="/home/vm/projects/ev-charging-bot/users.db",
        alias="USERS_DB_PATH",
    )
    admin_chat_id: Optional[int] = Field(default=None, alias="ADMIN_CHAT_ID")
    debug: bool = Field(default=False, alias="DEBUG")

settings = Settings()
```

### 8.3 `bot/main.py`

```python
import asyncio
import logging
from telethon import TelegramClient
from bot.config import settings
from bot.handlers import start, location, callbacks, settings as settings_handler
from bot.storage.users_db import init_users_db

async def main():
    logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

    # 1. אתחול DB משתמשים
    await init_users_db(settings.users_db_path)

    # 2. יצירת לקוח Telethon MTProto
    client = TelegramClient('bot_session', settings.api_id, settings.api_hash)

    # 3. רישום Handlers
    start.register_handlers(client)
    location.register_handlers(client)
    settings_handler.register_handlers(client)
    callbacks.register_handlers(client)

    # 4. הפעלת הבוט באמצעות bot_token והמתנה לעדכונים
    await client.start(bot_token=settings.bot_token)
    logging.info("Bot started successfully with Telethon MTProto!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
```

### 8.4 `ev-bot.service` (systemd)

```ini
[Unit]
Description=EV Charging Telegram Bot
After=network.target

[Service]
Type=simple
User=vm
WorkingDirectory=/home/vm/projects/ev-charging-bot
ExecStart=/usr/bin/python3 -m bot.main
Restart=always
RestartSec=10
EnvironmentFile=/home/vm/projects/ev-charging-bot/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

הפעלה:
```bash
sudo cp ev-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ev-bot
sudo journalctl -u ev-bot -f
```

---

## 9. תוכנית פיתוח

### שלב א' — תשתית וחיפוש (יום 1)

```
[ ] א1. צור מבנה תיקיות: bot/, handlers/, keyboards/, services/, storage/
[ ] א2. כתוב bot/config.py — Settings class עם api_id, api_hash, bot_token
[ ] א3. כתוב bot/storage/users_db.py — init, get, upsert
[ ] א4. כתוב bot/services/station_search.py — _find_nearby_sync + async wrapper
[ ] א5. בדוק station_search בנפרד:
         python3 -c "
           import asyncio
           from bot.services.station_search import find_nearby
           r = asyncio.run(find_nearby('data/ev_stations.db', 32.085, 34.781, 10))
           print(len(r), r[0]['name'], round(r[0]['distance_km'],2))
         "
         → צפוי: 10-15 תוצאות, המרחק הראשון < 2 ק"מ
[ ] א6. כתוב bot/services/formatter.py — format_station_card()
[ ] א7. בדוק formatter עם mock data
```

### שלב ב' — Handlers וזרימה ראשית (יום 2)

```
[ ] ב1. כתוב bot/keyboards/reply.py — location_request_keyboard() (Telethon Button.request_location)
[ ] ב2. כתוב bot/keyboards/inline.py — station_card_keyboard(), no_results_keyboard() (Button.inline)
[ ] ב3. כתוב bot/handlers/start.py — @client.on(events.NewMessage(pattern=r'^/(start|help)'))
[ ] ב4. כתוב bot/handlers/location.py:
         - @client.on(events.NewMessage(func=lambda e: bool(e.geo)))
         - is_in_israel() validation
         - get_user_settings(chat_id)
         - שלח "מחפש..." + הסרת מקלדת (buttons=Button.clear())
         - find_nearby() עם הגדרות
         - שמור results + current_idx ב-user_states (in-memory dict)
         - עריכת ההודעה (edit_message) לכרטיסיית עמדה 0
[ ] ב5. כתוב bot/handlers/callbacks.py:
         - @client.on(events.CallbackQuery)
         - פענוח data (למשל data = event.data.decode('utf-8'))
         - nav:next / nav:prev → עדכן current_idx + event.edit()
         - nav:noop → await event.answer()
         - nav:new_search → בקשת מיקום חדשה + location_request_keyboard()
         - range:N → חיפוש מחדש
[ ] ב6. כתוב bot/main.py — TelegramClient, client.start(bot_token=...), client.run_until_disconnected()
[ ] ב7. הרצה ראשונה:
         python3 -m bot.main
         → /start → שיתוף מיקום → בדוק תוצאות + ניווט ◀▶
```

### שלב ג' — הגדרות (יום 3)

```
[ ] ג1. הוסף ל-bot/keyboards/inline.py:
         settings_main_keyboard(), connector_keyboard(),
         speed_keyboard(), range_keyboard(), price_keyboard() עם Button.inline
[ ] ג2. כתוב bot/handlers/settings.py — settings:main callback handler
[ ] ג3. הוסף ל-bot/handlers/callbacks.py:
         - settings:connector / speed / range / price → event.edit() מסך בחירה
         - filter:connector:X / filter:speed:X / filter:range:X / filter:price:X
           → upsert_user() + await event.answer("✅ ההגדרה נשמרה!", alert=False)
           → event.edit() → הגדרות ראשי
[ ] ג4. בדוק: שנה שקע ל-CCS2 → חיפוש → רק CCS2 בתוצאות
```

### שלב ד' — הקשחה ו-Deploy (יום 4)

```
[ ] ד1. try/except גלובלי + הודעת שגיאה בעברית
[ ] ד2. לוגים: logging.info לכל חיפוש (chat_id, lat/lng מעוגלים, מס' תוצאות)
[ ] ד3. fallback: "ביטול" בטקסט → הסרת ReplyKeyboard
[ ] ד4. מקרי קצה: כפתור noop, ניווט בקצות הרשימה
[ ] ד5. .env מקובץ .env.example, הגדרת TELEGRAM_API_ID, TELEGRAM_API_HASH, BOT_TOKEN
[ ] ד6. systemd service:
         sudo cp ev-bot.service /etc/systemd/system/
         sudo systemctl enable --now ev-bot
         sudo journalctl -u ev-bot -f
[ ] ד7. בדיקת reboot
```

---

## 10. דוגמאות הודעה ויזואליות

### דוגמה 1: כרטיסיית עמדה — DC מהיר עם נתוני זמינות

```
┌─────────────────────────────────────────┐
│  ⚡ עמדה 1/8 | 10 ק"מ                   │
│                                         │
│  🏢 קניון עזריאלי תל אביב               │
│  📍 דרך מנחם בגין 132, תל אביב          │
│  📏 מרחק: 1.4 ק"מ                       │
│  🏭 מפעיל: Afcon EV                     │
│                                         │
│  🔌 מחברים: ⚡ CCS2 (DC) 150kW          │
│             🔌 Type 2 (AC) 22kW         │
│                                         │
│  💰 מחיר: עד 2.29 ₪ לקוט"ש             │
│                                         │
│  🟢 פנויות: 2 | 🔴 תפוסות: 1 | סה"כ: 6 │
│                                         │
│  🏛️ מאומתת במאגר הממשלתי               │
│  ─────────────────────────────────────  │
│  [◀ הקודמת]  [1 / 8]  [הבאה ▶]         │
│  [🚗 נווט ב-Waze]  [🗺️ Google Maps]     │
│  [🔄 חיפוש חדש]   [⚙️ הגדרות]          │
└─────────────────────────────────────────┘
```

---

### דוגמה 2: עמדה AC בלבד — ללא נתוני זמינות, ללא מחיר

```
┌─────────────────────────────────────────┐
│  ⚡ עמדה 3/8 | 10 ק"מ                   │
│                                         │
│  🏢 חניון עירוני — שוק הכרמל            │
│  📍 הכרמל 12, תל אביב                   │
│  📏 מרחק: 2.1 ק"מ                       │
│  🏭 מפעיל: EV Edge                      │
│                                         │
│  🔌 מחברים: 🔌 Type 2 (AC) 22kW         │
│                                         │
│  💰 מחיר: לא ידוע                       │
│                                         │
│  🔘 סטטוס: לא ידוע                      │
│  ─────────────────────────────────────  │
│  [◀ הקודמת]  [3 / 8]  [הבאה ▶]         │
│  [🚗 נווט ב-Waze]  [🗺️ Google Maps]     │
│  [🔄 חיפוש חדש]   [⚙️ הגדרות]          │
└─────────────────────────────────────────┘
```

---

### דוגמה 3: לא נמצאו תוצאות

```
┌─────────────────────────────────────────┐
│                                         │
│  😕 לא נמצאו עמדות טעינה בטווח 10 ק"מ  │
│     ממך.                                │
│                                         │
│  💡 נסה להרחיב את טווח החיפוש, או      │
│     לשנות את פילטר השקע/המהירות        │
│     בהגדרות.                            │
│  ─────────────────────────────────────  │
│  [🔍 הרחב ל-20 ק"מ]                     │
│  [🔍 הרחב ל-40 ק"מ]                     │
│  [⚙️ שנה פילטרים]  [🔄 שתף מיקום חדש] │
│                                         │
└─────────────────────────────────────────┘
```

---

### דוגמה 4: מסך הגדרות ראשי

```
┌─────────────────────────────────────────┐
│  ⚙️ ההגדרות שלך                         │
│                                         │
│  🔌 סוג שקע מועדף: הכל                  │
│  ⚡ מהירות טעינה: מהירה (50–150kW)      │
│  📏 טווח ברירת מחדל: 10 ק"מ            │
│  💰 מחיר מקסימלי: עד 2.50 ₪            │
│                                         │
│  בחר הגדרה לשינוי:                      │
│  ─────────────────────────────────────  │
│  [🔌 סוג שקע]    [⚡ מהירות טעינה]      │
│  [📏 טווח]       [💰 מחיר מקסימלי]     │
│  [↩ חזור לתוצאות]                       │
└─────────────────────────────────────────┘
```

---

## נספח: מיפוי ערכים להצגה בעברית

```python
CONNECTOR_DISPLAY = {
    "ALL":        "הכל",
    "CCS2_COMBO": "⚡ CCS2 (DC מהיר)",
    "TYPE2":      "🔌 Type 2 (AC)",
    "CHADEMO":    "🇯🇵 CHAdeMO",
}

SPEED_DISPLAY = {
    "ALL":   "הכל",
    "SLOW":  "🐢 רגילה (עד 22kW)",
    "FAST":  "⚡ מהירה (50–150kW)",
    "ULTRA": "🚀 אולטרה-מהירה (150kW+)",
}

PRICE_DISPLAY = {
    None:  "ללא הגבלה",
    1.5:   "עד 1.50 ₪",
    2.0:   "עד 2.00 ₪",
    2.5:   "עד 2.50 ₪",
}
```

---

*מסמך זה מבוסס על: `data/ev_stations.db` (סכמה אמיתית מ-build_db.py שורות 438–471), `research/03-technical-integration.md`, `research/05-crawl-architecture.md`. כל שמות callback_data, שדות DB, ועמודות הסכמה אומתו מול הקבצים הקיימים.*
