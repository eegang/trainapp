"""Формирование текстового отчёта для выгрузки и сводки за сегодня."""

from __future__ import annotations

from datetime import datetime

from app.dates import human_date, shift_days, today, working_days_between
from app.duration import format_minutes, format_short_hours, percent, progress_bar

GPT_PROMPT = (
    "Проанализируй эти данные о тренировках, питании, сне и рабочем времени за период. "
    "Дай рекомендации по питанию, режиму тренировок, балансу работы и отдыха. "
    "Выдели тренды и предложи план улучшений."
)


def _section(lines: list[str], title: str, count: int, rows: list[str]) -> None:
    """Однотипная секция отчёта."""
    lines.append(f"[{title}] — {count} записей")
    if rows:
        lines.extend(f"  {row}" for row in rows)
    else:
        lines.append("  (нет данных)")
    lines.append("")


def build_report(
    data: dict,
    *,
    days: int = 30,
    work_hours_per_day: float = 8.0,
) -> str:
    """Собирает текстовый отчёт за последние N дней."""
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append(f"ОТЧЁТ ЗА ПОСЛЕДНИЕ {days} ДНЕЙ")
    lines.append(f"Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)
    lines.append("")

    # --- Вес ---
    lines.append("[ПРОГРЕСС ВЕСА]")
    current = data.get("current_weight")
    if current:
        lines.append(f"Текущий вес: {current[0]} кг (обновлён {human_date(current[1])})")
    else:
        lines.append("Вес: не указан")

    history = data.get("weight_history") or []
    lines.append("Последние записи веса:")
    if history:
        lines.extend(f"  {human_date(date)}: {weight} кг" for weight, date in history[:7])
    else:
        lines.append("  (нет данных)")
    lines.append("")

    # --- Еда ---
    meals = data.get("meals") or []
    _section(
        lines,
        "ПРИЁМЫ ПИЩИ",
        len(meals),
        [f"{human_date(date)}: {calories} ккал" for date, calories in meals],
    )

    # --- Упражнения ---
    exercises = data.get("exercises") or []
    _section(
        lines,
        "УПРАЖНЕНИЯ",
        len(exercises),
        [f"{human_date(date)}: {description}" for date, description in exercises],
    )

    # --- Работа ---
    lines.extend(build_work_lines(data, days=days, work_hours_per_day=work_hours_per_day))

    # --- Сон ---
    sleeps = data.get("sleeps") or []
    rows = []
    for start, end, duration in sleeps:
        if end is None:
            rows.append(f"{start} — ещё спит")
        else:
            rows.append(f"{start} → {end}  ({format_minutes(duration)})")
    _section(lines, "СОН", len(sleeps), rows)

    lines.append("=" * 50)
    lines.append("ПРОМПТ ДЛЯ GPT:")
    lines.append(GPT_PROMPT)
    lines.append("=" * 50)

    return "\n".join(lines)


def build_work_lines(data: dict, *, days: int, work_hours_per_day: float) -> list[str]:
    """Секция рабочего времени для отчёта: факт против нормы."""
    work = data.get("work") or []
    total_min = sum(minutes for _, minutes in work)
    day_target_min = int(round(work_hours_per_day * 60))
    expected_min = day_target_min * working_days_between(shift_days(today(), -days), today())

    lines = [f"[РАБОЧЕЕ ВРЕМЯ] — {len(work)} дней с записями"]
    lines.append(
        f"  Итого: {format_minutes(total_min)} из {format_short_hours(expected_min)} "
        f"нормы ({percent(total_min, expected_min)}%)"
    )
    lines.append(f"  Норма: {format_short_hours(day_target_min)} в день (пн–пт)")

    if total_min > expected_min > 0:
        lines.append(f"  ⚠️ Переработка за период: +{format_minutes(total_min - expected_min)}")

    if work:
        lines.append("  По дням:")
        lines.extend(f"    {human_date(date)}: {format_minutes(minutes)}" for date, minutes in work)
    else:
        lines.append("  (нет данных)")
    lines.append("")

    return lines


def build_today_summary(
    *,
    weight: float | None,
    calories: int,
    exercises: list[str],
    is_sleeping: bool,
    work_minutes: int = 0,
    work_hours_per_day: float = 8.0,
    active_work_minutes: int | None = None,
) -> str:
    """Короткая сводка за сегодня."""
    day_target_min = int(round(work_hours_per_day * 60))

    lines = [f"Данные за {human_date(today())}:", ""]
    lines.append(f"Вес: {weight} кг" if weight is not None else "Вес: не указан")
    lines.append(f"Калории за сегодня: {calories} ккал")

    if exercises:
        lines.append(f"Упражнения: {', '.join(exercises)}")
    else:
        lines.append("Упражнения: не указано")

    work_line = f"Рабочее время: {format_minutes(work_minutes)} из {format_short_hours(day_target_min)}"
    if active_work_minutes is not None:
        work_line += f" (🟢 сессия идёт, {format_minutes(active_work_minutes)})"
    lines.append(work_line)

    lines.append("Статус: Спите" if is_sleeping else "Статус: Проснулись")
    lines.append("")

    return "\n".join(lines)
