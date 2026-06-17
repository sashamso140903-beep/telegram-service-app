from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .statuses import ADMIN_STATUS_ACTIONS


def order_status_keyboard(order_number: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"order_status:{order_number}:{status}",
                )
            ]
            for status, label in ADMIN_STATUS_ACTIONS
        ]
    )
