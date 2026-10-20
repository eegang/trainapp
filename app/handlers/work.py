"""Хендлеры блока «Рабочее время».

Способы учёта:
  1. Таймер: «▶ Начать работу» / «■ Завершить работу».
  2. Вручную: длительность + заметка за любой день.
  3. Статистика: день / неделя / месяц против нормы.

Порядок регистрации важен: сначала кнопки навигации, затем хендлеры состояний
(они принимают любой текст). В каждом хендлере состояния первым идёт
``forward_to_menu`` — он даёт кнопкам сработать, даже если сейчас идёт ввод.
"""

from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app import prefs
from app.dates import (
    human_date,
    human_range,
    month_label,
    month_range,
    parse_user_date,
    shift_days,
    today,
    week_range,
    working_days_between,
    yesterday,
)
from app.duration import (
    SUSPICIOUS_OPEN_MINUTES,
    format_hours_value,
    format_minutes,
    format_short_hours,
    minutes_since,
    parse_duration,
    parse_hours,
    percent,
    progress_bar,
)
from app.keyboards import (
    TODAY_BUTTON,
    WORK_BACK_TEXT,
    WORK_DELETE_TEXT,
    WORK_FINISH_TEXT,
    WORK_MANUAL_TEXT,
    WORK_NORM_TEXT,
    WORK_START_TEXT,
    WORK_STATS_TEXT,
    WORK_TEXT,
    YESTERDAY_BUTTON,
    date_choice_keyboard,
    main_keyboard,
    work_delete_confirm_keyboard,
    work_delete_keyboard,
    work_keyboard,
    work_long_session_keyboard,
    work_stats_keyboard,
)
from app.navigation import forward_to_menu
from app.states import Work
from db.repository import (
    add_work_entry,
    delete_work_entry,
    finish_work,
    get_active_work,
    get_work_by_date,
    get_work_daily_breakdown,
    list_work_entries,
    start_work,
    sum_work_minutes,
)

logger = logging.getLogger(__name__)
router = Router()

#: Записей в списке на удаление и в статистике за день.
LIST_LIMIT = 12
#: Глубина истории, которую показываем и с которой удаляем.
HISTORY_DAYS = 45

PERIOD_LABELS = {"day": "День", "week": "Неделя", "month": "Месяц"}


def format_entry_button(entry: dict) -> str:
    """Подпись кнопки в списке на удаление."""
    mark = "⏱" if entry["source"] == "timer" else "✍"
    return f"{human_date(entry['date'])} · {format_minutes(entry['duration_min'])} · {mark}"


# ---------- Навигация ----------

@router.message(F.text == WORK_TEXT)
async def open_work_menu(message: types.Message, state: FSMContext) -> None:
    """Вход в блок."""
    await show_work_menu(message, state)


@router.message(F.text == WORK_BACK_TEXT)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    """Выход в главное меню."""
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=main_keyboard())


async def show_work_menu(message: types.Message, state: FSMContext, note: str | None = None) -> None:
    """Меню блока с текущим статусом таймера."""
    await state.clear()
    user_id = message.from_user.id
    active = await get_active_work(user_id)

    lines = ["⏱ Рабочее время", ""]
    if active:
        elapsed = minutes_since(active["start_time"]) or 0
        lines.append(f"🟢 На работе с {active['start_time'][11:16]} — уже {format_minutes(elapsed)}")
    else:
        lines.append("⚪ Сейчас не на работе.")

    lines.append(f"Записано сегодня: {format_minutes(await get_work_by_date(user_id, today()))}")

    if note:
        lines.extend(["", note])

    await message.answer(
        "\n".join(lines),
        reply_markup=work_keyboard(is_working=active is not None),
    )


# ---------- Таймер ----------

@router.message(F.text == WORK_START_TEXT)
async def start_timer(message: types.Message, state: FSMContext) -> None:
    """Запускает сессию."""
    await state.clear()
    user_id = message.from_user.id

    active = await get_active_work(user_id)
    if active:
        elapsed = minutes_since(active["start_time"]) or 0
        await message.answer(
            f"Сессия уже идёт — {format_minutes(elapsed)}. Сначала завершите её.",
            reply_markup=work_keyboard(is_working=True),
        )
        return

    await start_work(user_id)
    await message.answer("Отмечено, поехали 🚀", reply_markup=work_keyboard(is_working=True))


