from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return int(value)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "").strip()
    telegram_webhook_secret: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "change-this-webhook-secret").strip()
    bot_mode: str = os.getenv("BOT_MODE", "polling").strip().lower()
    admin_telegram_id: int | None = _optional_int("ADMIN_TELEGRAM_ID")
    web_app_url: str = os.getenv("WEB_APP_URL", "http://127.0.0.1:8000").strip()
    admin_secret: str = os.getenv("ADMIN_SECRET", "change-this-secret").strip()
    database_path: Path = PROJECT_ROOT / Path(os.getenv("DATABASE_PATH", "data/app.sqlite3"))
    allow_dev_user: bool = _bool_env("ALLOW_DEV_USER", default=True)


settings = Settings()
