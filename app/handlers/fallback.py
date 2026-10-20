"""Запасной хендлер: текст вне меню, и никакой ввод сейчас не ждём.

Регистрируется последним, поэтому срабатывает только если ни один другой
хендлер не подошёл.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.menu import main_keyboard

router = Router()


@router.message(F.text)
async def fallback(message: types.Message, state: FSMContext) -> None:
    """Подсказывает, что делать дальше."""
    if await state.get_state() is None:
        await message.answer("Выбери действие в меню 👇", reply_markup=main_keyboard())
