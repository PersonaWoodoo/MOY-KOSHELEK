import hashlib
import hmac
import json
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from config import CRYPTOBOT_API_KEY, BOT_TOKEN
from database import (
    update_balance, get_pending_invoice, mark_invoice_paid,
)
from aiogram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
bot = Bot(token=BOT_TOKEN)


def check_signature(body: bytes, signature: str) -> bool:
    secret = hashlib.sha256(CRYPTOBOT_API_KEY.encode()).digest()
    calculated = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated, signature or "")


@app.post("/webhook")
async def crypto_webhook(request: Request):
    raw = await request.body()
    signature = request.headers.get("crypto-pay-api-signature", "")

    if not check_signature(raw, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    update_type = data.get("update_type")
    if update_type != "invoice_paid":
        return JSONResponse({"ok": True})

    payload = data.get("payload", {})
    invoice_id = str(payload.get("invoice_id", ""))
    amount = float(payload.get("amount", 0))
    asset = payload.get("asset", "USDT")
    user_id_str = payload.get("payload", "")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid user_id in payload: {user_id_str}")
        return JSONResponse({"ok": True})

    invoice = await get_pending_invoice(invoice_id)
    if invoice and invoice[4] == "paid":
        logger.info(f"Invoice {invoice_id} already paid")
        return JSONResponse({"ok": True})

    await update_balance(user_id, amount)
    await mark_invoice_paid(invoice_id, "paid")

    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Оплата получена!</b>\n\n"
            f"💎 Зачислено: <code>{amount} {asset}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Can't notify user {user_id}: {e}")

    logger.info(f"Invoice {invoice_id} paid: +{amount} {asset} to user {user_id}")
    return JSONResponse({"ok": True})


@app.get("/")
async def root():
    return {"status": "ok", "service": "Stake Pay webhook"}
