import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonDefault
from aiohttp import web

from src.core.config import settings
from src.db.database import init_db
from src.scrapers.engine import ScraperEngine
from src.services.scheduler import NotificationDispatcher, scraper_loop, digest_loop, alert_batch_loop, keep_alive_loop
from src.scrapers.browser import close_browser_runtime
from src.web.server import create_web_app
from src.bot.handlers import start, test_handler, settings as settings_handler, promos

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("belgiumpromos")

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🇧🇪 Open Main Menu"),
        BotCommand(command="promos", description="🔍 Browse by Belgian supermarket"),
        BotCommand(command="folders", description="📰 Weekly folders & leaflets"),
        BotCommand(command="search", description="🔎 Multilingual product search"),
        BotCommand(command="stores", description="🏪 Select tracked supermarkets"),
        BotCommand(command="categories", description="🏷️ Filter product categories"),
        BotCommand(command="favorites", description="⭐ View saved discounts"),
        BotCommand(command="settings", description="⚙️ Language & notification alerts"),
        BotCommand(command="test_promo", description="🧪 Test promo card & notifications"),
        BotCommand(command="help", description="ℹ️ Information & instructions"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands menu registered with Telegram.")
    except Exception as e:
        logger.warning(f"Could not register bot commands: {e}")

async def main():
    logger.info("Starting Belgium Promo's service...")
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required. Set it through the environment or a managed secret.")
    await init_db()

    bot = Bot(token=settings.BOT_TOKEN)
    dispatcher = NotificationDispatcher(bot)

    async def on_new_promo(promo):
        dispatcher.queue_new_promo(promo)

    engine = ScraperEngine(on_new_promo_callback=on_new_promo)
    await engine.seed_data_if_empty()

    # Setup aiogram Dispatcher
    dp = Dispatcher()
    # Explicit handler precedence: specific command routers BEFORE general text search
    dp.include_router(start.router)
    dp.include_router(test_handler.router)
    dp.include_router(settings_handler.router)
    dp.include_router(promos.router)

    await setup_bot_commands(bot)

    # Setup the HTTP service for health checks, pings, and inbound webhooks.
    app = create_web_app(engine, dispatcher)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.HOST, settings.PORT)
    await site.start()
    logger.info(f"Web server online on http://{settings.HOST}:{settings.PORT}")

    # Launch background workers
    bg_tasks = [
        asyncio.create_task(scraper_loop(engine, settings.SCRAPE_INTERVAL_MINUTES)),
        asyncio.create_task(digest_loop(dispatcher)),
        asyncio.create_task(alert_batch_loop(dispatcher, settings.ALERT_BATCH_INTERVAL_MINUTES)),
    ]
    if settings.KEEP_ALIVE_URL:
        bg_tasks.append(asyncio.create_task(keep_alive_loop(settings.KEEP_ALIVE_URL)))

    # Start live Telegram polling
    logger.info("Belgium Promo's Telegram Bot polling started.")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down Belgium Promo's service...")
        for task in bg_tasks:
            task.cancel()
        await close_browser_runtime()
        await runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Service stopped.")
