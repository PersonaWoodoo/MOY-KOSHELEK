import aiohttp
from config import CRYPTOBOT_API_KEY, CRYPTOBOT_API_URL

HEADERS = {"Crypto-Pay-API-Token": CRYPTOBOT_API_KEY}


async def create_invoice(asset: str, amount: float, description: str = ""):
    payload = {
        "asset": asset,
        "amount": str(amount),
        "description": description or "Stake Pay Deposit",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CRYPTOBOT_API_URL}/createInvoice", json=payload, headers=HEADERS) as resp:
            return await resp.json()


async def get_exchange_rate():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRYPTOBOT_API_URL}/getExchangeRates", headers=HEADERS) as resp:
            return await resp.json()


async def transfer(user_id: int, asset: str, amount: float, spend_id: str, comment: str = ""):
    """
    Вывод на Telegram-пользователя через CryptoBot.
    user_id — Telegram ID получателя (юзер должен был запускать @CryptoBot).
    spend_id — уникальный ID транзакции (защита от повторов).
    """
    payload = {
        "user_id": user_id,
        "asset": asset,
        "amount": str(amount),
        "spend_id": spend_id,
        "comment": comment or "Stake Pay withdrawal",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CRYPTOBOT_API_URL}/transfer", json=payload, headers=HEADERS) as resp:
            return await resp.json()
