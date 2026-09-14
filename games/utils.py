import asyncio
import uuid
from typing import Dict

from database import get_user, update_balance

_locks: Dict[int, asyncio.Lock] = {}


def fmt_money(amount) -> str:
    try:
        amount = float(amount)
    except Exception:
        amount = 0.0
    if amount == int(amount):
        return f"{int(amount)}"
    return f"{amount:.2f}"


def parse_bet(text: str) -> float:
    text = text.strip().lower().replace(",", ".").replace(" ", "")
    if text.endswith("к") or text.endswith("k"):
        return float(text[:-1]) * 1000
    if text.endswith("м") or text.endswith("m"):
        return float(text[:-1]) * 1000000
    return float(text)


def _game_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _locks:
        _locks[user_id] = asyncio.Lock()
    return _locks[user_id]


def _new_gid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:8]


async def get_balance(user_id: int) -> float:
    user = await get_user(user_id)
    return float(user[2]) if user else 0.0


async def get_user_balance(user_id: int) -> float:
    return await get_balance(user_id)


async def add_balance(user_id: int, amount: float) -> float:
    await update_balance(user_id, amount)
    return await get_balance(user_id)


async def update_balance_async(user_id: int, amount: float) -> float:
    await update_balance(user_id, amount)
    return await get_balance(user_id)


async def reserve_bet(user_id: int, amount: float):
    balance = await get_balance(user_id)
    if balance < amount:
        return False, balance
    await update_balance(user_id, -amount)
    new_balance = await get_balance(user_id)
    return True, new_balance


async def finalize_bet(user_id: int, bet: float, payout: float, game: str = "", detail: str = "") -> float:
    if payout > 0:
        await update_balance(user_id, payout)
    return await get_balance(user_id)
