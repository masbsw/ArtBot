import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError

from app.config import Settings, get_settings
from app.db.session import Database
from app.handlers import admin, artist, client, start
from app.middlewares.performance import SlowUpdateLoggingMiddleware

logger = logging.getLogger(__name__)
GET_ME_RETRY_DELAYS = (2, 4, 8, 16)
POLLING_RESTART_DELAY = 5


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def setup_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(SlowUpdateLoggingMiddleware())
    dispatcher.include_router(start.router)
    dispatcher.include_router(artist.router)
    dispatcher.include_router(client.router)
    dispatcher.include_router(admin.router)
    return dispatcher


def create_bot(settings: Settings) -> Bot:
    session = AiohttpSession(timeout=60, limit=100)
    session._connector_init.update(
        {
            "force_close": False,
            "enable_cleanup_closed": True,
        }
    )
    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def ensure_bot_ready(bot: Bot) -> None:
    total_attempts = len(GET_ME_RETRY_DELAYS) + 1
    last_error: Exception | None = None
    for attempt in range(1, total_attempts + 1):
        try:
            me = await bot.get_me()
            logger.info(
                "Bot API preflight succeeded on attempt %s/%s for @%s id=%s",
                attempt,
                total_attempts,
                me.username,
                me.id,
            )
            return
        except TelegramNetworkError as exc:
            last_error = exc
            logger.warning(
                "bot.get_me failed with TelegramNetworkError on attempt %s/%s",
                attempt,
                total_attempts,
                exc_info=True,
            )
        except TimeoutError as exc:
            last_error = exc
            logger.warning(
                "bot.get_me failed with TimeoutError on attempt %s/%s",
                attempt,
                total_attempts,
                exc_info=True,
            )

        if attempt == total_attempts:
            if last_error is not None:
                raise last_error

        delay = GET_ME_RETRY_DELAYS[attempt - 1]
        logger.info("Retrying bot.get_me in %s seconds", delay)
        await asyncio.sleep(delay)


async def run_polling(settings: Settings) -> None:
    database = Database(settings)

    try:
        await database.check_connection()
        restart_count = 0
        while True:
            bot = create_bot(settings)
            dispatcher = setup_dispatcher()
            try:
                await ensure_bot_ready(bot)
                logger.info("Starting polling loop")
                await dispatcher.start_polling(bot, settings=settings, db=database)
                logger.info("Polling exited without network error")
                return
            except (TelegramNetworkError, TimeoutError):
                restart_count += 1
                logger.exception(
                    "Polling stopped because of a network error. Restart #%s in %s seconds",
                    restart_count,
                    POLLING_RESTART_DELAY,
                )
                await asyncio.sleep(POLLING_RESTART_DELAY)
            finally:
                await bot.session.close()
    finally:
        await database.engine.dispose()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    await run_polling(settings)


if __name__ == "__main__":
    asyncio.run(main())
