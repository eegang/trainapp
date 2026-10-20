"""Клавиатуры бота.

Тексты кнопок — константы: хендлеры матчатся по ним же, опечатка невозможна.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ---------- Главное меню ----------
MAIN_MENU_TEXT = "Вес на сегодня"
MEALS_TEXT = "Приемы пищи"
EXERCISES_TEXT = "Показатели упражнений"
EXPORT_TEXT = "Выгрузить данные за 30 дней"
TODAY_TEXT = "Данные за сегодня"
SLEEP_TEXT = "Я сплю"
WAKE_TEXT = "Я проснулся"
WORK_TEXT = "Рабочее время"
PAYOUT_TEXT = "Заработок"

TODAY_BUTTON = "Сегодня"
YESTERDAY_BUTTON = "Вчера"

#: Колбэк кнопки «изменить ставку» в расчёте.
RATE_CALLBACK = "payout_rate"


def main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_TEXT), KeyboardButton(text=MEALS_TEXT)],
            [KeyboardButton(text=EXERCISES_TEXT), KeyboardButton(text=WORK_TEXT)],
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=SLEEP_TEXT)],
            [KeyboardButton(text=PAYOUT_TEXT), KeyboardButton(text=EXPORT_TEXT)],
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
    """Выбор дня: сегодня или вчера."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=TODAY_BUTTON), KeyboardButton(text=YESTERDAY_BUTTON)]],
        resize_keyboard=True,
    )


def payout_keyboard(rate: float | None) -> InlineKeyboardMarkup | None:
    """Кнопка изменения ставки под расчётом (ставкой управляем отсюда)."""
    label = f"Ставка: {rate:g} — изменить" if rate else "Указать часовую ставку"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=RATE_CALLBACK)]]
    )
