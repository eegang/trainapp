"""Хендлеры: тренировки (свободный текст, одно сообщение — одна запись)."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.menu import TRAINING, main_keyboard
from app.navigation import forward_to_menu
from app.states import Form
from db.repository import add_exercise

router = Router()


@router.message(F.text == TRAINING)
async def ask_exercise(message: types.Message, state: FSMContext) -> None:
    """Просит описание тренировки."""
    await state.clear()
    await message.answer("Опиши тренировку одним сообщением, например:\nбицепс 20x5\nпресс 30x3")
    await state.set_state(Form.exercises)


@router.message(Form.exercises)
async def save_exercise(message: types.Message, state: FSMContext) -> None:
    """Сохраняет описание тренировки."""
    if await forward_to_menu(message, state):
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Опиши тренировку текстом:")
        return

    await add_exercise(message.from_user.id, text)
    await state.clear()
    await message.answer(f"Записал 💾\n{text}", reply_markup=main_keyboard())
