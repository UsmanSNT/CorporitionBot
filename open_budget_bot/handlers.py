import logging
import os
import glob as glob_module
from datetime import datetime, date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, Application

from config import config
import database as db
from openbudget_api import fetch_vote_count

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _project_text() -> str:
    lines = [f"<b>{config.PROJECT_TITLE}</b>"]
    if config.PROJECT_ID:
        lines.append(f"📋 Loyiha raqami: <code>{config.PROJECT_ID}</code>")
    if config.PROJECT_REGION:
        lines.append(f"📍 Hudud: {config.PROJECT_REGION}")
    if config.PROJECT_DESCRIPTION:
        lines.append(f"\n{config.PROJECT_DESCRIPTION}")
    if config.VOTING_DEADLINE:
        lines.append(f"\n⏰ Muddati: <b>{config.VOTING_DEADLINE}</b>")
    # Rasmiy sayt ovozlarni kechikib yangilaydi — 0 bo'lsa ko'rsatmaymiz,
    # aks holda odamlar "ovozim hisobga olinmadi" deb o'ylaydi.
    if config.INITIATIVE_UUID:
        count = fetch_vote_count(config.INITIATIVE_UUID)
        if count:
            lines.append(f"\n🗳 Rasmiy saytdagi ovozlar: <b>{count}</b>")
    voted = db.get_stats()["voted"]
    if voted:
        lines.append(f"✅ Bot orqali tasdiqlangan: <b>{voted}</b> kishi")
    return "\n".join(lines)


def _referral_link(user_id: int) -> str:
    if config.BOT_USERNAME:
        return f"https://t.me/{config.BOT_USERNAME}?start=ref_{user_id}"
    return ""


def _days_left() -> int | None:
    if not config.DEADLINE_DATE:
        return None
    try:
        return (date.fromisoformat(config.DEADLINE_DATE) - date.today()).days
    except ValueError:
        return None


def _main_keyboard(pending: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("🗳 Ovoz berish", url=config.VOTE_URL)]]
    if not pending:
        rows.append([InlineKeyboardButton("📸 Ovoz berdim — tasdiqlash", callback_data="submit_proof")])
    else:
        rows.append([InlineKeyboardButton("⏳ Tasdiq kutilmoqda...", callback_data="noop")])
    rows.append([InlineKeyboardButton("📢 Do'stlarga ulash", callback_data="share")])
    return InlineKeyboardMarkup(rows)


def _voted_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗳 Rasmiy sayt", url=config.VOTE_URL)],
        [InlineKeyboardButton("📢 Do'stlarga ulash", callback_data="share")],
        [
            InlineKeyboardButton("🏘 Mahalla reytingi", callback_data="rating"),
            InlineKeyboardButton("🏆 Top faollar", callback_data="leaderboard"),
        ],
    ])


def _mahalla_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(m, callback_data=f"mahalla:{m}")] for m in config.MAHALLAS]
    rows.append([InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="mahalla:skip")])
    return InlineKeyboardMarkup(rows)


def _get_images() -> list[str]:
    if not config.IMAGE_DIR or not os.path.isdir(config.IMAGE_DIR):
        return []
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        files.extend(glob_module.glob(os.path.join(config.IMAGE_DIR, ext)))
    return sorted(files)[:10]


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS or db.is_db_admin(user_id)


def _is_main_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def _notify_admins(bot, text: str, **kwargs):
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML", **kwargs)
        except Exception as e:
            logger.warning(f"Admin notify failed {admin_id}: {e}")


# ── commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0][4:])
            if ref_id != user.id:
                referred_by = ref_id
        except ValueError:
            pass

    existing = db.get_user(user.id)
    is_new = existing is None
    db.upsert_user(user.id, user.username, user.first_name, referred_by)

    if is_new:
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        ref_note = f"\n🔗 Referral: ID {referred_by}" if referred_by else ""
        await _notify_admins(
            context.bot,
            f"👤 <b>Yangi foydalanuvchi</b>\n{user.first_name} ({uname}){ref_note}",
        )

    existing = db.get_user(user.id)
    has_voted = bool(existing and existing["voted"])
    pending = bool(existing and existing["pending_approval"])

    days = _days_left()
    deadline_line = ""
    if days is not None and not has_voted:
        if days == 0:
            deadline_line = "\n\n🔴 <b>Bugun oxirgi kun!</b>"
        elif days <= 3:
            deadline_line = f"\n\n🟡 <b>{days} kun qoldi!</b>"

    if has_voted:
        status_line = "\n\n✅ <b>Siz ovoz bergansiz. Rahmat!</b>"
        keyboard = _voted_keyboard()
    elif pending:
        status_line = "\n\n⏳ <b>Tasdiqlash kutilmoqda...</b>"
        keyboard = _main_keyboard(pending=True)
    else:
        status_line = "\n\n👇 Ovoz berib, screenshot yuboring:"
        keyboard = _main_keyboard()

    caption = f"Assalomu alaykum, {user.first_name}! 👋\n\n" + _project_text() + deadline_line + status_line

    images = _get_images()
    if images:
        if len(images) == 1:
            with open(images[0], "rb") as f:
                await update.message.reply_photo(photo=f, caption=caption, parse_mode="HTML", reply_markup=keyboard)
        else:
            media = []
            for i, path in enumerate(images):
                with open(path, "rb") as f:
                    data = f.read()
                media.append(InputMediaPhoto(data, caption=caption, parse_mode="HTML") if i == 0 else InputMediaPhoto(data))
            await update.message.reply_media_group(media=media)
            await update.message.reply_text(status_line.strip(), reply_markup=keyboard)
    else:
        await update.message.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)

    if config.MAHALLAS and existing and existing.get("mahalla") is None:
        await update.message.reply_text(
            "🏘 <b>Qaysi mahalladan ekansiz?</b>",
            parse_mode="HTML",
            reply_markup=_mahalla_keyboard(),
        )


