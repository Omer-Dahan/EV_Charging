# ⚡ EV Charging IL Bot — חיפוש עמדות טעינה לרכב חשמלי בישראל

בוט טלגרם שמוצא עמדות טעינה קרובות אליך — מאגר מאוחד של **~3,400 אתרי טעינה** מכל המפעילים בארץ, מפה ויזואלית, סינון חכם, וניווט בלחיצה.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![Telethon](https://img.sh.shields.io/badge/Library-Telethon-orange)](https://docs.telethon.dev/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📱 מה הבוט עושה

שלח לבוט את המיקום שלך (GPS), בחר טווח חיפוש — 10 / 20 / 40 / 100 ק"מ — וקבל:

- 🔌 **כרטיסיית עמדה מלאה**: שם, כתובת, מרחק מדויק, מפעיל, סוגי מחברים (CCS2 / Type 2 / CHAdeMO) עם הספק kW, מחיר לקוט"ש, סטטוס זמינות
- 🗺️ **תמונת מפה** של האזור — המיקום שלך מסומן בסיכה אדומה, כל העמדות בסמני ברק ירוקים
- 🚗 **ניווט בלחיצה** — Waze או Google Maps
- ⚙️ **הגדרות אישיות**: סוג שקע מועדף, מהירות טעינה, טווח ברירת מחדל, מחיר מקסימלי
- 🏛️ תג "מאומתת במאגר משרד האנרגיה" על עמדות רשמיות

---

## 🗄️ מקורות הנתונים

המאגר מאחד 5 מקורות עצמאיים לתמונה המלאה:

| מקור | תיאור | תרומה |
|------|-------|-------|
| **CelloCharge** (משרד האנרגיה) | מאגר OCPI לאומי | עמוד שדרה: ~3,180 אתרים, זמן אמת, תעריפים |
| **data.gov.il** | מאגר פתוח רשמי | אישור רשמי + עמדות ייחודיות |
| **auto.co.il** | מפת EV הקהילתי | העשרה: שמות עבריים, סוגי טעינה |
| **evm.co.il** | מפה קהילתית | עמדות DC מהירות וטסלה |
| **Paz Charge / Yellow** | מאגר תחנות פז | 123 עמדות DC אולטרה-מהירות ברחבי הארץ |

**עדכון:** סריקה ואיחוד מלאים של כל 5 המקורות מדי כמה חודשים (בוצע בסקריפט `data/build_db.py`, אידמפוטנטי).

## 🏗️ ארכיטקטורה

```
bot/
├── main.py            # TelegramClient + רישום handlers
├── config.py          # Pydantic Settings (.env)
├── states.py          # State per-user בזיכרון
├── handlers/          # start, location, settings, callbacks
├── keyboards/         # inline + reply builders
├── services/          # station_search (Haversine), formatter, map_renderer
└── storage/users_db.py
data/
├── build_db.py        # pipeline מיזוג 5 המקורות → SQLite
├── paz_stations_cache.json # מטמון גיבוי עמדות פז
└── ev_stations.db     # מאגר מאוחד (~3,480 אתרים)
```

## 🚀 הרצה

```bash
# venv
python3.11 -m venv ~/venvs/ev-bot && source ~/venvs/ev-bot/bin/activate

# התקנה
pip install -r requirements.txt

# קונפיגורציה
cp .env.example .env   # מלא: TELEGRAM_API_ID/HASH, BOT_TOKEN

# בניית מאגר (פעם בתקופה)
python data/build_db.py

# הפעלה
python -m bot.main
```

## 🗺️ מפות

הבוט מרנדר מפות דרך [Geoapify Static Maps](https://www.geoapify.com/) (3,000 קרדיטים/יום חינם) עם סגנון `osm-carto` ועברית מלאה (`lang=he`). ללא מפתח — fallback אוטומטי ל-OpenStreetMap + PIL.

## 🛡️ פרטיות

- **אין איסוף נתונים** — לא שומרים מיקום, לא מפרופילים, לא מנתחים
- המיקום משמש **רק לרגע החיפוש** — מציאת עמדות קרובות ומיד נשכח
- ההגדרות (סוג שקע/מהירות) נשמרות ב-SQLite מקומי בלבד
- הקוד פתוח לבדיקה

## 📄 רישיון

MIT
