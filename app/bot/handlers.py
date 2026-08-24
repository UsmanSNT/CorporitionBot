import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from app.config import config
from app.database import get_session
from app.models import User, WatchRule, Notification
from app.services.listing_service import get_cheapest, get_latest_listings, search_listings
from app.services.watcher import SOURCE_STATUS
from app.bot.security import authorized_only, is_main_admin
from app.bot.keyboards import (
    main_menu_keyboard, rule_action_keyboard, latest_filter_keyboard,
    admin_users_keyboard,
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

    _is_admin = is_main_admin(tg_user.id)
    await update.message.reply_text(
        f"Assalomu alaykum, {tg_user.first_name}! 👋\n\n"
        "Men Uzbekiston davlat xarid saytlarini kuzataman:\n"
        "• cooperation.uz\n"
        "• new.cooperation.uz\n"
        "• xt-xarid.uz\n\n"
        "Yangi savdo chiqsa — darhol xabar beraman!\n\n"
        "👇 Menyudan boshlang:",
        reply_markup=main_menu_keyboard(is_admin=_is_admin),
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
        last_check_val = last_check_state.value if last_check_state else None
        from app.models import Listing as L
        total_listings = session.query(L).count()
        total_rules = session.query(WatchRule).count()
        total_notifs = session.query(Notification).count()

    last_check = last_check_val[:16] if last_check_val else "Hali tekshirilmagan"

    coop_status = SOURCE_STATUS.get("cooperation", "unknown")
    new_coop_status = SOURCE_STATUS.get("new_cooperation", "unknown")
    xt_xarid_status = SOURCE_STATUS.get("xt_xarid", "unknown")

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
        f"{status_emoji(new_coop_status)} New Cooperation: `{new_coop_status}`\n"
        f"{status_emoji(xt_xarid_status)} XT-Xarid: `{xt_xarid_status}`"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    _is_admin = is_main_admin(tg_user.id)
    admin_section = "\n\n👑 *Admin buyruqlari:*\n/admins — Adminlar ro'yxati va boshqaruv" if _is_admin else ""
    text = (
        "📖 *Yordam*\n\n"
        "🔎 *Kuzatuvlar* — qo'shgan kuzatuvlaringiz\n"
        "➕ *Kuzatuv qo'shish* — yangi kuzatuv yaratish\n"
        "🆕 *Yangi savdolar* — eng so'nggi e'lonlar\n"
        "🔥 *Eng arzon* — arzon savdolar\n"
        "📉 *Narxi tushganlar* — narxi pasaygan savdolar\n"
        "🔍 *Qidirish* — kalit so'z bo'yicha qidirish\n"
        "📊 *Holat* — bot va manbalar holati\n\n"
        "💡 *Maslahat:* Kuzatuv qo'shing, yangi savdo chiqsa avtomatik xabar olasiz!"
        + admin_section
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard(is_admin=_is_admin))


@authorized_only
async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not is_main_admin(tg_user.id):
        await update.message.reply_text("❌ Bu buyruq faqat asosiy admin uchun.")
        return

    with get_session() as session:
        all_users = session.query(User).all()
        user_data = [(u.telegram_user_id, u.username, u.first_name, u.is_admin) for u in all_users]

    if not user_data:
        await update.message.reply_text("Hozircha bot foydalanuvchilari yo'q.")
        return

    lines = ["👥 <b>Adminlar va foydalanuvchilar:</b>\n"]
    for uid, uname, fname, is_adm in user_data:
        role = "👑 Asosiy admin" if uid == config.TELEGRAM_ADMIN_USER_ID else ("🔑 Admin" if is_adm else "👤 Foydalanuvchi")
        name = f"@{uname}" if uname else (fname or str(uid))
        lines.append(f"{role}: {name} (<code>{uid}</code>)")

    admins = [(uid, uname, fname) for uid, uname, fname, is_adm in user_data
              if is_adm and uid != config.TELEGRAM_ADMIN_USER_ID]

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for uid, uname, fname in admins:
        label = f"@{uname}" if uname else (fname or str(uid))
        rows.append([InlineKeyboardButton(f"❌ {label} ni o'chirish", callback_data=f"admin:remove:{uid}")])
    rows.append([InlineKeyboardButton("➕ Admin qo'shish", callback_data="admin:addlist")])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if not text:
        return

    MENU_BUTTONS = {
        "🔎 Kuzatuvlar", "🔥 Eng arzon", "🆕 Yangi savdolar",
        "🔍 Qidirish", "📊 Holat", "📉 Narxi tushganlar",
        "⚙️ Sozlamalar", "➕ Kuzatuv qo'shish", "👥 Adminlar", "ℹ️ Yordam",
    }
    if text in MENU_BUTTONS:
        context.user_data.pop("awaiting_search", None)
        context.user_data.pop("awaiting_cheap_keyword", None)

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
    if text == "👥 Adminlar":
        return await cmd_admins(update, context)
    if text == "ℹ️ Yordam":
        return await cmd_help(update, context)
    if text == "⚙️ Sozlamalar":
        return await cmd_help(update, context)
    if text == "➕ Kuzatuv qo'shish":
        from app.bot.conversations import add_start
        return await add_start(update, context)

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

        from datetime import datetime, timedelta
        from app.models import SystemState, Listing as ListingModel

        with get_session() as session:
            # Get last check time
            last_check_state = session.get(SystemState, "last_check")
            last_check_str = last_check_state.value if last_check_state else None

            # Only show listings added in last 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            q = session.query(ListingModel).filter(ListingModel.first_seen_at >= cutoff)
            if src:
                q = q.filter(ListingModel.source == src)
            recent = q.order_by(ListingModel.first_seen_at.desc()).limit(10).all()
            listing_data = [(lst.title, lst.source_url, lst.price, lst.first_seen_at) for lst in recent]

        if not listing_data:
            # Show when last checked
            if last_check_str:
                try:
                    lc = datetime.fromisoformat(last_check_str)
                    diff = datetime.utcnow() - lc
                    mins = int(diff.total_seconds() / 60)
                    time_info = f"{mins} daqiqa oldin" if mins < 60 else f"{mins // 60} soat oldin"
                except Exception:
                    time_info = last_check_str[:16]
            else:
                time_info = "noma'lum"
            await query.answer()
            await query.edit_message_text(
                f"🆕 Yangi savdo yo'q\n\n"
                f"⏰ Oxirgi tekshiruv: {time_info}\n"
                f"🔄 Keyingi tekshiruv {config.CHECK_INTERVAL_MINUTES} daqiqadan so'ng"
            )
            return

        label = {
            "all": "Barchasi",
            "cooperation": "Cooperation",
            "new_cooperation": "New Cooperation",
            "xt_xarid": "XT-Xarid",
        }.get(source_filter, source_filter)
        lines = [f"🆕 *Yangi savdolar — {label}:*\n"]
        for title, source_url, price, seen_at in listing_data:
            time_str = seen_at.strftime("%H:%M") if seen_at else ""
            lines.append(
                f"• [{truncate(title, 60)}]({source_url or '#'})\n"
                f"  {format_price(price)}"
                + (f" | 🕐 {time_str}" if time_str else "")
            )
        await query.answer()
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )

    elif data.startswith("search:"):
        keyword = data.replace("search:", "")
        with get_session() as session:
            results = search_listings(session, keyword, limit=10)
            results_data = [(lst.title, lst.source_url) for lst in results]
        if not results_data:
            await query.answer(f"'{keyword}' bo'yicha natija yo'q.")
            return
        lines = [f"🔍 *'{keyword}':*\n"]
        for title, source_url in results_data:
            lines.append(f"• [{truncate(title, 60)}]({source_url or '#'})")
        await query.answer()
        await query.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
        )

    elif data.startswith("admin:"):
        tg_user = update.effective_user
        if not is_main_admin(tg_user.id):
            await query.answer("❌ Ruxsat yo'q.", show_alert=True)
            return

        parts = data.split(":")
        action = parts[1]

        if action == "close":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.answer()

        elif action == "addlist":
            with get_session() as session:
                non_admins = session.query(User).filter_by(is_admin=False).all()
                users = [(u.telegram_user_id, u.username, u.first_name) for u in non_admins
                         if u.telegram_user_id != config.TELEGRAM_ADMIN_USER_ID]
            if not users:
                await query.answer("Barcha foydalanuvchilar allaqachon admin.", show_alert=True)
                return
            await query.answer()
            await query.edit_message_reply_markup(reply_markup=admin_users_keyboard(users, "makeadmin"))

        elif action == "makeadmin":
            target_id = int(parts[2])
            with get_session() as session:
                user = session.query(User).filter_by(telegram_user_id=target_id).first()
                if user:
                    user.is_admin = True
                    name = f"@{user.username}" if user.username else (user.first_name or str(target_id))
                    await query.answer(f"✅ {name} admin qilindi!", show_alert=True)
                else:
                    await query.answer("Foydalanuvchi topilmadi.", show_alert=True)
                    return
            await cmd_admins(update, context)

        elif action == "remove":
            target_id = int(parts[2])
            with get_session() as session:
                user = session.query(User).filter_by(telegram_user_id=target_id).first()
                if user:
                    user.is_admin = False
                    name = f"@{user.username}" if user.username else (user.first_name or str(target_id))
                    await query.answer(f"✅ {name} admin emas.", show_alert=True)
                else:
                    await query.answer("Foydalanuvchi topilmadi.", show_alert=True)
                    return
            await cmd_admins(update, context)
