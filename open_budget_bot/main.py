import asyncio
import logging
from datetime import datetime, timedelta

from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database import init_db
from handlers import (
    cmd_start, cmd_stats, cmd_delete_me, cmd_privacy,
    handle_callback, send_due_reminders,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def post_init(app):
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        send_due_reminders,
        "interval",
        minutes=1,
        args=[app],
        next_run_time=datetime.now() + timedelta(seconds=10),
        id="reminders",
    )
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info("Open Budget Bot started")


async def post_shutdown(app):
    scheduler = app.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


def main():
    config.validate()
    init_db()

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("delete_me", cmd_delete_me))
    app.add_handler(CommandHandler("privacy", cmd_privacy))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info(f"Polling... admins={config.ADMIN_IDS}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
