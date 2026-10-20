"""Хендлеры: еда — калории за сегодня или вчера.

Выбранный день хранится в данных FSM (``meal_date``), поэтому запись
попадает именно в тот день, который выбрал пользователь.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app.dates import human_date, today, yesterday
from app.menu import DAY_TODAY, DAY_YESTERDAY, MEALS, date_keyboard, main_keyboard
from app.navigation import forward_to_menu
from app.states import Form
from db.repository import add_meal_calories, get_meals_calories

router = Router()

DATE_CHOICES = {DAY_TODAY: today, DAY_YESTERDAY: yesterday}


@router.message(F.text == MEALS)
async def ask_calories_date(message: types.Message, state: FSMContext) -> None:
    """Спрашивает, за какой день записывать калории."""
    await state.clear()
    await state.set_state(Form.meals_date)
    await message.answer("За какой день?", reply_markup=date_keyboard())


@router.message(Form.meals_date, F.text.in_(list(DATE_CHOICES)))
async def choose_date(message: types.Message, state: FSMContext) -> None:
    """Запоминает день и просит калории."""
    target = DATE_CHOICES[message.text]()
    await state.update_data(meal_date=target)
    await state.set_state(Form.meals)
    await message.answer(f"Сколько ккал за {human_date(target)}? Напиши число, например 550.")


@router.message(Form.meals_date)
async def wrong_date_choice(message: types.Message, state: FSMContext) -> None:
    """Не распознали выбор дня — переспрашиваем."""
    if await forward_to_menu(message, state):
        return
    await message.answer("Выбери «Сегодня» или «Вчера».", reply_markup=date_keyboard())


@router.message(Form.meals)
async def save_calories(message: types.Message, state: FSMContext) -> None:
    """Сохраняет калории за выбранный день и показывает итог дня."""
    if await forward_to_menu(message, state):
        return

    raw = (message.text or "").strip()
    if raw in DATE_CHOICES:
        await message.answer("Сначала напиши калории числом, например 550.")
        return

    try:
        calories = int(raw)
    except ValueError:
        await message.answer("Нужно целое число, например 550.")
        return

    if calories <= 0:
        await message.answer("Калории должны быть больше нуля.")
        return

    user_id = message.from_user.id
    data = await state.get_data()
    target = data.get("meal_date") or today()

    await add_meal_calories(user_id, calories, target)
    total = await get_meals_calories(user_id, target)

    await state.clear()
    await message.answer(
        f"➕ {calories} ккал · {human_date(target)}: всего {total} ккал",
        reply_markup=main_keyboard(),
    )
