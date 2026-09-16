import secrets
import random
import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    PreCheckoutQuery,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import (
    ADMIN_IDS, MIN_CHECK_AMOUNT, CHANNEL_LINK, TON_WALLET,
    STAR_RATE, CARD_NUMBER, CARD_NAME,
    MIN_WITHDRAW_STARS, MIN_WITHDRAW_CRYPTO, MIN_WITHDRAW_RUB
)
from database import (
    init_db, get_user, create_user, update_balance, update_turnover, set_balance, ban_user,
    all_users, get_top_users, log_admin,
    create_own_check_v2, get_own_check, increment_check_activation, get_stats,
    get_withdrawal, set_withdrawal_status, get_pending_withdrawals,
    create_withdrawal_full,
    check_already_activated, log_check_activation, get_user_by_username,
    reset_economy,
    get_user_checks, delete_own_check, get_own_check_by_id,
    save_referral, get_referral_stats, mark_bonus_paid, get_referral,
    get_daily_bonus, update_daily_bonus,
    create_deposit, get_deposit, set_deposit_status, get_pending_deposits,
)
from cryptobot_api import create_invoice, get_exchange_rate, transfer
from keyboards import (
    main_menu, subscribe_menu, captcha_menu, games_menu,
    deposit_methods_menu, deposit_crypto_menu,
    withdraw_assets_menu, withdraw_network_menu, check_assets_menu,
    check_type_menu, check_share_menu, check_password_menu, top_menu,
    cancel_kb, confirm_kb,
    admin_menu, withdrawal_action_menu, deposit_action_menu, admin_user_actions,
    reset_confirm_menu, reply_menu,
    my_checks_menu, my_check_actions_menu, my_check_confirm_delete,
    referrals_menu
)
from states import (
    CheckStates, DepositStates, WithdrawStates, TransferStates,
    AdminStates, CaptchaStates
)
from subscription import check_subscription

from games.tower import router as tower_router
from games.gold import router as gold_router
from games.dice import router as dice_router
from games.kwak import router as kwak_router
from games.bowling import router as bowling_router
from games.football import router as football_router
from games.basketball import router as basketball_router
from games.slots import router as slots_router

import emojis as E

router = Router()

