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
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_DB = Path(tempfile.gettempdir()) / "trainapp_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DB_PATH"] = str(TEST_DB)

from aiogram import types                                    # noqa: E402
from aiogram.client.session.base import BaseSession          # noqa: E402

from app import handlers as app_handlers                    # noqa: E402
from app.bot import bot, dp                                 # noqa: E402
from app.dates import (                                     # noqa: E402
    human_date,
    month_range,
    parse_user_date,
    today,
    week_range,
    working_days_between,
    yesterday,
)
from app.duration import (                                  # noqa: E402
    format_minutes,
    format_short_hours,
    parse_duration,
    parse_hours,
    percent,
    progress_bar,
)
from app.report import build_report, build_today_summary    # noqa: E402
from db.schema import init_db                                # noqa: E402

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

    def _mark(self) -> int:
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
        """Тексты ответов бота, начиная с метки."""
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


def db_one(sql: str, params: tuple = ()):  # noqa: ANN201
    rows = db_all(sql, params)
    return rows[0] if rows else None


# ---------- отчёт о результатах ----------

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, condition, detail))
    if not condition:
        print(f"FAIL  {name}  {detail}")


async def unit_tests() -> None:
    """Юниты на разбор строк и арифметику периодов."""
    print("\n— парсеры и даты")

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
        check(f"parse_duration({text!r})", parse_duration(text) == expected, str(parse_duration(text)))

    check("parse_hours('8ч30')", parse_hours("8ч30") == 8.5, str(parse_hours("8ч30")))
    check("parse_hours с заметкой отклонён", parse_hours("8 30") is None, str(parse_hours("8 30")))
    # голое число в вопросе про норму — это часы, а не минуты
    check("parse_hours('30') = 30 часов", parse_hours("30") == 30.0, str(parse_hours("30")))
    check("parse_hours('7,5')", parse_hours("7,5") == 7.5, str(parse_hours("7,5")))
    check("parse_hours('480мин')", parse_hours("480мин") == 8.0, str(parse_hours("480мин")))
    check("parse_hours('15.10.2026') отклонён", parse_hours("15.10.2026") is None, str(parse_hours("15.10.2026")))
    check("format_minutes", [format_minutes(m) for m in (0, 45, 480, 510)] == ["0 мин", "45 мин", "8 ч", "8 ч 30 мин"])
    check("format_short_hours", format_short_hours(510) == "8,5 ч", format_short_hours(510))
    check("percent от нуля", percent(100, 0) == 0)
    check("progress_bar", progress_bar(50, 100) == "▓▓▓▓▓░░░░░", progress_bar(50, 100))
    check("progress_bar перелёт", progress_bar(200, 100) == "▓▓▓▓▓▓▓▓▓▓", progress_bar(200, 100))

    check("today", parse_user_date("сегодня") == today())
    check("вчера", parse_user_date("вчера") == yesterday())
    check("дата без года", parse_user_date("20.10") == today() if date.today().day >= 20 else True)
    check("невалидная дата", parse_user_date("31.02") is None)
    check("недата", parse_user_date("абракадабра") is None)
    check("неделя с понедельника", week_range()[0] <= today() <= week_range()[1])
    check("рабочие дни месяца", working_days_between(*month_range()) >= 20)


