"""Настройки пользователя поверх таблицы settings (ключ-значение).

Новая настройка добавляется одной константой — миграция схемы не нужна,
`db/schema.py` дописывает только колонки таблиц, а значения лежат в паре
ключ-значение.
"""

from __future__ import annotations

from db.repository import get_setting, set_setting

#: Часовая ставка, за которую считается заработок.
HOURLY_RATE = "hourly_rate"

#: Допустимые границы ставки (за час).
RATE_BOUNDS = (0.01, 10_000_000.0)


async def get_hourly_rate(user_id: int) -> float | None:
    """Ставка пользователя или None, если он её ещё не указал."""
    raw = await get_setting(user_id, HOURLY_RATE)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


async def set_hourly_rate(user_id: int, rate: float) -> tuple[bool, float]:
    """Сохраняет ставку в разумных границах.

    Возвращает ``(принято, значение)``: при выходе за границы — не сохраняет
    и возвращает ``False``, чтобы хендлер мог переспросить.
    """
    low, high = RATE_BOUNDS
    if not low <= rate <= high:
        return False, rate
    await set_setting(user_id, HOURLY_RATE, str(rate))
    return True, rate
