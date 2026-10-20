"""Схема базы данных и лёгкие миграции.

`CREATE TABLE IF NOT EXISTS` не дополняет уже существующие таблицы, а база
пользователя исторически создавалась более ранней версией схемы. Без
проверки колонок это тихо роняет запросы с «no such column» — поэтому здесь
схема сверяется и доводится до актуальной состояния на каждом старте.
"""

from __future__ import annotations

import logging

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

#: Требуемые колонки: таблица -> {колонка: SQL-тип}.
EXPECTED_COLUMNS: dict[str, dict[str, str]] = {
    "users": {"user_id": "INTEGER", "weight": "REAL", "weight_date": "TEXT"},
    "weight_entries": {"id": "INTEGER", "user_id": "INTEGER", "weight": "REAL", "date": "TEXT"},
    "meals": {"id": "INTEGER", "user_id": "INTEGER", "date": "TEXT", "calories": "INTEGER"},
    "exercises": {"id": "INTEGER", "user_id": "INTEGER", "date": "TEXT", "description": "TEXT"},
    "sleep": {
        "id": "INTEGER",
        "user_id": "INTEGER",
        "start_time": "TEXT",
        "end_time": "TEXT",
        "duration_min": "INTEGER",
    },
    "work_days": {
        "id": "INTEGER",
        "user_id": "INTEGER",
        "date": "TEXT",
        "duration_min": "INTEGER",
        "note": "TEXT",
        "created_at": "TEXT",
    },
    "settings": {"user_id": "INTEGER", "key": "TEXT", "value": "TEXT", "updated_at": "TEXT"},
}

CREATE_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        weight REAL,
        weight_date TEXT
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
    """
    CREATE TABLE IF NOT EXISTS work_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        duration_min INTEGER NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        value TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (user_id, key)
    )
    """,
)

#: Старая таблица сессий: учёт переведён на модель «одна строка на день».
LEGACY_WORK_TABLE = "work_sessions"

#: Исторические имена колонок веса -> современные.
LEGACY_USER_COLUMNS = {
    "current_weight": "weight",
    "current_weight_date": "weight_date",
}


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    async with conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ) as cursor:
        return await cursor.fetchone() is not None


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cursor:
        return {row[1] for row in await cursor.fetchall()}


async def _rename_legacy_user_columns(conn: aiosqlite.Connection) -> None:
    """`users.current_weight` -> `users.weight`, если база досталась старой."""
    columns = await _columns(conn, "users")

    for old, new in LEGACY_USER_COLUMNS.items():
        if old in columns and new not in columns:
            await conn.execute(f"ALTER TABLE users RENAME COLUMN {old} TO {new}")
            logger.info("колонка users.%s переименована в %s", old, new)


async def _migrate_work_table(conn: aiosqlite.Connection) -> None:
    """Переносит старые сессии в `work_days`: часы за день суммируются."""
    if not await _table_exists(conn, LEGACY_WORK_TABLE):
        return

    async with conn.execute(
        f"SELECT user_id, date, SUM(duration_min), MAX(note) FROM {LEGACY_WORK_TABLE} "
        f"WHERE duration_min IS NOT NULL GROUP BY user_id, date"
    ) as cursor:
        merged = await cursor.fetchall()

    await conn.execute(f"DROP TABLE {LEGACY_WORK_TABLE}")

    for user_id, date_str, minutes, note in merged:
        await conn.execute(
            "INSERT INTO work_days (user_id, date, duration_min, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, date) DO UPDATE SET duration_min = excluded.duration_min",
            (user_id, date_str, int(minutes), note),
        )

    logger.info(
        "таблица %s заменена на work_days (перенесено дней: %d)", LEGACY_WORK_TABLE, len(merged)
    )


async def _ensure_columns(conn: aiosqlite.Connection) -> None:
    """Дописывает отсутствующие колонки. Существующие данные не трогаются."""
    for table, expected in EXPECTED_COLUMNS.items():
        if not await _table_exists(conn, table):
            continue
        columns = await _columns(conn, table)
        for name, sql_type in expected.items():
            if name not in columns:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
                logger.info("в таблицу %s добавлена колонка %s", table, name)


async def _verify(conn: aiosqlite.Connection) -> None:
    """Финальная сверка: если чего-то не хватает — громко сигналим на старте."""
    problems: list[str] = []

    for table, expected in EXPECTED_COLUMNS.items():
        if not await _table_exists(conn, table):
            problems.append(f"нет таблицы {table}")
            continue
        missing = expected.keys() - await _columns(conn, table)
        if missing:
            problems.append(f"в {table} нет колонок {sorted(missing)}")

    if problems:
        logger.error("Схема БД не соответствует коду: %s", "; ".join(problems))
    else:
        logger.info("Схема БД проверена, расхождений нет")


async def init_db() -> None:
    """Создаёт таблицы, прогоняет миграции и сверяет схему."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(DB_PATH)
    try:
        await conn.execute("PRAGMA journal_mode=WAL")

        for statement in CREATE_TABLES:
            await conn.execute(statement)

        await _rename_legacy_user_columns(conn)
        await _migrate_work_table(conn)
        await _ensure_columns(conn)
        await conn.commit()

        await _verify(conn)
    finally:
        await conn.close()

    logger.info("База данных готова: %s", DB_PATH)
