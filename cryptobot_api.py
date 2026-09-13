import aiohttp
from config import CRYPTOBOT_API_KEY, CRYPTOBOT_API_URL

HEADERS = {"Crypto-Pay-API-Token": CRYPTOBOT_API_KEY}


async def create_check(asset: str, amount: float, description: str = ""):
    payload = {
        "asset": asset,
        "amount": str(amount),
        "description": description or "Stake Pay Check",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CRYPTOBOT_API_URL}/createCheck", json=payload, headers=HEADERS) as resp:
            return await resp.json()


async def create_invoice(asset: str, amount: float, description: str = ""):
    payload = {
        "asset": asset,
        "amount": str(amount),
        "description": description or "Stake Pay Deposit",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CRYPTOBOT_API_URL}/createInvoice", json=payload, headers=HEADERS) as resp:
            return await resp.json()


async def get_balance():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRYPTOBOT_API_URL}/getBalance", headers=HEADERS) as resp:
            return await resp.json()


async def get_exchange_rate():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRYPTOBOT_API_URL}/getExchangeRates", headers=HEADERS) as resp:
            return await resp.json()


async def transfer(user_id: int, asset: str, amount: float, comment: str = ""):
    payload = {
        "user_id": user_id,
        "asset": asset,
        "amount": str(amount),
        "comment": comment,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CRYPTOBOT_API_URL}/transfer", json=payload, headers=HEADERS) as resp:
            return await resp.json()