async def cmd_holat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_stats()
    days = _days_left()
    deadline_str = f"{days} kun qoldi" if days is not None else config.VOTING_DEADLINE
    lines = [
        "📊 <b>Bot holati</b>\n",
        f"👤 Foydalanuvchilar: <b>{stats['total']}</b>",
        f"✅ Botda tasdiqlangan: <b>{stats['voted']}</b>",
        f"📢 Referral orqali: <b>{stats['via_referral']}</b>",
    ]
    if config.INITIATIVE_UUID:
        real_count = fetch_vote_count(config.INITIATIVE_UUID)
        if real_count is not None:
            lines.append(f"\n🗳 <b>Rasmiy saytdagi ovozlar: {real_count}</b>")
            if real_count == 0:
                lines.append("<i>(sayt hisobni kechikib yangilaydi)</i>")
    lines.append(f"\n⏰ Muddatga: <b>{deadline_str}</b>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Ruxsat yo'q.")
        return
    stats = db.get_stats()
    top = db.get_top_referrers(5)
    mahalla_stats = db.get_mahalla_stats()
    days = _days_left()
    lines = [
        "📊 <b>Statistika</b>\n",
        f"👤 Boshlagan: <b>{stats['total']}</b>",
        f"🔗 Saytga o'tgan: <b>{stats['clicked']}</b>",
        f"✅ Ovoz bergan: <b>{stats['voted']}</b>",
        f"⏳ Tasdiq kutmoqda: <b>{stats.get('pending', 0)}</b>",
        f"📢 Referral orqali: <b>{stats['via_referral']}</b>",
    ]
    if mahalla_stats:
        lines.append("\n🏘 <b>Mahallalar:</b>")
        for row in mahalla_stats:
            lines.append(f"  • {row['mahalla']}: {row['total']} ({row['voted_count']} ovoz)")
    if top:
        lines.append("\n🏆 <b>Top referralchilar:</b>")
        for i, row in enumerate(top, 1):
            name = row["first_name"] or str(row["user_id"])
            lines.append(f"{i}. {name} — {row['referral_count']} kishi")
    if days is not None:
        lines.append(f"\n⏰ Muddatga: <b>{days} kun</b>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Ruxsat yo'q.")
        return
    users = db.get_recent_users(30)
    if not users:
        await update.message.reply_text("Foydalanuvchilar yo'q.")
        return
    lines = ["👥 <b>So'nggi 30 foydalanuvchi</b>\n"]
    for row in users:
        name = row["first_name"] or "—"
        uname = f"@{row['username']}" if row["username"] else f"ID:{row['user_id']}"
        voted_icon = "✅" if row["voted"] else ("⏳" if row["pending_approval"] else "❌")
        started = (row["started_at"] or "")[:10]
        lines.append(f"{voted_icon} {name} ({uname}) — {started}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def _format_top10() -> str:
    top = db.get_top_referrers(10)
    if not top:
        return ""
    lines = ["🏆 <b>Top-10 faollar</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(top):
        icon = medals[i] if i < 3 else f"{i+1}."
        name = row["first_name"] or str(row["user_id"])
        uname = f" (@{row['username']})" if row["username"] else ""
        lines.append(f"{icon} {name}{uname} — {row['referral_count']} kishi")
    return "\n".join(lines)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        return
    text = _format_top10() or "Hali ma'lumot yo'q."
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Foydalanish:\n<code>/broadcast Xabar</code>", parse_mode="HTML")
        return
    user_ids = db.get_all_user_ids()
    ok = fail = 0
    msg = await update.message.reply_text(f"Yuborilmoqda... 0/{len(user_ids)}")
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await msg.edit_text(f"✅ {ok} ta yuborildi\n❌ {fail} ta yetkazilmadi")


async def cmd_announce_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        return
    top_text = _format_top10()
    if not top_text:
        await update.message.reply_text("Hali ma'lumot yo'q.")
        return
    prize_note = " ".join(context.args) if context.args else ""
    full_text = top_text
    if prize_note:
        full_text += f"\n\n🎁 <b>Mukofot:</b> {prize_note}"
    full_text += f"\n\n📣 {config.PROJECT_TITLE}\n⏰ {config.VOTING_DEADLINE}"
    user_ids = db.get_all_user_ids()
    ok = fail = 0
    msg = await update.message.reply_text(f"Yuborilmoqda... 0/{len(user_ids)}")
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, full_text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await msg.edit_text(f"✅ {ok} ta yuborildi\n❌ {fail} ta yetkazilmadi")


async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Ruxsat yo'q.")
        return
    db_admins = db.get_admins()
    lines = ["👥 <b>Adminlar ro'yxati</b>\n"]
    lines.append("⭐ <b>Asosiy adminlar (config):</b>")
    for aid in config.ADMIN_IDS:
        lines.append(f"  • ID: <code>{aid}</code>")
    if db_admins:
        lines.append("\n➕ <b>Qo'shilgan adminlar:</b>")
        for row in db_admins:
            name = row["first_name"] or "—"
            uname = f"@{row['username']}" if row["username"] else f"ID:{row['user_id']}"
            lines.append(f"  • {name} ({uname})")
    if _is_main_admin(user.id):
        lines.append("\n<i>Admin qo'shish: /addadmin &lt;user_id&gt;</i>")
        lines.append("<i>Admin olish: /removeadmin &lt;user_id&gt;</i>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_main_admin(user.id):
        await update.message.reply_text("Faqat asosiy admin admin qo'sha oladi.")
        return
    if not context.args:
        await update.message.reply_text("Foydalanish:\n<code>/addadmin 123456789</code>", parse_mode="HTML")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID raqam bo'lishi kerak.")
        return
    if target_id in config.ADMIN_IDS:
        await update.message.reply_text("Bu foydalanuvchi allaqachon asosiy admin.")
        return
    target = db.get_user(target_id)
    if not target:
        await update.message.reply_text(
            f"ID <code>{target_id}</code> topilmadi. Foydalanuvchi avval botga /start bosishi kerak.",
            parse_mode="HTML",
        )
        return
    db.set_admin(target_id, True)
    name = target["first_name"] or str(target_id)
    await update.message.reply_text(f"✅ {name} adminga qo'shildi.")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🎉 Siz adminga qo'shildingiz!\n\nAdmin buyruqlar: /stats /users /top /broadcast",
        )
    except Exception:
        pass


async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_main_admin(user.id):
        await update.message.reply_text("Faqat asosiy admin adminni olib tashlaydi.")
        return
    if not context.args:
        await update.message.reply_text("Foydalanish:\n<code>/removeadmin 123456789</code>", parse_mode="HTML")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID raqam bo'lishi kerak.")
        return
    if target_id in config.ADMIN_IDS:
        await update.message.reply_text("Asosiy adminni olib bo'lmaydi.")
        return
    db.set_admin(target_id, False)
    await update.message.reply_text(f"❌ ID <code>{target_id}</code> adminlikdan olindi.", parse_mode="HTML")


async def cmd_delete_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.delete_user(update.effective_user.id)
    await update.message.reply_text("Ma'lumotlaringiz o'chirildi. /start")


async def cmd_mening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    row = db.get_user(user.id)
    ref_count, rank = db.get_referral_rank(user.id)

    if row["voted"]:
        voted_icon = "✅ Ovoz bergan"
    elif row["pending_approval"]:
        voted_icon = "⏳ Tasdiq kutmoqda"
    else:
        voted_icon = "❌ Ovoz bermagan"

    lines = [f"👤 <b>{user.first_name}</b>\n", f"🗳 Holat: {voted_icon}"]
    if row.get("voted_at"):
        lines.append(f"📅 Tasdiqlangan: {row['voted_at'][:10]}")
    if row.get("mahalla"):
        lines.append(f"🏘 Mahalla: {row['mahalla']}")
    lines.append(f"\n📢 Taklif qilganlar: <b>{ref_count}</b> kishi")
    if rank > 0:
        lines.append(f"🏆 Reyting: <b>#{rank}</b>-o'rin")

    ref_link = _referral_link(user.id)
    if ref_link:
        lines.append(f"\n🔗 Taklif havolasi:\n<code>{ref_link}</code>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Ruxsat yo'q.")
        return
    pending = db.get_pending_users()
    if not pending:
        await update.message.reply_text("✅ Tasdiq kutayotgan foydalanuvchi yo'q.")
        return
    lines = [f"⏳ <b>Tasdiq kutayotganlar: {len(pending)} ta</b>\n"]
    for row in pending:
        name = row["first_name"] or "—"
        uname = f"@{row['username']}" if row["username"] else f"ID:{row['user_id']}"
        lines.append(f"• {name} ({uname})\n  ID: <code>{row['user_id']}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── proof flow ────────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sends screenshot as proof of voting."""
    user = update.effective_user
    existing = db.get_user(user.id)
    if not existing:
        return
    if existing["voted"]:
        await update.message.reply_text("✅ Siz allaqachon tasdiqlangansiz.")
        return
    if existing["pending_approval"]:
        await update.message.reply_text("⏳ Tasdiqlash allaqachon yuborilgan. Admin ko'rib chiqmoqda.")
        return
    if not existing.get("awaiting_proof"):
        return  # not in proof flow, ignore

    db.set_awaiting_proof(user.id, False)
    db.set_pending_approval(user.id, True)

    name = user.first_name or "—"
    uname = f"@{user.username}" if user.username else f"ID:{user.id}"
    caption = (
        f"📱 <b>SMS tasdiqnomasi keldi</b>\n\n"
        f"👤 {name} ({uname})\n"
        f"🆔 user_id: <code>{user.id}</code>\n\n"
        f"SMS screenshot ni tekshiring va tasdiqlang:"
    )
    approve_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve:{user.id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject:{user.id}"),
        ]
    ])
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
            await context.bot.send_message(
                chat_id=admin_id, text=caption, parse_mode="HTML", reply_markup=approve_kb
            )
        except Exception as e:
            logger.warning(f"Forward to admin {admin_id} failed: {e}")

    await update.message.reply_text(
        "✅ Screenshot qabul qilindi. Admin ko'rib chiqishi bilan xabar beramiz."
    )


# ── callbacks ─────────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if data == "noop":
        await query.answer("Tasdiq kutilmoqda.", show_alert=False)
        return

    # admin approval callbacks
    if data.startswith("approve:") or data.startswith("reject:"):
        if not _is_admin(user.id):
            await query.answer("Ruxsat yo'q.")
            return
        action, uid_str = data.split(":", 1)
        target_id = int(uid_str)
        target = db.get_user(target_id)
        target_name = (target["first_name"] if target else "") or str(target_id)

        if action == "approve":
            db.mark_voted(target_id)
            db.set_pending_approval(target_id, False)
            await query.answer("✅ Tasdiqlandi!")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ {target_name} tasdiqlandi.")
            ref_link = _referral_link(target_id)
            share_note = f"\n\n📢 Do'stlarni taklif qiling:\n<code>{ref_link}</code>" if ref_link else ""
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        "🎉 <b>Rahmat! Ovozingiz tasdiqlandi!</b>\n\n"
                        f"{config.PROJECT_TITLE} loyihasiga hissangiz qo'shildi."
                        + share_note
                    ),
                    parse_mode="HTML",
                    reply_markup=_voted_keyboard(),
                )
            except Exception as e:
                logger.warning(f"Notify user {target_id}: {e}")
        else:
            db.set_pending_approval(target_id, False)
            await query.answer("❌ Rad etildi.")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"❌ {target_name} rad etildi.")
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        "❌ Afsuski, screenshot tasdiqlanmadi.\n\n"
                        "Iltimos, rasmiy saytda ovoz berib, aniq screenshot yuboring."
                    ),
                    reply_markup=_main_keyboard(),
                )
            except Exception as e:
                logger.warning(f"Notify user {target_id}: {e}")
        return

    db.upsert_user(user.id, user.username, user.first_name)
    user_row = db.get_user(user.id)
    has_voted = bool(user_row and user_row["voted"])
    pending = bool(user_row and user_row["pending_approval"])

    if data == "submit_proof":
        if has_voted:
            await query.answer("Siz allaqachon tasdiqlangansiz ✅", show_alert=False)
            return
        if pending:
            await query.answer("Tasdiq allaqachon yuborilgan, admin ko'rmoqda.", show_alert=True)
            return
        db.set_awaiting_proof(user.id, True)
        await query.answer()
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "📱 <b>SMS tasdiqlash</b>\n\n"
                "OpenBudget saytida ovoz bergandan so'ng <b>1 soat ichida</b> rasmiy SMS xabar keladi:\n\n"
                "<i>«Sizning ovoz berish yuzasidan so'rovingiz qabul qilindi...»</i>\n\n"
                "O'sha <b>SMS xabarining screenshot ini</b> shu yerga yuboring.\n"
                "Admin ko'rib chiqib tasdiqlaydi. ✅"
            ),
            parse_mode="HTML",
        )

    elif data == "share":
        await query.answer()
        ref_link = _referral_link(user.id)
        link = ref_link if ref_link else config.VOTE_URL
        ref_count, rank = db.get_referral_rank(user.id)
        text = (
            f"📣 <b>Siz ham ovoz bering!</b>\n\n"
            f"{config.PROJECT_TITLE}\n📍 {config.PROJECT_REGION}\n\n"
            f"👉 {link}\n\n⏰ {config.VOTING_DEADLINE}"
        )
        my_stats = ""
        if ref_count > 0:
            my_stats = f"\n\n📊 Siz: <b>{ref_count}</b> kishi taklif qildingiz (#{rank}-o'rin)"
        await query.edit_message_text(
            text + my_stats + "\n\n<i>Nusxalab do'stlaringizga yuboring.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="back")]]),
        )

    elif data == "rating":
        await query.answer()
        stats = db.get_mahalla_stats()
        if not stats:
            await query.answer("Hali ma'lumot yo'q.", show_alert=True)
            return
        lines = ["🏘 <b>Mahalla reytingi</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        user_mahalla = (user_row or {}).get("mahalla")
        for i, row in enumerate(stats):
            icon = medals[i] if i < 3 else f"{i+1}."
            marker = " 👈" if row["mahalla"] == user_mahalla else ""
            lines.append(f"{icon} <b>{row['mahalla']}</b> — {row['total']} kishi{marker}")
        lines.append(f"\n✅ Jami ovoz: <b>{sum(r['voted_count'] for r in stats)}</b>")
        await query.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="back")]]),
        )

    elif data == "leaderboard":
        await query.answer()
        top = db.get_top_referrers(10)
        if not top:
            await query.answer("Hali ma'lumot yo'q.", show_alert=True)
            return
        ref_count, my_rank = db.get_referral_rank(user.id)
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 <b>Top faollar</b>\n"]
        for i, row in enumerate(top):
            icon = medals[i] if i < 3 else f"{i+1}."
            name = row["first_name"] or str(row["user_id"])
            marker = " 👈" if row["user_id"] == user.id else ""
            lines.append(f"{icon} <b>{name}</b> — {row['referral_count']} kishi{marker}")
        if ref_count > 0 and my_rank > 10:
            lines.append(f"\n👤 Sizning o'rningiz: #{my_rank} ({ref_count} kishi)")
        await query.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="back")]]),
        )

    elif data.startswith("mahalla:"):
        choice = data.split(":", 1)[1]
        await query.answer()
        if choice != "skip":
            db.set_mahalla(user.id, choice)
            await query.edit_message_text(f"✅ <b>{choice}</b> saqlandi.", parse_mode="HTML")
        else:
            await query.edit_message_text("Tushunildi.")

    elif data == "back":
        await query.answer()
        user_row2 = db.get_user(user.id)
        hv = bool(user_row2 and user_row2["voted"])
        pend = bool(user_row2 and user_row2["pending_approval"])
        days = _days_left()
        dl = ""
        if days is not None and not hv:
            dl = ("\n\n🔴 <b>Bugun oxirgi kun!</b>" if days == 0
                  else f"\n\n🟡 <b>{days} kun qoldi!</b>" if days <= 3 else "")
        if hv:
            sl = "\n\n✅ <b>Siz ovoz bergansiz. Rahmat!</b>"
            kb = _voted_keyboard()
        elif pend:
            sl = "\n\n⏳ <b>Tasdiq kutilmoqda...</b>"
            kb = _main_keyboard(pending=True)
        else:
            sl = "\n\n👇 Ovoz berib, screenshot yuboring:"
            kb = _main_keyboard()
        await query.edit_message_text(
            _project_text() + dl + sl, parse_mode="HTML", reply_markup=kb
        )


