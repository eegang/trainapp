"""Конфигурация приложения. Все секреты читаются из .env / переменных окружения."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# Токен бота от @BotFather. НЕ хранить в коде.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Путь к файлу SQLite-базы.
DB_PATH = Path(os.getenv("DB_PATH") or (BASE_DIR / "training_bot.db")).resolve()

# Уровень логирования: DEBUG / INFO / WARNING ...
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def validate() -> None:
    """Проверяет, что обязательные настройки заданы. Вызывается при старте."""
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не найден.\n"
            f"Создайте файл {BASE_DIR / '.env'} (скопируйте .env.example) "
            "и впишите токен от @BotFather."
        )
