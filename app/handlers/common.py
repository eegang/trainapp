"""Хендлеры: /start, /cancel и навигация по разделам меню."""

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.menu import BACK, RECORD, SLEEP, VIEW, main_keyboard, section_keyboard
from db.repository import has_active_sleep

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Приветствие и главное меню."""
    await state.clear()

    hint = ""
    if await has_active_sleep(message.from_user.id):
        hint = f"\n\nСейчас отмечено, что ты спишь. Проснёшься — жми «{SLEEP}»."

    await message.answer(f"Привет! Что сделаем?{hint}", reply_markup=main_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Прерывает текущий ввод и возвращает в главное меню."""
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_keyboard())


@router.message(F.text == RECORD)
async def open_record(message: types.Message, state: FSMContext) -> None:
    """Раздел «Записать»."""
    await state.clear()
    await message.answer("Что записываем?", reply_markup=section_keyboard(RECORD))


@router.message(F.text == VIEW)
async def open_view(message: types.Message, state: FSMContext) -> None:
    """Раздел «Смотреть»."""
    await state.clear()
    await message.answer("Что посмотрим?", reply_markup=section_keyboard(VIEW))


@router.message(F.text == BACK)
async def go_back(message: types.Message, state: FSMContext) -> None:
    """Назад в главное меню из любого раздела или ввода."""
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_keyboard())
