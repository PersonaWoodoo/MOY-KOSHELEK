import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
CRYPTOBOT_API_KEY = os.getenv("CRYPTOBOT_API_KEY")
CRYPTOBOT_API_URL = os.getenv("CRYPTOBOT_API_URL", "https://pay.crypt.bot/api")
TON_WALLET = os.getenv("TON_WALLET")
MIN_CHECK_AMOUNT = float(os.getenv("MIN_CHECK_AMOUNT", "0.1"))
STAR_RATE = float(os.getenv("STAR_RATE", "1.35"))
CARD_NUMBER = os.getenv("CARD_NUMBER")
CARD_NAME = os.getenv("CARD_NAME")