BONUS_AMOUNT = 0.55
REQUIRED_TEXTS = [
    "@Stake_pay_bot — №1 среди игровых ботов в Telegram.",
    "@Stake_pay_bot — твой быстрый старт к реальным выплатам.",
    "@Stake_pay_bot — больше, чем просто игра.",
    "@Stake_pay_bot — играй, выигрывай, выводи.",
    "@Stake_pay_bot — топовый бот для тех, кто играет по-крупному.",
    "@Stake_pay_bot — честная игра и моментальные выплаты.",
    "@Stake_pay_bot — где азарт встречается с прибылью.",
    "@Stake_pay_bot — лучший способ превратить игру в доход.",
    "@Stake_pay_bot — проверенный бот, реальные деньги, ноль лишних слов.",
    "@Stake_pay_bot — играй умно, зарабатывай легко.",
]


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def require_subscription(message: Message, bot: Bot) -> bool:
    ok = await check_subscription(bot, message.from_user.id)
    if not ok:
        await message.answer(
            f"{E.ERROR} <b>Подпишись на канал:</b>\n\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
    return ok


async def require_sub_cb(call: CallbackQuery, bot: Bot) -> bool:
    ok = await check_subscription(bot, call.from_user.id)
    if not ok:
        await call.answer(f"{E.ERROR} Подпишись на канал!", show_alert=True)
    return ok


async def try_pay_referral_bonus(user_id: int, bot: Bot):
    ref = await get_referral(user_id)
    if not ref:
        return
    referrer_id = ref[1]
    bonus_paid = ref[3]
    if bonus_paid == 1:
        return
    await update_balance(referrer_id, 0.1)
    await mark_bonus_paid(user_id)
    try:
        user = await get_user(user_id)
        username = user[1] if user else str(user_id)
        await bot.send_message(
            referrer_id,
            f"{E.BONUS} <b>+0.1 USDT за реферала!</b>\n\n"
            f"👤 @{username} подписался на канал.",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ========== START ==========
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    user = await get_user(message.from_user.id)

    if not user and message.from_user.username:
        existing = await get_user_by_username(message.from_user.username)
        if existing and existing[0] != message.from_user.id:
            await message.answer(f"{E.BAN} <b>Дубликат аккаунта.</b>", parse_mode="HTML")
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"🚨 Твинк: @{message.from_user.username} ({message.from_user.id})\nУже есть: {existing[0]}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return

    args = message.text.split(maxsplit=1)
    ref_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
        except ValueError:
            ref_id = None

    if not user:
        await create_user(message.from_user.id, message.from_user.username or "")
        if ref_id and ref_id != message.from_user.id:
            await save_referral(ref_id, message.from_user.id)
            try:
                await bot.send_message(
                    ref_id,
                    f"{E.REFERRALS} <b>Новый реферал!</b>\n\n"
                    f"👤 @{message.from_user.username or message.from_user.id} перешёл по ссылке.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await state.set_state(CaptchaStates.waiting)
        await message.answer(
            f"{E.ROCKET} <b>Добро пожаловать!</b>\n\n🔐 Подтверди, что ты не робот:",
            parse_mode="HTML", reply_markup=captcha_menu()
        )
        return

    if user[4] == 1:
        await message.answer(f"{E.BAN} Ты забанен.", parse_mode="HTML")
        return

    if len(args) > 1 and args[1].startswith("check_"):
        code = args[1].replace("check_", "")
        await activate_check_flow(message, code, bot)
        return

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            f"{E.ROCKET} <b>Добро пожаловать!</b>\n\nПодпишись:\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
        return

    await try_pay_referral_bonus(message.from_user.id, bot)

    await message.answer(
        f"{E.ROCKET} Привет, {message.from_user.first_name}!",
        parse_mode="HTML", reply_markup=reply_menu()
    )
    await message.answer(f"{E.GAMES} Меню:", reply_markup=main_menu())


@router.callback_query(F.data == "captcha_pass")
async def captcha_pass(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    if not await check_subscription(bot, call.from_user.id):
        await call.message.edit_text(
            f"{E.ROCKET} Подпишись:\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
        return
    await try_pay_referral_bonus(call.from_user.id, bot)
    await call.message.edit_text(f"{E.SUCCESS} <b>Проверка пройдена!</b>", parse_mode="HTML")
    await call.message.answer(f"{E.GAMES} Меню:", reply_markup=main_menu())


# ========== АКТИВАЦИЯ ЧЕКА ==========
async def activate_check_flow(message: Message, code: str, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            f"{E.ERROR} <b>Подпишись на канал:</b>\n\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
        return

    check = await get_own_check(code)
    if not check:
        await message.answer(f"{E.ERROR} Чек не найден.", parse_mode="HTML")
        return

    # id, code, creator_id, target_id, target_username, asset, amount, description, max_act, act, status, password, check_type, min_turnover, created_at
    _, _, creator_id, target_id, target_username, asset, amount, description, max_activations, activations, status, password, check_type, min_turnover, _ = check

    if activations >= max_activations:
        await message.answer(f"{E.ERROR} Чек уже активирован.", parse_mode="HTML")
        return

    if creator_id == message.from_user.id:
        await message.answer(f"{E.ERROR} Это твой чек.", parse_mode="HTML")
        return

    if await check_already_activated(code, message.from_user.id):
        await message.answer(f"{E.ERROR} Ты уже активировал.", parse_mode="HTML")
        return

    # Пароль
    if password:
        await message.answer(
            f"{E.BAN} <b>Этот чек защищён паролем.</b>",
            parse_mode="HTML", reply_markup=check_password_menu(code)
        )
        return

    # Для рефералов
    if check_type == "refs":
        ref = await get_referral(message.from_user.id)
        if not ref or ref[1] != creator_id:
            await message.answer(f"{E.ERROR} Чек только для рефералов автора.", parse_mode="HTML")
            return

    # По обороту
    if min_turnover > 0:
        user = await get_user(message.from_user.id)
        user_turnover = user[3] if user and len(user) > 3 else 0
        if user_turnover < min_turnover:
            await message.answer(
                f"{E.ERROR} Нужен оборот ≥ <b>{min_turnover}</b> USDT.\n"
                f"Твой: <b>{user_turnover:.2f}</b>",
                parse_mode="HTML"
            )
            return

    if target_id and target_id != message.from_user.id:
        await message.answer(f"{E.ERROR} Чек для другого юзера.", parse_mode="HTML")
        return

    if target_username and not target_id:
        uname = (message.from_user.username or "").lower()
        if uname != target_username:
            await message.answer(f"{E.ERROR} Чек для @{target_username}.", parse_mode="HTML")
            return

    await update_balance(message.from_user.id, amount)
    await increment_check_activation(code)
    await log_check_activation(code, message.from_user.id)

    remaining = max_activations - activations - 1

    await message.answer(
        f"{E.SUCCESS} <b>Чек активирован!</b>\n\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
        f"{E.ACTIVATIONS} Осталось: <b>{remaining}</b>",
        parse_mode="HTML", reply_markup=main_menu()
    )

    try:
        await bot.send_message(
            creator_id,
            f"{E.SUCCESS} Твой чек активирован.\n"
            f"{E.ACTIVATIONS} Осталось: {remaining}/{max_activations}\n"
            f"👤 @{message.from_user.username or message.from_user.id}",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(CheckStates.password)
async def check_password_entered(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    code = data.get("check_code")
    if not code:
        await state.clear()
        return

    password_input = message.text.strip()
    check = await get_own_check(code)
    if not check:
        await message.answer(f"{E.ERROR} Чек не найден.", parse_mode="HTML")
        await state.clear()
        return

    _, _, creator_id, target_id, target_username, asset, amount, description, max_activations, activations, status, password, check_type, min_turnover, _ = check

    if password_input != password:
        await message.answer(f"{E.ERROR} Неверный пароль.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    if await check_already_activated(code, message.from_user.id):
        await message.answer(f"{E.ERROR} Ты уже активировал.", parse_mode="HTML")
        await state.clear()
        return

    await update_balance(message.from_user.id, amount)
    await increment_check_activation(code)
    await log_check_activation(code, message.from_user.id)

    remaining = max_activations - activations - 1

    await message.answer(
        f"{E.SUCCESS} <b>Чек активирован!</b>\n\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
        f"{E.ACTIVATIONS} Осталось: <b>{remaining}</b>",
        parse_mode="HTML", reply_markup=main_menu()
    )

    try:
        await bot.send_message(
            creator_id,
            f"{E.SUCCESS} Твой чек активирован.\n"
            f"{E.ACTIVATIONS} Осталось: {remaining}/{max_activations}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await state.clear()


@router.callback_query(F.data.startswith("check_pass_input:"))
async def check_pass_input(call: CallbackQuery, state: FSMContext, bot: Bot):
    code = call.data.split(":")[1]
    await state.update_data(check_code=code)
    await state.set_state(CheckStates.password)
    await call.message.edit_text(
        f"{E.BAN} <b>Введи пароль от чека:</b>",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.callback_query(F.data == "check_copy_link")
async def check_copy_link(call: CallbackQuery):
    await call.answer(f"{E.SUCCESS} Ссылка скопирована!", show_alert=True)


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery, bot: Bot):
    if await check_subscription(bot, call.from_user.id):
        await try_pay_referral_bonus(call.from_user.id, bot)
        await call.message.edit_text(f"{E.SUCCESS} Подписка подтверждена!", parse_mode="HTML")
        await call.message.answer(f"{E.GAMES} Меню:", reply_markup=main_menu())
    else:
        await call.answer(f"{E.ERROR} Не подписан!", show_alert=True)


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    try:
        await call.message.answer(f"{E.GAMES} Меню:", reply_markup=main_menu())
    except Exception:
        pass


# ========== REPLY ==========
@router.message(F.text == "💎 Баланс")
async def reply_balance(message: Message, bot: Bot):
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id)
        user = await get_user(message.from_user.id)
    await message.answer(
        f"{E.BALANCE} <b>Баланс</b>\n\n💎 USDT: <code>{user[2]:.2f}</code>",
        parse_mode="HTML"
    )


@router.message(F.text == "🧾 Чек")
async def reply_check(message: Message, state: FSMContext, bot: Bot):
    await state.set_state(CheckStates.asset)
    await message.answer(f"{E.CHECK} Актив:", parse_mode="HTML", reply_markup=check_assets_menu())


@router.message(F.text == "🎮 Игры")
async def reply_games(message: Message, bot: Bot):
    await message.answer(f"{E.GAMES} <b>Игры</b>", parse_mode="HTML", reply_markup=games_menu())


@router.message(F.text == "💸 Перевести")
async def reply_transfer(message: Message, state: FSMContext, bot: Bot):
    await state.set_state(TransferStates.target)
    await message.answer(
        f"{E.GIFT} <b>Перевод</b>\n\nВведи @username или ID:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(F.text.lower() == "б")
async def cmd_b_balance(message: Message, bot: Bot):
    await reply_balance(message, bot)


@router.message(Command("balance"))
async def cmd_balance(message: Message, bot: Bot):
    await reply_balance(message, bot)


# ========== BALANCE ==========
@router.callback_query(F.data == "menu_balance")
async def menu_balance(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    user = await get_user(call.from_user.id)
    if not user:
        await create_user(call.from_user.id)
        user = await get_user(call.from_user.id)
    text = (
        f"{E.BALANCE} <b>Баланс</b>\n\n"
        f"💎 USDT: <code>{user[2]:.2f}</code>\n"
        f"{E.RATES} Оборот: <code>{user[3] if len(user) > 3 else 0:.2f}</code>"
    )
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    except Exception:
        try:
            await call.message.answer(text, parse_mode="HTML", reply_markup=main_menu())
        except Exception:
            pass


# ========== ТОП ==========
@router.callback_query(F.data == "menu_top")
async def menu_top(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    top = await get_top_users(10)
    if not top:
        await call.message.edit_text(f"{E.RATES} Топ пуст.", parse_mode="HTML", reply_markup=main_menu())
        return

    text = f"{E.WIN} <b>Топ-10 по балансу</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(top, 1):
        uid, uname, bal = u
        medal = medals[i - 1] if i <= 3 else f"<b>{i}.</b>"
        name = f"@{uname}" if uname else f"ID {uid}"
        text += f"{medal} {name} — <b>{bal:.2f}</b> USDT\n"

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=top_menu())
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=top_menu())


@router.message(Command("top"))
async def cmd_top(message: Message, bot: Bot):
    if not await require_subscription(message, bot):
        return
    top = await get_top_users(10)
    if not top:
        await message.answer(f"{E.RATES} Топ пуст.", parse_mode="HTML")
        return
    text = f"{E.WIN} <b>Топ-10 по балансу</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(top, 1):
        uid, uname, bal = u
        medal = medals[i - 1] if i <= 3 else f"<b>{i}.</b>"
        name = f"@{uname}" if uname else f"ID {uid}"
        text += f"{medal} {name} — <b>{bal:.2f}</b> USDT\n"
    await message.answer(text, parse_mode="HTML", reply_markup=top_menu())


# ========== ПОПОЛНЕНИЕ ==========
@router.callback_query(F.data == "menu_deposit")
async def menu_deposit(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    try:
        await call.message.edit_text(
            f"{E.DEPOSIT} <b>Пополнение</b>",
            parse_mode="HTML", reply_markup=deposit_methods_menu()
        )
    except Exception:
        await call.message.answer(
            f"{E.DEPOSIT} <b>Пополнение</b>",
            parse_mode="HTML", reply_markup=deposit_methods_menu()
        )


@router.callback_query(F.data == "dep_stars")
async def dep_stars(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    await state.set_state(DepositStates.crypto_amount)
    await state.update_data(asset="STARS")
    await call.message.edit_text(
        f"{E.STARS} Введи количество звёзд:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.callback_query(F.data == "dep_crypto")
async def dep_crypto(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    await call.message.edit_text(
        f"{E.DEPOSIT} Выбери актив:",
        parse_mode="HTML", reply_markup=deposit_crypto_menu()
    )


@router.callback_query(F.data.startswith("asset_"))
async def dep_crypto_asset(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(DepositStates.crypto_amount)
    await call.message.edit_text(
        f"Актив: <b>{asset}</b>\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(DepositStates.crypto_amount)
async def dep_crypto_amount(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    data = await state.get_data()
    asset = data["asset"]
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if amount <= 0:
        await message.answer(f"{E.ERROR} Больше 0.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    if asset == "STARS":
        try:
            from aiogram.types import LabeledPrice
            uniq = secrets.token_hex(4)
            prices = [LabeledPrice(label="Stars", amount=int(amount))]
            await bot.send_invoice(
                chat_id=message.chat.id,
                title="Пополнение Stake Pay",
                description=f"Пополнение на {int(amount)} звёзд",
                payload=f"stars_{message.from_user.id}_{int(amount)}_{uniq}",
                provider_token="",
                currency="XTR",
                prices=prices,
            )
            await message.answer(f"{E.STARS} Оплати счёт выше 👆", parse_mode="HTML", reply_markup=main_menu())
        except Exception as e:
            await message.answer(f"{E.ERROR} Ошибка: {e}", parse_mode="HTML", reply_markup=main_menu())
        await state.clear()
        return

    dep_id = await create_deposit(message.from_user.id, asset, amount, "")
    if not dep_id:
        await message.answer(f"{E.ERROR} Ошибка создания заявки.", parse_mode="HTML", reply_markup=main_menu())
        await state.clear()
        return

    await message.answer(
        f"{E.SUCCESS} <b>Заявка на пополнение создана!</b>\n\n"
        f"🆔 Заявка: <b>#{dep_id}</b>\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code>\n\n"
        f"{E.WAIT} Переведи <b>{amount} {asset}</b> на кошелёк:\n"
        f"<code>{TON_WALLET}</code>\n\n"
        f"После перевода админ подтвердит зачисление.",
        parse_mode="HTML", reply_markup=main_menu()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"{E.DEPOSIT} <b>Заявка на пополнение #{dep_id}</b>\n\n"
                f"👤 @{message.from_user.username or message.from_user.id} "
                f"(<code>{message.from_user.id}</code>)\n"
                f"{E.BALANCE} {asset}: <code>{amount}</code>",
                parse_mode="HTML",
                reply_markup=deposit_action_menu(dep_id)
            )
        except Exception:
            pass

    await state.clear()


# ========== ИГРЫ ==========
@router.callback_query(F.data == "menu_games")
async def menu_games(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    try:
        await call.message.edit_text(
            f"{E.GAMES} <b>Игры Stake Pay</b>",
            parse_mode="HTML", reply_markup=games_menu()
        )
    except Exception:
        await call.message.answer(
            f"{E.GAMES} <b>Игры Stake Pay</b>",
            parse_mode="HTML", reply_markup=games_menu()
        )


@router.callback_query(F.data == "game_tower")
async def game_tower_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🗼 <b>БАШНЯ</b>\n\nОтправь: <code>башня 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_gold")
async def game_gold_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🥇 <b>ЗОЛОТО</b>\n\nОтправь: <code>золото 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_dice")
async def game_dice_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🎲 <b>КУБИК</b>\n\nОтправь: <code>куб 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_kwak")
async def game_kwak_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🐸 <b>КВАК</b>\n\nОтправь: <code>квак 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_bowling")
async def game_bowling_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🎳 <b>БОУЛИНГ</b>\n\nОтправь: <code>боулинг 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_football")
async def game_football_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"⚽ <b>ФУТБОЛ</b>\n\nОтправь: <code>футбол 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_basketball")
async def game_basketball_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🏀 <b>БАСКЕТБОЛ</b>\n\nОтправь: <code>баскетбол 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


@router.callback_query(F.data == "game_slots")
async def game_slots_cb(call: CallbackQuery):
    await call.message.edit_text(
        f"🎰 <b>СЛОТЫ</b>\n\nОтправь: <code>слоты 0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="menu_games", style="danger")],
        ])
    )


# ========== БОНУС ==========
@router.callback_query(F.data == "menu_bonus")
async def menu_bonus(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return

    try:
        chat = await bot.get_chat(call.from_user.id)
        bio = (chat.bio or "").strip()
    except Exception:
        bio = ""

    has_text = any(t.lower().strip() in bio.lower() for t in REQUIRED_TEXTS)

    bonus = await get_daily_bonus(call.from_user.id)
    can_spin = True
    wait_text = ""
    if bonus and bonus[2]:
        try:
            last = datetime.fromisoformat(bonus[2])
            diff = datetime.utcnow() - last
            if diff < timedelta(hours=24):
                can_spin = False
                hours = 24 - int(diff.total_seconds() // 3600)
                wait_text = f"\n{E.WAIT} Приходи через <b>{hours} ч.</b>"
        except Exception:
            pass

    variants_lines = "\n".join([f"• <code>{t}</code>" for t in REQUIRED_TEXTS])
    variants_block = (
        f"{E.REQUESTS} <b>Варианты bio:</b>\n"
        f"<blockquote expandable>{variants_lines}</blockquote>\n"
        f"<i>Нажми чтобы развернуть</i>"
    )

    if not has_text:
        text = (
            f"{E.BONUS} <b>Ежедневный бонус</b>\n\n"
            f"📝 Поставь одну из фраз в <b>bio</b> и нажми Проверить\n\n"
            f"{variants_block}\n\n"
            f"🎁 Награда: <b>0.55 USDT</b> за 7️⃣ 7️⃣ 7️⃣"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.SUCCESS} Проверить", callback_data="bonus_check", style="success")],
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="back_main", style="danger")],
        ])
    elif not can_spin:
        text = f"{E.BONUS} Уже крутил сегодня.{wait_text}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E.BACK} Назад", callback_data="back_main", style="danger")],
        ])
    else:
        text = f"{E.BONUS} <b>Bio подтверждён!</b>\n\n🎰 Крути!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Крутить", callback_data="bonus_spin", style="success")],
            [InlineKeyboardButton(text=f"{E.CANCEL} Отмена", callback_data="back_main", style="danger")],
        ])

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "bonus_check")
async def bonus_check(call: CallbackQuery, bot: Bot):
    try:
        chat = await bot.get_chat(call.from_user.id)
        bio = (chat.bio or "").strip()
    except Exception:
        bio = ""

    if not any(t.lower().strip() in bio.lower() for t in REQUIRED_TEXTS):
        await call.answer(f"{E.ERROR} Bio не подтверждён", show_alert=True)
        return
    await menu_bonus(call, bot)


@router.callback_query(F.data == "bonus_spin")
async def bonus_spin(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return

    try:
        chat = await bot.get_chat(call.from_user.id)
        bio = (chat.bio or "").strip()
    except Exception:
        bio = ""

    if not any(t.lower().strip() in bio.lower() for t in REQUIRED_TEXTS):
        await call.answer(f"{E.ERROR} Bio не подтверждён", show_alert=True)
        return

    bonus = await get_daily_bonus(call.from_user.id)
    if bonus and bonus[2]:
        try:
            last = datetime.fromisoformat(bonus[2])
            if datetime.utcnow() - last < timedelta(hours=24):
                await call.answer(f"{E.WAIT} Уже крутил", show_alert=True)
                return
        except Exception:
            pass

    await update_daily_bonus(call.from_user.id)

    try:
        await call.message.delete()
    except Exception:
        pass

    spin_msg = await call.message.answer("🎰")
    await asyncio.sleep(2.5)
    try:
        await spin_msg.delete()
    except Exception:
        pass

    if random.random() < 0.05:
        reels = ["7️⃣", "7️⃣", "7️⃣"]
    else:
        reels = random.choices(["🍒", "🍋", "🍇", "💎", "7️⃣"], weights=[35, 28, 18, 12, 7], k=3)

    display = f"{reels[0]} {reels[1]} {reels[2]}"

    if reels[0] == reels[1] == reels[2] == "7️⃣":
        await update_balance(call.from_user.id, BONUS_AMOUNT)
        user = await get_user(call.from_user.id)
        await call.message.answer(
            f"{E.BONUS} <b>ДЖЕКПОТ!</b>\n\n🎰 {display}\n{E.PAID} +{BONUS_AMOUNT} USDT\n{E.BALANCE} {user[2]:.2f}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Меню", callback_data="back_main", style="primary")],
            ])
        )
    else:
        await call.message.answer(
            f"{E.LOSE} <b>Не повезло</b>\n\n🎰 {display}\n{E.WAIT} Через 24 часа",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Меню", callback_data="back_main", style="primary")],
            ])
        )


