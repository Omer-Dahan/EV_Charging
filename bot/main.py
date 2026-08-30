import asyncio
import logging
import os

from telethon import TelegramClient

from bot.config import settings
from bot.handlers import start, location, callbacks, admin
from bot.handlers import settings as settings_handler
from bot.services import rate_limiter
from bot.services.bot_health import setup_error_tracker
from bot.storage.users_db import init_users_db


async def main():
    logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

    # 1. Setup error tracking for health diagnostics
    setup_error_tracker()

    # 2. Initialise users DB and stats tables
    await init_users_db(settings.users_db_path)

    # 3. Derive session file path from the same directory as users.db so the
    #    session is always co-located with its data, regardless of CWD.
    session_path = os.path.join(os.path.dirname(os.path.abspath(settings.users_db_path)), "bot_session")

    # 4. Create Telethon MTProto client
    client = TelegramClient(session_path, settings.api_id, settings.api_hash)

    # 5. Register rate limiting protection before all other handlers
    rate_limiter.register_handlers(client)

    # 6. Register handlers
    start.register_handlers(client)
    location.register_handlers(client)
    settings_handler.register_handlers(client)
    callbacks.register_handlers(client)
    admin.register_handlers(client)

    # 7. Start the bot and wait for updates
    await client.start(bot_token=settings.bot_token)
    logging.info("Bot started successfully with Telethon MTProto!")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
