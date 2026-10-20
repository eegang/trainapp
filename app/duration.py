"""Разбор и форматирование длительностей.

Два семейства функций:
  * :func:`parse_duration` — «сколько это минут» (голое число больше 24 —
    минуты: «480» = 8 ч);
  * :func:`parse_hours_and_note` — «сколько это часов» для ввода рабочих
    часов и ставки (голое число — всегда часы: «30» = 30 ч, а не полчаса).
"""

from __future__ import annotations

import re

#: Максимум часов, которые можно записать за один день.
MAX_DAY_HOURS = 24.0

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
# «8», «8,5», «8.25», «8 закрыл год»; после числа — конец строки или пробел,
# иначе «8:30» распалось бы на 8 часов и заметку «:30».
_HOURS_LEADING = re.compile(r"^(\d{1,4}(?:\.\d{1,2})?)(?:\s+(.*))?$", re.DOTALL)

_SEPARATORS = " \t\r\n-–—:;,."

#: Часы за день, которые можно записать (в минутах).
MAX_DAY_MINUTES = int(MAX_DAY_HOURS * 60)


def _tail(text: str, end: int) -> str:
    """Остаток строки после распознанного значения."""
    return text[end:].strip(_SEPARATORS).strip()


def parse_duration(raw: str | None) -> tuple[int | None, str]:
    """Разбирает длительность в минутах и заметку.

    >>> parse_duration("8:30 закрыл год")
    (510, 'закрыл год')

    Возвращает ``(минуты, заметка)``; минуты равны ``None``, если текст не
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
            minutes = round(whole * 60 + float("0." + fraction) * 60)
        elif whole <= 24:
            minutes = whole * 60
        else:
            minutes = whole
        if not 0 < minutes <= MAX_DAY_MINUTES:
            return None, ""
        return minutes, _tail(text, m.end())

    return None, ""


def parse_hours_and_note(raw: str | None) -> tuple[float | None, str]:
    """Разбирает часы и необязательную заметку: «8», «8,5», «8:30», «8ч30».

    Голое число трактуется как **часы** всегда: в ответ на вопрос «сколько
    часов» «30» означает 30 часов, а не полчаса.
    """
    if not raw:
        return None, ""

    text = raw.strip()
    if not text:
        return None, ""

    m = _HOURS_LEADING.match(text.replace(",", "."))
    if m:
        return float(m.group(1)), (m.group(2) or "").strip()

    minutes, note = parse_duration(text)
    if minutes is None:
        return None, ""
    return round(minutes / 60, 2), note


def parse_hours(raw: str | None) -> float | None:
    """Часы без примеси заметки. None, если текст не понят."""
    hours, note = parse_hours_and_note(raw)
    if hours is None or note:
        return None
    return hours


def format_minutes(total: int | None) -> str:
    """Минуты -> «8 ч 30 мин»."""
    if total is None:
        return "—"
    total = int(total)
    if total < 60:
        return f"{total} мин"
    hours, minutes = divmod(total, 60)
    return f"{hours} ч {minutes:02d} мин" if minutes else f"{hours} ч"


def _trim(value: float) -> str:
    """8.0 -> «8», 8.5 -> «8,5»."""
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def format_hours(total: float | None) -> str:
    """Часы -> «8 ч», «8,5 ч»."""
    if total is None:
        return "—"
    return f"{_trim(total)} ч"


def format_minutes_as_hours(total_minutes: int | None) -> str:
    """Минуты в часовом виде: 510 -> «8,5 ч»."""
    if total_minutes is None:
        return "—"
    return format_hours(total_minutes / 60)
