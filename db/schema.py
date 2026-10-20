"""Схема базы данных.

Схема не менялась по сравнению с исходной версией проекта, поэтому
существующий файл training_bot.db остаётся совместимым.
"""

from __future__ import annotations

import logging

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        current_weight REAL,
        current_weight_date TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS weight_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        weight REAL,
        date TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        calories INTEGER,
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sleep (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        duration_min INTEGER
    )
    """,
)


async def init_db() -> None:
    """Создаёт таблицы, если их ещё нет. Существующие данные не трогает."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(DB_PATH)
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        for statement in SCHEMA:
            await conn.execute(statement)
        await conn.commit()
    finally:
        await conn.close()

    logger.info("База данных готова: %s", DB_PATH)
