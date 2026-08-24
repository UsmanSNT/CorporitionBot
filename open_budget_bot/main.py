import asyncio
import logging
from datetime import datetime, timedelta

from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database import init_db
from handlers import (
    cmd_start, cmd_holat, cmd_stats, cmd_users, cmd_top,
    cmd_broadcast, cmd_announce_top,
    cmd_admins, cmd_addadmin, cmd_removeadmin, cmd_delete_me,
    handle_callback, handle_photo,
    send_due_reminders, send_deadline_reminders,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# httpx INFO logi har bir so'rovni to'liq URL bilan yozadi — unda bot tokeni bor.
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def post_init(app):
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        send_due_reminders, "interval", minutes=1, args=[app],
        next_run_time=datetime.now() + timedelta(seconds=10),
        id="reminders",
    )
    scheduler.add_job(
        send_deadline_reminders, "cron", hour=9, minute=0, args=[app],
        id="deadline_reminders",
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
    app.add_handler(CommandHandler("holat", cmd_holat))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("announce_top", cmd_announce_top))
    app.add_handler(CommandHandler("admins", cmd_admins))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("removeadmin", cmd_removeadmin))
    app.add_handler(CommandHandler("delete_me", cmd_delete_me))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info(f"Polling... admins={config.ADMIN_IDS}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
