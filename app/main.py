import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from app.config import Settings, get_settings
from app.db.session import Database
from app.handlers import admin, artist, client, start


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def setup_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(start.router)
    dispatcher.include_router(artist.router)
    dispatcher.include_router(client.router)
    dispatcher.include_router(admin.router)
    return dispatcher


async def run_polling(settings: Settings) -> None:
    session = AiohttpSession(timeout=60)
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = setup_dispatcher()
    database = Database(settings)

    try:
        await database.check_connection()
        await dispatcher.start_polling(bot, settings=settings, db=database)
    finally:
        await database.engine.dispose()
        await bot.session.close()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    await run_polling(settings)


if __name__ == "__main__":
    asyncio.run(main())
