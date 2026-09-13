from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 Баланс"), KeyboardButton(text="🧾 Создать чек")],
            [KeyboardButton(text="📥 Пополнить"), KeyboardButton(text="📤 Вывести")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True
    )
    return kb


def subscribe_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/stake_pay", style="primary")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub", style="success")],
    ])
    return kb


def assets_menu(prefix: str = "asset"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="USDT", callback_data=f"{prefix}_USDT", style="primary"),
            InlineKeyboardButton(text="TON", callback_data=f"{prefix}_TON", style="primary"),
        ],
        [
            InlineKeyboardButton(text="BTC", callback_data=f"{prefix}_BTC", style="primary"),
            InlineKeyboardButton(text="ETH", callback_data=f"{prefix}_ETH", style="primary"),
        ],
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data=f"{prefix}_STARS", style="primary"),
            InlineKeyboardButton(text="💵 RUB", callback_data=f"{prefix}_RUB", style="primary"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main", style="danger"),
        ],
    ])
    return kb


def confirm_check_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_check", style="success"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_check", style="danger"),
        ],
    ])
    return kb


def admin_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats", style="primary")],
        [InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin_withdrawals", style="primary")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users", style="primary")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="back_main", style="danger")],
    ])
    return kb


def withdrawal_action_menu(wid: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выплачено", callback_data=f"wd_paid_{wid}", style="success"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd_reject_{wid}", style="danger"),
        ],
    ])
    return kb
