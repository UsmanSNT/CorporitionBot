import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗳 Ovoz berish", url=config.VOTE_URL)],
        [InlineKeyboardButton("✅ Ovoz berdim", callback_data="voted"),
         InlineKeyboardButton("🔔 Eslatma", callback_data="reminder")],
        [InlineKeyboardButton("ℹ️ Maxfiylik", callback_data="privacy")],
    ])


def _reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ 1 soatdan keyin", callback_data="remind:1h")],
        [InlineKeyboardButton("📅 Ertaga", callback_data="remind:1d")],
        [InlineKeyboardButton("🔕 Eslatmani bekor qilish", callback_data="remind:cancel")],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    text = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        + _project_text()
        + "\n\n👇 Quyidagi tugmadan rasmiy saytga o'tib ovoz bering:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=_main_keyboard())


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return

    stats = db.get_stats()
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👤 Botni boshlagan: <b>{stats['total']}</b>\n"
        f"🔗 Havolani bosgan: <b>{stats['clicked']}</b>\n"
        f"✅ «Ovoz berdim» degan: <b>{stats['voted']}</b>\n"
        f"🔔 Eslatma so'ragan: <b>{stats['reminded']}</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_delete_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.delete_user(user.id)
    await update.message.reply_text(
        "🗑 Sizning barcha ma'lumotlaringiz o'chirildi.\n"
        "Botdan yana foydalanish uchun /start yozing."
    )


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔒 <b>Maxfiylik siyosati</b>\n\n"
        "Bot faqat quyidagi ma'lumotlarni saqlaydi:\n"
        "• Telegram foydalanuvchi ID\n"
        "• Ism va username\n"
        "• Botni boshlagan vaqt\n"
        "• Havolani bosganmi (ha/yo'q)\n"
        "• «Ovoz berdim» deb belgilaganmi\n"
        "• Eslatma vaqti\n\n"
        "Bot hech qanday parol, SMS yoki shaxsiy hujjat so'ramaydi.\n"
        "Ma'lumotlarni o'chirish: /delete_me"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    db.upsert_user(user.id, user.username, user.first_name)

    if data == "voted":
        existing = db.get_user(user.id)
        if existing and existing["voted"]:
            await query.answer("Siz allaqachon ovoz bergan sifatida belgilangansiiz ✅", show_alert=False)
            return
        db.mark_voted(user.id)
        await query.answer("✅ Rahmat! Ovozingiz hisobga olindi.", show_alert=True)
        await query.edit_message_text(
            _project_text() + "\n\n✅ <b>Ovoz berildi! Rahmat!</b>\n\nBu bot faqat sizning ixtiyoriy belgilashingizni saqlaydi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗳 Rasmiy sayt", url=config.VOTE_URL)],
                [InlineKeyboardButton("ℹ️ Maxfiylik", callback_data="privacy")],
            ])
        )

    elif data == "reminder":
        existing = db.get_user(user.id)
        if existing and existing["voted"]:
            await query.answer("Siz allaqachon ovoz bergansiz ✅", show_alert=True)
            return
        await query.answer()
        await query.edit_message_text(
            "🔔 <b>Eslatma</b>\n\nQachon eslatma yuboraylik?",
            parse_mode="HTML",
            reply_markup=_reminder_keyboard()
        )

    elif data.startswith("remind:"):
        choice = data.split(":")[1]
        if choice == "cancel":
            db.clear_reminder(user.id)
            await query.answer("🔕 Eslatma bekor qilindi.", show_alert=False)
        else:
            now = datetime.utcnow()
            if choice == "1h":
                remind_at = now + timedelta(hours=1)
                label = "1 soatdan keyin"
            else:
                remind_at = now + timedelta(days=1)
                label = "ertaga"
            db.set_reminder(user.id, remind_at.strftime("%Y-%m-%d %H:%M:%S"))
            await query.answer(f"✅ {label} eslatma yuboriladi!", show_alert=True)

        await query.edit_message_text(
            _project_text() + "\n\n👇 Rasmiy saytga o'tib ovoz bering:",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )

    elif data == "privacy":
        await query.answer()
        text = (
            "🔒 <b>Maxfiylik</b>\n\n"
            "Saqlanadigan ma'lumotlar: ID, ism, username, havolani bosganmi, «Ovoz berdim» belgilashmi, eslatma vaqti.\n\n"
            "O'chirish: /delete_me"
        )
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="back")]])
        )

    elif data == "back":
        await query.answer()
        await query.edit_message_text(
            _project_text() + "\n\n👇 Rasmiy saytga o'tib ovoz bering:",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )


async def send_due_reminders(app: Application):
    due = db.get_due_reminders()
    for row in due:
        try:
            text = (
                f"🔔 <b>Eslatma!</b>\n\n"
                + _project_text()
                + "\n\nHali ovoz bermagansiz. Rasmiy saytga o'ting:"
            )
            await app.bot.send_message(
                chat_id=row["user_id"],
                text=text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗳 Ovoz berish", url=config.VOTE_URL)],
                    [InlineKeyboardButton("✅ Ovoz berdim", callback_data="voted")],
                ])
            )
            db.clear_reminder(row["user_id"])
            logger.info(f"Reminder sent to {row['user_id']}")
        except Exception as e:
            logger.warning(f"Failed to send reminder to {row['user_id']}: {e}")
            db.clear_reminder(row["user_id"])
