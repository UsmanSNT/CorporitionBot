from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        ["🔎 Kuzatuvlar", "➕ Kuzatuv qo'shish"],
        ["🔥 Eng arzon", "🆕 Yangi savdolar"],
        ["📉 Narxi tushganlar", "🔍 Qidirish"],
        ["⚙️ Sozlamalar", "📊 Holat"],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def source_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Barchasi", callback_data="src:all"),
            InlineKeyboardButton("Cooperation", callback_data="src:cooperation"),
        ],
        [
            InlineKeyboardButton("New Cooperation", callback_data="src:new_cooperation"),
            InlineKeyboardButton("XT-Xarid", callback_data="src:xt_xarid"),
        ],
    ])


def region_keyboard() -> InlineKeyboardMarkup:
    regions = [
        "Barchasi", "Toshkent", "Samarqand", "Andijon",
        "Farg'ona", "Namangan", "Buxoro", "Jizzax",
        "Qashqadaryo", "Navoiy", "Surxondaryo", "Sirdaryo",
        "Xorazm", "Qoraqalpog'iston",
    ]
    rows = []
    for i in range(0, len(regions), 2):
        row = [InlineKeyboardButton(regions[i], callback_data=f"reg:{regions[i]}")]
        if i + 1 < len(regions):
            row.append(InlineKeyboardButton(regions[i+1], callback_data=f"reg:{regions[i+1]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def notify_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Yangi savdo", callback_data="notify:new")],
        [InlineKeyboardButton("📉 Narx tushishi", callback_data="notify:price")],
        [InlineKeyboardButton("✅ Ikkisi ham", callback_data="notify:both")],
    ])


def listing_keyboard(source_url: str | None, keyword: str = "") -> InlineKeyboardMarkup:
    buttons = []
    if source_url:
        buttons.append([InlineKeyboardButton("🔗 Savdoni ochish", url=source_url)])
    if keyword:
        buttons.append([InlineKeyboardButton("🔍 O'xshashlarni qidirish", callback_data=f"search:{keyword}")])
    return InlineKeyboardMarkup(buttons) if buttons else InlineKeyboardMarkup([[]])


def skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip")]])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm:yes"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm:no"),
        ]
    ])


def rule_action_keyboard(rule_id: int, enabled: bool) -> InlineKeyboardMarkup:
    toggle_label = "⏸ To'xtatish" if enabled else "▶️ Davom ettirish"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(toggle_label, callback_data=f"rule:toggle:{rule_id}"),
            InlineKeyboardButton("🗑 O'chirish", callback_data=f"rule:delete:{rule_id}"),
        ]
    ])


def latest_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Barchasi", callback_data="latest:all"),
            InlineKeyboardButton("Cooperation", callback_data="latest:cooperation"),
        ],
        [
            InlineKeyboardButton("New Coop", callback_data="latest:new_cooperation"),
            InlineKeyboardButton("XT-Xarid", callback_data="latest:xt_xarid"),
        ],
    ])
