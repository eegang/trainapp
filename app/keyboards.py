"""Клавиатуры бота."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU_TEXT = "Вес на сегодня"
MEALS_TEXT = "Приемы пищи"
EXERCISES_TEXT = "Показатели упражнений"
EXPORT_TEXT = "Выгрузить данные за 30 дней"
TODAY_TEXT = "Данные за сегодня"
SLEEP_TEXT = "Я сплю"
WAKE_TEXT = "Я проснулся"

TODAY_BUTTON = "Сегодня"
YESTERDAY_BUTTON = "Вчера"


def main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_TEXT), KeyboardButton(text=MEALS_TEXT)],
            [KeyboardButton(text=EXERCISES_TEXT), KeyboardButton(text=EXPORT_TEXT)],
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=SLEEP_TEXT)],
        ],
        resize_keyboard=True,
    )


def sleep_keyboard() -> ReplyKeyboardMarkup:
    """Меню во время сна."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=WAKE_TEXT)]],
        resize_keyboard=True,
    )


def date_choice_keyboard() -> ReplyKeyboardMarkup:
    """Выбор дня для приёма пищи."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=TODAY_BUTTON), KeyboardButton(text=YESTERDAY_BUTTON)]],
        resize_keyboard=True,
    )
