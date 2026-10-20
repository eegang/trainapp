"""Хендлеры: вес."""

import math

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.menu import WEIGHT, main_keyboard
from app.navigation import forward_to_menu
from app.states import Form
from db.repository import add_weight_entry, get_user_weight, set_user_weight

router = Router()

MIN_WEIGHT = 1.0
MAX_WEIGHT = 500.0


@router.message(F.text == WEIGHT)
async def ask_weight(message: types.Message, state: FSMContext) -> None:
    """Просит вес. Если он уже известен, показывает его."""
    await state.clear()

    current = await get_user_weight(message.from_user.id)
    if current is not None:
        await message.answer(f"Сейчас {current} кг. Напиши новый вес:")
    else:
        await message.answer("Напиши вес в кг, например 75,5:")

    await state.set_state(Form.weight)


@router.message(Form.weight)
async def save_weight(message: types.Message, state: FSMContext) -> None:
    """Сохраняет вес и добавляет запись в историю."""
    if await forward_to_menu(message, state):
        return

    raw = (message.text or "").strip().replace(",", ".")
    try:
        weight = float(raw)
    except ValueError:
        await message.answer("Нужно число, например 75,5.")
        return

    if not math.isfinite(weight) or not (MIN_WEIGHT <= weight <= MAX_WEIGHT):
        await message.answer(f"Вес должен быть от {MIN_WEIGHT:g} до {MAX_WEIGHT:g} кг.")
        return

    user_id = message.from_user.id
    await set_user_weight(user_id, weight)
    await add_weight_entry(user_id, weight)

    await state.clear()
    await message.answer(f"Вес {weight} кг сохранён ✅", reply_markup=main_keyboard())
