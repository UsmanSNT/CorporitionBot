import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from app.config import config

logger = logging.getLogger(__name__)


def is_main_admin(user_id: int) -> bool:
    return user_id == config.TELEGRAM_ADMIN_USER_ID


def is_authorized(user_id: int) -> bool:
    if user_id == config.TELEGRAM_ADMIN_USER_ID:
        return True
    if user_id in config.TELEGRAM_EXTRA_USER_IDS:
        return True
    try:
        from app.database import get_session
        from app.models import User
        with get_session() as session:
            user = session.query(User).filter_by(telegram_user_id=user_id).first()
            return user is not None and bool(user.is_admin)
    except Exception:
        return False


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
