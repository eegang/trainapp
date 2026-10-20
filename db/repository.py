"""Запросы к базе данных.

Все функции асинхронные и работают поверх aiosqlite, чтобы не блокировать
event loop бота. Схема таблиц не менялась — совместимость с существующей
базой training_bot.db сохранена.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

import aiosqlite

from config import DB_PATH


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """Открывает соединение с БД и гарантированно закрывает его."""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        await conn.close()


# ---------- Пользователь и вес ----------

async def get_user_weight(user_id: int) -> float | None:
    """Текущий вес пользователя или None."""
    async with get_connection() as conn:
        async with conn.execute(
            "SELECT current_weight FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row["current_weight"] if row else None


async def set_user_weight(user_id: int, weight: float) -> None:
    """Обновляет текущий вес пользователя."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, current_weight, current_weight_date)
            VALUES (?, ?, date('now', 'localtime'))
            ON CONFLICT(user_id) DO UPDATE SET
                current_weight = excluded.current_weight,
                current_weight_date = excluded.current_weight_date
            """,
            (user_id, weight),
        )
        await conn.commit()


async def add_weight_entry(user_id: int, weight: float) -> None:
    """Добавляет запись в историю веса."""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO weight_entries (user_id, weight, date) "
            "VALUES (?, ?, date('now', 'localtime'))",
            (user_id, weight),
        )
        await conn.commit()


async def get_weight_history(user_id: int, limit: int = 7) -> list[tuple[float, str]]:
    """Последние записи веса: [(вес, дата), ...] от свежих к старым."""
    async with get_connection() as conn:
        async with conn.execute(
            "SELECT weight, date FROM weight_entries "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [(row["weight"], row["date"]) for row in rows]


# ---------- Приёмы пищи ----------

async def add_meal_calories(user_id: int, calories: int, date_str: str) -> None:
    """Прибавляет калории к дню date_str (YYYY-MM-DD)."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO meals (user_id, date, calories)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                calories = calories + excluded.calories
            """,
            (user_id, date_str, calories),
        )
        await conn.commit()


async def get_meals_calories(user_id: int, date_str: str) -> int:
    """Сумма калорий за конкретный день."""
    async with get_connection() as conn:
        async with conn.execute(
            "SELECT calories FROM meals WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        ) as cursor:
            row = await cursor.fetchone()
    return int(row["calories"]) if row else 0


# ---------- Упражнения ----------

async def add_exercise(user_id: int, description: str) -> None:
    """Сохраняет описание тренировки за сегодня."""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO exercises (user_id, date, description) "
            "VALUES (?, date('now', 'localtime'), ?)",
            (user_id, description),
        )
        await conn.commit()


async def get_exercises_for_date(user_id: int, date_str: str) -> list[str]:
    """Список упражнений за конкретный день."""
    async with get_connection() as conn:
        async with conn.execute(
            "SELECT description FROM exercises WHERE user_id = ? AND date = ? ORDER BY id",
            (user_id, date_str),
        ) as cursor:
            rows = await cursor.fetchall()
    return [row["description"] for row in rows]


# ---------- Сон ----------

async def start_sleep(user_id: int) -> int:
    """Открывает сеанс сна и возвращает его id."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO sleep (user_id, start_time) VALUES (?, ?)", (user_id, now)
        )
        await conn.commit()
        sleep_id = cursor.lastrowid
    return sleep_id


async def end_sleep(user_id: int) -> tuple[int | None, str | None]:
    """Закрывает последний открытый сеанс сна.

    Возвращает (длительность в минутах, время начала) либо (None, None),
    если открытого сеанса нет.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_connection() as conn:
        async with conn.execute(
            "SELECT id, start_time FROM sleep "
            "WHERE user_id = ? AND end_time IS NULL ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None, None

        sleep_id, start_time = row["id"], row["start_time"]
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        duration = int((end_dt - start_dt).total_seconds() // 60)

        await conn.execute(
            "UPDATE sleep SET end_time = ?, duration_min = ? WHERE id = ?",
            (now, duration, sleep_id),
        )
        await conn.commit()

    return duration, start_time


async def has_active_sleep(user_id: int) -> bool:
    """Есть ли незакрытый сеанс сна."""
    async with get_connection() as conn:
        async with conn.execute(
            "SELECT 1 FROM sleep WHERE user_id = ? AND end_time IS NULL LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return row is not None


# ---------- Сводные данные ----------

async def get_report_data(user_id: int, days: int = 30) -> dict:
    """Собирает все данные пользователя за последние N дней для отчёта."""
    date_from = _shift_days(datetime.now().strftime("%Y-%m-%d"), -days)

    async with get_connection() as conn:
        async with conn.execute(
            "SELECT current_weight, current_weight_date FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            weight_row = await cursor.fetchone()

        async with conn.execute(
            "SELECT weight, date FROM weight_entries "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, days),
        ) as cursor:
            weight_history = await cursor.fetchall()

        async with conn.execute(
            "SELECT date, calories FROM meals "
            "WHERE user_id = ? AND date >= ? ORDER BY date",
            (user_id, date_from),
        ) as cursor:
            meals = await cursor.fetchall()

        async with conn.execute(
            "SELECT date, description FROM exercises "
            "WHERE user_id = ? AND date >= ? ORDER BY date, id",
            (user_id, date_from),
        ) as cursor:
            exercises = await cursor.fetchall()

        async with conn.execute(
            "SELECT start_time, end_time, duration_min FROM sleep "
            "WHERE user_id = ? AND start_time >= ? ORDER BY start_time",
            (user_id, date_from),
        ) as cursor:
            sleeps = await cursor.fetchall()

    return {
        "current_weight": (
            (weight_row["current_weight"], weight_row["current_weight_date"])
            if weight_row
            else None
        ),
        "weight_history": [(row["weight"], row["date"]) for row in weight_history],
        "meals": [(row["date"], row["calories"]) for row in meals],
        "exercises": [(row["date"], row["description"]) for row in exercises],
        "sleeps": [
            (row["start_time"], row["end_time"], row["duration_min"]) for row in sleeps
        ],
    }


def _shift_days(date_str: str, days: int) -> str:
    """Сдвигает дату YYYY-MM-DD на N дней."""
    from datetime import date, timedelta

    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (parsed + timedelta(days=days)).strftime("%Y-%m-%d")
