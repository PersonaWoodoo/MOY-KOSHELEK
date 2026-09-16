import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import (
    init_db, get_pending_invoice, mark_invoice_paid,
    update_balance, save_invoice, get_user,
)
from handlers import router
from cryptobot_api import get_invoices

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_payments(bot: Bot):
    """Каждые 30 сек проверяем оплаченные инвойсы через CryptoBot."""
    while True:
        try:
            await asyncio.sleep(30)

            result = await get_invoices(status="paid")
            if not result.get("ok"):
                continue

            invoices = result.get("result", {}).get("items", [])
            for inv in invoices:
                inv_id = str(inv.get("invoice_id", ""))
                payload = inv.get("payload", "")
                amount = float(inv.get("amount", 0))
                asset = inv.get("asset", "USDT")

                # КРИТИЧЕСКАЯ ПРОВЕРКА: инвойс ДОЛЖЕН быть в БД
                existing = await get_pending_invoice(inv_id)
                if not existing:
                    # Инвойса нет в БД — это НЕ наш инвойс, скипаем
                    continue

                # Если статус paid/rejected/processing — скипаем
                if existing[4] in ("paid", "rejected", "processing"):
                    continue

                # Статус pending — зачисляем
                try:
                    user_id = int(payload)
                except (ValueError, TypeError):
                    # Если payload пустой, берём user_id из БД
                    user_id = existing[2]

                user = await get_user(user_id)
                if not user:
                    continue

                # Зачисляем
                await update_balance(user_id, amount)
                # Ставим paid
                await mark_invoice_paid(inv_id, "paid")
                logger.info(f"✅ Invoice {inv_id} paid: +{amount} {asset} → user {user_id}")

                try:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>Оплата получена!</b>\n\n"
                        f"💎 Зачислено: <code>{amount} {asset}</code>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"check_payments error: {e}")


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    print("🚀 Stake Pay запущен")

    await asyncio.gather(
        dp.start_polling(bot),
        check_payments(bot),
    )


if __name__ == "__main__":
    asyncio.run(main())
