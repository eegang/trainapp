"""Формирование текстового отчёта для выгрузки и сводки за сегодня."""

from __future__ import annotations

from datetime import datetime

from app import money
from app.dates import human_date, today
from app.duration import format_minutes

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


def build_report(data: dict, *, days: int = 30, hourly_rate: float | None = None) -> str:
    """Собирает текстовый отчёт за последние N дней."""
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append(f"ОТЧЁТ ЗА ПОСЛЕДНИЕ {days} ДНЕЙ")
    lines.append(f"Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if hourly_rate:
        lines.append(f"Часовая ставка: {money.format_money(hourly_rate)}")
    lines.append("=" * 50)
    lines.append("")

    # --- Вес ---
    lines.append("[ПРОГРЕСС ВЕСА]")
    current = data.get("weight")
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
    lines.extend(build_work_lines(data, hourly_rate=hourly_rate))

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


def build_work_lines(data: dict, *, hourly_rate: float | None = None) -> list[str]:
    """Секция рабочего времени: часы за период и деньги по ставке."""
    work = data.get("work") or []
    total_min = sum(minutes for _, minutes, _ in work)
    hours = total_min / 60

    lines = [f"[РАБОЧЕЕ ВРЕМЯ] — {len(work)} дней"]

    if work:
        summary = f"  Итого: {format_minutes(total_min)}"
        earned = money.earnings(hours, hourly_rate)
        if earned is not None:
            summary += f" = {money.format_money(earned)}"
        elif hourly_rate is None:
            summary += " (ставка не задана)"
        lines.append(summary)
        lines.append(
            f"  Среднее за рабочий день: {format_minutes(round(total_min / len(work)))}"
        )
        lines.append("  По дням:")
        for date, minutes, note in work:
            entry = f"    {human_date(date)}: {format_minutes(minutes)}"
            if note:
                entry += f" — {note}"
            lines.append(entry)
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
    hourly_rate: float | None = None,
) -> str:
    """Короткая сводка за сегодня."""
    lines = [f"Данные за {human_date(today())}:", ""]
    lines.append(f"Вес: {weight} кг" if weight is not None else "Вес: не указан")
    lines.append(f"Калории за сегодня: {calories} ккал")

    if exercises:
        lines.append(f"Упражнения: {', '.join(exercises)}")
    else:
        lines.append("Упражнения: не указано")

    earned = money.earnings(work_minutes / 60, hourly_rate) if work_minutes else None
    work_line = f"Рабочее время: {format_minutes(work_minutes)}"
    if earned is not None:
        work_line += f" = {money.format_money(earned)}"
    lines.append(work_line)

    lines.append("Статус: Спите" if is_sleeping else "Статус: Проснулись")
    lines.append("")

    return "\n".join(lines)
