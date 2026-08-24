import logging
import os
import glob as glob_module
from datetime import datetime, date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, Application

from config import config
import database as db

logger = logging.getLogger(__name__)


def _project_text() -> str:
    lines = [f"<b>{config.PROJECT_TITLE}</b>"]
    if config.PROJECT_ID:
        lines.append(f"📋 Loyiha raqami: <code>{config.PROJECT_ID}</code>")
    if config.PROJECT_REGION:
        lines.append(f"📍 Hudud: {config.PROJECT_REGION}")
    if config.PROJECT_DESCRIPTION:
        lines.append(f"\n{config.PROJECT_DESCRIPTION}")
    if config.VOTING_DEADLINE:
        lines.append(f"\n⏰ Ovoz berish muddati: <b>{config.VOTING_DEADLINE}</b>")
    return "\n".join(lines)


def _referral_link(user_id: int) -> str:
    if config.BOT_USERNAME:
        return f"https://t.me/{config.BOT_USERNAME}?start=ref_{user_id}"
    return ""


def _main_keyboard(has_voted: bool = False, clicked: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("🗳 Ovoz berish", callback_data="goto_vote")]]
    if clicked and not has_voted:
        rows.append([InlineKeyboardButton("✅ Ovoz berdim", callback_data="voted")])
    if not has_voted:
        rows.append([InlineKeyboardButton("🔔 Eslatma", callback_data="reminder")])
    rows.append([
        InlineKeyboardButton("📢 Do'stlarga ulash", callback_data="share"),
        InlineKeyboardButton("ℹ️ Maxfiylik", callback_data="privacy"),
    ])
    return InlineKeyboardMarkup(rows)


def _voted_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗳 Rasmiy sayt", callback_data="goto_vote")],
        [InlineKeyboardButton("📢 Do'stlarga ulash", callback_data="share")],
        [InlineKeyboardButton("🏘 Mahalla reytingi", callback_data="rating")],
        [InlineKeyboardButton("ℹ️ Maxfiylik", callback_data="privacy")],
    ])


def _mahalla_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for m in config.MAHALLAS:
        rows.append([InlineKeyboardButton(m, callback_data=f"mahalla:{m}")])
    rows.append([InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="mahalla:skip")])
    return InlineKeyboardMarkup(rows)


def _reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ 1 soatdan keyin", callback_data="remind:1h")],
        [InlineKeyboardButton("📅 Ertaga", callback_data="remind:1d")],
        [InlineKeyboardButton("🔕 Eslatmani bekor qilish", callback_data="remind:cancel")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back")],
    ])


def _get_images() -> list[str]:
    if not config.IMAGE_DIR or not os.path.isdir(config.IMAGE_DIR):
        return []
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        files.extend(glob_module.glob(os.path.join(config.IMAGE_DIR, ext)))
    return sorted(files)[:10]


