import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from app.config import config
from app.database import get_session
from app.models import User, WatchRule, Notification
from app.services.listing_service import get_cheapest, get_latest_listings, search_listings
from app.services.watcher import SOURCE_STATUS
from app.bot.security import authorized_only
from app.bot.keyboards import (
    main_menu_keyboard, rule_action_keyboard, latest_filter_keyboard,
)
from app.utils.money import format_price
from app.utils.text import truncate

logger = logging.getLogger(__name__)


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


@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    with get_session() as session:
        _get_or_create_user(session, tg_user, update.effective_chat.id)

    await update.message.reply_text(
        f"Salom, {tg_user.first_name}! 👋\n\n"
        "Men cooperation.uz va new.cooperation.uz saytlarini kuzatib, "
        "mos mahsulotlar topilganda sizga xabar beraman.\n\n"
        "Boshlash uchun quyidagi menyudan foydalaning:",
        reply_markup=main_menu_keyboard(),
    )


@authorized_only
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    with get_session() as session:
        user = session.query(User).filter_by(telegram_user_id=tg_user.id).first()
        if not user:
            await update.message.reply_text("Hozircha kuzatuv yo'q.")
            return

        rules = session.query(WatchRule).filter_by(user_id=user.id).all()
        if not rules:
            await update.message.reply_text("🔎 Kuzatuvlar yo'q.\n\n'➕ Kuzatuv qo'shish' tugmasini bosing.")
            return

        for rule in rules:
            status = "✅" if rule.enabled else "⏸"
            price_info = ""
            if rule.max_price:
                price_info += f"≤ {format_price(rule.max_price)}"
            if rule.min_price:
                price_info += f" / ≥ {format_price(rule.min_price)}"

            text = (
                f"{status} *{rule.name}*\n"
                f"🔑 `{rule.keyword}`"
                f"{' | ' + price_info if price_info else ''}"
                f"{' | ' + rule.region if rule.region else ''}\n"
                f"📡 {rule.source or 'Barchasi'}"
            )
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=rule_action_keyboard(rule.id, rule.enabled),
            )


@authorized_only
async def cmd_cheap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    keyword = " ".join(args) if args else None

    if not keyword:
        await update.message.reply_text(
            "🔥 *Eng arzon mahsulotlar*\n\nKalit so'z yozing (masalan: konditsioner) yoki bo'sh qoldiring:",
            parse_mode="Markdown",
        )
        context.user_data["awaiting_cheap_keyword"] = True
        return

    await _show_cheap(update, keyword)


async def _show_cheap(update: Update, keyword: str | None) -> None:
    with get_session() as session:
        listings = get_cheapest(session, keyword, limit=10)

    if not listings:
        await update.effective_message.reply_text(
            f"'{keyword}' bo'yicha arzon savdo topilmadi." if keyword else "Ma'lumotlar yo'q."
        )
        return

    lines = [f"🔥 *Eng arzon{' — ' + keyword if keyword else ''}:*\n"]
    for i, lst in enumerate(listings, 1):
        price_str = format_price(lst.price, lst.currency or "UZS")
        lines.append(
            f"{i}. [{truncate(lst.title, 60)}]({lst.source_url or '#'})\n"
            f"   💰 {price_str}"
            f"{' | ' + lst.seller_name if lst.seller_name else ''}"
            f"{' | ' + lst.region if lst.region else ''}\n"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


@authorized_only
async def cmd_latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🆕 *Yangi savdolar* — manba tanlang:",
        parse_mode="Markdown",
        reply_markup=latest_filter_keyboard(),
    )