@router.message(F.text == WORK_FINISH_TEXT)
async def finish_timer(message: types.Message, state: FSMContext) -> None:
    """Закрывает сессию; слишком длинную — сперва показывает на подтверждение."""
    await state.clear()
    user_id = message.from_user.id

    active = await get_active_work(user_id)
    if not active:
        await message.answer(
            "Нет активной сессии. Нажмите «▶ Начать работу».",
            reply_markup=work_keyboard(is_working=False),
        )
        return

    elapsed = minutes_since(active["start_time"]) or 0
    if elapsed > SUSPICIOUS_OPEN_MINUTES:
        await message.answer(
            f"Сессия тянется {format_minutes(elapsed)} (с {human_date(active['date'])}). "
            "Похоже, вы её забыли закрыть. Сохранить как есть или удалить?",
            reply_markup=work_long_session_keyboard(active["id"]),
        )
        return

    saved = await finish_work(user_id, active["id"])
    await show_work_menu(
        message, state, note=f"✅ Смена закрыта: {format_minutes(saved['duration_min'])}."
    )


# ---------- Действия блока ----------

@router.message(F.text == WORK_MANUAL_TEXT)
async def ask_manual_date(message: types.Message, state: FSMContext) -> None:
    """Шаг 1 ручной записи: день."""
    await state.clear()
    await state.set_state(Work.manual_date)
    await message.answer(
        "За какой день записать? Нажмите кнопку или напишите дату, например 20.10.",
        reply_markup=date_choice_keyboard(),
    )


@router.message(F.text == WORK_STATS_TEXT)
async def stats(message: types.Message, state: FSMContext) -> None:
    """Статистика за неделю по умолчанию."""
    await state.clear()
    text, keyboard = await build_stats(message.from_user.id, "week")
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text == WORK_DELETE_TEXT)
async def list_for_delete(message: types.Message, state: FSMContext) -> None:
    """Список записей на удаление."""
    await state.clear()
    entries = await list_work_entries(
        message.from_user.id, date_from=shift_days(today(), -HISTORY_DAYS), limit=LIST_LIMIT
    )

    if not entries:
        await message.answer(
            "Нечего удалять — записей не находилось.",
            reply_markup=work_keyboard(is_working=False),
        )
        return

    await message.answer(
        "Какую запись удалить?", reply_markup=work_delete_keyboard(entries, format_entry_button)
    )


@router.message(F.text == WORK_NORM_TEXT)
async def ask_norm_day(message: types.Message, state: FSMContext) -> None:
    """Шаг 1 нормы: часов в день."""
    await state.clear()
    current = await prefs.get_work_hours_per_day(message.from_user.id)
    await state.set_state(Work.norm_day)
    await message.answer(
        f"Сколько часов в день для вас норма? Сейчас {format_hours_value(current)}. "
        "Напишите число: 8 или 7,5."
    )


# ---------- Колбэки ----------

@router.callback_query(F.data.startswith("work_p:"))
async def switch_stats_period(callback: types.CallbackQuery) -> None:
    """Переключение периода в статистике."""
    period = callback.data.split(":", 1)[1]
    text, keyboard = await build_stats(callback.from_user.id, period)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("work_del:"))
async def confirm_delete(callback: types.CallbackQuery) -> None:
    """Удаление с подтверждением: одним тапом данные не стираются."""
    raw = callback.data.split(":", 1)[1]
    if raw == "cancel":
        await callback.message.edit_text("Отменил.")
        await callback.answer()
        return

    entry_id = int(raw)
    entry = await _find_own_entry(callback.from_user.id, entry_id)
    if not entry:
        await callback.message.edit_text("Такой записи уже нет.")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"Удалить {human_date(entry['date'])} — {format_minutes(entry['duration_min'])}?",
        reply_markup=work_delete_confirm_keyboard(entry_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("work_del_yes:"))
async def do_delete(callback: types.CallbackQuery) -> None:
    """Собирает удаление."""
    entry_id = int(callback.data.split(":", 1)[1])
    deleted = await delete_work_entry(callback.from_user.id, entry_id)

    if deleted:
        await callback.message.edit_text("🗑 Удалил.")
        await callback.answer("Готово")
    else:
        await callback.message.edit_text("Эта запись уже удалена.")
        await callback.answer()


