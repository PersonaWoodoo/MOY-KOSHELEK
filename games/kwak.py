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

KWAK_GAMES: Dict[str, Dict[str, Any]] = {}

# Множители по шагам
MULTIPLIERS = [1.4, 2.0, 2.8, 4.0, 5.6, 8.0, 11.0, 15.0, 21.0, 30.0]
FALL_CHANCE = 0.30  # 30% упасть


def kwak_text(game: Dict[str, Any]) -> str:
    step = int(game["step"])
    bet = float(game["bet"])
    next_mult = MULTIPLIERS[step] if step < len(MULTIPLIERS) else MULTIPLIERS[-1]
    current = bet * MULTIPLIERS[step - 1] if step > 0 else 0
    row = "🐸" + "🟢" * step + "🟤" * (10 - step)
    return (
        f"🐸 <b>КВАК</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n"
        f"📊 Шаг: <b>{step}/10</b>\n"
        f"{E.RATES} Следующий множитель: <b>x{next_mult}</b>\n"
        f"💰 Текущий выигрыш: <b>{fmt_money(current)}</b>\n\n"
        f"{row}\n\n"
        f"👇 Прыгай или забери!"
    )


def kwak_kb(gid: str, step: int):
    rows = [[InlineKeyboardButton(text="🐸 Прыгнуть", callback_data=f"kwak:{gid}:jump", style="primary")]]
    if step > 0:
        rows.append([InlineKeyboardButton(text="✅ Забрать", callback_data=f"kwak:{gid}:collect", style="success")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"kwak:{gid}:cancel", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.lower().startswith("квак"))
async def kwak_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: <code>квак 0.5</code>", parse_mode="HTML")

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in KWAK_GAMES.values()):
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

        gid = _new_gid("k")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "step": 0, "state": "playing"}
        KWAK_GAMES[gid] = game
        await message.answer(kwak_text(game), reply_markup=kwak_kb(gid, 0), parse_mode="HTML")


@router.callback_query(F.data.startswith("kwak:"))
async def kwak_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]

    game = KWAK_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = KWAK_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])
        step = int(game["step"])

        if action == "cancel":
            if step > 0:
                return await query.answer("Нельзя отменить после прыжка", show_alert=True)
            await add_balance(query.from_user.id, bet)
            KWAK_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "collect":
            if step <= 0:
                return await query.answer("Прыгни хотя бы раз", show_alert=True)
            mult = MULTIPLIERS[step - 1]
            payout = round(bet * mult, 4)
            balance = await finalize_bet(query.from_user.id, bet, payout, "kwak", f"collect={step}")
            KWAK_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.SUCCESS} <b>Забрал!</b>\n"
                f"➖➖➖➖➖➖➖➖➖\n"
                f"📊 Шагов: <b>{step}</b>\n"
                f"{E.RATES} Множитель: <b>x{mult}</b>\n"
                f"{E.WIN} Выигрыш: <b>{fmt_money(payout)}</b>\n"
                f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "jump":
            if step >= 10:
                return await query.answer("Максимум шагов", show_alert=True)

            spin_msg = await query.message.answer("🐸")
            await asyncio.sleep(1)
            try:
                await spin_msg.delete()
            except Exception:
                pass

            if random.random() < FALL_CHANCE:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "kwak", f"fall={step + 1}")
                KWAK_GAMES.pop(gid, None)
                await query.message.edit_text(
                    f"{E.LOSE} <b>Квак упал в воду!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🐸 Успел прыгнуть: <b>{step}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
                return await query.answer()

            game["step"] = step + 1
            KWAK_GAMES[gid] = game
            await query.message.edit_text(kwak_text(game), reply_markup=kwak_kb(gid, step + 1), parse_mode="HTML")
            return await query.answer()
