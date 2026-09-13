import secrets


@router.message(WithdrawStates.address)
async def wd_address(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    address = message.text.strip()
    amount = data["amount"]
    asset = data["asset"]

    # Проверка баланса перед выводом
    user = await get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount > balance:
        await message.answer(
            f"{E.ERROR} Недостаточно средств.\nБаланс: <b>{balance:.2f}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )
        await state.clear()
        return

    # ===== АВТО-ВЫВОД КРИПТЫ через CryptoBot =====
    if asset in ("USDT", "TON", "BTC", "ETH", "TRX", "SOL"):
        try:
            # Получатель — либо указанный Telegram ID, либо сам юзер
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
                    f"{E.ERROR} Ошибка вывода: <code>{err_name}</code>\n\n"
                    f"Проверь адрес или попробуй позже.",
                    parse_mode="HTML", reply_markup=main_menu()
                )
                await state.clear()
                return

            # Списываем баланс только после успешного перевода
            await update_balance(message.from_user.id, -amount)
            await create_withdrawal(message.from_user.id, asset, amount, address)

            await message.answer(
                f"{E.SUCCESS} <b>Вывод выполнен!</b>\n\n"
                f"💎 {asset}: <code>{amount}</code>\n"
                f"📮 Куда: <code>{address}</code>\n\n"
                f"⏳ Зачисление в течение минуты.",
                parse_mode="HTML", reply_markup=main_menu()
            )
            await state.clear()
            return

        except Exception as e:
            await message.answer(f"{E.ERROR} Ошибка: <code>{e}</code>", parse_mode="HTML")
            await state.clear()
            return

    # ===== RUB / STARS — вручную через админку =====
    await update_balance(message.from_user.id, -amount)
    await create_withdrawal(message.from_user.id, asset, amount, address)

    await message.answer(
        f"{E.SUCCESS} <b>Заявка создана!</b>\n\n"
        f"💎 {asset}: <code>{amount}</code>\n"
        f"📮 <code>{address}</code>\n\n⏳ Ожидай обработки.",
        parse_mode="HTML", reply_markup=main_menu()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📤 <b>Ручной вывод ({asset})</b>\n\n"
                f"👤 @{message.from_user.username or message.from_user.id} (<code>{message.from_user.id}</code>)\n"
                f"💎 {asset}: <code>{amount}</code>\n📮 <code>{address}</code>",
                parse_mode="HTML",
                reply_markup=withdrawal_action_menu(0)
            )
        except Exception:
            pass
    await state.clear()
