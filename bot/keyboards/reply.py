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

