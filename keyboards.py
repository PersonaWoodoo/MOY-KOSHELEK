from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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


def subscribe_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/stake_pay", style="primary")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub", style="success")],
    ])
    return kb


def deposit_methods_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Рубли (карта РФ)", callback_data="dep_rub", style="primary")],
        [InlineKeyboardButton(text="⭐ Звёзды", callback_data="dep_stars", style="primary")],
        [InlineKeyboardButton(text="💎 Крипта (CryptoBot)", callback_data="dep_crypto", style="primary")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main", style="danger")],
    ])
    return kb


def deposit_crypto_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="USDT", callback_data="asset_USDT", style="primary"),
            InlineKeyboardButton(text="TON", callback_data="asset_TON", style="primary"),
        ],
        [
            InlineKeyboardButton(text="BTC", callback_data="asset_BTC", style="primary"),
            InlineKeyboardButton(text="ETH", callback_data="asset_ETH", style="primary"),
        ],
        [
            InlineKeyboardButton(text="TRX", callback_data="asset_TRX", style="primary"),
            InlineKeyboardButton(text="SOL", callback_data="asset_SOL", style="primary"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main", style="danger")],
    ])
    return kb


def withdraw_assets_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="USDT", callback_data="wd_USDT", style="primary"),
            InlineKeyboardButton(text="TON", callback_data="wd_TON", style="primary"),
        ],
        [
            InlineKeyboardButton(text="BTC", callback_data="wd_BTC", style="primary"),
            InlineKeyboardButton(text="ETH", callback_data="wd_ETH", style="primary"),
        ],
        [
            InlineKeyboardButton(text="💵 RUB", callback_data="wd_RUB", style="primary"),
            InlineKeyboardButton(text="⭐ Stars", callback_data="wd_STARS", style="primary"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main", style="danger")],
    ])
    return kb


def check_assets_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="USDT", callback_data="chk_USDT", style="primary"),
            InlineKeyboardButton(text="TON", callback_data="chk_TON", style="primary"),
        ],
        [
            InlineKeyboardButton(text="BTC", callback_data="chk_BTC", style="primary"),
            InlineKeyboardButton(text="ETH", callback_data="chk_ETH", style="primary"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main", style="danger")],
    ])
    return kb


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main", style="danger")],
    ])


def admin_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats", style="primary")],
        [InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin_withdrawals", style="primary")],
        [InlineKeyboardButton(text="💰 Заявки на пополнение RUB", callback_data="admin_deposits", style="primary")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users", style="primary")],
        [InlineKeyboardButton(text="💎 Выдать валюту", callback_data="admin_give", style="success")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast", style="success")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="back_main", style="danger")],
    ])
    return kb


def withdrawal_action_menu(wid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выплачено", callback_data=f"wd_paid_{wid}", style="success"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd_reject_{wid}", style="danger"),
        ],
    ])


def deposit_action_menu(did: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"dep_ok_{did}", style="success"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"dep_no_{did}", style="danger"),
        ],
    ])


def admin_user_actions(uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 +100", callback_data=f"uadd100_{uid}", style="success"),
            InlineKeyboardButton(text="💰 -100", callback_data=f"usub100_{uid}", style="danger"),
        ],
        [
            InlineKeyboardButton(text="🚫 Бан", callback_data=f"uban_{uid}", style="danger"),
            InlineKeyboardButton(text="✅ Разбан", callback_data=f"uunban_{uid}", style="success"),
        ],
        [InlineKeyboardButton(text="✏️ Изменить баланс", callback_data=f"uset_{uid}", style="primary")],
    ])
