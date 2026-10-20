"""Настройки пользователя поверх таблицы settings (ключ-значение).

Единый доступ к значениям по умолчанию, чтобы цифры не размножались по коду.
Новые настройки для будущих привычек добавляются сюда одной строкой.
"""

from __future__ import annotations

from db.repository import get_setting, set_setting

#: Норма рабочих часов в день.
WORK_HOURS_PER_DAY = "work_hours_per_day"
#: Норма рабочих часов в неделю.
WORK_HOURS_PER_WEEK = "work_hours_per_week"

_DEFAULTS = {
    WORK_HOURS_PER_DAY: 8.0,
    WORK_HOURS_PER_WEEK: 40.0,
}

_BOUNDS = {
    WORK_HOURS_PER_DAY: (0.5, 24.0),
    WORK_HOURS_PER_WEEK: (1.0, 168.0),
}


async def get_number(user_id: int, key: str) -> float:
    """Числовое значение настройки или значение по умолчанию."""
    raw = await get_setting(user_id, key)
    if raw is None:
        return _DEFAULTS[key]
    try:
        return float(raw)
    except ValueError:
        return _DEFAULTS[key]


async def set_number(user_id: int, key: str, value: float) -> tuple[bool, float]:
    """Сохраняет число в пределах допуска.

    Возвращает ``(принято, сохранённое_значение)``. Если значение вне
    диапазона — не сохраняет и возвращает ``False``.
    """
    low, high = _BOUNDS[key]
    if not low <= value <= high:
        return False, value
    await set_setting(user_id, key, str(value))
    return True, value


def default_of(key: str) -> float:
    """Значение по умолчанию (для текстов в подсказках)."""
    return _DEFAULTS[key]


def bounds_of(key: str) -> tuple[float, float]:
    """Допустимый диапазон настройки."""
    return _BOUNDS[key]


async def get_work_hours_per_day(user_id: int) -> float:
    return await get_number(user_id, WORK_HOURS_PER_DAY)


async def get_work_hours_per_week(user_id: int) -> float:
    return await get_number(user_id, WORK_HOURS_PER_WEEK)
