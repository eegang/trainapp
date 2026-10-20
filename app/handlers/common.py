"""Хендлеры: общие команды /start и /cancel."""

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.keyboards import main_keyboard, sleep_keyboard
from db.repository import has_active_sleep

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Приветствие и главное меню."""
    await state.clear()

    if await has_active_sleep(message.from_user.id):
        await message.answer(
            "Вы уже спите! Нажмите «Я проснулся», чтобы завершить.",
            reply_markup=sleep_keyboard(),
        )
    else:
        await message.answer("Выберите действие:", reply_markup=main_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Прерывает текущий диалог."""
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_keyboard())
