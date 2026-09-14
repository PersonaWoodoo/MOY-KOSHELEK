from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)


# ==================== REPLY (нижняя панель) ====================
def reply_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 Баланс"), KeyboardButton(text="🧾 Чек")],
            [KeyboardButton(text="🎮 Игры"), KeyboardButton(text="💸 Перевести")],
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    return kb


# ==================== INLINE ====================
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
            InlineKeyboardButton(text="🎮 Игры", callback_data="menu_games", style="primary"),
            InlineKeyboardButton(text="💸 Перевести", callback_data="menu_transfer", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🧾 Мои чеки", callback_data="menu_my_checks", style="primary"),
            InlineKeyboardButton(text="🎁 Рефералы", callback_data="menu_referrals", style="success"),
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


def captcha_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я не робот", callback_data="captcha_pass", style="success")],
    ])
    return kb


def games_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗼 Башня", callback_data="game_tower", style="primary")],
        [InlineKeyboardButton(text="🥇 Золото", callback_data="game_gold", style="primary")],
        [InlineKeyboardButton(text="❌ Назад", callback_data="back_main", style="danger")],
    ])
    return kb


def deposit_methods_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
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


def confirm_kb(action: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}", style="success"),
            InlineKeyboardButton(text="❌ Нет", callback_data="back_main", style="danger"),
        ],
    ])


# ==================== МОИ ЧЕКИ ====================
def my_checks_menu(checks: list, page: int = 0):
    rows = []
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_checks = checks[start:end]

    for c in page_checks:
        # c: (id, code, creator_id, target_id, target_username, asset, amount, description, max_act, act, status, created)
        cid = c[0]
        code = c[1]
        asset = c[5]
        amount = c[6]
        max_act = c[8]
        act = c[9]
        status = c[10]

        status_icon = "🟢" if status == "active" else "⚪"
        if act >= max_act:
            status_icon = "✅"

        rows.append([
            InlineKeyboardButton(
                text=f"{status_icon} {asset} {amount} [{act}/{max_act}]",
                callback_data=f"mycheck_view_{cid}",
                style="primary"
            ),
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"mycheck_page_{page - 1}", style="primary"))
    if end < len(checks):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"mycheck_page_{page + 1}", style="primary"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="back_main", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_check_actions_menu(cid: int, code: str, can_delete: bool = True, can_share: bool = True):
    rows = []

    if can_share:
        # Кнопка "поделиться" через Telegram
        share_url = f"https://t.me/share/url?url=https://t.me/Stake_pay_bot?start=check_{code}"
        rows.append([
            InlineKeyboardButton(text="📤 Поделиться", url=share_url, style="success"),
        ])

    rows.append([
        InlineKeyboardButton(text="🔗 Ссылка", callback_data=f"mycheck_copy_{cid}", style="primary"),
    ])

    if can_delete:
        rows.append([
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"mycheck_del_{cid}", style="danger"),
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_my_checks", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_check_confirm_delete(cid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"mycheck_del_yes_{cid}", style="success"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="menu_my_checks", style="danger"),
        ],
    ])


# ==================== АДМИНКА ====================
def admin_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats", style="primary")],
        [InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin_withdrawals", style="primary")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users", style="primary")],
        [InlineKeyboardButton(text="💎 Выдать валюту", callback_data="admin_give", style="success")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast", style="success")],
        [InlineKeyboardButton(text="🗑 Обнулить экономику", callback_data="admin_reset", style="danger")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="back_main", style="danger")],
    ])
    return kb


def reset_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, обнулить", callback_data="admin_reset_confirm", style="success"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_main", style="danger"),
        ],
    ])


def withdrawal_action_menu(wid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выплачено", callback_data=f"wd_paid_{wid}", style="success"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd_reject_{wid}", style="danger"),
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
