"""Переключение разделов из середины ввода.

Пока бот ждёт число (вес, калории, часы, ставку), любое сообщение попадает в
хендлер состояния. Без этой проверки нажатие «💰 Заработок» привело бы к
ответу «не похоже на часы». Поэтому каждый хендлер ввода начинается с
``forward_to_menu``: если текст — подпись из реестра меню, состояние
сбрасывается и раздел открывается по-настоящему.
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from functools import lru_cache

from aiogram import types
from aiogram.fsm.context import FSMContext

from app.menu import HANDLERS

Handler = Callable[[types.Message, FSMContext], Awaitable[None]]


@lru_cache(maxsize=None)
def _resolve(label: str) -> Handler | None:
    """Импортирует обработчик по подписи кнопки (ленивый импорт — без циклов)."""
    target = HANDLERS.get(label)
    if target is None:
        return None
    module_name, func_name = target.split(":")
    return getattr(importlib.import_module(module_name), func_name)


async def forward_to_menu(message: types.Message, state: FSMContext) -> bool:
    """True, если текст оказался кнопкой меню и раздел уже открыт."""
    handler = _resolve((message.text or "").strip())
    if handler is None:
        return False

    await state.clear()
    await handler(message, state)
    return True
