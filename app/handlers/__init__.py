"""Подключение хендлеров к диспетчеру.

Порядок регистрации важен: сначала идут команды и кнопки главного меню,
затем диалоги, и только в самом конце — запасной хендлер.
"""

from aiogram import Dispatcher

from app.handlers import common, exercises, export, fallback, meals, sleep, weight


def register(dp: Dispatcher) -> None:
    """Регистрирует все роутеры в правильном порядке."""
    dp.include_router(common.router)
    dp.include_router(weight.router)
    dp.include_router(exercises.router)
    dp.include_router(sleep.router)
    dp.include_router(export.router)
    dp.include_router(meals.router)
    dp.include_router(fallback.router)