# ========== МОИ ЧЕКИ ==========
@router.callback_query(F.data == "menu_my_checks")
async def menu_my_checks(call: CallbackQuery):
    checks = await get_user_checks(call.from_user.id)
    if not checks:
        await call.message.edit_text(
            f"{E.HISTORY} Нет чеков.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"{E.CANCEL} Закрыть", callback_data="back_main", style="danger")]
            ])
        )
        return
    text = f"{E.HISTORY} Твои чеки: {len(checks)}"
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=my_checks_menu(checks, 0))
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=my_checks_menu(checks, 0))


@router.callback_query(F.data.startswith("mycheck_page_"))
async def mycheck_page(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    checks = await get_user_checks(call.from_user.id)
    text = f"{E.HISTORY} Твои чеки: {len(checks)}"
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=my_checks_menu(checks, page))
    except Exception:
        pass


@router.callback_query(F.data.startswith("mycheck_view_"))
async def mycheck_view(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split("_")[2])
    check = await get_own_check_by_id(cid)
    if not check:
        await call.answer("Не найден", show_alert=True)
        return
    code = check[1]
    creator_id = check[2]
    asset = check[5]
    amount = check[6]
    max_act = check[8]
    act = check[9]
    status = check[10]
    if creator_id != call.from_user.id:
        await call.answer(f"{E.ERROR} Не твой чек", show_alert=True)
        return
    can_delete = status == "active" and act < max_act
    text = (
        f"{E.CHECK} <b>Чек</b>\n\n"
        f"💎 {asset}: <code>{amount}</code>\n"
        f"{E.ACTIVATIONS} {act}/{max_act}\n"
        f"👤 {check[4] or 'Публичный'}"
    )
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=my_check_actions_menu(cid, code, can_delete=can_delete))
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=my_check_actions_menu(cid, code, can_delete=can_delete))


