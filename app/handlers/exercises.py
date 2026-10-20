"""Хендлеры: упражнения."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.keyboards import main_keyboard
from app.navigation import forward_to_menu
from app.states import Form
from db.repository import add_exercise

router = Router()


@router.message(F.text == "Показатели упражнений")
async def ask_exercise(message: types.Message, state: FSMContext) -> None:
    """Просит описание тренировки."""
    await state.clear()
    await message.answer(
        "Введите данные упражнений одним сообщением.\nНапример: бицепс 20x5\nПресс 30x3"
    )
    await state.set_state(Form.exercises)


@router.message(Form.exercises)
async def save_exercise(message: types.Message, state: FSMContext) -> None:
    """Сохраняет описание тренировки."""
    if await forward_to_menu(message, state):
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Введите данные упражнения:")
        return

    await add_exercise(message.from_user.id, text)

    await state.clear()
    await message.answer(f"Сохранено: {text}", reply_markup=main_keyboard())