def _days_left() -> int | None:
    if not config.DEADLINE_DATE:
        return None
    try:
        deadline = date.fromisoformat(config.DEADLINE_DATE)
        return (deadline - date.today()).days
    except ValueError:
        return None


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

    db.upsert_user(user.id, user.username, user.first_name, referred_by)

    existing = db.get_user(user.id)
    has_voted = bool(existing and existing["voted"])
    clicked = bool(existing and existing["clicked_vote"])

    days = _days_left()
    deadline_line = ""
    if days is not None and not has_voted:
        if days == 0:
            deadline_line = "\n\n🔴 <b>Bugun oxirgi kun! Ovoz bering!</b>"
        elif days <= 3:
            deadline_line = f"\n\n🟡 <b>Ovoz berishga {days} kun qoldi!</b>"

    if has_voted:
        status_line = "\n\n✅ <b>Siz ovoz bergansiz. Rahmat!</b>"
        keyboard = _voted_keyboard()
    elif clicked:
        status_line = "\n\n👆 Saytga o'tdingiz. Ovoz bergach, quyidagi tugmani bosing:"
        keyboard = _main_keyboard(has_voted=False, clicked=True)
    else:
        status_line = "\n\n👇 Quyidagi tugmadan rasmiy saytga o'tib ovoz bering:"
        keyboard = _main_keyboard(has_voted=False, clicked=False)

    caption = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        + _project_text()
        + deadline_line
        + status_line
    )

    images = _get_images()
    if images:
        if len(images) == 1:
            with open(images[0], "rb") as f:
                await update.message.reply_photo(
                    photo=f, caption=caption, parse_mode="HTML", reply_markup=keyboard
                )
        else:
            media = []
            for i, path in enumerate(images):
                with open(path, "rb") as f:
                    data = f.read()
                if i == 0:
                    media.append(InputMediaPhoto(data, caption=caption, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(data))
            await update.message.reply_media_group(media=media)
            await update.message.reply_text(
                "✅ Ovoz berildi" if has_voted else "👇 Rasmiy saytga o'tib ovoz bering:",
                reply_markup=keyboard,
            )
    else:
        await update.message.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)

    # ask mahalla only on first visit and if mahallas configured
    if config.MAHALLAS and existing and existing.get("mahalla") is None and not referred_by:
        await update.message.reply_text(
            "🏘 <b>Qaysi mahalladan ekansiz?</b>\n\nMahallangizni tanlang (ixtiyoriy):",
            parse_mode="HTML",
            reply_markup=_mahalla_keyboard(),
        )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("Ruxsat yo'q.")
        return

    stats = db.get_stats()
    top = db.get_top_referrers(5)

    lines = [
        "📊 <b>Statistika</b>\n",
        f"👤 Boshlagan: <b>{stats['total']}</b>",
        f"🔗 Saytga o'tgan: <b>{stats['clicked']}</b>",
        f"✅ Ovoz bergan: <b>{stats['voted']}</b>",
        f"🔔 Eslatma so'ragan: <b>{stats['reminded']}</b>",
        f"📢 Referral orqali kelgan: <b>{stats['via_referral']}</b>",
    ]
    if top:
        lines.append("\n🏆 <b>Eng ko'p olib kelganlar:</b>")
        for i, row in enumerate(top, 1):
            name = row["first_name"] or row["username"] or str(row["user_id"])
            lines.append(f"{i}. {name} — {row['referral_count']} kishi")

    days = _days_left()
    if days is not None:
        lines.append(f"\n⏰ Muddatga: <b>{days} kun</b>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def _format_top10() -> str:
    top = db.get_top_referrers(10)
    if not top:
        return ""
    lines = ["🏆 <b>Top-10 faollar</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(top):
        icon = medals[i] if i < 3 else f"{i+1}."
        name = row["first_name"] or row["username"] or str(row["user_id"])
        uname = f"@{row['username']}" if row["username"] else ""
        suffix = f" ({uname})" if uname else ""
        lines.append(f"{icon} {name}{suffix} — {row['referral_count']} kishi")
    return "\n".join(lines)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("Ruxsat yo'q.")
        return
    text = _format_top10()
    if not text:
        await update.message.reply_text("Hali referral ma'lumoti yo'q.")
        return
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("Ruxsat yo'q.")
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Foydalanish:\n<code>/broadcast Xabar matni shu yerga</code>",
            parse_mode="HTML",
        )
        return

    user_ids = db.get_all_user_ids()
    ok, fail = 0, 0
    msg = await update.message.reply_text(f"Yuborilmoqda... (0/{len(user_ids)})")
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await msg.edit_text(f"✅ Yuborildi: {ok} ta\n❌ Yetkazilmadi: {fail} ta")


async def cmd_announce_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("Ruxsat yo'q.")
        return
    top_text = _format_top10()
    if not top_text:
        await update.message.reply_text("Hali referral ma'lumoti yo'q.")
        return
    prize_note = " ".join(context.args) if context.args else ""
    full_text = top_text
    if prize_note:
        full_text += f"\n\n🎁 <b>Mukofot:</b> {prize_note}"
    full_text += f"\n\n📣 {config.PROJECT_TITLE}\n⏰ Muddati: {config.VOTING_DEADLINE}"

    user_ids = db.get_all_user_ids()
    ok, fail = 0, 0
    msg = await update.message.reply_text(f"E'lon yuborilmoqda... (0/{len(user_ids)})")
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=full_text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await msg.edit_text(f"✅ Yuborildi: {ok} ta\n❌ Yetkazilmadi: {fail} ta")


async def cmd_delete_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.delete_user(update.effective_user.id)
    await update.message.reply_text(
        "Ma'lumotlaringiz o'chirildi. Yana foydalanish uchun /start yozing."
    )


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔒 <b>Maxfiylik siyosati</b>\n\n"
        "Bot faqat quyidagi ma'lumotlarni saqlaydi:\n"
        "• Telegram foydalanuvchi ID, ism, username\n"
        "• Botni boshlagan vaqt\n"
        "• Saytga o'tganmi, ovoz berganmi\n"
        "• Eslatma vaqti\n\n"
        "Bot hech qanday parol yoki shaxsiy hujjat so'ramaydi.\n"
        "Ma'lumotlarni o'chirish: /delete_me"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    db.upsert_user(user.id, user.username, user.first_name)
    user_row = db.get_user(user.id)
    has_voted = bool(user_row and user_row["voted"])
    clicked = bool(user_row and user_row["clicked_vote"])

    if data == "goto_vote":
        db.mark_clicked_vote(user.id)
        await query.answer()
        await query.edit_message_reply_markup(
            reply_markup=_main_keyboard(has_voted=False, clicked=True)
        )
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                f"🗳 <b>Rasmiy ovoz berish sahifasi:</b>\n{config.VOTE_URL}\n\n"
                "Ovoz bergach, qaytib <b>✅ Ovoz berdim</b> tugmasini bosing."
            ),
            parse_mode="HTML",
        )

    elif data == "voted":
        if has_voted:
            await query.answer("Siz allaqachon ovoz bergansiz ✅", show_alert=False)
            return
        if not clicked:
            await query.answer(
                "Avval 🗳 Ovoz berish tugmasini bosib, rasmiy saytda ovoz bering.",
                show_alert=True,
            )
            return
        db.mark_voted(user.id)
        await query.answer("✅ Rahmat!", show_alert=False)
        await query.edit_message_reply_markup(reply_markup=_voted_keyboard())
        ref_link = _referral_link(user.id)
        share_note = (
            f"\n\n📢 Do'stlaringizni ham taklif qiling:\n<code>{ref_link}</code>"
            if ref_link else ""
        )
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "🎉 <b>Rahmat!</b>\n\n"
                f"Siz <b>{config.PROJECT_TITLE}</b> loyihasiga ovoz berdingiz.\n"
                "Bu ovoz mahallamizning kelajagiga qo'shgan hissangiz!"
                + share_note
            ),
            parse_mode="HTML",
        )

    elif data == "share":
        await query.answer()
        ref_link = _referral_link(user.id)
        if ref_link:
            share_text = (
                f"📣 <b>Siz ham ovoz bering!</b>\n\n"
                f"{config.PROJECT_TITLE}\n"
                f"📍 {config.PROJECT_REGION}\n\n"
                f"Mahallamizdagi yo'l muammosini hal qilish uchun ovoz bering!\n\n"
                f"👉 {ref_link}\n\n"
                f"Muddati: {config.VOTING_DEADLINE}"
            )
            await query.edit_message_text(
                share_text + "\n\n<i>Yuqoridagi matnni nusxalab do'stlaringizga yuboring.</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Orqaga", callback_data="back")]
                ]),
            )
        else:
            share_text = (
                f"📣 <b>Siz ham ovoz bering!</b>\n\n"
                f"{config.PROJECT_TITLE}\n"
                f"📍 {config.PROJECT_REGION}\n\n"
                f"👉 {config.VOTE_URL}\n\n"
                f"Muddati: {config.VOTING_DEADLINE}"
            )
            await query.edit_message_text(
                share_text + "\n\n<i>Nusxalab do'stlaringizga yuboring.</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Orqaga", callback_data="back")]
                ]),
            )

    elif data == "reminder":
        if has_voted:
            await query.answer("Siz allaqachon ovoz bergansiz ✅", show_alert=True)
            return
        await query.answer()
        await query.edit_message_text(
            "🔔 <b>Eslatma</b>\n\nQachon eslatma yuboraylik?",
            parse_mode="HTML",
            reply_markup=_reminder_keyboard(),
        )

    elif data.startswith("remind:"):
        choice = data.split(":")[1]
        if choice == "cancel":
            db.clear_reminder(user.id)
            await query.answer("Eslatma bekor qilindi.", show_alert=False)
        else:
            now = datetime.utcnow()
            remind_at = now + (timedelta(hours=1) if choice == "1h" else timedelta(days=1))
            label = "1 soatdan keyin" if choice == "1h" else "ertaga"
            db.set_reminder(user.id, remind_at.strftime("%Y-%m-%d %H:%M:%S"))
            await query.answer(f"Eslatma {label} yuboriladi!", show_alert=True)
        await query.edit_message_text(
            _project_text() + "\n\n👇 Rasmiy saytga o'tib ovoz bering:",
            parse_mode="HTML",
            reply_markup=_main_keyboard(has_voted=False, clicked=clicked),
        )

    elif data == "privacy":
        await query.answer()
        await query.edit_message_text(
            "🔒 <b>Maxfiylik</b>\n\n"
            "Saqlanadigan: ID, ism, username, havolani bosganmi, ovoz berganmi, eslatma vaqti.\n\n"
            "O'chirish: /delete_me",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Orqaga", callback_data="back")]
            ]),
        )

    elif data.startswith("mahalla:"):
        choice = data.split(":", 1)[1]
        await query.answer()
        if choice != "skip":
            db.set_mahalla(user.id, choice)
            await query.edit_message_text(
                f"✅ <b>{choice}</b> mahallasi saqlandi.\n\nRahmat!",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text("Tushunildi. Keyinroq /start orqali o'rnatishingiz mumkin.")

    elif data == "rating":
        await query.answer()
        stats = db.get_mahalla_stats()
        if not stats:
            await query.answer("Hali ma'lumot yo'q.", show_alert=True)
            return
        lines = ["🏘 <b>Mahalla reytingi</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(stats):
            icon = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{icon} <b>{row['mahalla']}</b> — {row['total']} kishi")
        total_voted = sum(r["voted_count"] for r in stats)
        lines.append(f"\n✅ Jami ovoz bergan: <b>{total_voted}</b>")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Orqaga", callback_data="back")]
            ]),
        )

    elif data == "back":
        await query.answer()
        user_row2 = db.get_user(user.id)
        hv = bool(user_row2 and user_row2["voted"])
        cl = bool(user_row2 and user_row2["clicked_vote"])
        keyboard = _voted_keyboard() if hv else _main_keyboard(hv, cl)
        days = _days_left()
        deadline_line = ""
        if days is not None and not hv:
            if days == 0:
                deadline_line = "\n\n🔴 <b>Bugun oxirgi kun!</b>"
            elif days <= 3:
                deadline_line = f"\n\n🟡 <b>{days} kun qoldi!</b>"
        await query.edit_message_text(
            _project_text() + deadline_line + "\n\n👇 Rasmiy saytga o'tib ovoz bering:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def send_due_reminders(app: Application):
    due = db.get_due_reminders()
    for row in due:
        try:
            await app.bot.send_message(
                chat_id=row["user_id"],
                text=(
                    "🔔 <b>Eslatma!</b>\n\n"
                    + _project_text()
                    + "\n\nHali ovoz bermagansiz. Rasmiy saytga o'ting:"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗳 Ovoz berish", callback_data="goto_vote")],
                    [InlineKeyboardButton("✅ Ovoz berdim", callback_data="voted")],
                ]),
            )
            db.clear_reminder(row["user_id"])
        except Exception as e:
            logger.warning(f"Reminder failed for {row['user_id']}: {e}")
            db.clear_reminder(row["user_id"])


async def send_deadline_reminders(app: Application):
    days = _days_left()
    if days not in (3, 1, 0):
        return
    users = db.get_non_voted_users()
    if days == 0:
        text_extra = "🔴 <b>Bugun ovoz berish oxirgi kuni!</b>"
        threshold = 2
    elif days == 1:
        text_extra = "🟡 <b>Ertaga ovoz berish muddati tugaydi!</b>"
        threshold = 1
    else:
        text_extra = "🟡 <b>Ovoz berishga 3 kun qoldi!</b>"
        threshold = 0

    for row in users:
        if row["deadline_reminded"] > threshold:
            continue
        try:
            await app.bot.send_message(
                chat_id=row["user_id"],
                text=(
                    text_extra + "\n\n"
                    + _project_text()
                    + "\n\nVaqt o'tib ketmasidan ovoz bering:"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗳 Ovoz berish", callback_data="goto_vote")],
                ]),
            )
            db.mark_deadline_reminded(row["user_id"])
        except Exception as e:
            logger.warning(f"Deadline reminder failed for {row['user_id']}: {e}")
