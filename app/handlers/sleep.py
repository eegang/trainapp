"""Хендлеры: сон."""

from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.keyboards import main_keyboard, sleep_keyboard
from app.report import format_duration
from db.repository import end_sleep, has_active_sleep, start_sleep

router = Router()


@router.message(F.text == "Я сплю")
async def go_to_sleep(message: types.Message, state: FSMContext) -> None:
    """Запускает таймер сна."""
    await state.clear()

    if await has_active_sleep(message.from_user.id):
        await message.answer("Вы уже спите! Нажмите «Я проснулся».", reply_markup=sleep_keyboard())
        return

    await start_sleep(message.from_user.id)
    await message.answer(
        f"Хорошего сна! Таймер запущен в {datetime.now().strftime('%H:%M')}.",
        reply_markup=sleep_keyboard(),
    )


@router.message(F.text == "Я проснулся")
async def wake_up(message: types.Message, state: FSMContext) -> None:
    """Останавливает таймер сна и показывает длительность."""
    await state.clear()

    duration, start_time = await end_sleep(message.from_user.id)
    if duration is None:
        await message.answer(
            "Нет активного сеанса сна. Нажмите «Я сплю».", reply_markup=main_keyboard()
        )
        return

    await message.answer(
        f"Доброе утро! Вы спали {format_duration(duration)} (с {start_time[:16]}).",
        reply_markup=main_keyboard(),
    )
