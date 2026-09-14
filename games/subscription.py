from aiogram import Bot
from aiogram.types import Message

from subscription import check_subscription
from keyboards import subscribe_menu
import emojis as E


async def require_subscriptions(message: Message, bot: Bot) -> bool:
    ok = await check_subscription(bot, message.from_user.id)
    if not ok:
        await message.answer(
            f"{E.ERROR} <b>Подпишись на канал, чтобы играть:</b>\n\n👉 https://t.me/stake_pay",
            parse_mode="HTML",
            reply_markup=subscribe_menu()
        )
    return ok
