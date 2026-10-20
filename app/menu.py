"""Главное меню: подписи, раскладка и связь кнопок с обработчиками.

Это единственное место, где описаны кнопки. Чтобы добавить раздел:
  1. добавить подпись сюда (константа + строка в LAYOUT + запись в HANDLERS);
  2. написать обработчик в app/handlers/ с фильтром F.text == <подпись>.
Навигация из середины ввода (app/navigation.py) подхватит кнопку сама.

Подписи выбраны короткими и с эмодзи, которые не требуют селектора
вариантов (VS16), чтобы Telegram не менял текст кнопки при возврате.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# ---------- Подписи главного меню ----------
WEIGHT = "📈 Вес"
MEALS = "🍎 Еда"
TRAINING = "💪 Тренировка"
SLEEP = "😴 Сон"
WORK = "🕒 Работа"
PAYOUT = "💰 Заработок"
TODAY = "📊 Сегодня"
REPORT = "📤 Отчёт за 30 дней"

# ---------- Выбор дня (вторая кнопочная клавиатура) ----------
DAY_TODAY = "Сегодня"
DAY_YESTERDAY = "Вчера"

#: Раскладка главного меню: строки кнопок. Частое — сверху.
LAYOUT: list[list[str]] = [
    [WEIGHT, MEALS],
    [TRAINING, SLEEP],
    [WORK, PAYOUT],
    [TODAY, REPORT],
]

#: Подпись кнопки -> обработчик вида "модуль:функция".
#: Строки, а не импорты: модули хендлеров импортируют меню, и наоборот.
HANDLERS: dict[str, str] = {
    WEIGHT: "app.handlers.weight:ask_weight",
    MEALS: "app.handlers.meals:ask_calories_date",
    TRAINING: "app.handlers.exercises:ask_exercise",
    SLEEP: "app.handlers.sleep:toggle_sleep",
    WORK: "app.handlers.work:ask_date",
    PAYOUT: "app.handlers.payout:show_payout",
    TODAY: "app.handlers.export:today_data",
    REPORT: "app.handlers.export:export_data",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню, оно же «домашний экран» после любого действия."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in LAYOUT],
        resize_keyboard=True,
        input_field_placeholder="Выбери, что записать",
    )


def date_keyboard() -> ReplyKeyboardMarkup:
    """Выбор дня: сегодня или вчера. Дату можно и набрать текстом."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=DAY_TODAY), KeyboardButton(text=DAY_YESTERDAY)]],
        resize_keyboard=True,
        input_field_placeholder="Сегодня, Вчера или дата 20.10",
    )
