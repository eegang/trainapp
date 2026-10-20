"""Хендлеры: вес."""

import math

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.keyboards import main_keyboard
from app.states import Form
from db.repository import add_weight_entry, get_user_weight, set_user_weight

router = Router()

MIN_WEIGHT = 1.0
MAX_WEIGHT = 500.0


@router.message(F.text == "Вес на сегодня")
async def ask_weight(message: types.Message, state: FSMContext) -> None:
    """Просит текущий вес."""
    await state.clear()

    current = await get_user_weight(message.from_user.id)
    if current is not None:
        await message.answer(f"Текущий вес: {current} кг. Введите новый вес:")
    else:
        await message.answer("Введите ваш вес на сегодня (в кг):")

    await state.set_state(Form.weight)


@router.message(Form.weight)
async def save_weight(message: types.Message, state: FSMContext) -> None:
    """Сохраняет новый вес."""
    raw = (message.text or "").strip().replace(",", ".")
    try:
        weight = float(raw)
    except ValueError:
        await message.answer("Введите корректное число, например 75.5")
        return

    if not math.isfinite(weight) or not (MIN_WEIGHT <= weight <= MAX_WEIGHT):
        await message.answer(f"Вес должен быть числом от {MIN_WEIGHT} до {MAX_WEIGHT}. Попробуйте ещё раз.")
        return

    user_id = message.from_user.id
    await set_user_weight(user_id, weight)
    await add_weight_entry(user_id, weight)

    await state.clear()
    await message.answer(f"Вес {weight} кг сохранён!", reply_markup=main_keyboard())