@router.callback_query(F.data == "work_del_no")
async def cancel_delete(callback: types.CallbackQuery) -> None:
    await callback.message.edit_text("Не трогаю.")
    await callback.answer()


@router.callback_query(F.data.startswith("work_long_"))
async def resolve_long_session(callback: types.CallbackQuery) -> None:
    """Реакция на подсказку о забытой сессии."""
    action, _, raw_id = callback.data.partition(":")
    session_id = int(raw_id)
    user_id = callback.from_user.id

    if action == "work_long_drop":
        deleted = await delete_work_entry(user_id, session_id)
        await callback.message.edit_text("Сессию удалил." if deleted else "Этой сессии уже нет.")
        await callback.answer()
        return

    active = await get_active_work(user_id)
    if not active or active["id"] != session_id:
        await callback.message.edit_text("Эта сессия уже закрыта.")
        await callback.answer()
        return

    saved = await finish_work(user_id, session_id)
    await callback.message.edit_text(
        f"Сохранил как есть: {format_minutes(saved['duration_min'])}. "
        "Если лишнее — «Удалить запись»."
    )
    await callback.answer()


async def _find_own_entry(user_id: int, entry_id: int) -> dict | None:
    """Запись пользователя по id — чтобы кнопка не чужую запись удалила."""
    entries = await list_work_entries(user_id, date_from=shift_days(today(), -HISTORY_DAYS), limit=50)
    return next((entry for entry in entries if entry["id"] == entry_id), None)


# ---------- Состояния: ручной ввод и норма ----------

@router.message(Work.manual_date, F.text.in_([TODAY_BUTTON, YESTERDAY_BUTTON]))
async def pick_manual_date(message: types.Message, state: FSMContext) -> None:
    target = today() if message.text == TODAY_BUTTON else yesterday()
    await _ask_manual_duration(message, state, target)


@router.message(Work.manual_date)
async def type_manual_date(message: types.Message, state: FSMContext) -> None:
    """Дата с клавиатуры: 20.10, 20.10.2026, «сегодня»."""
    if await forward_to_menu(message, state):
        return

    target = parse_user_date(message.text)
    if not target:
        await message.answer(
            "Не понял дату. Нажмите «Сегодня»/«Вчера» или напишите 20.10.2026. /cancel — отмена.",
            reply_markup=date_choice_keyboard(),
        )
        return

    await _ask_manual_duration(message, state, target)


async def _ask_manual_duration(
    message: types.Message, state: FSMContext, target_date: str
) -> None:
    await state.update_data(work_date=target_date)
    await state.set_state(Work.manual_value)
    await message.answer(
        f"За {human_date(target_date)}. Сколько отработали?\n"
        "Форматы: 8 · 8,5 · 8:30 · 8ч30. Можно дописать заметку: «8:30 закрывал год»."
    )


@router.message(Work.manual_value)
async def save_manual(message: types.Message, state: FSMContext) -> None:
    """Шаг 2 ручной записи: длительность и необязательная заметка."""
    if await forward_to_menu(message, state):
        return

    minutes, note = parse_duration(message.text)
    if minutes is None:
        await message.answer(
            "Не похоже на длительность. Форматы: 8 · 8,5 · 8:30 · 8ч30 · 480мин. "
            "Пример с заметкой: «8:30 закрывал год». /cancel — отмена."
        )
        return

    data = await state.get_data()
    target = data.get("work_date") or today()
    user_id = message.from_user.id

    await add_work_entry(user_id, target, minutes, note or None)
    await state.clear()

    total = await get_work_by_date(user_id, target)
    note_text = f"\nЗаметка: {note}" if note else ""
    await show_work_menu(
        message,
        state,
        note=f"✅ Записано {format_minutes(minutes)} на {human_date(target)}.{note_text} "
        f"Всего за день: {format_minutes(total)}.",
    )


