"""Состояния FSM диалога."""

from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    """Шаги диалогов."""

    weight = State()          # ввод веса
    meals_date = State()      # выбор дня для приёма пищи
    meals = State()           # ввод калорий
    exercises = State()       # ввод упражнений
