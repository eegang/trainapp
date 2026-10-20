"""Работа с датами в формате YYYY-MM-DD и диапазоны (неделя с понедельника)."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta

DATE_FORMAT = "%Y-%m-%d"
#: 0 = понедельник ... 4 = пятница
WORKDAYS = range(5)


def _to_date(value: str) -> date:
    return datetime.strptime(value, DATE_FORMAT).date()


def today() -> str:
    """Сегодняшняя дата."""
    return date.today().strftime(DATE_FORMAT)


def yesterday() -> str:
    """Вчерашняя дата."""
    return (date.today() - timedelta(days=1)).strftime(DATE_FORMAT)


def shift_days(date_str: str, days: int) -> str:
    """Сдвигает дату YYYY-MM-DD на N дней."""
    return (_to_date(date_str) + timedelta(days=days)).strftime(DATE_FORMAT)


def human_date(date_str: str) -> str:
    """Человекочитаемая дата: 20.10.2026."""
    try:
        return _to_date(date_str).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(date_str)


def human_range(start: str, end: str) -> str:
    """Диапазон дат: 19.10 – 25.10."""
    try:
        s, e = _to_date(start), _to_date(end)
    except (TypeError, ValueError):
        return f"{start} – {end}"
    if s.month == e.month and s.year == e.year:
        return f"{s.day:02d}.{s.month:02d} – {e.day:02d}.{e.month:02d}"
    return f"{s.strftime('%d.%m.%Y')} – {e.strftime('%d.%m.%Y')}"


def month_label(date_str: str) -> str:
    """Название месяца и года в именительном падеже: «октябрь 2026»."""
    months = [
        "январь", "февраль", "март", "апрель", "май", "июнь",
        "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    ]
    d = _to_date(date_str)
    return f"{months[d.month - 1]} {d.year}"


def week_range(as_of: str | None = None) -> tuple[str, str]:
    """Границы недели (понедельник – воскресенье)."""
    day = _to_date(as_of) if as_of else date.today()
    monday = day - timedelta(days=day.weekday())
    return monday.strftime(DATE_FORMAT), (monday + timedelta(days=6)).strftime(DATE_FORMAT)


def month_range(as_of: str | None = None) -> tuple[str, str]:
    """Границы календарного месяца."""
    day = _to_date(as_of) if as_of else date.today()
    last = calendar.monthrange(day.year, day.month)[1]
    return (
        date(day.year, day.month, 1).strftime(DATE_FORMAT),
        date(day.year, day.month, last).strftime(DATE_FORMAT),
    )


def working_days_between(start: str, end: str) -> int:
    """Сколько рабочих дней (пн–пт) попадает в диапазон, включительно."""
    current, last = _to_date(start), _to_date(end)
    count = 0
    while current <= last:
        if current.weekday() in WORKDAYS:
            count += 1
        current += timedelta(days=1)
    return count


def is_valid_date(date_str: str) -> bool:
    """Проверяет формат YYYY-MM-DD."""
    try:
        _to_date(date_str)
    except (TypeError, ValueError):
        return False
    return True


_DATE_PATTERN = re.compile(r"^(\d{1,2})[./ ](\d{1,2})(?:[./ ](\d{2,4}))?$")
_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _make_date(year: int, month: int, day: int) -> date | None:
    """Дата или None, если такого дня не бывает (31.02, 29.02 не в високосный)."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_user_date(raw: str | None) -> str | None:
    """Понимает то, что человек пишет от руки.

    «сегодня», «вчера», «20.10.2026», «20.10», «2026-10-20» -> YYYY-MM-DD.
    Если год не указан и дата оказалась в будущем, берётся прошлый год.
    """
    if not raw:
        return None

    text = raw.strip().lower()
    if text in {"сегодня", "today", "сегодняшний день"}:
        return today()
    if text in {"вчера", "yesterday"}:
        return yesterday()

    if _ISO_PATTERN.match(text):
        return text if is_valid_date(text) else None

    m = _DATE_PATTERN.match(text)
    if not m:
        return None

    day, month = int(m.group(1)), int(m.group(2))
    raw_year = m.group(3)
    if raw_year:
        year = int(raw_year)
        if year < 100:
            year += 2000
    else:
        year = date.today().year

    parsed = _make_date(year, month, day)
    if parsed is None:
        return None

    # Год не назван, а дата вышла в будущем — значит, имелся в виду прошлый год.
    if not raw_year and parsed > date.today():
        parsed = _make_date(year - 1, month, day) or parsed

    return parsed.strftime(DATE_FORMAT)
