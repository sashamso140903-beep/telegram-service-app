from __future__ import annotations

import asyncio
import html

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from .config import settings
from .db import init_db, list_orders, set_user_referrer, update_order_status, upsert_user
from .formatting import format_rub
from .statuses import STATUS_LABELS, VALID_STATUSES


def app_keyboard() -> InlineKeyboardMarkup:
    if not settings.web_app_url.startswith("https://"):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Открыть локально",
                        url=settings.web_app_url,
                    )
                ]
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть каталог",
                    web_app=WebAppInfo(url=settings.web_app_url),
                )
            ]
        ]
    )


async def start(message: Message, command: CommandObject) -> None:
    if message.from_user:
        upsert_user(telegram_user_payload(message))

    referral_saved = False
    if message.from_user and command.args and command.args.startswith("ref_"):
        referrer_id = parse_referrer_id(command.args)
        if referrer_id:
            referral_saved = set_user_referrer(message.from_user.id, referrer_id)

    text = "Выберите услугу, оставьте комментарий к заказу, а оплату согласуем после заявки."
    if referral_saved:
        text += "\n\nРеферальная скидка 10% применится к заказу."
    if not settings.web_app_url.startswith("https://"):
        text += "\n\nСейчас стоит локальный адрес. Для открытия Mini App внутри Telegram нужен публичный HTTPS URL."
    await message.answer(text, reply_markup=app_keyboard())


async def referral(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить ваш Telegram ID.")
        return

    upsert_user(telegram_user_payload(message))
    username = settings.telegram_bot_username
    if not username:
        bot = Bot(token=settings.telegram_bot_token)
        try:
            me = await bot.get_me()
            username = me.username or ""
        finally:
            await bot.session.close()

    if not username:
        await message.answer("Не удалось сформировать ссылку: укажите TELEGRAM_BOT_USERNAME в .env.")
        return

    link = f"https://t.me/{username}?start=ref_{message.from_user.id}"
    await message.answer(
        "Ваша реферальная ссылка:\n"
        f"{link}\n\n"
        "Когда друг перейдет по ней и оформит заказ, у него будет скидка 10%."
    )


async def orders(message: Message) -> None:
    if not is_admin(message):
        await message.answer("Команда доступна только администратору.")
        return

    rows = list_orders(limit=10)
    if not rows:
        await message.answer("Заказов пока нет.")
        return

    lines = ["Последние заказы:"]
    for order in rows:
        lines.append(
            "\n"
            f"{order['order_number']}\n"
            f"{order['product_title']} - {format_order_price(order)}\n"
            f"Статус: {order['status']}, оплата: {order['payment_status']}\n"
            f"Комментарий: {order['comment'][:180]}"
        )
    await message.answer(html.escape("\n".join(lines)), parse_mode="HTML")


async def status(message: Message) -> None:
    if not is_admin(message):
        await message.answer("Команда доступна только администратору.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3 or parts[2] not in VALID_STATUSES:
        await message.answer("Формат: /status ORD-20260617-ABCD1234 in_progress")
        return

    order = update_order_status(parts[1], parts[2])
    if order is None:
        await message.answer("Заказ не найден.")
        return

    label = STATUS_LABELS.get(order["status"], order["status"])
    await notify_customer_status(order)
    await message.answer(f"Статус заказа {order['order_number']} изменен на «{label}».")


async def status_button(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    if not callback.from_user or callback.from_user.id != settings.admin_telegram_id:
        await callback.answer("Кнопка доступна только администратору.", show_alert=True)
        return

    data = callback.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "order_status" or parts[2] not in VALID_STATUSES:
        await callback.answer("Не удалось прочитать статус.", show_alert=True)
        return

    order_number = parts[1]
    new_status = parts[2]
    order = update_order_status(order_number, new_status)
    if order is None:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    label = STATUS_LABELS.get(new_status, new_status)
    await notify_customer_status(order)
    await callback.answer(f"Статус: {label}")
    await callback.message.answer(f"Заказ {order_number}: статус изменен на «{label}».")


async def notify_customer_status(order: dict) -> None:
    if not settings.telegram_bot_token:
        return

    label = STATUS_LABELS.get(order["status"], order["status"])
    text = (
        f"Статус вашего заказа {html.escape(order['order_number'])} изменен.\n\n"
        f"Услуга: {html.escape(order['product_title'])}\n"
        f"Новый статус: {html.escape(label)}"
    )

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(order["telegram_id"], text)
    except TelegramAPIError:
        return
    finally:
        await bot.session.close()


def telegram_user_payload(message: Message) -> dict:
    user = message.from_user
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
    }


def parse_referrer_id(value: str) -> int | None:
    try:
        return int(value.removeprefix("ref_"))
    except ValueError:
        return None


def format_order_price(order: dict) -> str:
    discount = int(order.get("discount_percent") or 0)
    final_price = int(order.get("final_price_rub") or order["price_rub"])
    if discount:
        return f"{format_rub(final_price)} (скидка {discount}%)"
    return format_rub(final_price)


def is_admin(message: Message) -> bool:
    return bool(settings.admin_telegram_id and message.from_user and message.from_user.id == settings.admin_telegram_id)


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in .env")

    init_db()
    bot = Bot(token=settings.telegram_bot_token)
    dp = create_dispatcher()
    await dp.start_polling(bot)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(start, CommandStart())
    dp.message.register(referral, Command("ref"))
    dp.message.register(orders, Command("orders"))
    dp.message.register(status, Command("status"))
    dp.callback_query.register(status_button, lambda callback: (callback.data or "").startswith("order_status:"))
    return dp


if __name__ == "__main__":
    asyncio.run(main())
