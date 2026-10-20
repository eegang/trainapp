"""Деньги: разбор ставки, расчёт по часам и форматирование сумм."""

from __future__ import annotations

import re

#: Ставка пишется простым числом: 850, 850,5, 1200.75
_RATE_PATTERN = re.compile(r"^\d{1,7}(?:\.\d{1,2})?$")


def parse_rate(raw: str | None) -> float | None:
    """Часовая ставка из простого числа. Всё остальное — None."""
    if not raw:
        return None
    text = raw.strip().replace(",", ".")
    if not _RATE_PATTERN.match(text):
        return None
    value = float(text)
    return value if value > 0 else None


def earnings(hours: float, rate: float | None) -> float | None:
    """Сумма за часы по ставке. None, если ставка ещё не задана."""
    if rate is None or not hours:
        return None
    return round(hours * rate, 2)


def minutes_to_hours(minutes: int) -> float:
    return minutes / 60


def format_money(amount: float | None) -> str:
    """75825.0 -> «75 825», 1234.56 -> «1 234,56»."""
    if amount is None:
        return "—"

    whole, fraction = f"{round(float(amount), 2):.2f}".split(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    fraction = fraction.rstrip("0")

    return f"{grouped},{fraction}" if fraction else grouped
