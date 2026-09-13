from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, MIN_CHECK_AMOUNT, CHANNEL_LINK, TON_WALLET
from database import (
    init_db, get_user, create_user, update_balance,
    save_check, get_check, activate_check, get_stats,
    create_withdrawal, get_pending_withdrawals, get_withdrawal,
    update_withdrawal_status
)
from cryptobot_api import create_check, create_invoice, get_exchange_rate
from keyboards import (
    main_menu, subscribe_menu, assets_menu, confirm_check_menu,
    admin_menu, withdrawal_action_menu
)
from states import CheckStates, DepositStates, WithdrawStates
from subscription import check_subscription

import emojis as E

router = Router()


# ---------- SUBSCRIPTION GUARD ----------
async def require_subscription(message: Message, bot: Bot) -> bool:
    ok = await check_subscription(bot, message.from_user.id)
    if not ok:
        await message.answer(
            f"{E.ERROR} <b>Для использования Stake Pay подпишись на канал:</b>\n\n"
            f"👉 {CHANNEL_LINK}",
            parse_mode="HTML",
            reply_markup=subscribe_menu()
        )
    return ok


# ---------- START ----------
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await create_user(message.from_user.id, message.from_user.username or "")

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            f"{E.ROCKET} <b>Добро пожаловать в Stake Pay!</b>\n\n"
            f"Для начала подпишись на наш канал:\n👉 {CHANNEL_LINK}",
            parse_mode="HTML",
            reply_markup=subscribe_menu()
        )
        return

    await message.answer(
        f"{E.ROCKET} Привет, {message.from_user.first_name}!\n\n"
        f"<b>Stake Pay</b> — твой крипто-кошелёк.\n\n"
        f"{E.BALANCE} Баланс — посмотреть средства\n"
        f"{E.CHECK} Создать чек — отправить крипту\n"
        f"{E.DEPOSIT} Пополнить — ввод средств\n"
        f"{E.WITHDRAW} Вывести — заявка на вывод",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery, bot: Bot):
    if await check_subscription(bot, call.from_user.id):
        await call.message.edit_text(f"{E.SUCCESS} Подписка подтверждена!", parse_mode="HTML")
        await call.message.answer("Главное меню:", reply_markup=main_menu())
    else:
        await call.answer("❌ Ты ещё не подписался!", show_alert=True)


# ---------- BALANCE ----------
@router.message(F.text == "💎 Баланс")
async def show_balance(message: Message, bot: Bot):
    if not await require_subscription(message, bot):
        return

    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id)
        user = await get_user(message.from_user.id)

    balance = user[2]

    rates = await get_exchange_rate()
    rub = 0
    if rates.get("ok"):
        for r in rates["result"]:
            if r["source"] == "USDT" and r["target"] == "RUB":
                rub = balance * float(r["rate"])
                break

    await message.answer(
        f"{E.BALANCE} <b>Твой баланс</b>\n\n"
        f"💎 USDT: <code>{balance:.2f}</code>\n"
        f"💵 RUB: <code>{rub:.2f} ₽</code>\n\n"
        f"{E.STARS} Stars: <code>{int(balance * 50)}</code> (примерный курс)",
        parse_mode="HTML"
    )


# ---------- DEPOSIT ----------
@router.message(F.text == "📥 Пополнить")
async def deposit_start(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    await state.set_state(DepositStates.asset)
    await message.answer(
        f"{E.DEPOSIT} <b>Пополнение</b>\n\nВыбери актив:",
        parse_mode="HTML",
        reply_markup=assets_menu("dep")
    )


@router.callback_query(DepositStates.asset, F.data.startswith("dep_"))
async def deposit_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)

    if asset == "TON":
        await call.message.edit_text(
            f"💎 <b>Пополнение TON</b>\n\n"
            f"Отправь TON на адрес:\n"
            f"<code>{TON_WALLET}</code>\n\n"
            f"После перевода нажми «Я оплатил».",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Я оплатил", callback_data="ton_paid", style="success")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main", style="danger")],
            ])
        )
        await state.clear()
        return

    await state.set_state(DepositStates.amount)
    await call.message.edit_text(
        f"{E.DEPOSIT} Актив: <b>{asset}</b>\n\nВведи сумму пополнения:",
        parse_mode="HTML"
    )


@router.message(DepositStates.amount)
async def deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML")
        return

    data = await state.get_data()
    asset = data["asset"]

    result = await create_invoice(asset=asset, amount=amount, description="Stake Pay Deposit")

    if not result.get("ok"):
        await message.answer(f"{E.ERROR} Ошибка: {result}", parse_mode="HTML")
        await state.clear()
        return

    pay_url = result["result"].get("bot_invoice_url") or result["result"].get("pay_url", "")
    await message.answer(
        f"{E.SUCCESS} <b>Инвойс создан!</b>\n\n"
        f"💎 Актив: <code>{asset}</code>\n"
        f"💰 Сумма: <code>{amount}</code>\n\n"
        f"🔗 Оплатить: {pay_url}",
        parse_mode="HTML"
    )
    await state.clear()


