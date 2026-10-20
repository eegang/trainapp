"""Хендлеры: сон. Одна кнопка-переключатель: первое нажатие — заснул, второе — проснулся."""

from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.duration import format_minutes
from app.menu import SLEEP, main_keyboard
from db.repository import end_sleep, has_active_sleep, start_sleep

router = Router()


@router.message(F.text == SLEEP)
async def toggle_sleep(message: types.Message, state: FSMContext) -> None:
    """Запускает или останавливает таймер сна в зависимости от состояния."""
    await state.clear()
    user_id = message.from_user.id

    if await has_active_sleep(user_id):
        duration, start_time = await end_sleep(user_id)
        await message.answer(
            f"☀️ Доброе утро! Спал {format_minutes(duration)} (с {start_time[:16]}).",
            reply_markup=main_keyboard(),
        )
        return

    await start_sleep(user_id)
    await message.answer(
        f"🌙 Спокойной ночи! Засёк {datetime.now():%H:%M}. Проснёшься — жми «{SLEEP}».",
        reply_markup=main_keyboard(),
    )
