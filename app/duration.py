"""Разбор и форматирование длительностей.

Поддерживает то, что люди реально пишут в чат: «8», «8,5», «8:30»,
«8ч30», «480», а также заметку после значения: «8:30 закрывал год».
"""

from __future__ import annotations

import re
from datetime import datetime

#: Максимум, который можно записать за один день.
MAX_DAY_MINUTES = 24 * 60
#: Сессия, открытая дольше этого порога, почти наверняка забытая.
SUSPICIOUS_OPEN_MINUTES = 24 * 60

_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# 8:30
_HHMM = re.compile(r"^(\d{1,2})\s*:\s*(\d{1,2})(?!\d)")
# 8ч, 8 ч 30, 8 часов 30 минут, 8ч30м
_HOURS_WITH = re.compile(
    r"^(\d{1,2})\s*(?:час(?:ов|а)?|ч)(?:\s*(\d{1,2})\s*(?:мин(?:ут(?:ы|ов)?)?|м(?![а-яa-z\d]))?)?",
    re.IGNORECASE,
)
# 45мин, 45 мин, 90 минут
_MINUTES_ONLY = re.compile(r"^(\d{1,4})\s*(?:мин(?:ут(?:ы|ов)?)?|м(?![а-яa-z\d]))", re.IGNORECASE)
# 8, 8,5, 8.5, 480
_PLAIN = re.compile(r"^(\d{1,4})(?:[.,](\d{1,2}))?(?![\d.,])")

_SEPARATORS = " \t\r\n-–—:;,."


def _tail(text: str, end: int) -> str:
    """Остаток строки после распознанного значения."""
    return text[end:].strip(_SEPARATORS).strip()


def parse_duration(raw: str | None) -> tuple[int | None, str]:
    """Разбирает длительность и заметку.

    >>> parse_duration("8:30 закрыл год")
    (510, 'закрыл год')
    >>> parse_duration("8,5")
    (510, '')

    Возвращает ``(минуты, заметка)``. Минуты равны ``None``, если текст не
    похож на длительность.
    """
    if not raw:
        return None, ""

    text = raw.strip()

    m = _HHMM.match(text)
    if m:
        hours, minutes = int(m.group(1)), int(m.group(2))
        if hours > 24 or minutes > 59:
            return None, ""
        return hours * 60 + minutes, _tail(text, m.end())

    m = _HOURS_WITH.match(text)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2) or 0)
        if minutes > 59 or hours * 60 + minutes > MAX_DAY_MINUTES:
            return None, ""
        return hours * 60 + minutes, _tail(text, m.end())

    m = _MINUTES_ONLY.match(text)
    if m:
        minutes = int(m.group(1))
        if minutes > MAX_DAY_MINUTES:
            return None, ""
        return minutes, _tail(text, m.end())

    m = _PLAIN.match(text)
    if m:
        whole = int(m.group(1))
        fraction = m.group(2)
        if fraction is not None:
            # 8,5 и 8,75 — это доли часа
            minutes = round(whole * 60 + float("0." + fraction) * 60)
        elif whole <= 24:
            minutes = whole * 60
        else:
            minutes = whole  # 480 трактуем как минуты
        if not 0 < minutes <= MAX_DAY_MINUTES:
            return None, ""
        return minutes, _tail(text, m.end())

    return None, ""


def parse_hours(raw: str | None) -> float | None:
    """Часы как самостоятельная величина: 8, 8,5, 200, 8:30, 8ч30.

    В отличие от :func:`parse_duration`, голое число — это всегда **часы**,
    а не минуты: в ответ на вопрос «сколько часов норма» «30» означает
    30 часов, а не полчаса.
    """
    text = (raw or "").strip()
    if not text:
        return None

    normalized = text.replace(",", ".")
    if re.fullmatch(r"\d{1,4}(?:\.\d{1,2})?", normalized):
        return round(float(normalized), 2)

    minutes, note = parse_duration(text)
    if minutes is None or note:
        return None
    return round(minutes / 60, 2)


def minutes_since(timestamp: str | None) -> int | None:
    """Сколько минут прошло от метки времени «YYYY-MM-DD HH:MM:SS»."""
    if not timestamp:
        return None
    try:
        started = datetime.strptime(timestamp, _TS_FORMAT)
    except ValueError:
        return None
    return max(0, int((datetime.now() - started).total_seconds() // 60))


def format_minutes(total: int | None) -> str:
    """Минуты -> «8 ч 30 мин»."""
    if total is None:
        return "—"
    total = int(total)
    if total < 60:
        return f"{total} мин"
    hours, minutes = divmod(total, 60)
    return f"{hours} ч {minutes:02d} мин" if minutes else f"{hours} ч"


def format_short_hours(total_minutes: int | None) -> str:
    """Компактные часы для норм: 480 -> «8 ч», 510 -> «8,5 ч»."""
    if total_minutes is None:
        return "—"
    hours = total_minutes / 60
    text = f"{hours:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} ч"


def format_hours_value(hours: float | None) -> str:
    """То же самое, но для значения в часах (нормы, границы допусков)."""
    if hours is None:
        return "—"
    return format_short_hours(int(round(hours * 60)))


def percent(fact: int, target: int) -> int:
    """Доля выполнения, без деления на ноль."""
    if target <= 0:
        return 0
    return round(fact / target * 100)


def progress_bar(fact: int, target: int, width: int = 10) -> str:
    """▓▓▓▓░░░░░░ — наглядная шкала выполнения."""
    if target <= 0:
        return "░" * width
    filled = max(0, min(width, round(fact / target * width)))
    return "▓" * filled + "░" * (width - filled)
