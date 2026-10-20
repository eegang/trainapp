"""Хендлеры: сводка за сегодня и текстовый отчёт за 30 дней."""

import os
import tempfile

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app import prefs
from app.dates import today
from app.menu import REPORT, TODAY, main_keyboard
from app.report import build_report, build_today_summary
from db.repository import (
    get_exercises_for_date,
    get_meals_calories,
    get_report_data,
    get_user_weight,
    get_work_by_date,
    has_active_sleep,
)

router = Router()


@router.message(F.text == REPORT)
async def export_data(message: types.Message, state: FSMContext) -> None:
    """Отправляет файл с отчётом за 30 дней (для анализа в GPT)."""
    await state.clear()

    user_id = message.from_user.id
    data = await get_report_data(user_id, days=30)
    report = build_report(data, days=30, hourly_rate=await prefs.get_hourly_rate(user_id))

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(report)
            temp_path = temp_file.name

        await message.bot.send_document(
            message.chat.id,
            types.FSInputFile(temp_path),
            caption="Отчёт за 30 дней — можно отправить в GPT на разбор.",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.message(F.text == TODAY)
async def today_data(message: types.Message, state: FSMContext) -> None:
    """Сводка за сегодня: вес, еда, тренировки, работа, сон."""
    await state.clear()

    user_id = message.from_user.id
    summary = build_today_summary(
        weight=await get_user_weight(user_id),
        calories=await get_meals_calories(user_id, today()),
        exercises=await get_exercises_for_date(user_id, today()),
        is_sleeping=await has_active_sleep(user_id),
        work_minutes=await get_work_by_date(user_id, today()),
        hourly_rate=await prefs.get_hourly_rate(user_id),
    )

    await message.answer(summary, reply_markup=main_keyboard())
