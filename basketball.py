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

BASKET_GAMES: Dict[str, Dict[str, Any]] = {}

HIT_MULT = 1.8
MISS_MULT = 1.9

HIT_CHANCE = 0.55


def basket_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    return (
        f"🏀 <b>Баскетбол · выбери исход!</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"{E.BALANCE} <b>Ставка:</b> {fmt_money(bet)}\n\n"
        f"👇 Что будет?"
    )


def basket_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏀 Заброшу — x{HIT_MULT}", callback_data=f"basket:{gid}:hit", style="success")],
        [InlineKeyboardButton(text=f"❌ Промахнусь — x{MISS_MULT}", callback_data=f"basket:{gid}:miss", style="primary")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"basket:{gid}:cancel", style="danger")],
    ])


@router.message(F.text.lower().startswith("баскетбол"))
async def basket_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: <code>баскетбол 0.5</code>", parse_mode="HTML")

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in BASKET_GAMES.values()):
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

        gid = _new_gid("bs")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "state": "playing"}
        BASKET_GAMES[gid] = game
        await message.answer(basket_text(game), reply_markup=basket_kb(gid), parse_mode="HTML")


@router.callback_query(F.data.startswith("basket:"))
async def basket_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]

    game = BASKET_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = BASKET_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            BASKET_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action in ("hit", "miss"):
            try:
                await query.message.delete()
            except Exception:
                pass

            spin_msg = await query.message.answer("🏀")
            await asyncio.sleep(2)
            try:
                await spin_msg.delete()
            except Exception:
                pass

            is_hit = random.random() < HIT_CHANCE
            result = "hit" if is_hit else "miss"

            if action == result:
                mult = HIT_MULT if action == "hit" else MISS_MULT
                payout = round(bet * mult, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "basket", f"win_{result}")
                BASKET_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.WIN} <b>Баскетбол · Победа!</b> ✅\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🏀 Выбрано: <b>{'заброшу' if action == 'hit' else 'промахнусь'}</b>\n"
                    f"{E.RATES} Выигрыш: x{mult} / {fmt_money(payout)}\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"⚡ Итог: <b>{'попал' if result == 'hit' else 'мимо'}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "basket", f"lose_{result}")
                BASKET_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Баскетбол · Проигрыш</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🏀 Выбрано: <b>{'заброшу' if action == 'hit' else 'промахнусь'}</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"⚡ Итог: <b>{'попал' if result == 'hit' else 'мимо'}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
