"""Хендлеры: /start и /cancel."""

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.menu import SLEEP, main_keyboard
from db.repository import has_active_sleep

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Приветствие и главное меню."""
    await state.clear()

    hint = ""
    if await has_active_sleep(message.from_user.id):
        hint = f"\n\nСейчас отмечено, что ты спишь. Проснёшься — жми «{SLEEP}»."

    await message.answer(f"Привет! Что записываем?{hint}", reply_markup=main_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Прерывает текущий ввод и возвращает в меню."""
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_keyboard())
