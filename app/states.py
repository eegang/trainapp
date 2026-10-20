"""Состояния FSM диалога."""

from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    """Шаги диалогов общего меню."""

    weight = State()          # ввод веса
    meals_date = State()      # выбор дня для приёма пищи
    meals = State()           # ввод калорий
    exercises = State()       # ввод упражнений


class Work(StatesGroup):
    """Шаги блока рабочего времени."""

    manual_date = State()     # за какой день пишем часы
    manual_value = State()    # ввод количества часов
    rate = State()            # ввод часовой ставки
