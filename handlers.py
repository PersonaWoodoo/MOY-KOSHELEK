import secrets
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import (
    ADMIN_IDS, MIN_CHECK_AMOUNT, CHANNEL_LINK, TON_WALLET,
    STAR_RATE, CARD_NUMBER, CARD_NAME
)
from database import (
    init_db, get_user, create_user, update_balance, set_balance, ban_user,
    all_users, log_admin, create_deposit,
    create_own_check, get_own_check, increment_check_activation, get_stats,
    create_withdrawal, get_pending_withdrawals, get_withdrawal,
    update_withdrawal_status
)
from cryptobot_api import create_invoice, get_exchange_rate, transfer
from keyboards import (
    main_menu, subscribe_menu, deposit_methods_menu, deposit_crypto_menu,
    withdraw_assets_menu, check_assets_menu, cancel_kb,
    admin_menu, withdrawal_action_menu, deposit_action_menu, admin_user_actions
)
from states import CheckStates, DepositStates, WithdrawStates, AdminStates
from subscription import check_subscription

import emojis as E

router = Router()


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def require_subscription(message: Message, bot: Bot) -> bool:
    ok = await check_subscription(bot, message.from_user.id)
    if not ok:
        await message.answer(
            f"{E.ERROR} <b>Подпишись на канал, чтобы пользоваться Stake Pay:</b>\n\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
    return ok


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await create_user(message.from_user.id, message.from_user.username or "")

    user = await get_user(message.from_user.id)
    if user and user[3] == 1:
        await message.answer(f"{E.BAN} Ты забанен.", parse_mode="HTML")
        return

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("check_"):
        code = args[1].replace("check_", "")
        await activate_check_flow(message, code, bot)
        return

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            f"{E.ROCKET} <b>Добро пожаловать в Stake Pay!</b>\n\n"
            f"Подпишись на канал:\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
        return

    await message.answer(
        f"{E.ROCKET} Привет, {message.from_user.first_name}!\n\n"
        f"<b>Stake Pay</b> — твой крипто-кошелёк.\n\nВыбирай действие 👇",
        parse_mode="HTML", reply_markup=main_menu()
    )


async def activate_check_flow(message: Message, code: str, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            f"{E.ERROR} <b>Подпишись на канал, чтобы активировать чек:</b>\n\n👉 {CHANNEL_LINK}",
            parse_mode="HTML", reply_markup=subscribe_menu()
        )
        return

    check = await get_own_check(code)
    if not check:
        await message.answer(f"{E.ERROR} Чек не найден.", parse_mode="HTML")
        return

    _, _, creator_id, target_id, target_username, asset, amount, description, max_activations, activations, status, _ = check

    if activations >= max_activations:
        await message.answer(f"{E.ERROR} Чек уже полностью активирован.", parse_mode="HTML")
        return

    if creator_id == message.from_user.id:
        await message.answer(f"{E.ERROR} Ты не можешь активировать свой же чек.", parse_mode="HTML")
        return

    if target_id and target_id != message.from_user.id:
        await message.answer(f"{E.ERROR} Этот чек предназначен другому пользователю.", parse_mode="HTML")
        return

    if target_username and not target_id:
        uname = (message.from_user.username or "").lower()
        if uname != target_username:
            await message.answer(f"{E.ERROR} Этот чек предназначен @{target_username}.", parse_mode="HTML")
            return

    await update_balance(message.from_user.id, amount)
    await increment_check_activation(code)

    remaining = max_activations - activations - 1

    await message.answer(
        f"{E.SUCCESS} <b>Чек активирован!</b>\n\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code> зачислено на баланс.\n"
        f"{E.CHECK} {description or '—'}\n"
        f"🔢 Осталось активаций: <b>{remaining}</b>",
        parse_mode="HTML", reply_markup=main_menu()
    )

    try:
        await bot.send_message(
            creator_id,
            f"{E.SUCCESS} Твой чек на <code>{amount} {asset}</code> активирован.\n"
            f"🔢 Осталось: {remaining}/{max_activations}",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery, bot: Bot):
    if await check_subscription(bot, call.from_user.id):
        await call.message.edit_text(f"{E.SUCCESS} Подписка подтверждена!", parse_mode="HTML")
        await call.message.answer("🏠 Главное меню:", reply_markup=main_menu())
    else:
        await call.answer("❌ Ты ещё не подписался!", show_alert=True)


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("🏠 Главное меню:", reply_markup=main_menu())


@router.callback_query(F.data == "menu_balance")
async def menu_balance(call: CallbackQuery, bot: Bot):
    if not await check_subscription(bot, call.from_user.id):
        await call.answer("Сначала подпишись!", show_alert=True)
        return
    user = await get_user(call.from_user.id)
    if not user:
        await create_user(call.from_user.id)
        user = await get_user(call.from_user.id)

    balance = user[2]

    rates = await get_exchange_rate()
    rub = 0
    if rates.get("ok"):
        for r in rates["result"]:
            if r["source"] == "USDT" and r["target"] == "RUB":
                rub = balance * float(r["rate"])
                break

    await call.message.edit_text(
        f"{E.BALANCE} <b>Твой баланс</b>\n\n"
        f"💎 USDT: <code>{balance:.2f}</code>\n"
        f"{E.RUB} RUB: <code>{rub:.2f} ₽</code>\n"
        f"{E.STARS} Stars: <code>{int(rub / STAR_RATE)}</code>",
        parse_mode="HTML", reply_markup=main_menu()
    )


@router.callback_query(F.data == "menu_deposit")
async def menu_deposit(call: CallbackQuery, bot: Bot):
    if not await check_subscription(bot, call.from_user.id):
        await call.answer("Сначала подпишись!", show_alert=True)
        return
    await call.message.edit_text(
        f"{E.DEPOSIT} <b>Пополнение</b>\n\nВыбери способ:",
        parse_mode="HTML", reply_markup=deposit_methods_menu()
    )


@router.callback_query(F.data == "dep_rub")
async def dep_rub(call: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.rub_amount)
    await call.message.edit_text(
        f"{E.CARD} <b>Пополнение рублями (карта РФ)</b>\n\nВведи сумму в рублях:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(DepositStates.rub_amount)
async def dep_rub_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    if amount < 100:
        await message.answer(f"{E.ERROR} Минимум 100 ₽.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    await state.update_data(rub_amount=amount)
    await state.set_state(DepositStates.rub_txid)
    await message.answer(
        f"{E.CARD} <b>Реквизиты для перевода</b>\n\n"
        f"💳 Карта: <code>{CARD_NUMBER}</code>\n"
        f"👤 Получатель: <b>{CARD_NAME}</b>\n"
        f"{E.RUB} Сумма: <b>{amount:.0f} ₽</b>\n\n"
        f"После перевода отправь <b>ID транзакции</b>.",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(DepositStates.rub_txid)
async def dep_rub_txid(message: Message, state: FSMContext, bot: Bot):
    txid = message.text.strip()
    if len(txid) < 4:
        await message.answer(f"{E.ERROR} ID слишком короткий.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    amount = data["rub_amount"]

    ok = await create_deposit(message.from_user.id, "RUB", amount, txid)
    if not ok:
        await message.answer(f"{E.ERROR} Этот ID уже был использован.", parse_mode="HTML", reply_markup=cancel_kb())
        await state.clear()
        return

    await message.answer(
        f"{E.SUCCESS} <b>Заявка создана!</b>\n\n"
        f"{E.RUB} {amount:.0f} ₽\n"
        f"🆔 TX: <code>{txid}</code>\n\n"
        f"{E.WAIT} Ожидай подтверждения админа.",
        parse_mode="HTML", reply_markup=main_menu()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"{E.RUB} <b>Заявка на пополнение RUB</b>\n\n"
                f"👤 @{message.from_user.username or message.from_user.id} (<code>{message.from_user.id}</code>)\n"
                f"{E.RUB} {amount:.0f} ₽\n"
                f"🆔 TX: <code>{txid}</code>",
                parse_mode="HTML",
                reply_markup=deposit_action_menu(0)
            )
        except Exception:
            pass
    await state.clear()


@router.callback_query(F.data == "dep_stars")
async def dep_stars(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(DepositStates.crypto_amount)
    await state.update_data(asset="STARS")
    await call.message.edit_text(
        f"{E.STARS} <b>Пополнение звёздами</b>\n\n"
        f"Курс: <b>1 ⭐ = {STAR_RATE} ₽</b>\n\n"
        f"Введи количество звёзд:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.callback_query(F.data == "dep_crypto")
async def dep_crypto(call: CallbackQuery):
    await call.message.edit_text(
        f"{E.DEPOSIT} <b>Пополнение криптой</b>\n\nВыбери актив:",
        parse_mode="HTML", reply_markup=deposit_crypto_menu()
    )


@router.callback_query(F.data.startswith("asset_"))
async def dep_crypto_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(DepositStates.crypto_amount)
    await call.message.edit_text(
        f"{E.DEPOSIT} Актив: <b>{asset}</b>\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(DepositStates.crypto_amount)
async def dep_crypto_amount(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    asset = data["asset"]

    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    if amount <= 0:
        await message.answer(f"{E.ERROR} Сумма должна быть больше 0.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    if asset == "STARS":
        try:
            from aiogram.types import LabeledPrice
            prices = [LabeledPrice(label="Stars", amount=int(amount))]
            await bot.send_invoice(
                chat_id=message.chat.id,
                title="Пополнение Stake Pay",
                description=f"Пополнение баланса на {int(amount)} звёзд",
                payload=f"stars_{message.from_user.id}_{int(amount)}",
                provider_token="",
                currency="XTR",
                prices=prices,
            )
            await message.answer(
                f"{E.STARS} Оплати счёт выше 👆\n\nПосле оплаты средства зачислятся автоматически.",
                parse_mode="HTML", reply_markup=main_menu()
            )
        except Exception as e:
            await message.answer(f"{E.ERROR} Ошибка: {e}", parse_mode="HTML", reply_markup=main_menu())
        await state.clear()
        return

    result = await create_invoice(asset=asset, amount=amount, description="Stake Pay Deposit")
    if not result.get("ok"):
        await message.answer(f"{E.ERROR} Ошибка: {result}", parse_mode="HTML", reply_markup=main_menu())
        await state.clear()
        return

    pay_url = result["result"].get("bot_invoice_url") or result["result"].get("pay_url", "")
    await message.answer(
        f"{E.SUCCESS} <b>Инвойс создан!</b>\n\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code>\n\n"
        f"{E.LINK} {pay_url}",
        parse_mode="HTML", reply_markup=main_menu()
    )
    await state.clear()


@router.callback_query(F.data == "menu_check")
async def menu_check(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await check_subscription(bot, call.from_user.id):
        await call.answer("Сначала подпишись!", show_alert=True)
        return
    await state.set_state(CheckStates.asset)
    await call.message.edit_text(
        f"{E.CHECK} Выбери актив для чека:",
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
async def check_amount(message: Message, state: FSMContext):
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
            f"{E.ERROR} Недостаточно средств.\nБаланс: <b>{balance:.2f}</b> {asset}",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    await state.update_data(amount=amount)
    await state.set_state(CheckStates.description)
    await message.answer("📝 Введи описание (или <code>-</code>):", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(CheckStates.description)
async def check_desc(message: Message, state: FSMContext):
    desc = "" if message.text == "-" else message.text
    await state.update_data(description=desc)
    await state.set_state(CheckStates.max_activations)
    await message.answer(
        "🔢 Введи количество активаций (1-100):\n"
        "• 1 — обычный чек\n"
        "• >1 — многоразовый",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(CheckStates.max_activations)
async def check_max_activations(message: Message, state: FSMContext):
    try:
        max_act = int(message.text.strip())
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число от 1 до 100.", parse_mode="HTML", reply_markup=cancel_kb())
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
            f"{E.ERROR} Недостаточно средств для {max_act} активаций.\n"
            f"Нужно: <b>{total:.2f}</b>\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    await state.update_data(max_activations=max_act)
    await state.set_state(CheckStates.target)
    await message.answer(
        f"{E.PERSONAL} Получатель:\n• @username — личный\n• <code>-</code> — публичный",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(CheckStates.target)
async def check_target(message: Message, state: FSMContext, bot: Bot):
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

    await create_own_check(
        code=code,
        creator_id=message.from_user.id,
        target_id=target_id,
        target_username=target_username,
        asset=data["asset"],
        amount=data["amount"],
        description=data["description"],
        max_activations=max_activations
    )

    total_cost = data["amount"] * max_activations
    await update_balance(message.from_user.id, -total_cost)

    bot_info = await bot.get_me()
    url = f"https://t.me/{bot_info.username}?start=check_{code}"

    target_display = f"@{target_username}" if target_username else "Публичный"

    await message.answer(
        f"{E.SUCCESS} <b>Чек создан!</b>\n\n"
        f"{E.BALANCE} {data['asset']}: <code>{data['amount']}</code>\n"
        f"{E.CHECK} {data['description'] or '—'}\n"
        f"{E.PERSONAL} {target_display}\n"
        f"🔢 Активаций: <b>{max_activations}</b>\n"
        f"💰 Списано: <code>{total_cost:.2f}</code>\n\n"
        f"{E.LINK} <b>Ссылка:</b>\n{url}",
        parse_mode="HTML", reply_markup=main_menu()
    )

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


@router.callback_query(F.data == "menu_withdraw")
async def menu_withdraw(call: CallbackQuery, bot: Bot):
    if not await check_subscription(bot, call.from_user.id):
        await call.answer("Сначала подпишись!", show_alert=True)
        return
    await call.message.edit_text(
        f"{E.WITHDRAW} <b>Вывод</b>\n\nВыбери актив:",
        parse_mode="HTML", reply_markup=withdraw_assets_menu()
    )


@router.callback_query(F.data.startswith("wd_"))
async def wd_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(WithdrawStates.amount)

    user = await get_user(call.from_user.id)
    balance = user[2] if user else 0

    await call.message.edit_text(
        f"{E.WITHDRAW} Актив: <b>{asset}</b>\n"
        f"Баланс: <b>{balance:.2f}</b>\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(WithdrawStates.amount)
async def wd_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML", reply_markup=cancel_kb())
        return

    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0

    if amount <= 0 or amount > balance:
        await message.answer(
            f"{E.ERROR} Недостаточно средств.\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    await state.update_data(amount=amount)
    await state.set_state(WithdrawStates.address)

    data = await state.get_data()
    if data["asset"] == "RUB":
        prompt = f"{E.RUB} Номер карты / СБП:"
    elif data["asset"] == "STARS":
        prompt = f"{E.STARS} Твой @username для получения звёзд:"
    else:
        prompt = "📮 Адрес кошелька (или твой Telegram ID):"

    await message.answer(prompt, parse_mode="HTML", reply_markup=cancel_kb())


@router.message(WithdrawStates.address)
async def wd_address(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    address = message.text.strip()
    amount = data["amount"]
    asset = data["asset"]

    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount > balance:
        await message.answer(
            f"{E.ERROR} Недостаточно средств.\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    if asset in ("USDT", "TON", "BTC", "ETH", "TRX", "SOL"):
        try:
            target_id = int(address) if address.isdigit() else message.from_user.id
            spend_id = secrets.token_hex(8)
            result = await transfer(
                user_id=target_id,
                asset=asset,
                amount=amount,
                spend_id=spend_id,
                comment="Stake Pay"
            )

            if not result.get("ok"):
                err_name = result.get("error", {}).get("name", "unknown")
                await message.answer(
                    f"{E.ERROR} Ошибка вывода: <code>{err_name}</code>",
                    parse_mode="HTML", reply_markup=main_menu()
                )
                await state.clear()
                return

            await update_balance(message.from_user.id, -amount)
            await create_withdrawal(message.from_user.id, asset, amount, address)

            await message.answer(
                f"{E.SUCCESS} <b>Вывод выполнен!</b>\n\n"
                f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
                f"📮 <code>{address}</code>\n\n"
                f"{E.WAIT} Зачисление в течение минуты.",
                parse_mode="HTML", reply_markup=main_menu()
            )
            await state.clear()
            return

        except Exception as e:
            await message.answer(f"{E.ERROR} Ошибка: <code>{e}</code>", parse_mode="HTML")
            await state.clear()
            return

    await update_balance(message.from_user.id, -amount)
    await create_withdrawal(message.from_user.id, asset, amount, address)

    await message.answer(
        f"{E.SUCCESS} <b>Заявка создана!</b>\n\n"
        f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
        f"📮 <code>{address}</code>\n\n{E.WAIT} Ожидай обработки.",
        parse_mode="HTML", reply_markup=main_menu()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"{E.WITHDRAW} <b>Ручной вывод ({asset})</b>\n\n"
                f"👤 @{message.from_user.username or message.from_user.id} (<code>{message.from_user.id}</code>)\n"
                f"{E.BALANCE} {asset}: <code>{amount}</code>\n📮 <code>{address}</code>",
                parse_mode="HTML",
                reply_markup=withdrawal_action_menu(0)
            )
        except Exception:
            pass
    await state.clear()


@router.callback_query(F.data == "menu_help")
async def menu_help(call: CallbackQuery):
    await call.message.edit_text(
        f"{E.HELP} <b>Stake Pay — Помощь</b>\n\n"
        f"{E.BALANCE} Баланс\n{E.CHECK} Создать чек\n"
        f"{E.DEPOSIT} Пополнение (RUB / Stars / Крипта)\n"
        f"{E.WITHDRAW} Вывод\n\n"
        f"Канал: {CHANNEL_LINK}",
        parse_mode="HTML", reply_markup=main_menu()
    )


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{E.ERROR} Нет доступа.", parse_mode="HTML")
        return
    await message.answer(f"{E.ADMIN} <b>Админ-панель Stake Pay</b>", parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    count, total = await get_stats()
    users = await all_users()
    await call.message.edit_text(
        f"{E.STATS} <b>Статистика</b>\n\n"
        f"{E.USERS} Юзеров: <code>{len(users)}</code>\n"
        f"{E.SUCCESS} Чеков: <code>{count or 0}</code>\n"
        f"{E.BALANCE} Оборот: <code>{total or 0:.2f}</code>",
        parse_mode="HTML", reply_markup=admin_menu()
    )


@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pending = await get_pending_withdrawals()
    if not pending:
        await call.answer("📭 Нет заявок", show_alert=True)
        return
    for w in pending:
        wid, uid, asset, amount, address, status, created = w
        await call.message.answer(
            f"{E.REQUESTS} <b>Заявка #{wid}</b>\n\n"
            f"👤 <code>{uid}</code>\n"
            f"{E.BALANCE} {asset}: <code>{amount}</code>\n"
            f"📮 <code>{address}</code>\n📅 {created}",
            parse_mode="HTML", reply_markup=withdrawal_action_menu(wid)
        )


@router.callback_query(F.data.startswith("wd_paid_"))
async def wd_paid(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    wid = int(call.data.split("_")[2])
    w = await get_withdrawal(wid)
    if not w:
        return
    await update_withdrawal_status(wid, "paid")
    await log_admin(call.from_user.id, "withdraw_paid", w[1], f"{w[3]} {w[2]}")
    await call.message.edit_text(f"{E.SUCCESS} Заявка #{wid} выплачена.", parse_mode="HTML")
    try:
        await bot.send_message(w[1], f"{E.SUCCESS} Вывод #{wid} выплачен: <code>{w[3]} {w[2]}</code>", parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("wd_reject_"))
async def wd_reject(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    wid = int(call.data.split("_")[2])
    w = await get_withdrawal(wid)
    if not w:
        return
    await update_withdrawal_status(wid, "rejected")
    await update_balance(w[1], w[3])
    await log_admin(call.from_user.id, "withdraw_reject", w[1], f"{w[3]} {w[2]}")
    await call.message.edit_text(f"{E.ERROR} Заявка #{wid} отклонена.", parse_mode="HTML")
    try:
        await bot.send_message(w[1], f"{E.ERROR} Вывод #{wid} отклонён. <code>{w[3]} {w[2]}</code> возвращены.", parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    users = await all_users()
    text = f"{E.USERS} <b>Последние 20 юзеров</b>\n\n"
    for u in users[:20]:
        uid, uname, bal, banned, created = u
        flag = E.BAN if banned else E.SUCCESS
        text += f"{flag} <code>{uid}</code> @{uname or '—'} — <b>{bal:.2f}</b>\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_give")
async def admin_give(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.give_user)
    await call.message.edit_text(
        f"{E.PLUS} <b>Выдать валюту</b>\n\nВведи ID пользователя:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


@router.message(AdminStates.give_user)
async def give_user(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer(f"{E.ERROR} Введи числовой ID.", reply_markup=cancel_kb())
        return
    await state.update_data(target=uid)
    await state.set_state(AdminStates.give_amount)
    await message.answer(
        f"👤 ID: <code>{uid}</code>\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )


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
        await bot.send_message(target, f"{E.GIFT} Тебе начислено <code>{amount}</code>", parse_mode="HTML")
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
        f"{E.SUCCESS} Рассылка завершена\n\n✅ Доставлено: {ok}\n❌ Ошибок: {fail}",
        parse_mode="HTML", reply_markup=admin_menu()
    )
    await state.clear()


@router.callback_query(F.data.startswith("uadd100_"))
async def uadd100(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await update_balance(uid, 100)
    await log_admin(call.from_user.id, "add100", uid, "+100")
    await call.answer("✅ +100", show_alert=True)


@router.callback_query(F.data.startswith("usub100_"))
async def usub100(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await update_balance(uid, -100)
    await log_admin(call.from_user.id, "sub100", uid, "-100")
    await call.answer("✅ -100", show_alert=True)


@router.callback_query(F.data.startswith("uban_"))
async def uban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await ban_user(uid, True)
    await log_admin(call.from_user.id, "ban", uid, "")
    await call.answer("🚫 Забанен", show_alert=True)


@router.callback_query(F.data.startswith("uunban_"))
async def uunban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split("_")[1])
    await ban_user(uid, False)
    await log_admin(call.from_user.id, "unban", uid, "")
    await call.answer("✅ Разбанен", show_alert=True)
