import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import router
from webhook import app


async def run_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    print("🚀 Stake Pay запущен")
    await dp.start_polling(bot)


async def run_webhook():
    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()

    await asyncio.gather(
        run_bot(),
        run_webhook(),
    )


if __name__ == "__main__":
    asyncio.run(main())
