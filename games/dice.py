import random
import asyncio
from typing import Dict, Any

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from games.config import MIN_BET
from games.utils import (
    fmt_money, parse_bet, _game_lock, _new_gid,
    get_balance, reserve_bet, finalize_bet, add_balance
)
from games.subscriptions import require_subscriptions

import emojis as E

router = Router()

DICE_GAMES: Dict[str, Dict[str, Any]] = {}

DICE_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

WIN_MULT = 6.0


def dice_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    predict = int(game["predict"])
    return (
        f"🎲 <b>КУБИК</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n"
        f"🎯 Твой прогноз: <b>{DICE_EMOJI[predict]}</b>\n"
        f"📈 Множитель если угадаешь: <b>x{WIN_MULT}</b>\n\n"
        f"👇 Брось кубик!"
    )


def dice_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Бросить", callback_data=f"dice:{gid}:roll", style="success")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"dice:{gid}:cancel", style="danger")],
    ])


@router.message(F.text.lower().startswith("куб"))
async def dice_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 3:
        return await message.answer(
            "Формат: <code>куб 0.5 6</code>\n• 0.5 — ставка\n• 6 — число (1-6)",
            parse_mode="HTML"
        )

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in DICE_GAMES.values()):
            return await message.answer("У тебя уже активная игра.")

        try:
            bet = parse_bet(parts[1])
            predict = int(parts[2])
        except Exception:
            return await message.answer("Неверные параметры.")

        if not (1 <= predict <= 6):
            return await message.answer("Число: 1-6")
        if bet < MIN_BET:
            return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")

        balance = await get_balance(user_id)
        if bet > balance:
            return await message.answer("Недостаточно средств.")

        ok, _ = await reserve_bet(user_id, bet)
        if not ok:
            return await message.answer("Недостаточно средств.")

        gid = _new_gid("d")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "predict": predict, "state": "playing"}
        DICE_GAMES[gid] = game
        await message.answer(dice_text(game), reply_markup=dice_kb(gid), parse_mode="HTML")


@router.callback_query(F.data.startswith("dice:"))
async def dice_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]

    game = DICE_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = DICE_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])
        predict = int(game["predict"])

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            DICE_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "roll":
            try:
                await query.message.delete()
            except Exception:
                pass

            spin_msg = await query.message.answer("🎲")
            await asyncio.sleep(2)
            try:
                await spin_msg.delete()
            except Exception:
                pass

            roll = random.randint(1, 6)
            win = roll == predict

            if win:
                payout = round(bet * WIN_MULT, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "dice", f"roll={roll}")
                DICE_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.WIN} <b>Кубик · Победа!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎲 Выпало: <b>{DICE_EMOJI[roll]}</b>\n"
                    f"🎯 Твой прогноз: <b>{DICE_EMOJI[predict]}</b> ✅\n"
                    f"📈 Множитель: <b>x{WIN_MULT}</b>\n"
                    f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "dice", f"roll={roll}")
                DICE_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Кубик · Проигрыш!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎲 Выпало: <b>{DICE_EMOJI[roll]}</b>\n"
                    f"🎯 Твой прогноз: <b>{DICE_EMOJI[predict]}</b> ❌\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
