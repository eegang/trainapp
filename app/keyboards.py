"""Клавиатуры бота.

Тексты кнопок — константы: хендлеры матчатся по ним же, опечатка невозможна.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ---------- Тексты главного меню ----------
MAIN_MENU_TEXT = "Вес на сегодня"
MEALS_TEXT = "Приемы пищи"
EXERCISES_TEXT = "Показатели упражнений"
EXPORT_TEXT = "Выгрузить данные за 30 дней"
TODAY_TEXT = "Данные за сегодня"
SLEEP_TEXT = "Я сплю"
WAKE_TEXT = "Я проснулся"
WORK_TEXT = "Рабочее время"

# ---------- Тексты рабочего блока ----------
WORK_START_TEXT = "▶ Начать работу"
WORK_FINISH_TEXT = "■ Завершить работу"
WORK_MANUAL_TEXT = "Записать вручную"
WORK_STATS_TEXT = "Статистика"
WORK_DELETE_TEXT = "Удалить запись"
WORK_NORM_TEXT = "Норма часов"
WORK_BACK_TEXT = "Главное меню"

TODAY_BUTTON = "Сегодня"
YESTERDAY_BUTTON = "Вчера"


def main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_TEXT), KeyboardButton(text=MEALS_TEXT)],
            [KeyboardButton(text=EXERCISES_TEXT), KeyboardButton(text=WORK_TEXT)],
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=SLEEP_TEXT)],
            [KeyboardButton(text=EXPORT_TEXT)],
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


def work_keyboard(is_working: bool) -> ReplyKeyboardMarkup:
    """Меню блока «Рабочее время». Кнопка таймера зависит от статуса."""
    toggle = KeyboardButton(text=WORK_FINISH_TEXT if is_working else WORK_START_TEXT)
    return ReplyKeyboardMarkup(
        keyboard=[
            [toggle, KeyboardButton(text=WORK_STATS_TEXT)],
            [KeyboardButton(text=WORK_MANUAL_TEXT), KeyboardButton(text=WORK_DELETE_TEXT)],
            [KeyboardButton(text=WORK_NORM_TEXT), KeyboardButton(text=WORK_BACK_TEXT)],
        ],
        resize_keyboard=True,
    )


# ---------- Инлайн-клавиатуры (кнопки под сообщением) ----------

def work_stats_keyboard(period: str) -> InlineKeyboardMarkup:
    """Переключение периода статистики: день / неделя / месяц."""
    def mark(name: str) -> str:
        return f"● {name}" if period == name else f"○ {name}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=mark("day"), callback_data="work_p:day"),
                InlineKeyboardButton(text=mark("week"), callback_data="work_p:week"),
                InlineKeyboardButton(text=mark("month"), callback_data="work_p:month"),
            ]
        ]
    )


def work_delete_keyboard(entries: list[dict], formatter) -> InlineKeyboardMarkup:
    """Список записей для удаления: по одной кнопке на запись."""
    rows = [
        [InlineKeyboardButton(text=formatter(entry), callback_data=f"work_del:{entry['id']}")]
        for entry in entries
    ]
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="work_del:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def work_delete_confirm_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления — та же кнопка дважды опасна, поэтому спрашиваем."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data=f"work_del_yes:{entry_id}"),
                InlineKeyboardButton(text="Нет", callback_data="work_del_no"),
            ]
        ]
    )


def work_long_session_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Слишком длинная сессия: сохранить как есть или удалить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сохранить как есть", callback_data=f"work_long_save:{session_id}"),
                InlineKeyboardButton(text="Удалить сессию", callback_data=f"work_long_drop:{session_id}"),
            ]
        ]
    )
