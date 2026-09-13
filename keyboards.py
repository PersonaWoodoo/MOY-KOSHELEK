def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Баланс", callback_data="menu_balance", style="primary"),
            InlineKeyboardButton(text="🧾 Создать чек", callback_data="menu_check", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📥 Пополнить", callback_data="menu_deposit", style="success"),
            InlineKeyboardButton(text="📤 Вывести", callback_data="menu_withdraw", style="danger"),
        ],
        [
            InlineKeyboardButton(text="💸 Перевести", callback_data="menu_transfer", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📢 Подписаться", url="https://t.me/stake_pay", style="primary"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help"),
        ],
    ])
    return kb
