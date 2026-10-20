"""Состояния FSM диалога."""

from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    """Шаги диалогов."""

    weight = State()          # ввод веса
    meals_date = State()      # выбор дня для приёма пищи
    meals = State()           # ввод калорий
    exercises = State()       # ввод упражнений


class Work(StatesGroup):
    """Шаги блока «Рабочее время»."""

    manual_date = State()     # за какой день пишем
    manual_value = State()    # длительность + заметка
    norm_day = State()        # норма часов в день
    norm_week = State()       # норма часов в неделю