@router.callback_query(F.data.startswith("mycheck_copy_"))
async def mycheck_copy(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split("_")[2])
    check = await get_own_check_by_id(cid)
    if not check:
        return
    code = check[1]
    bot_info = await bot.get_me()
    url = f"https://t.me/{bot_info.username}?start=check_{code}"
    await call.answer(f"{E.LINK} Ссылка: {url}", show_alert=True)


@router.callback_query(F.data.startswith("mycheck_del_yes_"))
async def mycheck_del_yes(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split("_")[3])
    check = await get_own_check_by_id(cid)
    if not check:
        await call.answer("Не найден", show_alert=True)
        return
    creator_id = check[2]
    asset = check[5]
    amount = check[6]
    max_act = check[8]
    act = check[9]
    status = check[10]
    if creator_id != call.from_user.id:
        await call.answer("Не твой", show_alert=True)
        return
    if status != "active":
        await call.answer("Завершён", show_alert=True)
        return
    remaining = max_act - act
    refund = amount * remaining if remaining > 0 else 0
    await delete_own_check(cid)
    if refund > 0:
        await update_balance(call.from_user.id, refund)
    await call.message.edit_text(
        f"{E.SUCCESS} <b>Удалён</b>\n\n{E.PAID} Возврат: {refund:.2f}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧾 Мои чеки", callback_data="menu_my_checks", style="primary")],
        ])
    )


