import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from app.database import get_session
from app.models import User, WatchRule
from app.bot.security import authorized_only
from app.bot.keyboards import (
    region_keyboard, source_keyboard, notify_type_keyboard,
    confirm_keyboard, skip_keyboard, main_menu_keyboard,
)
from app.utils.money import parse_price, format_price

logger = logging.getLogger(__name__)

# Conversation states
(
    KEYWORD, MAX_PRICE, MIN_PRICE, MIN_QTY,
    REGION, SOURCE, NOTIFY_TYPE, CONFIRM,
) = range(8)

SKIP = "skip"


def _get_or_create_user(session, tg_user, chat_id: int) -> User:
    user = session.query(User).filter_by(telegram_user_id=tg_user.id).first()
    if not user:
        user = User(
            telegram_user_id=tg_user.id,
            telegram_chat_id=chat_id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        session.add(user)
        session.flush()
    return user


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "➕ *Yangi kuzatuv*\n\n"
        "1-qadam: Mahsulot nomi yoki kalit so'z yozing.\n"
        "_Masalan: konditsioner_",
        parse_mode="Markdown",
    )
    return KEYWORD


async def got_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyword = update.message.text.strip()
    if not keyword:
        await update.message.reply_text("Kalit so'z bo'sh bo'lmasligi kerak.")
        return KEYWORD

    context.user_data["keyword"] = keyword
    await update.message.reply_text(
        f"✅ Kalit so'z: *{keyword}*\n\n"
        "2-qadam: Maksimal narx (so'm)?\n"
        "_Masalan: 3500000_",
        parse_mode="Markdown",
        reply_markup=skip_keyboard(),
    )
    return MAX_PRICE


async def got_max_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data["max_price"] = None
    else:
        price = parse_price(update.message.text.strip())
        context.user_data["max_price"] = price

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(
        "3-qadam: Minimal narx?\n_O'tkazib yuborish uchun tugmani bosing._",
        parse_mode="Markdown",
        reply_markup=skip_keyboard(),
    )
    return MIN_PRICE


async def got_min_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data["min_price"] = None
    else:
        context.user_data["min_price"] = parse_price(update.message.text.strip())

    msg = update.effective_message
    await msg.reply_text(
        "4-qadam: Minimal miqdor?\n_O'tkazib yuborish uchun tugmani bosing._",
        parse_mode="Markdown",
        reply_markup=skip_keyboard(),
    )
    return MIN_QTY


async def got_min_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data["min_qty"] = None
    else:
        text = update.message.text.strip()
        try:
            context.user_data["min_qty"] = int(text)
        except ValueError:
            context.user_data["min_qty"] = None

    msg = update.effective_message
    await msg.reply_text(
        "5-qadam: Hudud tanlang:",
        reply_markup=region_keyboard(),
    )
    return REGION


async def got_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    region = query.data.replace("reg:", "")
    context.user_data["region"] = None if region.lower() == "barchasi" else region

    await query.edit_message_text(
        f"✅ Hudud: *{region}*\n\n6-qadam: Manba tanlang:",
        parse_mode="Markdown",
        reply_markup=source_keyboard(),
    )
    return SOURCE


async def got_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    src = query.data.replace("src:", "")
    context.user_data["source"] = None if src == "all" else src

    await query.edit_message_text(
        "7-qadam: Qanday xabar olmoqchisiz?",
        reply_markup=notify_type_keyboard(),
    )
    return NOTIFY_TYPE


async def got_notify_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ntype = query.data.replace("notify:", "")

    context.user_data["notify_new"] = ntype in ("new", "both")
    context.user_data["notify_price"] = ntype in ("price", "both")

    d = context.user_data
    keyword = d.get("keyword", "")
    max_p = d.get("max_price")
    min_p = d.get("min_price")
    region = d.get("region") or "Barchasi"
    source = d.get("source") or "Barchasi"
    notify_parts = []
    if d.get("notify_new"):
        notify_parts.append("Yangi savdo")
    if d.get("notify_price"):
        notify_parts.append("Narx tushishi")
    notify_str = " + ".join(notify_parts)

    summary = (
        f"📋 *Kuzatuv ma'lumotlari:*\n\n"
        f"🔑 Kalit so'z: `{keyword}`\n"
        f"💰 Narx: {'≤ ' + format_price(max_p) if max_p else '—'}"
        f"{' / ≥ ' + format_price(min_p) if min_p else ''}\n"
        f"📍 Hudud: {region}\n"
        f"📡 Manba: {source}\n"
        f"🔔 Xabar: {notify_str}\n\n"
        f"Tasdiqlaysizmi?"
    )

    await query.edit_message_text(summary, parse_mode="Markdown", reply_markup=confirm_keyboard())
    return CONFIRM


async def got_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "confirm:no":
        await query.edit_message_text("❌ Bekor qilindi.")
        return ConversationHandler.END

    d = context.user_data
    keyword = d.get("keyword", "")

    with get_session() as session:
        tg_user = update.effective_user
        user = _get_or_create_user(session, tg_user, update.effective_chat.id)

        rule = WatchRule(
            user_id=user.id,
            name=keyword.capitalize(),
            keyword=keyword,
            max_price=d.get("max_price"),
            min_price=d.get("min_price"),
            min_quantity=d.get("min_qty"),
            region=d.get("region"),
            source=d.get("source"),
            notify_new=d.get("notify_new", True),
            notify_price_drop=d.get("notify_price", True),
        )
        session.add(rule)

    await query.edit_message_text(
        f"✅ *Kuzatuv yaratildi!*\n\nKalit so'z: `{keyword}`",
        parse_mode="Markdown",
    )
    await update.effective_message.reply_text(
        "Asosiy menyu:", reply_markup=main_menu_keyboard()
    )
    logger.info(f"Watch rule created: keyword='{keyword}' by user {tg_user.id}")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "❌ Bekor qilindi.", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


def build_add_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
            MessageHandler(filters.Regex("^➕ Kuzatuv qo'shish$"), add_start),
        ],
        states={
            KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_keyword)],
            MAX_PRICE: [
                CallbackQueryHandler(got_max_price, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_max_price),
            ],
            MIN_PRICE: [
                CallbackQueryHandler(got_min_price, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_min_price),
            ],
            MIN_QTY: [
                CallbackQueryHandler(got_min_qty, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_min_qty),
            ],
            REGION: [CallbackQueryHandler(got_region, pattern="^reg:")],
            SOURCE: [CallbackQueryHandler(got_source, pattern="^src:")],
            NOTIFY_TYPE: [CallbackQueryHandler(got_notify_type, pattern="^notify:")],
            CONFIRM: [CallbackQueryHandler(got_confirm, pattern="^confirm:")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^⚙️ Sozlamalar$"), cancel),
        ],
        per_message=False,
    )
