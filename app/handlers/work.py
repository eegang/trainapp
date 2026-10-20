"""Хендлеры блока «Рабочее время»: ручная запись часов за день.

Значение привязано к дате: повторный ввод за тот же день заменяет его, а
не добавляет вторую строку. Это и есть способ исправить опечатку.
"""

from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app import money, prefs
from app.dates import human_date, month_label, month_range, today, yesterday, parse_user_date
from app.duration import MAX_DAY_HOURS, format_minutes, parse_hours_and_note
from app.menu import (
    DAY_TODAY,
    DAY_YESTERDAY,
    WORK,
    date_keyboard,
    main_keyboard,
)
from app.navigation import forward_to_menu
from app.states import Work
from db.repository import (
    clear_work_day,
    get_work_by_date,
    save_work_day,
    sum_work_minutes,
)

logger = logging.getLogger(__name__)
router = Router()

#: Максимум часов за день.
MAX_HOURS = MAX_DAY_HOURS


@router.message(F.text == WORK)
async def ask_date(message: types.Message, state: FSMContext) -> None:
    """Начало записи: за какой день отработали."""
    await state.clear()
    await state.set_state(Work.manual_date)
    await message.answer(
        "За какой день записать часы? Нажмите кнопку или напиши дату, например 20.10.",
        reply_markup=date_keyboard(),
    )


@router.message(Work.manual_date, F.text.in_([DAY_TODAY, DAY_YESTERDAY]))
async def pick_date(message: types.Message, state: FSMContext) -> None:
    target = today() if message.text == DAY_TODAY else yesterday()
    await _ask_hours(message, state, target)


@router.message(Work.manual_date)
async def type_date(message: types.Message, state: FSMContext) -> None:
    """Дата с клавиатуры: 20.10, 20.10.2026, «сегодня»."""
    if await forward_to_menu(message, state):
        return

    target = parse_user_date(message.text)
    if not target:
        await message.answer(
            "Не понял дату. Нажми «Сегодня»/«Вчера» или напиши 20.10.2026. /cancel — отмена.",
            reply_markup=date_keyboard(),
        )
        return

    await _ask_hours(message, state, target)


async def _ask_hours(message: types.Message, state: FSMContext, target_date: str) -> None:
    """Второй шаг: количество часов. Предупреждаем, если день уже заполнен."""
    await state.update_data(work_date=target_date)
    await state.set_state(Work.manual_value)

    existing = await get_work_by_date(message.from_user.id, target_date)
    warning = (
        f"\nЗа этот день уже записано {format_minutes(existing)} — заменится новым значением."
        if existing
        else ""
    )

    await message.answer(
        f"Сколько часов отработано {human_date(target_date)}?{warning}\n"
        "Форматы: 8 · 8,5 · 8:30 · 8ч30. Заметку можно дописать рядом: «8:30 закрывал год». "
        "0 — убрать день из учёта."
    )


@router.message(Work.manual_value)
async def save_hours(message: types.Message, state: FSMContext) -> None:
    """Сохраняет часы за день и показывает итог месяца с деньгами."""
    if await forward_to_menu(message, state):
        return

    hours, note = parse_hours_and_note(message.text)
    if hours is None:
        await message.answer(
            "Не похоже на часы. Напиши 8, 8,5 или 8:30. "
            "0 — если день нужно убрать из учёта. /cancel — отмена."
        )
        return

    if hours > MAX_HOURS:
        await message.answer(
            f"За день больше {MAX_HOURS:g} часов не бывает. Проверь число — я ещё жду ввод."
        )
        return

    data = await state.get_data()
    target = data.get("work_date") or today()
    user_id = message.from_user.id
    minutes = round(hours * 60)

    if minutes == 0:
        removed = await clear_work_day(user_id, target)
        await state.clear()
        if removed:
            result = f"Убрал {human_date(target)} из учёта."
        else:
            result = f"За {human_date(target)} и так ничего не было записано."
        await message.answer(result, reply_markup=main_keyboard())
        return

    previous = await save_work_day(user_id, target, minutes, note or None)
    await state.clear()

    lines = [f"✅ {human_date(target)} — {format_minutes(minutes)}"]

    if previous is not None and previous != minutes:
        lines.append(f"   было {format_minutes(previous)}")
    if note:
        lines.append(f"   заметка: {note}")

    lines.append("")
    lines.append(await _month_summary(user_id, target))

    await message.answer("\n".join(lines), reply_markup=main_keyboard())


async def _month_summary(user_id: int, target_date: str) -> str:
    """Итог за месяц даты: часы и, если задана ставка, деньги."""
    start, end = month_range(target_date)
    minutes = await sum_work_minutes(user_id, start, min(end, today()))
    title = month_label(start).capitalize()

    rate = await prefs.get_hourly_rate(user_id)
    earned = money.earnings(minutes / 60, rate)

    if earned is None:
        return f"{title}: {format_minutes(minutes)}. Ставка не задана — «Заработок» посчитаю после её указания."
    return f"{title}: {format_minutes(minutes)} = {money.format_money(earned)}"
