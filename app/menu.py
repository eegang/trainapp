"""Меню бота: подписи, разделы и связь кнопок с обработчиками.

Структура:
  главное меню  ->  «📝 Записать»  или  «👀 Смотреть»  ->  действия раздела.

Это единственное место, где описаны кнопки. Чтобы добавить действие:
  1. подпись-константа здесь, строка в нужном разделе (RECORD_LAYOUT / VIEW_LAYOUT),
     запись в HANDLERS;
  2. обработчик в app/handlers/ с фильтром F.text == <подпись>.
Навигация из середины ввода (app/navigation.py) подхватит кнопку сама.

Подписи без селектора вариантов (VS16), чтобы Telegram не менял текст кнопки.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# ---------- Разделы главного меню ----------
RECORD = "📝 Записать"
VIEW = "👀 Смотреть"
BACK = "🔙 Назад"

# ---------- Действия раздела «Записать» ----------
WEIGHT = "📈 Вес"
MEALS = "🍎 Еда"
TRAINING = "💪 Тренировка"
SLEEP = "😴 Сон"
WORK = "🕒 Работа"

# ---------- Действия раздела «Смотреть» ----------
TODAY = "📊 Сегодня"
PAYOUT = "💰 Заработок"
REPORT = "📤 Отчёт за 30 дней"

# ---------- Выбор дня (клавиатура под вопросом «за какой день») ----------
DAY_TODAY = "Сегодня"
DAY_YESTERDAY = "Вчера"

#: Главное меню: всего два раздела.
MAIN_LAYOUT: list[list[str]] = [[RECORD, VIEW]]

#: Раздел «Записать»: то, что вводишь руками, частое — сверху.
RECORD_LAYOUT: list[list[str]] = [
    [WEIGHT, MEALS],
    [TRAINING, SLEEP],
    [WORK],
    [BACK],
]

#: Раздел «Смотреть»: сводки и выгрузки.
VIEW_LAYOUT: list[list[str]] = [
    [TODAY, PAYOUT],
    [REPORT],
    [BACK],
]

#: Какой раздел открывает какая раскладка.
SECTION_LAYOUTS: dict[str, list[list[str]]] = {
    RECORD: RECORD_LAYOUT,
    VIEW: VIEW_LAYOUT,
}

#: Подпись кнопки -> обработчик вида "модуль:функция".
#: Строки, а не импорты: модули хендлеров импортируют меню, и наоборот.
HANDLERS: dict[str, str] = {
    RECORD: "app.handlers.common:open_record",
    VIEW: "app.handlers.common:open_view",
    BACK: "app.handlers.common:go_back",
    WEIGHT: "app.handlers.weight:ask_weight",
    MEALS: "app.handlers.meals:ask_calories_date",
    TRAINING: "app.handlers.exercises:ask_exercise",
    SLEEP: "app.handlers.sleep:toggle_sleep",
    WORK: "app.handlers.work:ask_date",
    TODAY: "app.handlers.export:today_data",
    PAYOUT: "app.handlers.payout:show_payout",
    REPORT: "app.handlers.export:export_data",
}


def _keyboard(layout: list[list[str]], placeholder: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in layout],
        resize_keyboard=True,
        input_field_placeholder=placeholder,
    )


def main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню, оно же «домашний экран» после любого действия."""
    return _keyboard(MAIN_LAYOUT, "Что сделаем?")


def section_keyboard(section: str) -> ReplyKeyboardMarkup:
    """Меню раздела: «Записать» или «Смотреть»."""
    return _keyboard(SECTION_LAYOUTS[section], "Выбери действие")


def date_keyboard() -> ReplyKeyboardMarkup:
    """Выбор дня: сегодня или вчера. Дату можно и набрать текстом."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=DAY_TODAY), KeyboardButton(text=DAY_YESTERDAY)]],
        resize_keyboard=True,
        input_field_placeholder="Сегодня, Вчера или дата 20.10",
    )
