import asyncio
import logging
from datetime import datetime, timedelta

from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import config
from app.database import init_db
from app.utils.logging import setup_logging
from app.bot.handlers import (
    cmd_start, cmd_list, cmd_cheap, cmd_latest,
    cmd_search, cmd_status, cmd_help,
    handle_text, handle_callback,
)
from app.bot.conversations import build_add_conversation
from app.services.watcher import run_check

logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        run_check,
        "interval",
        minutes=config.CHECK_INTERVAL_MINUTES,
        args=[app],
        next_run_time=datetime.now() + timedelta(seconds=15),
        id="watcher",
    )
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info(
        f"Scheduler started — checking every {config.CHECK_INTERVAL_MINUTES} min"
    )


async def post_shutdown(app: Application) -> None:
    scheduler = app.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Bot stopped.")


def build_app() -> Application:
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Conversation handlers (must come before general handlers)
    app.add_handler(build_add_conversation())

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("cheap", cmd_cheap))
    app.add_handler(CommandHandler("latest", cmd_latest))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Plain text (menu buttons + awaiting inputs)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


def main() -> None:
    setup_logging()
    logger.info("Starting cooperation-watcher-bot")

    config.validate()
    init_db()
    logger.info("Database initialized")

    # Python 3.10+ requires explicit event loop in main thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = build_app()
    logger.info(f"Bot polling... admin={config.TELEGRAM_ADMIN_USER_ID}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
