"""Слой доступа к данным: схема и запросы к SQLite (aiosqlite)."""

from db.schema import init_db
from db.repository import (
    add_exercise,
    add_meal_calories,
    add_weight_entry,
    end_sleep,
    get_exercises_for_date,
    get_meals_calories,
    get_report_data,
    get_user_weight,
    get_weight_history,
    has_active_sleep,
    set_user_weight,
    start_sleep,
)

__all__ = [
    "init_db",
    "add_exercise",
    "add_meal_calories",
    "add_weight_entry",
    "end_sleep",
    "get_exercises_for_date",
    "get_meals_calories",
    "get_report_data",
    "get_user_weight",
    "get_weight_history",
    "has_active_sleep",
    "set_user_weight",
    "start_sleep",
]
