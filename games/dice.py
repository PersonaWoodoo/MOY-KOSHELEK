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


def dice_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    return (
        f"🎲 <b>Кубик · выбери исход!</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"{E.BALANCE} <b>Ставка:</b> {fmt_money(bet)}\n\n"
        f"👇 На что ставишь?"
    )


def dice_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Больше 3 — x1.5", callback_data=f"dice:{gid}:big", style="success"),
            InlineKeyboardButton(text="📉 Меньше 3 — x1.5", callback_data=f"dice:{gid}:small", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🎯 Ровно 3 — x3", callback_data=f"dice:{gid}:exact3", style="primary"),
            InlineKeyboardButton(text="🎯 Число — x4", callback_data=f"dice:{gid}:number", style="primary"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"dice:{gid}:cancel", style="danger")],
    ])


def dice_number_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣", callback_data=f"dice:{gid}:n:1", style="primary"),
            InlineKeyboardButton(text="2️⃣", callback_data=f"dice:{gid}:n:2", style="primary"),
            InlineKeyboardButton(text="3️⃣", callback_data=f"dice:{gid}:n:3", style="primary"),
        ],
        [
            InlineKeyboardButton(text="4️⃣", callback_data=f"dice:{gid}:n:4", style="primary"),
            InlineKeyboardButton(text="5️⃣", callback_data=f"dice:{gid}:n:5", style="primary"),
            InlineKeyboardButton(text="6️⃣", callback_data=f"dice:{gid}:n:6", style="primary"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"dice:{gid}:back", style="danger")],
    ])


@router.message(F.text.lower().startswith("куб"))
async def dice_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: <code>куб 0.5</code>", parse_mode="HTML")

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in DICE_GAMES.values()):
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

        gid = _new_gid("d")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "state": "playing"}
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

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            DICE_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "back":
            await query.message.edit_text(dice_text(game), reply_markup=dice_kb(gid), parse_mode="HTML")
            return await query.answer()

        if action == "number":
            await query.message.edit_text(
                f"🎲 <b>Выбери число (1-6)</b>\n\n"
                f"{E.BALANCE} Ставка: {fmt_money(bet)}\n"
                f"{E.RATES} Множитель: x4",
                parse_mode="HTML", reply_markup=dice_number_kb(gid)
            )
            return await query.answer()

        if action in ("big", "small", "exact3", "n"):
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

            win = False
            mult = 0.0
            choice_label = ""

            if action == "big":
                choice_label = "больше 3"
                if roll > 3:
                    win = True
                    mult = 1.5
            elif action == "small":
                choice_label = "меньше 3"
                if roll < 3:
                    win = True
                    mult = 1.5
            elif action == "exact3":
                choice_label = "ровно 3"
                if roll == 3:
                    win = True
                    mult = 3.0
            elif action == "n":
                num = int(parts[3])
                choice_label = f"число {num}"
                if roll == num:
                    win = True
                    mult = 4.0

            if win:
                payout = round(bet * mult, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "dice", f"win_{roll}")
                DICE_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.WIN} <b>Кубик · Победа!</b> ✅\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎲 Выпало: <b>{DICE_EMOJI[roll]}</b>\n"
                    f"🎯 Выбрано: <b>{choice_label}</b>\n"
                    f"{E.RATES} Выигрыш: x{mult} / {fmt_money(payout)}\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"⚡ Итог: <b>{roll}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "dice", f"lose_{roll}")
                DICE_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Кубик · Проигрыш</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎲 Выпало: <b>{DICE_EMOJI[roll]}</b>\n"
                    f"🎯 Выбрано: <b>{choice_label}</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"⚡ Итог: <b>{roll}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
