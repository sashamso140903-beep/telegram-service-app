from __future__ import annotations

import hashlib
import hmac
import html
import json
import time
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qsl

from aiogram import Bot
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .bot import create_dispatcher
from .db import create_order, get_user_referrer, init_db, list_orders, list_user_orders, update_order_status, upsert_user
from .formatting import format_rub
from .keyboards import order_status_keyboard
from .products import get_product, list_products
from .statuses import STATUS_LABELS, VALID_STATUSES


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app = FastAPI(title="Telegram Service Mini App")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
bot: Bot | None = None
dispatcher = create_dispatcher()


class OrderCreate(BaseModel):
    product_id: str
    comment: str = Field(min_length=5, max_length=2000)
    init_data: str = ""


class OrderListRequest(BaseModel):
    init_data: str = ""


class StatusUpdate(BaseModel):
    status: str


@app.on_event("startup")
async def startup() -> None:
    global bot
    init_db()
    if settings.telegram_bot_token:
        bot = Bot(token=settings.telegram_bot_token)
    if bot and settings.bot_mode == "webhook":
        await bot.set_webhook(webhook_url())


@app.on_event("shutdown")
async def shutdown() -> None:
    if bot:
        await bot.session.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict[str, bool]:
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    if not bot:
        raise HTTPException(status_code=500, detail="Bot is not configured")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}


def webhook_url() -> str:
    base_url = settings.web_app_url.rstrip("/")
    return f"{base_url}/telegram/webhook/{settings.telegram_webhook_secret}"


@app.get("/api/products")
def products() -> dict[str, Any]:
    return {"products": list_products()}


@app.post("/api/referral/status")
def referral_status(payload: OrderListRequest) -> dict[str, Any]:
    user = parse_telegram_user(payload.init_data)
    referrer_id = get_user_referrer(user["id"])
    return {
        "has_discount": bool(referrer_id),
        "discount_percent": 10 if referrer_id else 0,
        "referrer_telegram_id": referrer_id,
    }


@app.post("/api/orders/my")
def my_orders(payload: OrderListRequest) -> dict[str, Any]:
    user = parse_telegram_user(payload.init_data)
    orders = list_user_orders(user["id"])
    return {"orders": [serialize_client_order(order) for order in orders]}


@app.post("/api/orders")
async def orders(payload: OrderCreate) -> dict[str, Any]:
    product = get_product(payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Service not found")

    user = parse_telegram_user(payload.init_data)
    upsert_user(user)
    order = create_order(user, product, payload.comment.strip())
    await notify_admin(order, user)
    return {"order": order}


@app.get("/api/admin/orders")
def admin_orders(x_admin_secret: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    require_admin_secret(x_admin_secret)
    return {"orders": list_orders()}


@app.patch("/api/admin/orders/{order_number}")
def admin_update_order(
    order_number: str,
    payload: StatusUpdate,
    x_admin_secret: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    require_admin_secret(x_admin_secret)
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status")
    order = update_order_status(order_number, payload.status)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order": order}


def require_admin_secret(secret: str | None) -> None:
    if not settings.admin_secret or secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")


def serialize_client_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_number": order["order_number"],
        "product_title": order["product_title"],
        "price_rub": order["price_rub"],
        "original_price_rub": order.get("original_price_rub") or order["price_rub"],
        "discount_percent": order.get("discount_percent") or 0,
        "final_price_rub": order.get("final_price_rub") or order["price_rub"],
        "comment": order["comment"],
        "status": order["status"],
        "status_label": STATUS_LABELS.get(order["status"], order["status"]),
        "payment_status": order["payment_status"],
        "created_at": order["created_at"],
        "updated_at": order["updated_at"],
    }


def customer_profile_html(user: dict[str, Any]) -> str:
    username = user.get("username")
    first_name = user.get("first_name")
    last_name = user.get("last_name")
    telegram_id = user.get("id")

    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    title = username or full_name or str(telegram_id)

    if username:
        url = f"https://t.me/{username}"
    else:
        url = f"tg://user?id={telegram_id}"

    return f'<a href="{html.escape(url)}">{html.escape(title)}</a>'


def parse_telegram_user(init_data: str) -> dict[str, Any]:
    if init_data:
        return validate_init_data(init_data)
    if settings.allow_dev_user:
        return {
            "id": 1,
            "first_name": "Demo",
            "last_name": "User",
            "username": "demo_user",
            "language_code": "ru",
        }
    raise HTTPException(status_code=401, detail="Telegram init data is required")


def validate_init_data(init_data: str) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=500, detail="Bot token is not configured")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing init data hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(
        b"WebAppData",
        settings.telegram_bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")

    auth_date = int(parsed.get("auth_date", "0"))
    if auth_date <= 0:
        raise HTTPException(status_code=401, detail="Telegram auth date is missing")
    if time.time() - auth_date > 60 * 60 * 24:
        raise HTTPException(status_code=401, detail="Telegram init data is expired")

    user_json = parsed.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="Telegram user is missing")

    user = json.loads(user_json)
    if "id" not in user:
        raise HTTPException(status_code=401, detail="Telegram user id is missing")
    return user


async def notify_admin(order: dict[str, Any], user: dict[str, Any]) -> None:
    if not settings.telegram_bot_token or not settings.admin_telegram_id:
        return

    customer = customer_profile_html(user)
    discount_percent = int(order.get("discount_percent") or 0)
    final_price = int(order.get("final_price_rub") or order["price_rub"])
    price_text = format_rub(order["price_rub"])
    if discount_percent:
        price_text = (
            f"{format_rub(final_price)} "
            f"<s>{format_rub(order['price_rub'])}</s> "
            f"(скидка {discount_percent}%)"
        )

    text = (
        "<b>Новый заказ</b>\n\n"
        f"<b>Номер:</b> {html.escape(order['order_number'])}\n"
        f"<b>Услуга:</b> {html.escape(order['product_title'])}\n"
        f"<b>Цена:</b> {price_text}\n"
        f"<b>Клиент:</b> {customer}\n"
        f"<b>Telegram ID:</b> {html.escape(str(user.get('id')))}\n"
        f"{referrer_line_html(order)}"
        f"<b>Комментарий:</b>\n{html.escape(order['comment'])}\n\n"
        "Оплата: ожидает согласования"
    )

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(
            settings.admin_telegram_id,
            text,
            parse_mode="HTML",
            reply_markup=order_status_keyboard(order["order_number"]),
        )
    finally:
        await bot.session.close()


def referrer_line_html(order: dict[str, Any]) -> str:
    referrer_id = order.get("referrer_telegram_id")
    if not referrer_id:
        return ""
    return f'<b>Реферал от:</b> <a href="tg://user?id={referrer_id}">{referrer_id}</a>\n'
