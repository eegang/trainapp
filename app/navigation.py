"""Переключение разделов из середины ввода.

Пока бот ждёт число (вес, калории, длительность), любое сообщение попадает в
хендлер состояния. Без этой модули нажатие «Статистика» привело бы к ответу
«не похоже на длительность». Поэтому каждый хендлер-ввод начинается с
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
    from app.handlers import exercises, export, meals, sleep, weight, work

    _MENU = {
        # Главное меню
        kb.MAIN_MENU_TEXT: weight.ask_weight,
        kb.MEALS_TEXT: meals.ask_calories_date,
        kb.EXERCISES_TEXT: exercises.ask_exercise,
        kb.WORK_TEXT: work.open_work_menu,
        kb.TODAY_TEXT: export.today_data,
        kb.SLEEP_TEXT: sleep.go_to_sleep,
        kb.WAKE_TEXT: sleep.wake_up,
        kb.EXPORT_TEXT: export.export_data,
        # Блок «Рабочее время»
        kb.WORK_START_TEXT: work.start_timer,
        kb.WORK_FINISH_TEXT: work.finish_timer,
        kb.WORK_MANUAL_TEXT: work.ask_manual_date,
        kb.WORK_STATS_TEXT: work.stats,
        kb.WORK_DELETE_TEXT: work.list_for_delete,
        kb.WORK_NORM_TEXT: work.ask_norm_day,
        kb.WORK_BACK_TEXT: work.back_to_main,
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