# ---------- CREATE CHECK ----------
@router.message(F.text == "🧾 Создать чек")
async def create_check_start(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    await state.set_state(CheckStates.asset)
    await message.answer(
        f"{E.CHECK} Выбери актив для чека:",
        parse_mode="HTML",
        reply_markup=assets_menu("asset")
    )


@router.callback_query(CheckStates.asset, F.data.startswith("asset_"))
async def choose_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(CheckStates.amount)
    await call.message.edit_text(
        f"{E.CHECK} Актив: <b>{asset}</b>\n\nВведи сумму чека (минимум {MIN_CHECK_AMOUNT}):",
        parse_mode="HTML"
    )


@router.message(CheckStates.amount)
async def enter_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML")
        return

    data = await state.get_data()
    asset = data["asset"]

    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0

    if amount < MIN_CHECK_AMOUNT:
        await message.answer(f"{E.ERROR} Минимальная сумма — {MIN_CHECK_AMOUNT} {asset}", parse_mode="HTML")
        return
    if amount > balance:
        await message.answer(f"{E.ERROR} Недостаточно средств. Баланс: {balance:.2f} {asset}", parse_mode="HTML")
        return

    await state.update_data(amount=amount)
    await state.set_state(CheckStates.description)
    await message.answer("📝 Введи описание чека (или <code>-</code> чтобы пропустить):", parse_mode="HTML")


@router.message(CheckStates.description)
async def enter_description(message: Message, state: FSMContext):
    desc = "" if message.text == "-" else message.text
    await state.update_data(description=desc)
    await state.set_state(CheckStates.target)
    await message.answer(
        f"{E.PERSONAL} Укажи получателя:\n"
        "• @username — личный чек\n"
        "• <code>-</code> — публичный",
        parse_mode="HTML"
    )


@router.message(CheckStates.target)
async def enter_target(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_text = message.text.strip()
    target_id = None

    if target_text != "-":
        target_text = target_text.lstrip("@")
        try:
            chat = await bot.get_chat(f"@{target_text}")
            target_id = chat.id
        except Exception:
            await message.answer(f"{E.ERROR} Пользователь не найден. Попробуй ещё раз или <code>-</code>.", parse_mode="HTML")
            return

    result = await create_check(
        asset=data["asset"],
        amount=data["amount"],
        description=data["description"]
    )

    if not result.get("ok"):
        await message.answer(f"{E.ERROR} Ошибка: {result}", parse_mode="HTML")
        await state.clear()
        return

    check_data = result["result"]
    check_id = check_data["check_id"]
    url = check_data.get("bot_check_url", "")

    await save_check(
        check_id=check_id,
        creator_id=message.from_user.id,
        target_id=target_id,
        asset=data["asset"],
        amount=data["amount"],
        description=data["description"]
    )

    await update_balance(message.from_user.id, -data["amount"])

    text = (
        f"{E.SUCCESS} <b>Чек создан!</b>\n\n"
        f"💎 Актив: <code>{data['asset']}</code>\n"
        f"💰 Сумма: <code>{data['amount']}</code>\n"
        f"📝 Описание: {data['description'] or '—'}\n"
        f"{E.PERSONAL} Получатель: {'@' + target_text if target_id else 'Публичный'}\n\n"
        f"🔗 Ссылка: {url}"
    )

    await message.answer(text, parse_mode="HTML")

    if target_id:
        try:
            await bot.send_message(
                target_id,
                f"🎁 Тебе чек на <code>{data['amount']} {data['asset']}</code>\n"
                f"📝 {data['description'] or 'Без описания'}\n\n🔗 {url}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()


# ---------- WITHDRAW ----------
@router.message(F.text == "📤 Вывести")
async def withdraw_start(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    await state.set_state(WithdrawStates.asset)
    await message.answer(
        f"{E.WITHDRAW} <b>Вывод</b>\n\nВыбери актив:",
        parse_mode="HTML",
        reply_markup=assets_menu("wd")
    )


@router.callback_query(WithdrawStates.asset, F.data.startswith("wd_"))
async def withdraw_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(WithdrawStates.amount)
    await call.message.edit_text(
        f"{E.WITHDRAW} Актив: <b>{asset}</b>\n\nВведи сумму вывода:",
        parse_mode="HTML"
    )


@router.message(WithdrawStates.amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(f"{E.ERROR} Введи число.", parse_mode="HTML")
        return

    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0

    if amount <= 0 or amount > balance:
        await message.answer(f"{E.ERROR} Недостаточно средств. Баланс: {balance:.2f}", parse_mode="HTML")
        return

    await state.update_data(amount=amount)
    await state.set_state(WithdrawStates.address)

    data = await state.get_data()
    if data["asset"] == "RUB":
        prompt = "💵 Введи номер карты / СБП:"
    elif data["asset"] == "STARS":
        prompt = f"{E.STARS} Введи свой @username для получения звёзд:"
    else:
        prompt = "📮 Введи адрес кошелька:"

    await message.answer(prompt, parse_mode="HTML")


@router.message(WithdrawStates.address)
async def withdraw_address(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    address = message.text.strip()
    amount = data["amount"]
    asset = data["asset"]

    await update_balance(message.from_user.id, -amount)
    await create_withdrawal(message.from_user.id, asset, amount, address)

    await message.answer(
        f"{E.SUCCESS} <b>Заявка на вывод создана!</b>\n\n"
        f"💎 Актив: <code>{asset}</code>\n"
        f"💰 Сумма: <code>{amount}</code>\n"
        f"📮 Адрес: <code>{address}</code>\n\n"
        f"⏳ Ожидай обработки администратором.",
        parse_mode="HTML"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📤 <b>Новая заявка на вывод</b>\n\n"
                f"👤 @{message.from_user.username or message.from_user.id}\n"
                f"💎 {asset}: <code>{amount}</code>\n"
                f"📮 <code>{address}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()


# ---------- HELP ----------
@router.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: Message, bot: Bot):
    if not await require_subscription(message, bot):
        return
    await message.answer(
        f"📖 <b>Stake Pay — Помощь</b>\n\n"
        f"{E.BALANCE} Баланс — средства в USDT, RUB, Stars\n"
        f"{E.CHECK} Создать чек — отправить крипту\n"
        f"{E.DEPOSIT} Пополнить — через CryptoBot / TON\n"
        f"{E.WITHDRAW} Вывести — заявка админу\n\n"
        f"Мин. чек: {MIN_CHECK_AMOUNT}\n"
        f"Канал: {CHANNEL_LINK}",
        parse_mode="HTML"
    )


# ---------- ADMIN ----------
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(f"{E.ERROR} Нет доступа.", parse_mode="HTML")
        return
    await message.answer("🛠 <b>Stake Pay — Админ</b>", parse_mode="HTML", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    count, total = await get_stats()
    pending = await get_pending_withdrawals()
    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"✅ Чеков активировано: <code>{count or 0}</code>\n"
        f"💰 Оборот: <code>{total or 0:.2f}</code>\n"
        f"📤 Заявок на вывод: <code>{len(pending)}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    pending = await get_pending_withdrawals()
    if not pending:
        await call.message.edit_text("📭 Нет активных заявок.", reply_markup=admin_menu())
        return

    for w in pending:
        wid, uid, asset, amount, address, status, created = w
        await call.message.answer(
            f"📤 <b>Заявка #{wid}</b>\n\n"
            f"👤 ID: <code>{uid}</code>\n"
            f"💎 {asset}: <code>{amount}</code>\n"
            f"📮 <code>{address}</code>\n"
            f"📅 {created}",
            parse_mode="HTML",
            reply_markup=withdrawal_action_menu(wid)
        )


@router.callback_query(F.data.startswith("wd_paid_"))
async def wd_paid(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in ADMIN_IDS:
        return
    wid = int(call.data.split("_")[2])
    w = await get_withdrawal(wid)
    await update_withdrawal_status(wid, "paid")
    await call.message.edit_text(f"{E.SUCCESS} Заявка #{wid} выплачена.", parse_mode="HTML")

    try:
        await bot.send_message(
            w[1],
            f"{E.SUCCESS} <b>Вывод #{wid} выплачен!</b>\n"
            f"💎 {w[2]}: <code>{w[3]}</code>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("wd_reject_"))
async def wd_reject(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in ADMIN_IDS:
        return
    wid = int(call.data.split("_")[2])
    w = await get_withdrawal(wid)
    await update_withdrawal_status(wid, "rejected")
    await update_balance(w[1], w[3])
    await call.message.edit_text(f"{E.ERROR} Заявка #{wid} отклонена. Баланс возвращён.", parse_mode="HTML")

    try:
        await bot.send_message(
            w[1],
            f"{E.ERROR} <b>Вывод #{wid} отклонён.</b>\n"
            f"💰 <code>{w[3]} {w[2]}</code> возвращены на баланс.",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery):
    await call.message.delete()