@authorized_only
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Qidiruv so'zini yozing:")
    context.user_data["awaiting_search"] = True


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.models import SystemState
    with get_session() as session:
        last_check_state = session.get(SystemState, "last_check")
        from app.models import Listing as L
        total_listings = session.query(L).count()
        total_rules = session.query(WatchRule).count()
        total_notifs = session.query(Notification).count()

    last_check = last_check_state.value[:16] if last_check_state else "Hali tekshirilmagan"

    coop_status = SOURCE_STATUS.get("cooperation", "unknown")
    new_coop_status = SOURCE_STATUS.get("new_cooperation", "unknown")

    status_emoji = lambda s: "✅" if s == "ok" else "❌"

    text = (
        f"📊 *Bot holati*\n\n"
        f"🤖 Bot: ✅ Ishlayapti\n"
        f"⏰ Oxirgi tekshiruv: `{last_check}`\n"
        f"⏱ Interval: {config.CHECK_INTERVAL_MINUTES} daqiqa\n\n"
        f"📋 Aktiv kuzatuvlar: {total_rules}\n"
        f"📦 Saqlangan savdolar: {total_listings}\n"
        f"🔔 Yuborilgan xabarlar: {total_notifs}\n\n"
        f"🌐 *Manbalar:*\n"
        f"{status_emoji(coop_status)} Cooperation: `{coop_status}`\n"
        f"{status_emoji(new_coop_status)} New Cooperation: `{new_coop_status}`"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *Buyruqlar:*\n\n"
        "/start — Bosh menyu\n"
        "/add — Yangi kuzatuv qo'shish\n"
        "/list — Kuzatuvlar ro'yxati\n"
        "/cheap [so'z] — Eng arzon savdolar\n"
        "/latest — Yangi savdolar\n"
        "/search — Qidirish\n"
        "/status — Bot holati\n"
        "/help — Yordam\n"
        "/cancel — Amalni bekor qilish"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if not text:
        return

    # Menu buttons
    if text == "🔎 Kuzatuvlar":
        return await cmd_list(update, context)
    if text == "🔥 Eng arzon":
        return await cmd_cheap(update, context)
    if text == "🆕 Yangi savdolar":
        return await cmd_latest(update, context)
    if text == "🔍 Qidirish":
        return await cmd_search(update, context)
    if text == "📊 Holat":
        return await cmd_status(update, context)
    if text == "📉 Narxi tushganlar":
        await _show_price_drops(update)
        return
    if text == "⚙️ Sozlamalar":
        await update.message.reply_text(
            "⚙️ Sozlamalar hozircha mavjud emas.\n/help buyrug'ini ko'ring."
        )
        return

    # Awaiting inputs
    if context.user_data.get("awaiting_search"):
        context.user_data.pop("awaiting_search")
        with get_session() as session:
            results = search_listings(session, text, limit=10)
        if not results:
            await update.message.reply_text(f"'{text}' bo'yicha natija topilmadi.")
            return
        lines = [f"🔍 *'{text}' natijalari:*\n"]
        for lst in results:
            lines.append(
                f"• [{truncate(lst.title, 60)}]({lst.source_url or '#'})\n"
                f"  {format_price(lst.price)}"
            )
        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )
        return

    if context.user_data.get("awaiting_cheap_keyword"):
        context.user_data.pop("awaiting_cheap_keyword")
        await _show_cheap(update, text)
        return


async def _show_price_drops(update: Update) -> None:
    from app.models import Listing, PriceHistory
    from sqlalchemy import func
    with get_session() as session:
        # Listings that have more than one price record (meaning price changed)
        subq = (
            session.query(PriceHistory.listing_id)
            .group_by(PriceHistory.listing_id)
            .having(func.count(PriceHistory.id) > 1)
            .subquery()
        )
        listings = (
            session.query(Listing)
            .join(subq, Listing.id == subq.c.listing_id)
            .order_by(Listing.last_seen_at.desc())
            .limit(10)
            .all()
        )

    if not listings:
        await update.effective_message.reply_text("📉 Hozircha narxi tushgan savdo yo'q.")
        return

    lines = ["📉 *Narxi tushgan savdolar:*\n"]
    for lst in listings:
        lines.append(
            f"• [{truncate(lst.title, 60)}]({lst.source_url or '#'})\n"
            f"  {format_price(lst.price)}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data

    if data.startswith("rule:"):
        _, action, rule_id_str = data.split(":")
        rule_id = int(rule_id_str)

        with get_session() as session:
            rule = session.get(WatchRule, rule_id)
            if not rule:
                await query.answer("Kuzatuv topilmadi.")
                return

            if action == "toggle":
                rule.enabled = not rule.enabled
                status = "▶️ Davom ettirildi" if rule.enabled else "⏸ To'xtatildi"
                await query.answer(status)
                await query.edit_message_reply_markup(
                    reply_markup=rule_action_keyboard(rule.id, rule.enabled)
                )

            elif action == "delete":
                session.delete(rule)
                await query.answer("🗑 O'chirildi")
                await query.edit_message_text(f"🗑 Kuzatuv o'chirildi.")

    elif data.startswith("latest:"):
        source_filter = data.replace("latest:", "")
        src = None if source_filter == "all" else source_filter

        with get_session() as session:
            listings = get_latest_listings(session, src, limit=10)

        if not listings:
            await query.answer("Ma'lumot yo'q.")
            await query.edit_message_text("🆕 Hozircha yangi savdo yo'q.")
            return

        label = {"all": "Barchasi", "cooperation": "Cooperation", "new_cooperation": "New Cooperation"}.get(source_filter, source_filter)
        lines = [f"🆕 *Yangi savdolar — {label}:*\n"]
        for lst in listings:
            lines.append(
                f"• [{truncate(lst.title, 60)}]({lst.source_url or '#'})\n"
                f"  {format_price(lst.price)}"
            )
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )

    elif data.startswith("search:"):
        keyword = data.replace("search:", "")
        with get_session() as session:
            results = search_listings(session, keyword, limit=10)
        if not results:
            await query.answer(f"'{keyword}' bo'yicha natija yo'q.")
            return
        lines = [f"🔍 *'{keyword}':*\n"]
        for lst in results:
            lines.append(f"• [{truncate(lst.title, 60)}]({lst.source_url or '#'})")
        await query.answer()
        await query.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )
