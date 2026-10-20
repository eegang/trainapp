"""Смоук-тест бота: прогон через настоящий Dispatcher с фейковой HTTP-сессией.

Запускается без Telegram и без сети, но проверяет не только логику хендлеров,
а всю цепочку: матчинг фильтров, порядок роутеров, FSM-переходы и записи в БД.

    python tests/smoke.py

Каждый сценарий работает со своим user_id, поэтому состояния и строки в базе
сценариям не мешают.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_DB = Path(tempfile.gettempdir()) / "trainapp_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DB_PATH"] = str(TEST_DB)

import config                                                   # noqa: E402
import db.repository as repository                              # noqa: E402
import db.schema as schema_module                               # noqa: E402
from aiogram import types                                       # noqa: E402
from aiogram.client.session.base import BaseSession             # noqa: E402

from app import handlers as app_handlers                         # noqa: E402
from app import money                                           # noqa: E402
from app.bot import bot, dp                                      # noqa: E402
from app.dates import (                                          # noqa: E402
    month_range,
    parse_user_date,
    today,
    week_range,
    working_days_between,
    yesterday,
)
from app.duration import (                                       # noqa: E402
    format_hours,
    format_minutes,
    parse_duration,
    parse_hours,
    parse_hours_and_note,
)
from app.handlers.payout import month_title                      # noqa: E402
from app.report import build_report, build_today_summary         # noqa: E402
from db.schema import init_db                                    # noqa: E402

USER_SEQ = iter(range(900_000_000, 900_999_999))


class RecordingSession(BaseSession):
    """Пишет исходящие запросы в список вместо обращения к Telegram."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, str | None]] = []

    async def make_request(self, bot, method, timeout=None):  # noqa: ANN001, ANN401
        name = type(method).__name__
        self.sent.append((name, getattr(method, "text", None)))
        if name in {"SendMessage", "EditMessageText", "EditMessageReplyMarkup", "SendDocument"}:
            chat_id = int(getattr(method, "chat_id", 7))
            return types.Message(
                message_id=1, date=0, chat=types.Chat(id=chat_id, type="private")
            )
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, url, headers=None, timeout=None, chunk_size=65536, raise_for_status=True):  # noqa: D102, ANN001
        yield b""


class Harness:
    """Прогон обновлений через диспетчер и разбор ответов."""

    def __init__(self) -> None:
        self.session = RecordingSession()
        bot.session = self.session
        self._update_id = 0

    def mark(self) -> int:
        return len(self.session.sent)

    async def say(self, user_id: int, text: str) -> None:
        self._update_id += 1
        await dp.feed_update(
            bot,
            types.Update(
                update_id=self._update_id,
                message=types.Message(
                    message_id=self._update_id,
                    date=0,
                    text=text,
                    chat=types.Chat(id=user_id, type="private"),
                    from_user=types.User(id=user_id, is_bot=False, first_name="Тест"),
                ),
            ),
        )

    async def tap(self, user_id: int, data: str) -> None:
        self._update_id += 1
        message = types.Message(
            message_id=self._update_id,
            date=0,
            text="…",
            chat=types.Chat(id=user_id, type="private"),
            from_user=types.User(id=user_id, is_bot=False, first_name="Тест"),
        )
        await dp.feed_update(
            bot,
            types.Update(
                update_id=self._update_id,
                callback_query=types.CallbackQuery(
                    id=str(self._update_id),
                    data=data,
                    chat_instance="ci",
                    message=message,
                    from_user=types.User(id=user_id, is_bot=False, first_name="Тест"),
                ),
            ),
        )

    def since(self, mark: int) -> list[str]:
        return [text for _, text in self.session.sent[mark:] if text is not None]

    def last(self, mark: int) -> str:
        texts = self.since(mark)
        return texts[-1] if texts else ""

    def names(self, mark: int) -> list[str]:
        return [name for name, _ in self.session.sent[mark:]]


def db_all(sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(TEST_DB)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def db_one(sql: str, params: tuple = ()):  # noqa: ANN201
    rows = db_all(sql, params)
    return rows[0] if rows else None


def db_write(sql: str, params: tuple = ()) -> None:
    """Прямая запись в тестовую базу (для подготовки данных)."""
    conn = sqlite3.connect(TEST_DB)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def db_count(sql: str, params: tuple = ()) -> int:
    row = db_one(sql, params)
    return int(row[0]) if row else 0


# ---------- отчёт о результатах ----------

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, condition, detail))
    if not condition:
        print(f"FAIL  {name}  {detail}")


async def test_parsers() -> None:
    """Юниты на разбор строк, даты и деньги."""
    print("\n— парсеры, даты, деньги")

    duration_cases = [
        ("8", (480, "")),
        ("8,5", (510, "")),
        ("8.75", (525, "")),
        ("8:30", (510, "")),
        ("8ч", (480, "")),
        ("8 часов 30", (510, "")),
        ("8ч30м", (510, "")),
        ("45мин", (45, "")),
        ("480", (480, "")),
        ("8:30 закрывал год", (510, "закрывал год")),
        ("abc", (None, "")),
        ("1441", (None, "")),
        ("25:00", (None, "")),
    ]
    for text, expected in duration_cases:
        got = parse_duration(text)
        check(f"parse_duration({text!r})", got == expected, str(got))

    # часы: голое число — это ВСЕГДА часы, а не минуты
    hours_cases = [
        ("8", (8.0, "")),
        ("8,5", (8.5, "")),
        ("30", (30.0, "")),
        ("8:30", (8.5, "")),
        ("8ч30", (8.5, "")),
        ("480мин", (8.0, "")),
        ("8 закрыл год", (8.0, "закрыл год")),
        ("8:30 закрывал год", (8.5, "закрывал год")),
        ("abc", (None, "")),
        ("", (None, "")),
        ("15.10.2026", (None, "")),
    ]
    for text, expected in hours_cases:
        got = parse_hours_and_note(text)
        check(f"parse_hours_and_note({text!r})", got == expected, str(got))

    check("parse_hours('8ч30')", parse_hours("8ч30") == 8.5, str(parse_hours("8ч30")))
    check("parse_hours с заметкой отклонён", parse_hours("8 30") is None, str(parse_hours("8 30")))
    check("format_minutes", [format_minutes(m) for m in (0, 45, 480, 510)]
          == ["0 мин", "45 мин", "8 ч", "8 ч 30 мин"])
    check("format_hours", format_hours(8.5) == "8,5 ч", format_hours(8.5))

    money_cases = [(75825.0, "75 825"), (1234.5, "1 234,5"), (0.01, "0,01"),
                   (10000000, "10 000 000"), (25.5, "25,5"), (None, "—")]
    for value, expected in money_cases:
        check(f"format_money({value})", money.format_money(value) == expected,
              money.format_money(value))

    check("parse_rate('850')", money.parse_rate("850") == 850.0, str(money.parse_rate("850")))
    check("parse_rate('850,5')", money.parse_rate("850,5") == 850.5, str(money.parse_rate("850,5")))
    check("parse_rate('0') отклонён", money.parse_rate("0") is None)
    check("parse_rate('abc') отклонён", money.parse_rate("abc") is None)
    check("earnings", money.earnings(8.5, 850) == 7225.0, str(money.earnings(8.5, 850)))
    check("earnings без ставки", money.earnings(8.5, None) is None)

    check("today", parse_user_date("сегодня") == today())
    check("вчера", parse_user_date("вчера") == yesterday())
    check("невалидная дата", parse_user_date("31.02") is None)
    check("недата", parse_user_date("абракадабра") is None)
    check("неделя с понедельника", week_range()[0] <= today() <= week_range()[1])
    check("рабочие дни месяца", working_days_between(*month_range()) >= 20)


async def test_legacy_flows(h: Harness) -> None:
    """Регрессия: вес, еда, упражнения, сон, экспорт не сломаны."""
    print("\n— существующие разделы (регрессия)")

    uid = next(USER_SEQ)
    mark = h.mark()
    await h.say(uid, "/start")
    check("старт: меню показана", "Выберите действие" in h.last(mark), h.last(mark))

    mark = h.mark()
    await h.say(uid, "Вес на сегодня")
    await h.say(uid, "81,4")
    check("вес сохранён в users.weight",
          db_one("SELECT weight FROM users WHERE user_id=?", (uid,))[0] == 81.4)
    check("ответ про вес", "Вес 81.4 кг сохранён" in h.last(mark), h.last(mark))

    await h.say(uid, "Приемы пищи")
    await h.say(uid, "Вчера")
    await h.say(uid, "300")
    check("калории за вчера попали во вчера",
          db_one("SELECT calories FROM meals WHERE user_id=? AND date=?", (uid, yesterday()))[0] == 300)
    check("сегодня не тронуто", db_count(
        "SELECT COUNT(*) FROM meals WHERE user_id=? AND date=?", (uid, today())
    ) == 0)

    await h.say(uid, "Показатели упражнений")
    await h.say(uid, "грудь 10x3")
    check("упражнение сохранено",
          db_one("SELECT description FROM exercises WHERE user_id=?", (uid,))[0] == "грудь 10x3")

    await h.say(uid, "Я сплю")
    check("сон открыт", db_count(
        "SELECT COUNT(*) FROM sleep WHERE user_id=? AND end_time IS NULL", (uid,)
    ) == 1)
    await h.say(uid, "Я проснулся")
    check("сон закрыт", db_one("SELECT duration_min FROM sleep WHERE user_id=?", (uid,))[0] is not None)

    mark = h.mark()
    await h.say(uid, "Выгрузить данные за 30 дней")
    check("файл отчёта отправлен", "SendDocument" in h.names(mark), str(h.names(mark)))

    mark = h.mark()
    await h.say(uid, "Данные за сегодня")
    text = h.last(mark)
    check("сводка за сегодня работает", "Данные за" in text and "Вес: 81.4 кг" in text, text[:200])
    check("сводка содержит рабочее время", "Рабочее время: 0 мин" in text, text[:300])


async def test_work_entry(h: Harness) -> None:
    """Ручная запись часов: даты, форматы, замена, обнуление."""
    print("\n— рабочее время: запись часов")

    uid = next(USER_SEQ)

    mark = h.mark()
    await h.say(uid, "Рабочее время")
    check("сразу спрашивает день", "За какой день" in h.last(mark), h.last(mark))

    await h.say(uid, "Сегодня")
    mark = h.mark()
    await h.say(uid, "8:30 закрывал год")
    row = db_one("SELECT date, duration_min, note FROM work_days WHERE user_id=?", (uid,))
    check("часы записаны", row is not None and row[1] == 510, str(row))
    check("привязка к дате", row[0] == today(), str(row[0]))
    check("заметка сохранена", row[2] == "закрывал год", str(row[2]))
    text = h.last(mark)
    check("показан итог месяца", "Октябрь" in text or month_title(today()[:7]) in text, text)
    check("упоминание про ставку", "ставка" in text.lower(), text)

    # повторный ввод за тот же день заменяет значение, а не добавляет строку
    await h.say(uid, "Рабочее время")
    mark = h.mark()
    await h.say(uid, "Сегодня")
    check("предупреждает, что день уже заполнен",
          "уже записано 8 ч 30 мин" in h.last(mark) and "заменится" in h.last(mark), h.last(mark))

    mark = h.mark()
    await h.say(uid, "9")
    check("значение заменено",
          db_one("SELECT duration_min FROM work_days WHERE user_id=?", (uid,))[0] == 540)
    check("строка одна", db_count("SELECT COUNT(*) FROM work_days WHERE user_id=?", (uid,)) == 1)
    check("показано прежнее значение", "было 8 ч 30 мин" in h.last(mark), h.last(mark))
    check("заметка обновлена (пусто)",
          db_one("SELECT note FROM work_days WHERE user_id=?", (uid,))[0] is None)

    # дата с клавиатуры и за вчерашний день
    await h.say(uid, "Рабочее время")
    await h.say(uid, "Вчера")
    mark = h.mark()
    await h.say(uid, "7,5")
    check("запись за вчера",
          db_one("SELECT duration_min FROM work_days WHERE user_id=? AND date=?", (uid, yesterday()))[0] == 450)

    await h.say(uid, "Рабочее время")
    mark = h.mark()
    await h.say(uid, "15.10.2026")
    check("понимает дату", "15.10.2026" in h.last(mark), h.last(mark))
    await h.say(uid, "6")
    check("запись на введённую дату",
          db_count("SELECT COUNT(*) FROM work_days WHERE user_id=? AND date=?", (uid, "2026-10-15")) == 1)

    # обнуление дня
    await h.say(uid, "Рабочее время")
    await h.say(uid, "Сегодня")
    mark = h.mark()
    await h.say(uid, "0")
    check("0 убирает день из учёта",
          db_count("SELECT COUNT(*) FROM work_days WHERE user_id=? AND date=?", (uid, today())) == 0,
          h.last(mark))
    check("сообщение про удаление", "Убрал" in h.last(mark), h.last(mark))

    # ошибки ввода
    await h.say(uid, "Рабочее время")
    mark = h.mark()
    await h.say(uid, "31.02.2026")
    check("невалидная дата отклонена", "Не понял дату" in h.last(mark), h.last(mark))

    await h.say(uid, "Рабочее время")
    await h.say(uid, "Сегодня")
    mark = h.mark()
    await h.say(uid, "много работы")
    check("кривые часы -> переспрос", "Не похоже на часы" in h.last(mark), h.last(mark))

    mark = h.mark()
    await h.say(uid, "25")
    check("слишком много часов отклонено", "больше" in h.last(mark), h.last(mark))

    await h.say(uid, "8")
    check("после ошибок ввод продолжился",
          db_count("SELECT COUNT(*) FROM work_days WHERE user_id=? AND duration_min=480", (uid,)) == 1)


async def test_payout(h: Harness) -> None:
    """Ставка и расчёт за текущий и все предыдущие месяцы."""
    print("\n— заработок")

    uid = next(USER_SEQ)

    # ставка не задана -> бот просит её ввести
    mark = h.mark()
    await h.say(uid, "Заработок")
    check("без ставки просит ввести", "часовая ставка" in h.last(mark).lower(), h.last(mark))

    mark = h.mark()
    await h.say(uid, "abc")
    check("кривая ставка отклонена", "число за час" in h.last(mark), h.last(mark))

    mark = h.mark()
    await h.say(uid, "850")
    text = h.last(mark)
    check("ставка подтверждена в расчёте", "Ставка: 850 за час" in text, text)
    check("пустая база объясняется", "Записей пока нет" in text, text)
    check("ставка сохранена",
          float(db_one("SELECT value FROM settings WHERE user_id=? AND key='hourly_rate'", (uid,))[0]) == 850.0)

    # только прошлый месяц -> текущий помечен пустым
    db_write("INSERT INTO work_days (user_id, date, duration_min) VALUES (?, '2026-09-15', 480)", (uid,))
    db_write("INSERT INTO work_days (user_id, date, duration_min) VALUES (?, '2026-09-16', 240)", (uid,))

    mark = h.mark()
    await h.say(uid, "Заработок")
    text = h.last(mark)
    check("пустой текущий месяц помечен", "пока пусто" in text, text)
    check("прошлый месяц в списке", "Сентябрь 2026 · 12 ч за 2 дн. = 10 200" in text, text)

    # добавляем текущий месяц
    db_write("INSERT INTO work_days (user_id, date, duration_min) VALUES (?, ?, 510)", (uid, today()))

    mark = h.mark()
    await h.say(uid, "Заработок")
    text = h.last(mark)
    print(text)
    print("-" * 40)

    check("текущий месяц посчитан", f"{month_title(today()[:7])} · сейчас · 8 ч 30 мин" in text, text)
    check("деньги за текущий месяц", "= 7 225" in text, text)
    check("итог за всё время", "Итого: 20 ч 30 мин · 3 дн. = 17 425" in text, text)
    check("средний день посчитан", "Средний день: 6 ч 50 мин" in text, text)

    # ставка меняется кнопкой под сообщением
    mark = h.mark()
    await h.tap(uid, "payout_rate")
    check("кнопка ставки спрашивает число", "часовая ставка" in h.last(mark).lower(), h.last(mark))

    mark = h.mark()
    await h.say(uid, "1000")
    text = h.last(mark)
    check("пересчёт по новой ставке", "Ставка: 1 000 за час" in text and "= 8 500" in text, text)

    await h.tap(uid, "payout_rate")
    mark = h.mark()
    await h.say(uid, "0")
    check("нулевая ставка отклонена", "число за час" in h.last(mark), h.last(mark))


