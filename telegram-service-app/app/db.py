from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .products import Product

REFERRAL_DISCOUNT_PERCENT = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                referrer_telegram_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                telegram_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                product_title TEXT NOT NULL,
                price_rub INTEGER NOT NULL,
                original_price_rub INTEGER,
                discount_percent INTEGER NOT NULL DEFAULT 0,
                final_price_rub INTEGER,
                referrer_telegram_id INTEGER,
                comment TEXT NOT NULL,
                status TEXT NOT NULL,
                payment_status TEXT NOT NULL,
                customer_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
            """
        )
        _ensure_column(conn, "users", "referrer_telegram_id", "referrer_telegram_id INTEGER")
        _ensure_column(conn, "orders", "original_price_rub", "original_price_rub INTEGER")
        _ensure_column(conn, "orders", "discount_percent", "discount_percent INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "orders", "final_price_rub", "final_price_rub INTEGER")
        _ensure_column(conn, "orders", "referrer_telegram_id", "referrer_telegram_id INTEGER")
        conn.execute("UPDATE orders SET original_price_rub = price_rub WHERE original_price_rub IS NULL")
        conn.execute("UPDATE orders SET final_price_rub = price_rub WHERE final_price_rub IS NULL")
        conn.commit()


def upsert_user(user: dict[str, Any]) -> None:
    now = _now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, language_code, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                updated_at = excluded.updated_at
            """,
            (
                user["id"],
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
                user.get("language_code"),
                now,
                now,
            ),
        )
        conn.commit()


def set_user_referrer(telegram_id: int, referrer_telegram_id: int) -> bool:
    if telegram_id == referrer_telegram_id:
        return False

    now = _now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, language_code,
                referrer_telegram_id, created_at, updated_at
            )
            VALUES (?, NULL, NULL, NULL, NULL, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                referrer_telegram_id = COALESCE(users.referrer_telegram_id, excluded.referrer_telegram_id),
                updated_at = excluded.updated_at
            """,
            (telegram_id, referrer_telegram_id, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT referrer_telegram_id FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    return bool(row and row["referrer_telegram_id"] == referrer_telegram_id)


def get_user_referrer(telegram_id: int) -> int | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT referrer_telegram_id FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    return int(row["referrer_telegram_id"]) if row and row["referrer_telegram_id"] else None


def create_order(user: dict[str, Any], product: Product, comment: str) -> dict[str, Any]:
    now = _now()
    order_number = f"ORD-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    referrer_telegram_id = get_user_referrer(user["id"])
    discount_percent = REFERRAL_DISCOUNT_PERCENT if referrer_telegram_id else 0
    final_price_rub = product.price_rub * (100 - discount_percent) // 100
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO orders (
                order_number, telegram_id, product_id, product_title, price_rub,
                original_price_rub, discount_percent, final_price_rub, referrer_telegram_id,
                comment, status, payment_status, customer_snapshot, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_number,
                user["id"],
                product.id,
                product.title,
                product.price_rub,
                product.price_rub,
                discount_percent,
                final_price_rub,
                referrer_telegram_id,
                comment,
                "new",
                "pending",
                json.dumps(user, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
    return get_order(order_number) or {}


def get_order(order_number: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_number = ?",
            (order_number,),
        ).fetchone()
    return dict(row) if row else None


def list_orders(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_user_orders(telegram_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def update_order_status(order_number: str, status: str) -> dict[str, Any] | None:
    now = _now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = ?
            WHERE order_number = ?
            """,
            (status, now, order_number),
        )
        conn.commit()
    return get_order(order_number)