# ── scheduled jobs ────────────────────────────────────────────────────────────

async def send_due_reminders(app: Application):
    due = db.get_due_reminders()
    for row in due:
        try:
            await app.bot.send_message(
                chat_id=row["user_id"],
                text="🔔 <b>Eslatma!</b>\n\n" + _project_text() + "\n\nHali ovoz bermagansiz:",
                parse_mode="HTML",
                reply_markup=_main_keyboard(),
            )
            db.clear_reminder(row["user_id"])
        except Exception as e:
            logger.warning(f"Reminder failed {row['user_id']}: {e}")
            db.clear_reminder(row["user_id"])


async def send_deadline_reminders(app: Application):
    days = _days_left()
    if days not in (3, 1, 0):
        return
    users = db.get_non_voted_users()
    if days == 0:
        text_extra, threshold = "🔴 <b>Bugun oxirgi kun!</b>", 2
    elif days == 1:
        text_extra, threshold = "🟡 <b>Ertaga muddat tugaydi!</b>", 1
    else:
        text_extra, threshold = "🟡 <b>3 kun qoldi!</b>", 0
    for row in users:
        if row["deadline_reminded"] > threshold:
            continue
        try:
            await app.bot.send_message(
                chat_id=row["user_id"],
                text=text_extra + "\n\n" + _project_text() + "\n\nVaqt o'tmasdan ovoz bering:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗳 Ovoz berish", url=config.VOTE_URL)]]),
            )
            db.mark_deadline_reminded(row["user_id"])
        except Exception as e:
            logger.warning(f"Deadline reminder failed {row['user_id']}: {e}")