async def test_navigation(h: Harness) -> None:
    """Кнопки разделов работают прямо во время ввода."""
    print("\n— навигация из середины ввода")

    uid = next(USER_SEQ)

    await h.say(uid, "Приемы пищи")
    mark = h.mark()
    await h.say(uid, "Рабочее время")
    check("из ввода калорий можно уйти в часы", "За какой день" in h.last(mark), h.last(mark))

    await h.say(uid, "Сегодня")
    mark = h.mark()
    await h.say(uid, "Заработок")
    check("из ввода часов можно уйти в расчёт",
          "ставка" in h.last(mark).lower() or "Заработок" in h.last(mark), h.last(mark))

    # ставка не задана -> мы в состоянии Work.rate; кнопка раздела уводит оттуда
    mark = h.mark()
    await h.say(uid, "Данные за сегодня")
    check("сводка доступна из ввода ставки", "Данные за" in h.last(mark), h.last(mark)[:120])

    mark = h.mark()
    await h.say(uid, "Рабочее время")
    await h.say(uid, "Сегодня")
    await h.say(uid, "5")
    check("запись после перехода работает", "5 ч" in h.last(mark), h.last(mark))

    mark = h.mark()
    await h.say(uid, "Вес на сегодня")
    check("кнопка веса работает из ввода часов", "Введите ваш вес" in h.last(mark), h.last(mark))


async def test_fallback(h: Harness) -> None:
    """Запасной хендлер и /cancel."""
    print("\n— fallback и cancel")

    uid = next(USER_SEQ)
    mark = h.mark()
    await h.say(uid, "просто так")
    check("непонятный текст -> подсказка", "Выберите действие" in h.last(mark), h.last(mark))

    await h.say(uid, "Рабочее время")
    mark = h.mark()
    await h.say(uid, "/cancel")
    check("/cancel сбрасывает ввод", "Отменено" in h.last(mark), h.last(mark))

    await h.say(uid, "Рабочее время")
    await h.say(uid, "Сегодня")
    mark = h.mark()
    await h.say(uid, "/cancel")
    check("/cancel работает на втором шаге", "Отменено" in h.last(mark), h.last(mark))

    mark = h.mark()
    await h.say(uid, "10")
    check("после /cancel число не записалось",
          db_count("SELECT COUNT(*) FROM work_days WHERE user_id=?", (uid,)) == 0)


async def test_report_building(h: Harness) -> None:
    """Отчёт и сводка включают часы и деньги."""
    print("\n— отчёт")

    uid = next(USER_SEQ)
    db_write("INSERT INTO work_days (user_id, date, duration_min, note) VALUES (?, ?, 510, 'год')", (uid, today()))
    db_write("INSERT INTO work_days (user_id, date, duration_min) VALUES (?, ?, 480)", (uid, yesterday()))
    db_write("INSERT INTO meals (user_id, date, calories) VALUES (?, ?, 1500)", (uid, today()))
    db_write("INSERT INTO users (user_id, weight, weight_date) VALUES (?, 80.5, ?)", (uid, today()))

    from db.repository import get_report_data

    data = await get_report_data(uid, days=30)
    report = build_report(data, days=30, hourly_rate=850.0)

    check("в отчёте есть секция работы", "[РАБОЧЕЕ ВРЕМЯ]" in report)
    check("в отчёте есть ставка", "Часовая ставка: 850" in report, report[:200])
    check("в отчёте есть вес", "Текущий вес: 80.5 кг" in report, report[:200])
    check("в отчёте есть сумма часов", "16 ч 30 мин" in report, report[report.find("[РАБОЧЕЕ") :][:200])
    check("в отчёте есть деньги", "14 025" in report, report[report.find("[РАБОЧЕЕ") :][:200])
    check("в отчёте есть заметка дня", "— год" in report)
    check("в отчёте есть промпт GPT", "ПРОМПТ ДЛЯ GPT" in report)

    summary = build_today_summary(
        weight=80.5, calories=1500, exercises=["жим"], is_sleeping=False,
        work_minutes=510, hourly_rate=850.0,
    )
    check("сводка содержит часы и деньги",
          "Рабочее время: 8 ч 30 мин = 7 225" in summary, summary)

    no_rate = build_today_summary(
        weight=None, calories=0, exercises=[], is_sleeping=False, work_minutes=510, hourly_rate=None
    )
    check("сводка без ставки — только часы", "Рабочее время: 8 ч 30 мин" in no_rate and "=" not in no_rate.split("Рабочее время")[1][:20], no_rate)


