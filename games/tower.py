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

TOWER_GAMES: Dict[str, Dict[str, Any]] = {}

# Множители по уровням (9 этажей)
MULTIPLIERS = [1.4, 2.0, 2.8, 4.0, 5.6, 8.0, 11.0, 15.0, 21.0]

MINES_OPTIONS = [1, 2, 3, 4]


def tower_text(game: Dict[str, Any]) -> str:
    level = int(game["level"])
    mines = int(game["mines"])
    bet = float(game["bet"])
    next_level = level + 1
    current = bet * MULTIPLIERS[level - 1] if level > 0 else 0
    next_mult = MULTIPLIERS[level] if level < len(MULTIPLIERS) else MULTIPLIERS[-1]

    # Визуализация этажей
    rows = []
    for i in range(9):
        if i < level:
            rows.append(f"✅ Этаж {i + 1}")
        elif i == level:
            rows.append(f"▶️ Этаж {i + 1} — x{MULTIPLIERS[i]}")
        else:
            rows.append(f"🔒 Этаж {i + 1}")

    return (
        f"🗼 <b>БАШНЯ</b>\n\n"
        f"{E.BALANCE} Ставка: <b>{fmt_money(bet)}</b>\n"
        f"💣 Мин в ряду: <b>{mines}</b>\n"
        f"📊 Этаж: <b>{level}/9</b>\n"
        f"{E.RATES} Следующий множитель: <b>x{next_mult}</b>\n"
        f"💰 Текущий выигрыш: <b>{fmt_money(current)}</b>\n\n"
        f"👇 Выбери клетку на этаже {next_level}:"
    )


def tower_kb(gid: str, level: int):
    # 5 клеток — 1 мина
    pick_row = [
        InlineKeyboardButton(text="❔", callback_data=f"tower:{gid}:pick:0", style="primary"),
        InlineKeyboardButton(text="❔", callback_data=f"tower:{gid}:pick:1", style="primary"),
        InlineKeyboardButton(text="❔", callback_data=f"tower:{gid}:pick:2", style="primary"),
        InlineKeyboardButton(text="❔", callback_data=f"tower:{gid}:pick:3", style="primary"),
        InlineKeyboardButton(text="❔", callback_data=f"tower:{gid}:pick:4", style="primary"),
    ]
    rows = [pick_row]

    if level > 0:
        rows.append([InlineKeyboardButton(text=f"💰 Забрать", callback_data=f"tower:{gid}:collect", style="success")])

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"tower:{gid}:cancel", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.lower().startswith("башня"))
async def tower_start(message: Message, bot: Bot):
    if not await require_subscriptions(message, bot):
        return

    parts = message.text.split()
    if len(parts) not in (2, 3):
        return await message.answer(
            "Формат: <code>башня 0.5</code>\n"
            "Или: <code>башня 0.5 2</code> — 2 мины",
            parse_mode="HTML"
        )

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if any(g.get("uid") == user_id and g.get("state") == "playing" for g in TOWER_GAMES.values()):
            return await message.answer("У тебя уже активная игра.")

        try:
            bet = parse_bet(parts[1])
        except Exception:
            return await message.answer("Неверная ставка.")

        mines = 1
        if len(parts) == 3:
            try:
                mines = int(parts[2])
            except Exception:
                pass

        if mines not in MINES_OPTIONS:
            return await message.answer("Количество мин: 1, 2, 3 или 4")

        if bet < MIN_BET:
            return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")

        balance = await get_balance(user_id)
        if bet > balance:
            return await message.answer("Недостаточно средств.")

        ok, _ = await reserve_bet(user_id, bet)
        if not ok:
            return await message.answer("Недостаточно средств.")

        # Генерируем мины на каждом этаже
        bombs = []
        for _ in range(9):
            row = [0] * 5
            for idx in random.sample(range(5), mines):
                row[idx] = 1
            bombs.append(row)

        gid = _new_gid("t")
        game = {
            "gid": gid,
            "uid": user_id,
            "bet": float(bet),
            "mines": mines,
            "level": 0,
            "bombs": bombs,
            "state": "playing"
        }
        TOWER_GAMES[gid] = game
        await message.answer(tower_text(game), reply_markup=tower_kb(gid, 0), parse_mode="HTML")


@router.callback_query(F.data.startswith("tower:"))
async def tower_cb(query: CallbackQuery):
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer()
    _, gid, action = parts[:3]
    choice = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else None

    game = TOWER_GAMES.get(gid)
    if not game:
        return await query.answer("Игра завершена", show_alert=True)
    if int(game["uid"]) != query.from_user.id:
        return await query.answer("Это не твоя игра", show_alert=True)

    async with _game_lock(query.from_user.id):
        game = TOWER_GAMES.get(gid)
        if not game or game.get("state") != "playing":
            return await query.answer("Игра завершена", show_alert=True)

        bet = float(game["bet"])
        level = int(game["level"])

        if action == "cancel":
            if level > 0:
                return await query.answer("Нельзя отменить после хода", show_alert=True)
            await add_balance(query.from_user.id, bet)
            TOWER_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.ERROR} Игра отменена. Возврат: <b>{fmt_money(bet)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "collect":
            if level <= 0:
                return await query.answer("Пройди хотя бы 1 этаж", show_alert=True)
            mult = MULTIPLIERS[level - 1]
            payout = round(bet * mult, 4)
            balance = await finalize_bet(query.from_user.id, bet, payout, "tower", f"collect={level}")
            TOWER_GAMES.pop(gid, None)
            await query.message.edit_text(
                f"{E.SUCCESS} <b>Забрал!</b>\n"
                f"➖➖➖➖➖➖➖➖➖\n"
                f"🗼 Этажей: <b>{level}</b>\n"
                f"{E.RATES} Множитель: <b>x{mult}</b>\n"
                f"{E.WIN} Выигрыш: <b>{fmt_money(payout)}</b>\n"
                f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                parse_mode="HTML"
            )
            return await query.answer()

        if action == "pick":
            if choice is None or not (0 <= choice <= 4):
                return await query.answer("Неверный выбор", show_alert=True)
            if level >= 9:
                return await query.answer("Максимум этажей", show_alert=True)

            if game["bombs"][level][choice] == 1:
                # Попал на мину
                balance = await finalize_bet(query.from_user.id, bet, 0.0, "tower", f"bomb_lvl={level + 1}")
                TOWER_GAMES.pop(gid, None)
                await query.message.edit_text(
                    f"{E.LOSE} <b>Взрыв!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"💥 Попал на мину на этаже <b>{level + 1}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
                return await query.answer()

            # Успешно
            game["level"] = level + 1

            if game["level"] >= 9:
                # Прошёл все 9 этажей
                mult = MULTIPLIERS[8]
                payout = round(bet * mult, 4)
                balance = await finalize_bet(query.from_user.id, bet, payout, "tower", "top")
                TOWER_GAMES.pop(gid, None)
                await query.message.edit_text(
                    f"{E.BONUS} <b>ПОБЕДА! Башня пройдена!</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🗼 Все 9 этажей пройдены\n"
                    f"{E.RATES} Множитель: <b>x{mult}</b>\n"
                    f"💰 Выигрыш: <b>{fmt_money(payout)}</b>\n"
                    f"{E.BALANCE} Баланс: <b>{fmt_money(balance)}</b>",
                    parse_mode="HTML"
                )
                return await query.answer()

            TOWER_GAMES[gid] = game
            await query.message.edit_text(
                tower_text(game),
                reply_markup=tower_kb(gid, game["level"]),
                parse_mode="HTML"
            )
            return await query.answer()