@router.callback_query(F.data.startswith("mycheck_del_"))
async def mycheck_del(call: CallbackQuery, bot: Bot):
    cid = int(call.data.split("_")[2])
    check = await get_own_check_by_id(cid)
    if not check:
        await call.answer("Не найден", show_alert=True)
        return
    creator_id = check[2]
    amount = check[6]
    max_act = check[8]
    act = check[9]
    if creator_id != call.from_user.id:
        await call.answer("Не твой", show_alert=True)
        return
    remaining = max_act - act
    refund = amount * remaining
    await call.message.edit_text(
        f"{E.ERROR} <b>Удалить?</b>\n\n{E.PAID} Возврат: <code>{refund:.2f}</code>",
        parse_mode="HTML",
        reply_markup=my_check_confirm_delete(cid)
    )


# ========== СОЗДАНИЕ ЧЕКА ==========
@router.callback_query(F.data == "menu_check")
async def menu_check(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    await state.set_state(CheckStates.asset)
    await call.message.edit_text(
        f"{E.CHECK} Выбери актив:",
        parse_mode="HTML", reply_markup=check_assets_menu()
    )


@router.callback_query(CheckStates.asset, F.data.startswith("chk_"))
async def check_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(CheckStates.amount)
    await call.message.edit_text(
        f"{E.CHECK} Актив: <b>{asset}</b>\n\nВведи сумму (мин. {MIN_CHECK_AMOUNT}):",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(CheckStates.amount)
async def check_amount(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    data = await state.get_data()
    asset = data["asset"]
    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount < MIN_CHECK_AMOUNT:
        await message.answer(f"{E.ERROR} Минимум {MIN_CHECK_AMOUNT} {asset}", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if amount > balance:
        await message.answer(
            f"{E.ERROR} Недостаточно.\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return
    await state.update_data(amount=amount)
    await state.set_state(CheckStates.description)
    await message.answer("📝 Введи описание (или <code>-</code>):", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(CheckStates.description)
async def check_desc(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    desc = "" if message.text == "-" else message.text
    await state.update_data(description=desc)
    await state.set_state(CheckStates.max_activations)
    await message.answer(
        f"{E.ACTIVATIONS} Введи количество активаций (1-100):",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(CheckStates.max_activations)
async def check_max_activations(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    try:
        max_act = int(message.text.strip())
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число 1-100.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if max_act < 1 or max_act > 100:
        await message.answer(f"{E.ERROR} От 1 до 100.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    amount = data["amount"]
    total = amount * max_act
    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if total > balance:
        await message.answer(
            f"{E.ERROR} Нужно: <b>{total:.2f}</b>\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    await state.update_data(max_activations=max_act)
    await state.set_state(CheckStates.check_type)
    await message.answer(
        f"{E.CHECK} <b>Тип чека:</b>",
        parse_mode="HTML", reply_markup=check_type_menu()
    )


@router.callback_query(CheckStates.check_type, F.data.startswith("chktype_"))
async def check_type_chosen(call: CallbackQuery, state: FSMContext, bot: Bot):
    ctype = call.data.replace("chktype_", "")
    await state.update_data(check_type=ctype)

    if ctype == "password":
        await state.set_state(CheckStates.password)
        await call.message.edit_text(
            f"{E.BAN} <b>Введи пароль для чека:</b>\n\n"
            f"Получатель должен ввести пароль, чтобы активировать.",
            parse_mode="HTML", reply_markup=cancel_kb()
        )
        return

    if ctype == "turnover":
        await state.set_state(CheckStates.min_turnover)
        await call.message.edit_text(
            f"{E.RATES} <b>Введи минимальный оборот (USDT):</b>",
            parse_mode="HTML", reply_markup=cancel_kb()
        )
        return

    await state.set_state(CheckStates.target)
    if ctype == "refs":
        await call.message.edit_text(
            f"{E.REFERRALS} Чек для твоих рефералов\n\nОтправь <code>-</code>, чтобы создать.",
            parse_mode="HTML", reply_markup=cancel_kb()
        )
    else:
        await call.message.edit_text(
            f"{E.PERSONAL} Получатель:\n• @username — личный\n• <code>-</code> — публичный",
            parse_mode="HTML", reply_markup=cancel_kb()
        )


@router.message(CheckStates.min_turnover)
async def check_min_turnover(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    try:
        min_turn = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if min_turn < 0:
        await message.answer(f"{E.ERROR} Больше 0.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    await state.update_data(min_turnover=min_turn)
    await state.set_state(CheckStates.target)
    await message.answer(
        f"{E.PERSONAL} Получатель:\n• @username — личный\n• <code>-</code> — публичный",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(CheckStates.target)
async def check_target(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    data = await state.get_data()
    target_text = message.text.strip()
    target_id = None
    target_username = None

    if target_text != "-":
        target_username = target_text.lstrip("@").lower()
        try:
            chat = await bot.get_chat(f"@{target_username}")
            target_id = chat.id
        except Exception:
            target_id = None

    code = secrets.token_urlsafe(8)
    while await get_own_check(code):
        code = secrets.token_urlsafe(8)

    max_activations = int(data.get("max_activations", 1))
    password = data.get("password", "")
    check_type = data.get("check_type", "public")
    min_turnover = float(data.get("min_turnover", 0))

    await create_own_check_v2(
        code=code,
        creator_id=message.from_user.id,
        target_id=target_id,
        target_username=target_username,
        asset=data["asset"],
        amount=data["amount"],
        description=data["description"],
        max_activations=max_activations,
        password=password,
        check_type=check_type,
        min_turnover=min_turnover
    )

    total_cost = data["amount"] * max_activations
    await update_balance(message.from_user.id, -total_cost)

    bot_info = await bot.get_me()
    url = f"https://t.me/{bot_info.username}?start=check_{code}"

    target_display = f"@{target_username}" if target_username else "Публичный"

    text = (
        f"{E.SUCCESS} <b>Чек создан!</b>\n\n"
        f"{E.BALANCE} {data['asset']}: <code>{data['amount']}</code>\n"
        f"{E.CHECK} {data['description'] or '—'}\n"
        f"{E.PERSONAL} {target_display}\n"
    )

    if password:
        text += f"{E.BAN} Пароль: <code>{password}</code>\n"
    if check_type == "refs":
        text += f"{E.REFERRALS} Только для рефералов\n"
    if min_turnover > 0:
        text += f"{E.RATES} Мин. оборот: <b>{min_turnover}</b> USDT\n"

    text += f"\n{E.ACTIVATIONS} Активаций: <b>{max_activations}</b>\n"
    text += f"{E.PAID} Списано: <code>{total_cost:.2f}</code>\n\n"
    text += f"{E.LINK} <b>Ссылка:</b>\n{url}"

    await message.answer(text, parse_mode="HTML", reply_markup=check_share_menu())

    if target_id:
        try:
            await bot.send_message(
                target_id,
                f"{E.GIFT} <b>Тебе чек от Stake Pay</b>\n\n"
                f"{E.BALANCE} {data['asset']}: <code>{data['amount']}</code>\n"
                f"{E.CHECK} {data['description'] or '—'}\n\n"
                f"{E.LINK} {url}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()


# ========== ВЫВОД ==========
@router.callback_query(F.data == "menu_withdraw")
async def menu_withdraw(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    await call.message.edit_text(
        f"{E.WITHDRAW} <b>Вывод</b>\n\nВыбери актив:",
        parse_mode="HTML", reply_markup=withdraw_assets_menu()
    )


@router.callback_query(F.data.startswith("wd_"))
async def wd_asset(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    asset = call.data.split("_")[1]
    if asset == "RUB":
        await call.answer(f"{E.ERROR} Вывод в рублях отключён", show_alert=True)
        return
    await state.update_data(asset=asset)
    await state.set_state(WithdrawStates.amount)
    user = await get_user(call.from_user.id)
    balance = user[2] if user else 0
    await call.message.edit_text(
        f"{E.WITHDRAW} Актив: <b>{asset}</b>\n"
        f"Баланс: <b>{balance:.2f}</b>\n"
        f"Минимум: <b>${MIN_WITHDRAW_CRYPTO}</b>\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(WithdrawStates.amount)
async def wd_amount(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount < MIN_WITHDRAW_CRYPTO:
        await message.answer(f"{E.ERROR} Минимум: <b>${MIN_WITHDRAW_CRYPTO}</b>", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if amount <= 0 or amount > balance:
        await message.answer(
            f"{E.ERROR} Недостаточно.\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    data = await state.get_data()
    asset = data["asset"]
    await state.update_data(amount=amount)

    if asset == "TON":
        await state.update_data(network="TON")
        await state.set_state(WithdrawStates.address)
        await message.answer(f"📮 Введи TON-адрес:", parse_mode="HTML", reply_markup=cancel_kb())
        return

    await state.set_state(WithdrawStates.network)
    gid = secrets.token_hex(4)
    await state.update_data(wd_gid=gid)
    await message.answer(
        f"🌐 Выбери сеть для <b>{asset}</b>:",
        parse_mode="HTML", reply_markup=withdraw_network_menu(gid)
    )


@router.callback_query(F.data.startswith("wdnet:"))
async def wd_network(call: CallbackQuery, state: FSMContext, bot: Bot):
    parts = call.data.split(":")
    _, gid, action = parts[:3]

    if action == "cancel":
        await state.clear()
        await call.message.edit_text(f"{E.ERROR} Отменено.", parse_mode="HTML", reply_markup=main_menu())
        return

    await state.update_data(network=action)
    await state.set_state(WithdrawStates.address)
    await call.message.edit_text(
        f"📮 Введи адрес кошелька в сети <b>{action}</b>:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(WithdrawStates.address)
async def wd_address(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    data = await state.get_data()
    address = message.text.strip()
    amount = data["amount"]
    asset = data["asset"]
    network = data.get("network", asset)

    if len(address) < 10:
        await message.answer(f"{E.ERROR} Адрес слишком короткий.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount > balance:
        await message.answer(
            f"{E.ERROR} Недостаточно.\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    await update_balance(message.from_user.id, -amount)
    wid = await create_withdrawal_full(message.from_user.id, asset, amount, address, network)

    await message.answer(
        f"{E.SUCCESS} <b>Заявка на вывод создана!</b>\n\n"
        f"🆔 Заявка: <b>#{wid}</b>\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
        f"🌐 Сеть: <b>{network}</b>\n"
        f"📮 Адрес: <code>{address}</code>\n\n"
        f"{E.WAIT} Ожидай обработки админом.",
        parse_mode="HTML", reply_markup=main_menu()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"{E.WITHDRAW} <b>Новая заявка на вывод #{wid}</b>\n\n"
                f"👤 @{message.from_user.username or message.from_user.id} (<code>{message.from_user.id}</code>)\n"
                f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
                f"🌐 Сеть: <b>{network}</b>\n"
                f"📮 <code>{address}</code>",
                parse_mode="HTML",
                reply_markup=withdrawal_action_menu(wid)
            )
        except Exception:
            pass

    await state.clear()


@router.callback_query(F.data.startswith("admin_wd_paid:"))
async def admin_wd_paid(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    wid = int(call.data.split(":")[1])
    w = await get_withdrawal(wid)
    if not w:
        await call.answer("Не найдена", show_alert=True)
        return
    await set_withdrawal_status(wid, "paid")
    await call.message.edit_text(f"{E.SUCCESS} <b>Выплачено #{wid}</b>", parse_mode="HTML")
    try:
        await bot.send_message(w[1], f"{E.SUCCESS} <b>Вывод #{wid} выплачен!</b>\n\n{E.BALANCE} {w[2]}: <code>{w[3]}</code>", parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_wd_reject:"))
async def admin_wd_reject(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    wid = int(call.data.split(":")[1])
    w = await get_withdrawal(wid)
    if not w:
        await call.answer("Не найдена", show_alert=True)
        return
    await state.update_data(reject_wid=wid, reject_user=w[1], reject_amount=w[3], reject_asset=w[2])
    await state.set_state(AdminStates.reject_reason)
    await call.message.edit_text(
        f"{E.ERROR} <b>Причина отказа для #{wid}:</b>\n\nНапиши причину:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(AdminStates.reject_reason)
async def process_reject(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    wid = data.get("reject_wid")
    if not wid:
        await state.clear()
        return
    reason = message.text.strip()
    uid = data["reject_user"]
    amount = data["reject_amount"]
    asset = data["reject_asset"]
    await set_withdrawal_status(wid, "rejected", reason)
    await update_balance(uid, amount)
    await message.answer(
        f"{E.SUCCESS} <b>Заявка #{wid} отклонена</b>\n\n{E.PAID} Возврат: <code>{amount} {asset}</code>\n📝 Причина: {reason}",
        parse_mode="HTML", reply_markup=admin_menu()
    )
    try:
        await bot.send_message(uid, f"{E.ERROR} <b>Вывод #{wid} отклонён</b>\n\n{E.PAID} Возврат: <code>{amount} {asset}</code>\n📝 Причина: {reason}", parse_mode="HTML")
    except Exception:
        pass
    await state.clear()


# ========== АДМИН: ДЕПОЗИТЫ ==========
@router.callback_query(F.data.startswith("admin_dep_ok:"))
async def admin_dep_ok(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    did = int(call.data.split(":")[1])
    d = await get_deposit(did)
    if not d:
        await call.answer("Не найдена", show_alert=True)
        return
    await update_balance(d[1], d[3])
    await set_deposit_status(did, "paid")
    await call.message.edit_text(f"{E.SUCCESS} <b>Зачислено #{did}</b>", parse_mode="HTML")
    try:
        await bot.send_message(d[1], f"{E.SUCCESS} <b>Пополнение #{did} зачислено!</b>\n\n{E.BALANCE} {d[2]}: +<code>{d[3]}</code>", parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_dep_reject:"))
async def admin_dep_reject(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    did = int(call.data.split(":")[1])
    d = await get_deposit(did)
    if not d:
        await call.answer("Не найдена", show_alert=True)
        return
    await set_deposit_status(did, "rejected")
    await call.message.edit_text(f"{E.ERROR} <b>Отклонено #{did}</b>", parse_mode="HTML")
    try:
        await bot.send_message(d[1], f"{E.ERROR} <b>Пополнение #{did} отклонено.</b>", parse_mode="HTML")
    except Exception:
        pass


# ========== ПЕРЕВОД ==========
@router.callback_query(F.data == "menu_transfer")
async def menu_transfer(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    await state.set_state(TransferStates.target)
    await call.message.edit_text(
        f"{E.GIFT} <b>Перевод</b>\n\nВведи @username или ID:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(TransferStates.target)
async def transfer_target(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    target_text = message.text.strip()
    target_id = None
    target_username = None
    if target_text.startswith("@"):
        target_username = target_text.lstrip("@").lower()
        try:
            chat = await bot.get_chat(f"@{target_username}")
            target_id = chat.id
        except Exception:
            await message.answer(f"{E.ERROR} Не найден.", parse_mode="HTML", reply_markup=cancel_kb())
            return
    else:
        try:
            target_id = int(target_text)
        except ValueError:
            await message.answer(f"{E.ERROR} Введи @username или ID.", parse_mode="HTML", reply_markup=cancel_kb())
            return
    if target_id == message.from_user.id:
        await message.answer(f"{E.ERROR} Нельзя себе.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    target_user = await get_user(target_id)
    if not target_user:
        await message.answer(f"{E.ERROR} Не найден в боте.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if target_user[4] == 1:
        await message.answer(f"{E.ERROR} Забанен.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    await state.update_data(target_id=target_id, target_username=target_username)
    await state.set_state(TransferStates.amount)
    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    display = f"@{target_username}" if target_username else f"ID {target_id}"
    await message.answer(
        f"{E.GIFT} Получатель: <b>{display}</b>\n"
        f"Баланс: <b>{balance:.2f}</b>\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(TransferStates.amount)
async def transfer_amount(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if amount <= 0:
        await message.answer(f"{E.ERROR} Больше 0.", parse_mode="HTML", reply_markup=cancel_kb())
        return
    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount > balance:
        await message.answer(f"{E.ERROR} Недостаточно.", parse_mode="HTML", reply_markup=main_menu())
        await state.clear()
        return
    data = await state.get_data()
    target_id = data["target_id"]
    target_username = data.get("target_username")
    await update_balance(message.from_user.id, -amount)
    await update_balance(target_id, amount)
    display = f"@{target_username}" if target_username else f"ID {target_id}"
    await message.answer(
        f"{E.SUCCESS} <b>Перевод выполнен!</b>\n\n{E.PAID} Сумма: <code>{amount:.2f}</code>\n👤 {display}",
        parse_mode="HTML", reply_markup=main_menu()
    )
    try:
        await bot.send_message(target_id, f"{E.GIFT} <b>Перевод!</b>\n{E.PAID} <code>{amount:.2f}</code>\n👤 От: @{message.from_user.username or message.from_user.id}", parse_mode="HTML")
    except Exception:
        pass
    await state.clear()


# ========== ПОМОЩЬ ==========
@router.callback_query(F.data == "menu_help")
async def menu_help(call: CallbackQuery, bot: Bot):
    if not await require_sub_cb(call, bot):
        return
    text = (
        f"{E.HELP} <b>Помощь</b>\n\n"
        f"{E.BALANCE} Баланс\n{E.CHECK} Чек\n"
        f"{E.DEPOSIT} Пополнение\n{E.WITHDRAW} Вывод\n"
        f"{E.GAMES} Игры\n{E.GIFT} Перевод\n{E.BONUS} Бонус\n"
        f"{E.WIN} Топ\n{E.HISTORY} Мои чеки\n\n"
        f"Канал: {CHANNEL_LINK}"
    )
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=main_menu())


# ========== АДМИНКА ==========
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{E.ERROR} Нет доступа.", parse_mode="HTML")
        return
    await message.answer(f"{E.ADMIN} <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    count, total = await get_stats()
    users = await all_users()
    text = (
        f"{E.STATS} <b>Статистика</b>\n\n"
        f"{E.USERS} Юзеров: <code>{len(users)}</code>\n"
        f"{E.SUCCESS} Чеков: <code>{count or 0}</code>\n"
        f"{E.BALANCE} Оборот: <code>{total or 0:.2f}</code>"
    )
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_menu())
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pending = await get_pending_withdrawals()
    if not pending:
        await call.answer("📭 Нет заявок", show_alert=True)
        return
    for w in pending:
        wid, uid, asset, amount, address, network, status, reason, created = w
        await call.message.answer(
            f"{E.WITHDRAW} <b>Заявка #{wid}</b>\n\n"
            f"👤 <code>{uid}</code>\n"
            f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
            f"🌐 Сеть: <b>{network}</b>\n"
            f"📮 <code>{address}</code>",
            parse_mode="HTML", reply_markup=withdrawal_action_menu(wid)
        )


@router.callback_query(F.data == "admin_deposits")
async def admin_deposits(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pending = await get_pending_deposits()
    if not pending:
        await call.answer("📭 Нет заявок", show_alert=True)
        return
    for d in pending:
        did, uid, asset, amount, txid, status, created = d
        await call.message.answer(
            f"{E.DEPOSIT} <b>Пополнение #{did}</b>\n\n"
            f"👤 <code>{uid}</code>\n"
            f"{E.BALANCE} {asset}: <code>{amount}</code>",
            parse_mode="HTML", reply_markup=deposit_action_menu(did)
        )


@router.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    users = await all_users()
    text = f"{E.USERS} <b>Последние 20</b>\n\n"
    for u in users[:20]:
        uid, uname, bal, banned, created = u
        flag = E.BAN if banned else E.SUCCESS
        text += f"{flag} <code>{uid}</code> @{uname or '—'} — <b>{bal:.2f}</b>\n"
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_menu())
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_give")
async def admin_give(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.give_user)
    await call.message.edit_text(f"{E.PLUS} <b>Выдать валюту</b>\n\nВведи ID:", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminStates.give_user)
async def give_user(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer(f"{E.ERROR} Введи ID.", reply_markup=cancel_kb())
        return
    await state.update_data(target=uid)
    await state.set_state(AdminStates.give_amount)
    await message.answer(f"👤 ID: <code>{uid}</code>\n\nВведи сумму:", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminStates.give_amount)
async def give_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", reply_markup=cancel_kb())
        return
    data = await state.get_data()
    target = data["target"]
    await update_balance(target, amount)
    await log_admin(message.from_user.id, "give", target, f"{amount}")
    await message.answer(
        f"{E.SUCCESS} Выдано <code>{amount}</code> юзеру <code>{target}</code>",
        parse_mode="HTML", reply_markup=admin_menu()
    )
    try:
        await bot.send_message(target, f"{E.GIFT} Начислено <code>{amount}</code>", parse_mode="HTML")
    except Exception:
        pass
    await state.clear()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.broadcast)
    await call.message.edit_text(
        f"{E.BROADCAST} <b>Рассылка</b>\n\nОтправь текст:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(AdminStates.broadcast)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot):
    users = await all_users()
    ok, fail = 0, 0
    for u in users:
        try:
            await bot.send_message(u[0], message.text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await message.answer(
        f"{E.SUCCESS} Доставлено: {ok}, ошибок: {fail}",
        parse_mode="HTML", reply_markup=admin_menu()
    )
    await state.clear()


@router.callback_query(F.data == "admin_reset")
async def admin_reset(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        f"{E.ERROR} <b>Обнулить экономику?</b>\n\n<b>Необратимо!</b>",
        parse_mode="HTML", reply_markup=reset_confirm_menu()
    )


@router.callback_query(F.data == "admin_reset_confirm")
async def admin_reset_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await reset_economy()
    await call.message.edit_text(f"{E.SUCCESS} <b>Экономика обнулена!</b>", parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data.startswith("uadd100_"))
async def uadd100(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await update_balance(uid, 100)
    await log_admin(call.from_user.id, "add100", uid, "+100")
    await call.answer(f"{E.SUCCESS} +100", show_alert=True)


@router.callback_query(F.data.startswith("usub100_"))
async def usub100(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await update_balance(uid, -100)
    await log_admin(call.from_user.id, "sub100", uid, "-100")
    await call.answer(f"{E.SUCCESS} -100", show_alert=True)


@router.callback_query(F.data.startswith("uban_"))
async def uban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await ban_user(uid, True)
    await log_admin(call.from_user.id, "ban", uid, "")
    await call.answer(f"{E.BAN} Забанен", show_alert=True)


@router.callback_query(F.data.startswith("uunban_"))
async def uunban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await ban_user(uid, False)
    await log_admin(call.from_user.id, "unban", uid, "")
    await call.answer(f"{E.SUCCESS} Разбанен", show_alert=True)


# ========== ОПЛАТА ЗВЁЗДАМИ ==========
@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot):
    payment = message.successful_payment
    if not payment:
        return
    amount_stars = payment.total_amount
    payload = payment.invoice_payload
    try:
        parts = payload.split("_")
        user_id = int(parts[1])
        stars_amount = int(parts[2])
    except Exception:
        user_id = message.from_user.id
        stars_amount = amount_stars
    usdt_amount = round(stars_amount * STAR_RATE / 90, 4)
    await update_balance(user_id, usdt_amount)
    user = await get_user(user_id)
    await message.answer(
        f"{E.SUCCESS} <b>Оплата звёздами получена!</b>\n\n"
        f"{E.STARS} Оплачено: <b>{stars_amount} ⭐</b>\n"
        f"{E.BALANCE} Зачислено: <b>{usdt_amount} USDT</b>\n"
        f"Баланс: <b>{user[2]:.2f} USDT</b>",
        parse_mode="HTML"
    )


# ========== ПОДКЛЮЧЕНИЕ ИГР ==========
router.include_router(tower_router)
router.include_router(gold_router)
router.include_router(dice_router)
router.include_router(kwak_router)
router.include_router(bowling_router)
router.include_router(football_router)
router.include_router(basketball_router)
router.include_router(slots_router)
