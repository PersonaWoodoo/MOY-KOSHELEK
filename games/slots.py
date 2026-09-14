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

SLOTS_GAMES: Dict[str, Dict[str, Any]] = {}

SYMBOLS = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
WEIGHTS = [35, 28, 18, 12, 7]

PAYOUTS = {
    "🍒": 3.0, "🍋": 4.0, "🍇": 6.0, "💎": 10.0, "7️⃣": 25.0,
}

TWO_MATCH = 1.2


def slots_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    return (
        f"🎰 <b>СЛОТЫ</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n\n"
        f"🍒 ×3 = x3\n🍋 ×3 = x4\n🍇 ×3 = x6\n💎 ×3 = x10\n7️⃣ ×3 = x25 {E.BONUS}\n\n"
        f"👇 Крути!"
    )


def slots_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить", callback_data=f"slots:{gid}:spin", style="success")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"slots:{gid}:cancel", style="danger")],
    ])


@router.message(F.text.lower().startswith("слоты"))
async def slots_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: <code>слоты 0.5</code>", parse_mode="HTML")

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in SLOTS_GAMES.values()):
            return await message.answer("У тебя уже активная игра.")

        try:
            bet = parse_bet(parts[1])
        except Exception:
            return await message.answer("Неверная ставка.")

        if bet < MIN_BET:
            return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")

        balance = await get_balance(user_id)
        if bet > balance:
            return await message.answer("Недостаточно средств.")

        ok, _ = await reserve_bet(user_id, bet)
        if not ok:
            return await message.answer("Недостаточно средств.")

        gid = _new_gid("s")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "state": "playing"}
        SLOTS_GAMES[gid] = game
        await message.answer(slots_text(game), reply_markup=slots_kb(gid), parse_mode="HTML")


@router.callback_query(F.data.startswith("slots:"))
async def slots_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]

    game = SLOTS_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = SLOTS_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            SLOTS_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "spin":
            try:
                await query.message.delete()
            except Exception:
                pass

            spin_msg = await query.message.answer("🎰")
            await asyncio.sleep(2)
            try:
                await spin_msg.delete()
            except Exception:
                pass

            reels = random.choices(SYMBOLS, weights=WEIGHTS, k=3)
            display = f"{reels[0]} {reels[1]} {reels[2]}"

            if reels[0] == reels[1] == reels[2]:
                mult = PAYOUTS[reels[0]]
                payout = round(bet * mult, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "slots", f"win={reels[0]}")
                SLOTS_GAMES.pop(gid, None)
                icon = E.BONUS if reels[0] == "7️⃣" else E.WIN
                await query.message.answer(
                    f"{icon} <b>Слоты · Победа!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎰 Выпало: <b>{display}</b>\n"
                    f"📈 Множитель: <b>x{mult}</b>\n"
                    f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
                payout = round(bet * TWO_MATCH, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "slots", "two")
                SLOTS_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.SUCCESS} <b>Слоты · 2 совпадения</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎰 Выпало: <b>{display}</b>\n"
                    f"📈 Множитель: <b>x{TWO_MATCH}</b>\n"
                    f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "slots", "lose")
                SLOTS_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Слоты · Проигрыш!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎰 Выпало: <b>{display}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
