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

BOWLING_GAMES: Dict[str, Dict[str, Any]] = {}

MULTIPLIERS = {
    0: 5.0, 1: 8.0, 2: 6.0, 3: 5.0, 4: 4.0, 5: 3.5,
    6: 3.0, 7: 4.0, 8: 6.0, 9: 10.0, 10: 20.0,
}


def bowling_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    predict = int(game["predict"])
    return (
        f"🎳 <b>БОУЛИНГ</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n"
        f"🎯 Твой прогноз: <b>{predict}</b> кеглей\n"
        f"📈 Множитель если угадаешь: <b>x{MULTIPLIERS.get(predict, 3.0)}</b>\n\n"
        f"👇 Кидай шар!"
    )


def bowling_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎳 Бросить", callback_data=f"bowling:{gid}:roll", style="success")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"bowling:{gid}:cancel", style="danger")],
    ])


@router.message(F.text.lower().startswith("боулинг"))
async def bowling_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 3:
        return await message.answer(
            "Формат: <code>боулинг 0.5 7</code>\n• 0.5 — ставка\n• 7 — сколько кеглей (0-10)",
            parse_mode="HTML"
        )

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in BOWLING_GAMES.values()):
            return await message.answer("У тебя уже активная игра.")

        try:
            bet = parse_bet(parts[1])
            predict = int(parts[2])
        except Exception:
            return await message.answer("Неверные параметры.")

        if not (0 <= predict <= 10):
            return await message.answer("Прогноз: 0-10")
        if bet < MIN_BET:
            return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")

        balance = await get_balance(user_id)
        if bet > balance:
            return await message.answer("Недостаточно средств.")

        ok, _ = await reserve_bet(user_id, bet)
        if not ok:
            return await message.answer("Недостаточно средств.")

        gid = _new_gid("b")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "predict": predict, "state": "playing"}
        BOWLING_GAMES[gid] = game
        await message.answer(bowling_text(game), reply_markup=bowling_kb(gid), parse_mode="HTML")


@router.callback_query(F.data.startswith("bowling:"))
async def bowling_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]

    game = BOWLING_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = BOWLING_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])
        predict = int(game["predict"])

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            BOWLING_GAMES.pop(gid, None)
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

            spin_msg = await query.message.answer("🎳")
            await asyncio.sleep(2)
            try:
                await spin_msg.delete()
            except Exception:
                pass

            weights = [3, 4, 6, 8, 10, 12, 15, 12, 10, 8, 5]
            knocked = random.choices(range(11), weights=weights, k=1)[0]
            win = knocked == predict

            if win:
                mult = MULTIPLIERS.get(predict, 3.0)
                payout = round(bet * mult, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "bowling", f"hit={knocked}")
                BOWLING_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.WIN} <b>Боулинг · Победа!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎳 Сбито кеглей: <b>{knocked}/10</b>\n"
                    f"🎯 Твой прогноз: <b>{predict}</b> ✅\n"
                    f"📈 Множитель: <b>x{mult}</b>\n"
                    f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "bowling", f"miss={knocked}")
                BOWLING_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Боулинг · Проигрыш!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎳 Сбито кеглей: <b>{knocked}/10</b>\n"
                    f"🎯 Твой прогноз: <b>{predict}</b> ❌\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