async def test_migration_from_legacy_db() -> None:
    """Самое важное: база, созданная старой версией схемы, должна дожилиться.

    Именно этот тест ловит «no such column», когда CREATE TABLE IF NOT EXISTS
    не дополняет существующую таблицу.
    """
    print("\n— миграция со старой схемы")

    legacy_db = Path(tempfile.gettempdir()) / "trainapp_legacy.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(legacy_db) + suffix).unlink(missing_ok=True)

    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, current_weight REAL, current_weight_date TEXT)"
    )
    conn.execute("INSERT INTO users VALUES (1, 88.5, '2026-10-01')")
    conn.execute(
        "CREATE TABLE meals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, calories INTEGER, UNIQUE(user_id, date))"
    )
    conn.execute("INSERT INTO meals (user_id, date, calories) VALUES (1, '2026-10-10', 2000)")
    conn.execute(
        "CREATE TABLE work_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
        "date TEXT NOT NULL, start_time TEXT, end_time TEXT, duration_min INTEGER, "
        "source TEXT NOT NULL DEFAULT 'timer', note TEXT, created_at TEXT)"
    )
    # два дня: один день из двух сессий (должен просуммироваться), второй — ручная запись
    conn.execute("INSERT INTO work_sessions (user_id, date, duration_min) VALUES (1, '2026-10-12', 300)")
    conn.execute("INSERT INTO work_sessions (user_id, date, duration_min) VALUES (1, '2026-10-12', 180)")
    conn.execute("INSERT INTO work_sessions (user_id, date, duration_min) VALUES (1, '2026-10-13', 480)")
    conn.execute("INSERT INTO work_sessions (user_id, date, start_time) VALUES (1, '2026-10-14', '2026-10-14 09:00:00')")
    conn.commit()
    conn.close()

    # временно перенаправляем слой доступа к данных на старую базу
    saved = (config.DB_PATH, schema_module.DB_PATH, repository.DB_PATH)
    try:
        config.DB_PATH = legacy_db
        schema_module.DB_PATH = legacy_db
        repository.DB_PATH = legacy_db

        await init_db()

        conn = sqlite3.connect(legacy_db)
        try:
            user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            weight_row = conn.execute("SELECT weight, weight_date FROM users WHERE user_id=1").fetchone()
            work_days = conn.execute("SELECT date, duration_min FROM work_days ORDER BY date").fetchall()
            meals_calories = conn.execute("SELECT calories FROM meals WHERE user_id=1").fetchone()[0]
        finally:
            conn.close()

        check("колонки веса переименованы", {"weight", "weight_date"} <= user_cols, str(sorted(user_cols)))
        check("вес сохранён", weight_row == (88.5, "2026-10-01"), str(weight_row))
        check("старая таблица сессий удалена", "work_sessions" not in tables, str(sorted(tables)))
        check("work_days создана", "work_days" in tables, str(sorted(tables)))
        check("сессии одного дня просуммированы",
              (work_days[0][0], work_days[0][1]) == ("2026-10-12", 480), str(work_days))
        check("все перенесённые дни на месте", len(work_days) == 2, str(work_days))
        check("еда не пострадала", meals_calories == 2000, str(meals_calories))

        # запросы кода не падают на дожилённой базе
        check("get_user_weight работает", await repository.get_user_weight(1) == 88.5)
        check("get_work_by_date работает", await repository.get_work_by_date(1, "2026-10-12") == 480)
        check("get_work_months работает",
              await repository.get_work_months(1) == [("2026-10", 960, 2)], str(await repository.get_work_months(1)))

        report = build_report(await repository.get_report_data(1, days=30), days=30, hourly_rate=None)
        check("отчёт на старой базе собирается", "[РАБОЧЕЕ ВРЕМЯ]" in report and "16 ч" in report,
              report[report.find("[РАБОЧЕЕ") :][:120])
    finally:
        config.DB_PATH, schema_module.DB_PATH, repository.DB_PATH = saved
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(legacy_db) + suffix)
            if path.exists():
                path.unlink(missing_ok=True)


async def main() -> int:
    logging.getLogger("aiogram").setLevel(logging.WARNING)

    await init_db()
    app_handlers.register(dp)

    h = Harness()

    await test_parsers()
    await test_legacy_flows(h)
    await test_work_entry(h)
    await test_payout(h)
    await test_navigation(h)
    await test_fallback(h)
    await test_report_building(h)
    await test_migration_from_legacy_db()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [item for item in RESULTS if not item[1]]

    print(f"\n{'=' * 46}")
    print(f"ИТОГО: {passed}/{len(RESULTS)} проверок пройдено")
    if failed:
        print("\nПРОВАЛЕНО:")
        for name, _, detail in failed:
            print(f"  • {name}\n      {detail[:200]}")
    print("=" * 46)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
