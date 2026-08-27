import asyncio
import logging

from telethon import TelegramClient

from bot.config import settings
from bot.handlers import start, location, callbacks
from bot.handlers import settings as settings_handler
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
