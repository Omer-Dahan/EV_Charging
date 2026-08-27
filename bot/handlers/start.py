from telethon import TelegramClient, events

from bot.keyboards.inline import welcome_keyboard

WELCOME_MESSAGE = (
    "⚡ <b>ברוך הבא לבוט עמדות הטעינה של ישראל!</b>\n\n"
    "🔌 המאגר שלנו כולל כ-3,400 אתרי טעינה ברחבי הארץ — מידע מעודכן ממשרד האנרגיה, CelloCharge ומקורות נוספים.\n\n"
    "📍 <b>איך מחפשים?</b>\n"
    "• <b>טקסט:</b> שלח רחוב או שכונה ועיר מופרדים בפסיק (לדוגמה: <i>הרצל 7, חיפה</i>)\n"
    "• <b>קואורדינטות:</b> שלח קואורדינטות GPS (לדוגמה: <code>32.0853, 34.7818</code>)\n"
    "• <b>GPS:</b> שיתוף מיקום GPS, דרך סמל 📎 למטה בימין\n\n"
    "💡 <b>טיפ:</b> דרך ⚙️ <b>הגדרות</b> תוכל לסנן לפי סוג שקע, מהירות טעינה ומחיר מקסימלי."
)


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(pattern=r'^/(start|help)'))
    async def handle_start(event: events.NewMessage.Event) -> None:
        await event.respond(
            WELCOME_MESSAGE,
            buttons=welcome_keyboard(),
            parse_mode="html",
        )
