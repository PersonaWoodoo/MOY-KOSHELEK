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

MULTIPLIERS = [1.5, 2.5, 4.0, 7.0, 15.0]
HIT_CHANCE = 0.45
MAX_SHOTS = 5


def basket_text(game: Dict[str, Any]) -> str:
    hits = int(game["hits"])
    bet = float(game["bet"])
    next_mult = MULTIPLIERS[hits] if hits < len(MULTIPLIERS) else MULTIPLIERS[-1]
    current = bet * MULTIPLIERS[hits - 1] if hits > 0 else 0
    return (
        f"🏀 <b>БАСКЕТБОЛ</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n"
        f"🎯 Попаданий: <b>{hits}/{MAX_SHOTS}</b>\n"
        f"📈 Следующий множитель: <b>x{next_mult}</b>\n"
        f"💰 Текущий выигрыш: <b>{fmt_money(current)}</b>\n\n"
        f"👇 Бросай!"
    )


def basket_kb(gid: str, hits: int):
    rows = [[InlineKeyboardButton(text="🏀 Бросить", callback_data=f"basket:{gid}:shoot", style="primary")]]
    if hits > 0:
        rows.append([InlineKeyboardButton(text="✅ Забрать", callback_data=f"basket:{gid}:collect", style="success")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"basket:{gid}:cancel", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "hits": 0, "shots": 0, "state": "playing"}
        BASKET_GAMES[gid] = game
        await message.answer(basket_text(game), reply_markup=basket_kb(gid, 0), parse_mode="HTML")


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
        hits = int(game["hits"])

        if action == "cancel":
            if hits > 0:
                return await query.answer("Нельзя отменить после попадания", show_alert=True)
            await add_balance(query.from_user.id, bet)
            BASKET_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "collect":
            if hits <= 0:
                return await query.answer("Брось хотя бы раз", show_alert=True)
            mult = MULTIPLIERS[hits - 1]
            payout = round(bet * mult, 4)
            balance = await finalize_bet(query.from_user.id, bet, payout, "basket", f"collect={hits}")
            BASKET_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.SUCCESS} <b>Забрал!</b>\n"
                f"➖➖➖➖➖➖➖➖➖\n"
                f"🏀 Попаданий: <b>{hits}</b>\n"
                f"📈 Множитель: <b>x{mult}</b>\n"
                f"{E.WIN} Выигрыш: <b>{fmt_money(payout)}</b>\n"
                f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "shoot":
            if hits >= MAX_SHOTS:
                return await query.answer("Максимум бросков", show_alert=True)

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

            if random.random() < HIT_CHANCE:
                game["hits"] = hits + 1
                game["shots"] = int(game["shots"]) + 1
                BASKET_GAMES[gid] = game

                if game["hits"] >= MAX_SHOTS:
                    mult = MULTIPLIERS[MAX_SHOTS - 1]
                    payout = round(bet * mult, 4)
                    balance = await finalize_bet(query.from_user.id, bet, payout, "basket", f"won={hits + 1}")
                    BASKET_GAMES.pop(gid, None)
                    await query.message.answer(
                        f"{E.BONUS} <b>Баскетбол · 5/5 PERFECT!</b>\n"
                        f"➖➖➖➖➖➖➖➖➖\n"
                        f"🏀 Попаданий: <b>5/5</b>\n"
                        f"📈 Множитель: <b>x{mult}</b>\n"
                        f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                        f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                        parse_mode="HTML"
                    )
                    return await query.answer()

                await query.message.answer(
                    f"{E.SUCCESS} <b>Баскетбол · Попадание!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🏀 Попаданий: <b>{game['hits']}/{MAX_SHOTS}</b>",
                    parse_mode="HTML",
                    reply_markup=basket_kb(gid, game["hits"])
                )
                return await query.answer()

            else:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "basket", f"miss={hits}")
                BASKET_GAMES.pop(gid, None)
                await query.message.answer(
                    f"{E.LOSE} <b>Баскетбол · Промах!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🏀 Попаданий: <b>{hits}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
                return await query.answer()
