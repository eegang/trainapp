"""Хендлеры: приёмы пищи.

Выбранный день хранится в данных FSM (``meal_date``), поэтому запись
корректно попадает либо за сегодня, либо за вчера.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.dates import human_date, today, yesterday
from app.keyboards import TODAY_BUTTON, YESTERDAY_BUTTON, date_choice_keyboard, main_keyboard
from app.navigation import forward_to_menu
from app.states import Form
from db.repository import add_meal_calories, get_meals_calories

router = Router()

DATE_CHOICES = {
    TODAY_BUTTON: today,
    YESTERDAY_BUTTON: yesterday,
}


@router.message(F.text == "Приемы пищи")
async def ask_calories_date(message: types.Message, state: FSMContext) -> None:
    """Спрашивает, за какой день записывать калории."""
    await state.clear()
    await state.set_state(Form.meals_date)
    await message.answer("За какой день записать?", reply_markup=date_choice_keyboard())


@router.message(Form.meals_date, F.text.in_(list(DATE_CHOICES)))
async def choose_date(message: types.Message, state: FSMContext) -> None:
    """Запоминает выбранный день и просит количество калорий."""
    target_date = DATE_CHOICES[message.text]()

    await state.update_data(meal_date=target_date)
    await state.set_state(Form.meals)

    await message.answer(
        f"Введите количество калорий за {human_date(target_date)} (только число):"
    )


@router.message(Form.meals_date)
async def wrong_date_choice(message: types.Message, state: FSMContext) -> None:
    """Не распознали выбор дня — спрашиваем ещё раз."""
    if await forward_to_menu(message, state):
        return

    await message.answer("Выберите «Сегодня» или «Вчера».", reply_markup=date_choice_keyboard())


@router.message(Form.meals)
async def save_calories(message: types.Message, state: FSMContext) -> None:
    """Сохраняет калории за выбранный день."""
    if await forward_to_menu(message, state):
        return

    raw = (message.text or "").strip()

    if raw in DATE_CHOICES:
        await message.answer("Сначала введите количество калорий числом, например 550.")
        return

    try:
        calories = int(raw)
    except ValueError:
        await message.answer("Введите целое число, например 550")
        return

    if calories <= 0:
        await message.answer("Количество калорий должно быть больше нуля. Введите число.")
        return

    user_id = message.from_user.id
    data = await state.get_data()
    target_date = data.get("meal_date") or today()

    await add_meal_calories(user_id, calories, target_date)
    total = await get_meals_calories(user_id, target_date)

    await state.clear()
    await message.answer(
        f"+{calories} ккал добавлено. Итого за {human_date(target_date)}: {total} ккал",
        reply_markup=main_keyboard(),
    )
