"""Работа с датами в формате YYYY-MM-DD."""

from datetime import date, datetime, timedelta

DATE_FORMAT = "%Y-%m-%d"


def today() -> str:
    """Сегодняшняя дата."""
    return date.today().strftime(DATE_FORMAT)


def yesterday() -> str:
    """Вчерашняя дата."""
    return (date.today() - timedelta(days=1)).strftime(DATE_FORMAT)


def shift_days(date_str: str, days: int) -> str:
    """Сдвигает дату YYYY-MM-DD на N дней."""
    parsed = datetime.strptime(date_str, DATE_FORMAT).date()
    return (parsed + timedelta(days=days)).strftime(DATE_FORMAT)


def human_date(date_str: str) -> str:
    """Человекочитаемая дата: 20.10.2026."""
    try:
        return datetime.strptime(date_str, DATE_FORMAT).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(date_str)