async def test_legacy_flows(h: Harness) -> None:
    """Регрессия: вес, еда, упражнения, сон, экспорт не сломаны."""
    print("\n— существующие разделы (регрессия)")

    uid = next(USER_SEQ)
    mark = h._mark()
    await h.say(uid, "/start")
    check("старт: меню показана", "Выберите действие" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.say(uid, "Вес на сегодня")
    await h.say(uid, "81,4")
    check("вес сохранён", db_one("SELECT current_weight FROM users WHERE user_id=?", (uid,))[0] == 81.4)

    mark = h._mark()
    await h.say(uid, "Приемы пищи")
    await h.say(uid, "Вчера")
    await h.say(uid, "300")
    check("калории за вчера попали во вчера",
          db_one("SELECT calories FROM meals WHERE user_id=? AND date=?", (uid, yesterday()))[0] == 300)
    check("сегодня не тронуто", db_count(
        "SELECT COUNT(*) FROM meals WHERE user_id=? AND date=?", (uid, today())
    ) == 0)

    mark = h._mark()
    await h.say(uid, "Показатели упражнений")
    await h.say(uid, "грудь 10x3")
    check("упражнение сохранено",
          db_one("SELECT description FROM exercises WHERE user_id=?", (uid,))[0] == "грудь 10x3")

    await h.say(uid, "Я сплю")
    check("сон открыт", db_one("SELECT COUNT(*) FROM sleep WHERE user_id=? AND end_time IS NULL", (uid,))[0] == 1)
    await h.say(uid, "Я проснулся")
    check("сон закрыт", db_one("SELECT duration_min FROM sleep WHERE user_id=?", (uid,))[0] is not None)

    mark = h._mark()
    await h.say(uid, "Выгрузить данные за 30 дней")
    check("файл отчёта отправлен", "SendDocument" in h.names(mark), str(h.names(mark)))


async def test_work_timer(h: Harness) -> None:
    """Таймер рабочего времени."""
    print("\n— рабочее время: таймер")

    uid = next(USER_SEQ)
    mark = h._mark()
    await h.say(uid, "Рабочее время")
    check("меню открылось", "Рабочее время" in h.last(mark), h.last(mark))
    check("меню: сейчас не на работе", "не на работе" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.say(uid, "▶ Начать работу")
    check("сессия создана", db_one(
        "SELECT COUNT(*) FROM work_sessions WHERE user_id=? AND end_time IS NULL AND start_time IS NOT NULL", (uid,)
    )[0] == 1)

    mark = h._mark()
    await h.say(uid, "▶ Начать работу")
    check("двойной старт отклонён", "уже идёт" in h.last(mark), h.last(mark))
    check("вторая сессия не создана", db_one(
        "SELECT COUNT(*) FROM work_sessions WHERE user_id=?", (uid,)
    )[0] == 1)

    mark = h._mark()
    await h.say(uid, "■ Завершить работу")
    saved = db_one("SELECT duration_min, end_time FROM work_sessions WHERE user_id=?", (uid,))
    check("сессия закрыта", saved[1] is not None and saved[0] is not None, str(saved))
    check("итог показан", "Смена закрыта" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.say(uid, "■ Завершить работу")
    check("повторное завержение вежливое", "Нет активной сессии" in h.last(mark), h.last(mark))


async def test_work_long_session(h: Harness) -> None:
    """Забытая сессия: бот не должен молча записывать сутки."""
    print("\n— рабочее время: забытая сессия")

    uid = next(USER_SEQ)
    old = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")
    db_write(
        "INSERT INTO work_sessions (user_id, date, start_time, source) "
        "VALUES (?, date('now','localtime'), ?, 'timer')",
        (uid, old),
    )

    mark = h._mark()
    await h.say(uid, "Рабочее время")
    await h.say(uid, "■ Завершить работу")
    text = h.last(mark)
    check("длинная сессия требует подтверждения", "забыли" in text and "закрыть" in text, text)
    check("сессия НЕ закрыта заранее",
          db_count("SELECT COUNT(*) FROM work_sessions WHERE user_id=? AND end_time IS NULL", (uid,)) == 1)

    session_id = db_one("SELECT id FROM work_sessions WHERE user_id=?", (uid,))[0]

    await h.tap(uid, f"work_long_save:{session_id}")
    check("сохранено по подтверждению",
          db_one("SELECT end_time FROM work_sessions WHERE id=?", (session_id,))[0] is not None)

    # второй вариант: забытую сессию можно выбросить
    other = next(USER_SEQ)
    db_write(
        "INSERT INTO work_sessions (user_id, date, start_time, source) "
        "VALUES (?, date('now','localtime'), ?, 'timer')",
        (other, old),
    )
    drop_id = db_one("SELECT id FROM work_sessions WHERE user_id=?", (other,))[0]
    await h.say(other, "■ Завершить работу")
    await h.tap(other, f"work_long_drop:{drop_id}")
    check("забытую сессию можно удалить", db_count("SELECT COUNT(*) FROM work_sessions WHERE id=?", (drop_id,)) == 0)


async def test_work_manual(h: Harness) -> None:
    """Ручная запись: кнопки, дата с клавиатуры, заметка, ошибки."""
    print("\n— рабочее время: ручная запись")

    uid = next(USER_SEQ)
    mark = h._mark()
    await h.say(uid, "Записать вручную")
    check("спрашивает день", "За какой день" in h.last(mark), h.last(mark))

    await h.say(uid, "Сегодня")
    mark = h._mark()
    await h.say(uid, "8:30 закрывал год")
    row = db_one("SELECT date, duration_min, note, source FROM work_sessions WHERE user_id=?", (uid,))
    check("ручная запись сохранена", row is not None and row[1] == 510 and row[3] == "manual", str(row))
    check("заметка распознана", row[2] == "закрывал год", str(row[2]))
    check("привязка к сегодняшнему дню", row[0] == today(), str(row[0]))
    check("итог показан", "Записано" in h.last(mark), h.last(mark))

    await h.say(uid, "Записать вручную")
    await h.say(uid, "Вчера")
    await h.say(uid, "7")
    check("запись за вчера", db_one(
        "SELECT COUNT(*) FROM work_sessions WHERE user_id=? AND date=?", (uid, yesterday())
    )[0] == 1)

    await h.say(uid, "Записать вручную")
    mark = h._mark()
    await h.say(uid, "15.10.2026")
    check("понимает дату с клавиатуры", "15.10.2026" in h.last(mark), h.last(mark))
    await h.say(uid, "6")
    check("запись на введённую дату", db_one(
        "SELECT COUNT(*) FROM work_sessions WHERE user_id=? AND date=?", (uid, "2026-10-15")
    )[0] == 1)

    await h.say(uid, "Записать вручную")
    await h.say(uid, "Сегодня")
    before = db_count("SELECT COUNT(*) FROM work_sessions WHERE user_id=?", (uid,))
    mark = h._mark()
    await h.say(uid, "много работы")
    check("кривая длительность -> переспрос", "Не похоже на длительность" in h.last(mark), h.last(mark))

    # состояние не сброшено: следом можно дописать значение
    await h.say(uid, "6,5")
    check("после ошибки ввод продолжился",
          db_count("SELECT COUNT(*) FROM work_sessions WHERE user_id=? AND duration_min=390", (uid,)) == 1)
    check("ничего лишнего не записалось",
          db_count("SELECT COUNT(*) FROM work_sessions WHERE user_id=?", (uid,)) == before + 1)

    await h.say(uid, "Записать вручную")
    mark = h._mark()
    await h.say(uid, "31.02.2026")
    check("невалидная дата отклонена", "Не понял дату" in h.last(mark), h.last(mark))


async def test_work_stats(h: Harness) -> None:
    """Статистика и переключение периодов."""
    print("\n— рабочее время: статистика")

    uid = next(USER_SEQ)
    db_write(
        "INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 300, 'manual')", (uid, today())
    )
    db_write(
        "INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 480, 'manual')",
        (uid, week_range()[0]),
    )

    mark = h._mark()
    await h.say(uid, "Статистика")
    text = h.last(mark)
    check("статистика показалась", "Рабочее время" in text and "Неделя" in text, text[:80])
    check("прогресс-бар на месте", "▓" in text or "░" in text, text[:120])
    check("факт недели посчитан", "8 ч" in text, text)

    # переключение периода инлайн-кнопкой
    mark = h._mark()
    await h.tap(uid, "work_p:day")
    text = h.last(mark)
    check("переключение на день", "День" in text and human_date(today()) in text, text[:120])
    check("дневная разбивка с записями", "5 ч" in text, text)

    await h.tap(uid, "work_p:month")
    check("переключение на месяц", "Месяц" in h.last(mark), h.last(mark)[:120])


async def test_work_norm(h: Harness) -> None:
    """Настройка нормы часов."""
    print("\n— рабочее время: норма")

    uid = next(USER_SEQ)
    mark = h._mark()
    await h.say(uid, "Норма часов")
    check("спрашивает дневную норму", "часов в день" in h.last(mark), h.last(mark))

    await h.say(uid, "30")
    check("дневная норма вне диапазона отклонена", "разумных пределах" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.say(uid, "7,5")
    check("спрашивает недельную норму", "неделю" in h.last(mark), h.last(mark))

    await h.say(uid, "200")
    check("недельная норма вне диапазона отклонена", "в неделю" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.say(uid, "37,5")
    check("нормы сохранены", "Норма:" in h.last(mark), h.last(mark))
    saved_day = db_one("SELECT value FROM settings WHERE user_id=? AND key='work_hours_per_day'", (uid,))[0]
    saved_week = db_one("SELECT value FROM settings WHERE user_id=? AND key='work_hours_per_week'", (uid,))[0]
    check("дневная норма в базе", float(saved_day) == 7.5, str(saved_day))
    check("недельная норма в базе", float(saved_week) == 37.5, str(saved_week))

    # норма влияет на статистику
    db_write(
        "INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 450, 'manual')", (uid, today())
    )
    mark = h._mark()
    await h.say(uid, "Статистика")
    await h.tap(uid, "work_p:day")
    check("статистика учитывает новую норму", "7,5 ч" in h.last(mark), h.last(mark)[:200])


async def test_work_delete(h: Harness) -> None:
    """Удаление записи через инлайн-кнопки с подтверждением."""
    print("\n— рабочее время: удаление")

    uid = next(USER_SEQ)
    db_write(
        "INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 240, 'manual')", (uid, today())
    )
    entry_id = db_one("SELECT id FROM work_sessions WHERE user_id=?", (uid,))[0]

    mark = h._mark()
    await h.say(uid, "Удалить запись")
    check("список на удаление показан", "Какую запись удалить" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.tap(uid, f"work_del:{entry_id}")
    check("спрашивает подтверждение", "Удалить" in h.last(mark) and "240" not in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.tap(uid, "work_del_no")
    check("отмена работает", "Не трогаю" in h.last(mark), h.last(mark))
    check("после отмены запись цела", db_one("SELECT COUNT(*) FROM work_sessions WHERE id=?", (entry_id,))[0] == 1)

    await h.tap(uid, f"work_del:{entry_id}")
    mark = h._mark()
    await h.tap(uid, f"work_del_yes:{entry_id}")
    check("запись удалена", db_one("SELECT COUNT(*) FROM work_sessions WHERE id=?", (entry_id,))[0] == 0)

    # чужую запись удаление не зацепит: запрос фильтрует по user_id
    victim = next(USER_SEQ)
    db_write(
        "INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 60, 'manual')",
        (victim, today()),
    )
    victim_id = db_one("SELECT id FROM work_sessions WHERE user_id=?", (victim,))[0]
    await h.tap(uid, f"work_del_yes:{victim_id}")
    check("чужую запись не удаляет", db_count("SELECT COUNT(*) FROM work_sessions WHERE id=?", (victim_id,)) == 1)

    await h.say(uid, "Удалить запись")
    mark = h._mark()
    await h.tap(uid, "work_del:cancel")
    check("отмена списка", "Отменил" in h.last(mark), h.last(mark))


async def test_navigation(h: Harness) -> None:
    """Кнопки разделов работают прямо во время ввода."""
    print("\n— навигация из середины ввода")

    uid = next(USER_SEQ)
    await h.say(uid, "Приемы пищи")
    mark = h._mark()
    await h.say(uid, "Рабочее время")
    check("из ввода калорий можно уйти в работу", "Рабочее время" in h.last(mark), h.last(mark))

    mark = h._mark()
    await h.say(uid, "▶ Начать работу")
    check("таймер запустился после перехода", "поехали" in h.last(mark), h.last(mark))

    await h.say(uid, "Записать вручную")
    await h.say(uid, "Сегодня")
    mark = h._mark()
    await h.say(uid, "Данные за сегодня")
    check("сводка доступна из ввода длительности", "Данные за" in h.last(mark), h.last(mark)[:120])
    check("сводка содержит рабочее время", "Рабочее время" in h.last(mark), h.last(mark)[:200])

    mark = h._mark()
    await h.say(uid, "Главное меню")
    check("возврат в главное меню", "Выберите действие" in h.last(mark), h.last(mark))

    await h.say(uid, "Рабочее время")
    await h.say(uid, "▶ Начать работу")
    check("сессия живёт после выхода в меню",
          db_one("SELECT COUNT(*) FROM work_sessions WHERE user_id=? AND end_time IS NULL", (uid,))[0] == 1)
    await h.say(uid, "■ Завершить работу")


async def test_fallback(h: Harness) -> None:
    """Запасной хендлер и /cancel."""
    print("\n— fallback и cancel")

    uid = next(USER_SEQ)
    mark = h._mark()
    await h.say(uid, "просто так")
    check("непонятный текст -> подсказка", "Выберите действие" in h.last(mark), h.last(mark))

    await h.say(uid, "Вес на сегодня")
    mark = h._mark()
    await h.say(uid, "/cancel")
    check("/cancel сбрасывает ввод", "Отменено" in h.last(mark), h.last(mark))

    await h.say(uid, "Вес на сегодня")
    mark = h._mark()
    await h.say(uid, "Рабочее время")
    await h.say(uid, "7")
    check("случайное число после выхода из ввода не записалось в вес",
          db_one("SELECT current_weight FROM users WHERE user_id=?", (uid,)) is None)


async def test_report_building(h: Harness) -> None:
    """Отчёт и сводка включают рабочее время."""
    print("\n— отчёт")

    uid = next(USER_SEQ)
    db_write("INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 510, 'timer')", (uid, today()))
    db_write("INSERT INTO work_sessions (user_id, date, duration_min, source) VALUES (?, ?, 480, 'manual')", (uid, yesterday()))
    db_write(
        "INSERT INTO meals (user_id, date, calories) VALUES (?, ?, 1500)", (uid, today())
    )

    from db.repository import get_report_data

    data = await get_report_data(uid, days=30)
    report = build_report(data, days=30, work_hours_per_day=8.0)
    check("в отчёте есть секция работы", "[РАБОЧЕЕ ВРЕМЯ]" in report)
    check("в отчёте есть итог", "9 ч 30 мин" in report or "8 ч" in report, report[report.find("[РАБОЧЕЕ") :][:120])
    check("в отчёте есть промпт GPT", "ПРОМПТ ДЛЯ GPT" in report)
    check("в отчёте есть баланс работы", "нормы" in report and "%" in report)

    summary = build_today_summary(
        weight=80.0, calories=1500, exercises=["жим"], is_sleeping=False,
        work_minutes=510, work_hours_per_day=8.0, active_work_minutes=None,
    )
    check("сводка содержит рабочее время", "Рабочее время: 8 ч 30 мин из 8 ч" in summary, summary)

    running = build_today_summary(
        weight=None, calories=0, exercises=[], is_sleeping=False,
        work_minutes=0, work_hours_per_day=8.0, active_work_minutes=45,
    )
    check("сводка показывает активную сессию", "сессия идёт" in running, running)


async def main() -> int:
    logging.getLogger("aiogram").setLevel(logging.WARNING)

    await init_db()
    app_handlers.register(dp)

    h = Harness()

    await unit_tests()
    await test_legacy_flows(h)
    await test_work_timer(h)
    await test_work_long_session(h)
    await test_work_manual(h)
    await test_work_stats(h)
    await test_work_norm(h)
    await test_work_delete(h)
    await test_navigation(h)
    await test_fallback(h)
    await test_report_building(h)

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
