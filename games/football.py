import random
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

FOOTBALL_GAMES: Dict[str, Dict[str, Any]] = {}

ZONES = ["left", "center", "right"]
ZONE_LABELS = {"left": "⬅️ Лево", "center": "⬆️ Центр", "right": "➡️ Право"}
WIN_MULT = 2.7


def football_text(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    return (
        f"⚽ <b>ФУТБОЛ — ПЕНАЛЬТИ</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n"
        f"📈 Множитель за гол: <b>x{WIN_MULT}</b>\n\n"
        f"👇 Выбери зону удара:"
    )


def football_kb(gid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Лево", callback_data=f"football:{gid}:left", style="primary"),
            InlineKeyboardButton(text="⬆️ Центр", callback_data=f"football:{gid}:center", style="primary"),
            InlineKeyboardButton(text="➡️ Право", callback_data=f"football:{gid}:right", style="primary"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"football:{gid}:cancel", style="danger")],
    ])


@router.message(F.text.lower().startswith("футбол"))
async def football_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: <code>футбол 0.5</code>", parse_mode="HTML")

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in FOOTBALL_GAMES.values()):
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

        gid = _new_gid("f")
        game = {"gid": gid, "uid": user_id, "bet": float(bet), "state": "playing"}
        FOOTBALL_GAMES[gid] = game
        await message.answer(football_text(game), reply_markup=football_kb(gid), parse_mode="HTML")


@router.callback_query(F.data.startswith("football:"))
async def football_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]

    game = FOOTBALL_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = FOOTBALL_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])

        if action == "cancel":
            await add_balance(query.from_user.id, bet)
            FOOTBALL_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action in ZONES:
            keeper_zone = random.choice(ZONES)

            if keeper_zone == action:
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "football", f"save={action}")
                FOOTBALL_GAMES.pop(gid, None)
                await query.message.edit_text(
                    f"⚽ <b>Вратарь поймал!</b>\n\n"
                    f"Ты бил: <b>{ZONE_LABELS[action]}</b>\n"
                    f"Вратарь: <b>{ZONE_LABELS[keeper_zone]}</b>\n\n"
                    f"{E.LOSE} <b>Проигрыш</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            else:
                payout = round(bet * WIN_MULT, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "football", f"goal={action}")
                FOOTBALL_GAMES.pop(gid, None)
                await query.message.edit_text(
                    f"⚽ <b>ГОООЛ!</b>\n\n"
                    f"Ты бил: <b>{ZONE_LABELS[action]}</b>\n"
                    f"Вратарь: <b>{ZONE_LABELS[keeper_zone]}</b>\n\n"
                    f"{E.WIN} <b>ПОБЕДА!</b>\n"
                    f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
            return await query.answer()
