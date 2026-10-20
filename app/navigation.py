"""Переключение разделов из середины ввода.

Пока бот ждёт число (вес, калории, часы, ставку), любое сообщение попадает в
хендлер состояния. Без этой модули нажатие «Заработок» привело бы к ответу
«не похоже на часы». Поэтому каждый хендлер-ввод начинается с
``forward_to_menu``: если текст — кнопка раздела, состояние сбрасывается и
раздел открывается по-настоящему.
"""

from __future__ import annotations

import logging

from aiogram import types
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

_MENU: dict[str, object] | None = None


def _menu() -> dict[str, object]:
    """Строит таблицу «текст кнопки -> хендлер» лениво, чтобы не зациклить импорты."""
    global _MENU
    if _MENU is not None:
        return _MENU

    from app import keyboards as kb
    from app.handlers import exercises, export, meals, payout, sleep, weight, work

    _MENU = {
        kb.MAIN_MENU_TEXT: weight.ask_weight,
        kb.MEALS_TEXT: meals.ask_calories_date,
        kb.EXERCISES_TEXT: exercises.ask_exercise,
        kb.WORK_TEXT: work.ask_date,
        kb.PAYOUT_TEXT: payout.show_payout,
        kb.TODAY_TEXT: export.today_data,
        kb.SLEEP_TEXT: sleep.go_to_sleep,
        kb.WAKE_TEXT: sleep.wake_up,
        kb.EXPORT_TEXT: export.export_data,
    }
    return _MENU


async def forward_to_menu(message: types.Message, state: FSMContext) -> bool:
    """True, если текст оказался кнопкой раздела и раздел уже открыт."""
    text = (message.text or "").strip()
    handler = _menu().get(text)
    if handler is None:
        return False

    await state.clear()
    await handler(message, state)
    return True