@router.message(Work.norm_day)
async def save_norm_day(message: types.Message, state: FSMContext) -> None:
    """Сохраняет дневную норму и спрашивает недельную."""
    if await forward_to_menu(message, state):
        return

    hours = parse_hours(message.text)
    if hours is None:
        await message.answer("Нужно число часов: 8, 7,5 или 8:00. /cancel — отмена.")
        return

    ok, saved = await prefs.set_number(message.from_user.id, prefs.WORK_HOURS_PER_DAY, hours)
    if not ok:
        low, high = prefs.bounds_of(prefs.WORK_HOURS_PER_DAY)
        await message.answer(
            f"Давайте в разумных пределах: от {format_hours_value(low)} "
            f"до {format_hours_value(high)} в день."
        )
        return

    await state.set_state(Work.norm_week)
    week_current = await prefs.get_work_hours_per_week(message.from_user.id)
    await message.answer(
        f"Норма в день: {format_hours_value(saved)}. "
        f"А норма за неделю? Сейчас {format_hours_value(week_current)}."
    )


@router.message(Work.norm_week)
async def save_norm_week(message: types.Message, state: FSMContext) -> None:
    """Сохраняет недельную норму и показывает итог."""
    if await forward_to_menu(message, state):
        return

    hours = parse_hours(message.text)
    if hours is None:
        await message.answer("Нужно число часов: 40, 38,5 или 37. /cancel — отмена.")
        return

    ok, saved = await prefs.set_number(message.from_user.id, prefs.WORK_HOURS_PER_WEEK, hours)
    if not ok:
        low, high = prefs.bounds_of(prefs.WORK_HOURS_PER_WEEK)
        await message.answer(
            f"Давайте в разумных пределах: от {format_hours_value(low)} "
            f"до {format_hours_value(high)} в неделю."
        )
        return

    per_day = await prefs.get_work_hours_per_day(message.from_user.id)
    await show_work_menu(
        message,
        state,
        note=f"✅ Норма: {format_hours_value(saved)} в неделю, "
        f"{format_hours_value(per_day)} в день.",
    )


# ---------- Статистика ----------

async def build_stats(user_id: int, period: str) -> tuple[str, types.InlineKeyboardMarkup]:
    """Считает факт против нормы за день / неделю / месяц."""
    per_day = await prefs.get_work_hours_per_day(user_id)
    per_week = await prefs.get_work_hours_per_week(user_id)
    day_target_min = int(round(per_day * 60))

    if period == "day":
        start = end = today()
        range_label = human_date(start)
        target_min = day_target_min
    elif period == "month":
        start, month_end = month_range()
        end = min(month_end, today())
        range_label = f"{month_label(start)} · по {human_date(end)}"
        target_min = day_target_min * working_days_between(start, end)
    else:
        period = "week"
        start, end = week_range()
        end = min(end, today())
        range_label = human_range(start, end)
        target_min = int(round(per_week * 60))

    fact = await sum_work_minutes(user_id, start, end)
    share = percent(fact, target_min)

    lines = [
        f"📊 Рабочее время · {PERIOD_LABELS[period]}",
        f"{range_label}",
        "",
    ]

    if target_min > 0:
        lines.append(
            f"{progress_bar(fact, target_min)} {format_minutes(fact)} "
            f"из {format_short_hours(target_min)} · {share}%"
        )
        if fact > target_min:
            lines.append(f"⚠️ Переработка: +{format_minutes(fact - target_min)}")
    else:
        lines.append(f"Отработано: {format_minutes(fact)}")

    lines.append("")

    if period == "day":
        entries = await list_work_entries(user_id, date_from=start, date_to=end, limit=LIST_LIMIT)
        if entries:
            lines.append(f"Записи дня ({len(entries)}):")
            for entry in entries:
                mark = "⏱" if entry["source"] == "timer" else "✍"
                note = f" — {entry['note']}" if entry["note"] else ""
                lines.append(f"  {mark} {format_minutes(entry['duration_min'])}{note}")
        else:
            lines.append("Записей за день нет.")
    else:
        breakdown = await get_work_daily_breakdown(user_id, start, end)
        if breakdown:
            lines.append("По дням:")
            lines.extend(f"  {human_date(day)}: {format_minutes(minutes)}" for day, minutes in breakdown)
            lines.append("")
            lines.append(
                f"Дней с записями: {len(breakdown)} · "
                f"среднее {format_minutes(round(sum(minutes for _, minutes in breakdown) / len(breakdown)))}"
            )
        else:
            lines.append("Записей за период нет.")

    active = await get_active_work(user_id)
    if active:
        elapsed = minutes_since(active["start_time"]) or 0
        lines.extend(["", f"🟢 Сейчас на работе: {format_minutes(elapsed)}"])

    return "\n".join(lines), work_stats_keyboard(period)
