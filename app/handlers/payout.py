"""Хендлеры: заработок по часовой ставке.

Ставка задаётся один раз и лежит в `settings`; отчёт считается по всем
месяцам, когда-либо закрытым в «Рабочее время».
"""

from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from app import money, prefs
from app.dates import month_label, today
from app.duration import format_minutes
from app.menu import PAYOUT
from app.navigation import forward_to_menu
from app.states import Work
from db.repository import get_work_months

logger = logging.getLogger(__name__)
router = Router()

#: Колбэк кнопки «изменить ставку» под расчётом.
RATE_CALLBACK = "payout_rate"


def payout_keyboard(rate: float | None) -> InlineKeyboardMarkup:
    """Кнопка изменения ставки прямо под расчётом."""
    label = f"Ставка {money.format_money(rate)} · изменить" if rate else "Указать ставку"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=RATE_CALLBACK)]]
    )


def month_title(month: str) -> str:
    """«2026-10» -> «Октябрь 2026»."""
    return month_label(f"{month}-01").capitalize()


def month_line(month: str, minutes: int, days: int, rate: float | None, *, current: bool = False) -> str:
    """Строка отчёта: месячная выработка и деньги."""
    hours = minutes / 60
    earned = money.earnings(hours, rate)
    title = f"{month_title(month)} · сейчас" if current else month_title(month)
    tail = f" · {format_minutes(minutes)} за {days} дн."
    if earned is not None:
        tail += f" = {money.format_money(earned)}"
    return f"{title}{tail}"


async def build_payout_text(user_id: int, rate: float | None) -> str:
    """Собирает расчёт: текущий месяц, все предыдущие, итого за всё время."""
    lines = ["💰 Заработок"]
    lines.append(
        f"Ставка: {money.format_money(rate)} за час"
        if rate
        else "Ставка не задана — суммы появятся, как только укажешь её."
    )

    months = await get_work_months(user_id)
    if not months:
        lines.append("")
        lines.append(
            "Записей пока нет. Открой «Рабочее время» и внеси часы — "
            "я посчитаю по ставке за текущий и все прошлые месяцы."
        )
        return "\n".join(lines)

    current = today()[:7]
    total_minutes = sum(minutes for _, minutes, _ in months)
    total_days = sum(days for _, _, days in months)
    total_hours = total_minutes / 60

    lines.append("")

    found_current = False
    previous: list[str] = []

    for month, minutes, days in months:
        if month == current:
            lines.append(month_line(month, minutes, days, rate, current=True))
            found_current = True
        else:
            previous.append(month_line(month, minutes, days, rate))

    if not found_current:
        lines.append(f"{month_title(current)} · сейчас — пока пусто")

    if previous:
        lines.append("")
        lines.append("Предыдущие месяцы:")
        lines.extend(f"  {line}" for line in previous)

    lines.append("")
    total_line = f"Итого: {format_minutes(total_minutes)} · {total_days} дн."
    earned_total = money.earnings(total_hours, rate)
    if earned_total is not None:
        total_line += f" = {money.format_money(earned_total)}"
    lines.append(total_line)

    if total_days and rate:
        avg = money.earnings(total_minutes / total_days / 60, rate)
        lines.append(
            f"Средний день: {format_minutes(round(total_minutes / total_days))} "
            f"· {money.format_money(avg)}"
        )

    return "\n".join(lines)


async def ask_rate(message: types.Message, state: FSMContext, *, editing: bool = False) -> None:
    """Просит часовую ставку."""
    await state.set_state(Work.rate)
    text = (
        "Какая у тебя часовая ставка? Напиши число за час, например 850 "
        "или 1 234,56. /cancel — отмена."
    )
    if editing:
        await message.edit_text(text)
    else:
        await message.answer(text)


@router.message(F.text == PAYOUT)
async def show_payout(message: types.Message, state: FSMContext) -> None:
    """Расчёт за текущий и все предыдущие месяцы."""
    await state.clear()
    user_id = message.from_user.id
    rate = await prefs.get_hourly_rate(user_id)

    if rate is None:
        await message.answer(
            "Часовая ставка ещё не задана. Задай её один раз — и я буду считать "
            "деньги за текущий и все прошлые месяцы.\n"
            "Напиши число за час, например 850 или 1 234,56. /cancel — отмена."
        )
        await state.set_state(Work.rate)
        return

    await message.answer(
        await build_payout_text(user_id, rate), reply_markup=payout_keyboard(rate)
    )


@router.callback_query(F.data == RATE_CALLBACK)
async def change_rate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Ставка … — изменить»."""
    await state.clear()
    await ask_rate(callback.message, state, editing=True)
    await callback.answer()


@router.message(Work.rate)
async def save_rate(message: types.Message, state: FSMContext) -> None:
    """Сохраняет ставку и сразу показывает расчёт."""
    if await forward_to_menu(message, state):
        return

    rate = money.parse_rate(message.text)
    if rate is None:
        await message.answer("Нужно число за час: 850 или 1234,56. /cancel — отмена.")
        return

    ok, saved = await prefs.set_hourly_rate(message.from_user.id, rate)
    if not ok:
        low, high = prefs.RATE_BOUNDS
        await message.answer(
            f"Ставка должна быть от {money.format_money(low)} до {money.format_money(high)} за час."
        )
        return

    await state.clear()
    await message.answer(
        await build_payout_text(message.from_user.id, saved),
        reply_markup=payout_keyboard(saved),
    )
