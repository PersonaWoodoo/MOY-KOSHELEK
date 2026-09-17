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

# Множители для групп
GROUP_1_3 = 1.5   # 1-3 кегли
GROUP_4_5 = 1.5   # 4-5 кеглей
GROUP_6 = 1.5     # 6 кеглей
EXACT_MULT = 5.0  # ровно N кеглей

# Веса выпадения (0-10)
WEIGHTS = [3, 4, 6, 8, 10, 12, 15, 12, 10, 8, 5]


def bowling_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    return (
        f"🎳 <b>Боулинг · выбери исход!</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"{E.BALANCE} <b>Ставка:</b> {fmt_money(bet)}\n\n"
        f"👇 Что выпадет?"
    )


def bowling_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎳 1-3 кегли — x{GROUP_1_3}", callback_data=f"bowling:{gid}:g1", style="success")],
        [InlineKeyboardButton(text=f"🎳 4-5 кеглей — x{GROUP_4_5}", callback_data=f"bowling:{gid}:g2", style="primary")],
        [InlineKeyboardButton(text=f"🎳 6 кеглей — x{GROUP_6}", callback_data=f"bowling:{gid}:g3", style="primary")],
        [InlineKeyboardButton(text=f"🎯 Число — x{EXACT_MULT}", callback_data=f"bowling:{gid}:number", style="success")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"bowling:{gid}:cancel", style="danger")],
    ])


def bowling_number_kb(gid: str):
    rows = []
    row1 = [
        InlineKeyboardButton(text="0️⃣", callback_data=f"bowling:{gid}:n:0", style="primary"),
        InlineKeyboardButton(text="1️⃣", callback_data=f"bowling:{gid}:n:1", style="primary"),
        InlineKeyboardButton(text="2️⃣", callback_data=f"bowling:{gid}:n:2", style="primary"),
        InlineKeyboardButton(text="3️⃣", callback_data=f"bowling:{gid}:n:3", style="primary"),
        InlineKeyboardButton(text="4️⃣", callback_data=f"bowling:{gid}:n:4", style="primary"),
    ]
    row2 = [
        InlineKeyboardButton(text="5️⃣", callback_data=f"bowling:{gid}:n:5", style="primary"),
        InlineKeyboardButton(text="6️⃣", callback_data=f"bowling:{gid}:n:6", style="primary"),
        InlineKeyboardButton(text="7️⃣", callback_data=f"bowling:{gid}:n:7", style="primary"),
        InlineKeyboardButton(text="8️⃣", callback_data=f"bowling:{gid}:n:8", style="primary"),
        InlineKeyboardButton(text="9️⃣", callback_data=f"bowling:{gid}:n:9", style="primary"),
    ]
    row3 = [
        InlineKeyboardButton(text="🔟", callback_data=f"bowling:{gid}:n:10", style="primary"),
    ]
    rows.append(row1)
    rows.append(row2)
    rows.append(row3)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"bowling:{gid}:back", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.lower().startswith("боулинг"))
async def bowling_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: <code>боулинг 0.5</code>", parse_mode="HTML")

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in BOWLING_GAMES.values()):
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

        gid = _new_gid("b")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "state": "playing"}
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

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            BOWLING_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "back":
            await query.message.edit_text(bowling_text(game), reply_markup=bowling_kb(gid), parse_mode="HTML")
            return await query.answer()

        if action == "number":
            await query.message.edit_text(
                f"🎳 <b>Сколько кеглей собьёт?</b>\n\n"
                f"{E.BALANCE} Ставка: {fmt_money(bet)}\n"
                f"{E.RATES} Множитель: x{EXACT_MULT}",
                parse_mode="HTML", reply_markup=bowling_number_kb(gid)
            )
            return await query.answer()

        if action in ("g1", "g2", "g3", "n"):
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

            knocked = random.choices(range(11), weights=WEIGHTS, k=1)[0]

            win = False
            mult = 0.0
            choice_label = ""

            if action == "g1":
                choice_label = "1-3 кегли"
                if 1 <= knocked <= 3:
                    win = True
                    mult = GROUP_1_3
            elif action == "g2":
                choice_label = "4-5 кеглей"
                if 4 <= knocked <= 5:
                    win = True
                    mult = GROUP_4_5
            elif action == "g3":
                choice_label = "6 кеглей"
                if knocked == 6:
                    win = True
                    mult = GROUP_6
            elif action == "n":
                num = int(parts[3])
                choice_label = f"число {num}"
                if knocked == num:
                    win = True
                    mult = EXACT_MULT

            if win:
                payout = round(bet * mult, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "bowling", f"win_{knocked}")
                BOWLING_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.WIN} <b>Боулинг · Победа!</b> ✅\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎳 Сбито: <b>{knocked}/10</b>\n"
                    f"🎯 Выбрано: <b>{choice_label}</b>\n"
                    f"{E.RATES} Выигрыш: x{mult} / {fmt_money(payout)}\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "bowling", f"lose_{knocked}")
                BOWLING_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Боулинг · Проигрыш</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🎳 Сбито: <b>{knocked}/10</b>\n"
                    f"🎯 Выбрано: <b>{choice_label}</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
