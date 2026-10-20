"""Подключение хендлеров к диспетчеру.

Порядок: команды и кнопки меню — раньше, диалоги-состояния — позже, запасной
хендлер последним. Хендлеры состояний к тому же начинают вызов с
``forward_to_menu``, поэтому кнопка раздела сработает из любого шага ввода.
"""

from aiogram import Dispatcher

from app.handlers import common, exercises, export, fallback, meals, payout, sleep, weight, work


def register(dp: Dispatcher) -> None:
    """Регистрирует все роутеры."""
    dp.include_router(common.router)
    dp.include_router(weight.router)
    dp.include_router(exercises.router)
    dp.include_router(sleep.router)
    dp.include_router(export.router)
    dp.include_router(payout.router)
    dp.include_router(work.router)
    dp.include_router(meals.router)
    dp.include_router(fallback.router)
