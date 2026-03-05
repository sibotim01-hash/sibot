"""
Multi-Channel Manager & Rating Bot
Asosiy ishga tushirish fayli
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database.db import Database
from handlers.admin import admin_router
from handlers.channels import channels_router
from handlers.post_creator import post_router
from handlers.rating import rating_router
from handlers.stats import stats_router
from services.scheduler_service import SchedulerService
from services.rating_service import RatingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    config = Config()
    db = Database(config.DATABASE_URL)
    await db.init()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler_service = SchedulerService(bot, db, scheduler)
    rating_service = RatingService(bot, db)

    dp.include_router(admin_router)
    dp.include_router(channels_router)
    dp.include_router(post_router)
    dp.include_router(rating_router)
    dp.include_router(stats_router)

    dp["db"] = db
    dp["config"] = config
    dp["scheduler_service"] = scheduler_service
    dp["rating_service"] = rating_service

    scheduler.add_job(scheduler_service.scan_all_channels, "interval", hours=1, id="channel_scan", replace_existing=True)
    scheduler.add_job(rating_service.calculate_daily_rating, "cron", hour=21, minute=0, id="daily_rating", replace_existing=True)
    scheduler.add_job(scheduler_service.run_cross_promotion, "cron", hour=12, minute=0, id="cross_promo", replace_existing=True)
    scheduler.add_job(scheduler_service.check_scheduled_posts, "interval", minutes=1, id="scheduled_posts", replace_existing=True)

    scheduler.start()
    logger.info("✅ Bot ishga tushdi!")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())