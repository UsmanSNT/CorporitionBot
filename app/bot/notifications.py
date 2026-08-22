import logging
from telegram import Bot
from app.models import User, Listing, WatchRule
from app.utils.money import format_price
from app.utils.text import truncate
from app.bot.keyboards import listing_keyboard

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "cooperation": "Cooperation",
    "new_cooperation": "New Cooperation",
}


async def send_new_listing_notification(
    bot: Bot, user: User, listing: Listing, rule: WatchRule
) -> None:
    label = SOURCE_LABELS.get(listing.source, listing.source)
    price_str = format_price(listing.price, listing.currency or "UZS")
    qty_str = f"📦 Miqdor: {listing.quantity}" if listing.quantity else ""
    region_str = f"📍 {listing.region}" if listing.region else ""
    seller_str = f"🏢 {listing.seller_name}" if listing.seller_name else ""

    parts = [
        f"🆕 *Yangi mos savdo*",
        f"*{truncate(listing.title, 150)}*",
        f"💰 {price_str}",
    ]
    if qty_str:
        parts.append(qty_str)
    if region_str:
        parts.append(region_str)
    if seller_str:
        parts.append(seller_str)
    parts.append(f"🔎 Kuzatuv: _{rule.name}_")
    parts.append(f"📡 Manba: {label}")

    text = "\n".join(parts)
    keyboard = listing_keyboard(listing.source_url, rule.keyword)

    try:
        await bot.send_message(
            chat_id=user.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        logger.info(f"Sent new-listing notification to user {user.telegram_user_id}")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


async def send_price_drop_notification(
    bot: Bot, user: User, listing: Listing, rule: WatchRule, old_price: int
) -> None:
    label = SOURCE_LABELS.get(listing.source, listing.source)
    new_price = listing.price or 0
    diff = old_price - new_price
    pct = round(diff / old_price * 100, 1) if old_price else 0

    text = (
        f"📉 *Narx tushdi!*\n"
        f"*{truncate(listing.title, 150)}*\n"
        f"Eski narx: {format_price(old_price)}\n"
        f"Yangi narx: {format_price(new_price)}\n"
        f"Farq: -{format_price(diff)} (-{pct}%)\n"
    )
    if listing.seller_name:
        text += f"🏢 {listing.seller_name}\n"
    text += f"📡 Manba: {label}"

    keyboard = listing_keyboard(listing.source_url, rule.keyword)

    try:
        await bot.send_message(
            chat_id=user.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        logger.info(f"Sent price-drop notification to user {user.telegram_user_id}")
    except Exception as e:
        logger.error(f"Failed to send price-drop notification: {e}")
