import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from app.config import config

logger = logging.getLogger(__name__)


def is_authorized(user_id: int) -> bool:
    return user_id == config.TELEGRAM_ADMIN_USER_ID


def authorized_only(func):
    """Decorator: reject unauthorized users."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not is_authorized(user.id):
            logger.warning(f"Unauthorized access attempt from user_id={user.id if user else 'unknown'}")
            await update.effective_message.reply_text("❌ Ruxsat yo'q.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
