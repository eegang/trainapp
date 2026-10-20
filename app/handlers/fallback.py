"""Запасной хендлер: отвечает, если пользователь не выбрал действие.

Регистрируется последним, поэтому срабатывает только если ни один
другой хендлер не подошёл.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.keyboards import main_keyboard

router = Router()


@router.message(F.text)
async def fallback(message: types.Message, state: FSMContext) -> None:
    """Подсказывает доступные действия."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Выберите действие из меню:", reply_markup=main_keyboard())
