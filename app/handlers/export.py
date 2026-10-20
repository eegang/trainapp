"""Хендлеры: выгрузка отчёта и сводка за сегодня."""

import os
import tempfile

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.dates import today
from app.keyboards import main_keyboard
from app.report import build_report, build_today_summary
from db.repository import (
    get_exercises_for_date,
    get_meals_calories,
    get_report_data,
    get_user_weight,
    has_active_sleep,
)

router = Router()


@router.message(F.text == "Выгрузить данные за 30 дней")
async def export_data(message: types.Message, state: FSMContext) -> None:
    """Отправляет файл с отчётом за 30 дней."""
    await state.clear()

    data = await get_report_data(message.from_user.id, days=30)
    report = build_report(data)

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
            caption="Отчёт за 30 дней для анализа в GPT",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.message(F.text == "Данные за сегодня")
async def today_data(message: types.Message, state: FSMContext) -> None:
    """Показывает сводку за сегодня."""
    await state.clear()

    user_id = message.from_user.id
    summary = build_today_summary(
        weight=await get_user_weight(user_id),
        calories=await get_meals_calories(user_id, today()),
        exercises=await get_exercises_for_date(user_id, today()),
        is_sleeping=await has_active_sleep(user_id),
    )

    await message.answer(f"{summary}\nВыберите другое действие:", reply_markup=main_keyboard())
