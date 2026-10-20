"""Формирование текстового отчёта для выгрузки и для сводки за сегодня."""

from __future__ import annotations

from datetime import datetime

from app.dates import human_date


def format_duration(minutes: int | None) -> str:
    """Минуты -> «7 ч 30 мин»."""
    if minutes is None:
        return "—"
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"


def build_report(data: dict) -> str:
    """Собирает текстовый отчёт по данным за последние 30 дней."""
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append("ОТЧЁТ ЗА ПОСЛЕДНИЕ 30 ДНЕЙ")
    lines.append(f"Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)
    lines.append("")

    lines.append("[ПРОГРЕСС ВЕСА]")
    current = data.get("current_weight")
    if current:
        lines.append(f"Текущий вес: {current[0]} кг (обновлён {human_date(current[1])})")
    else:
        lines.append("Вес: не указан")

    history = data.get("weight_history") or []
    lines.append("Последние записи веса:")
    if history:
        for weight, date_str in history[:7]:
            lines.append(f"  {human_date(date_str)}: {weight} кг")
    else:
        lines.append("  (нет данных)")
    lines.append("")

    meals = data.get("meals") or []
    lines.append(f"[ПРИЁМЫ ПИЩИ] — {len(meals)} записей")
    if meals:
        for date_str, calories in meals:
            lines.append(f"  {human_date(date_str)}: {calories} ккал")
    else:
        lines.append("  (нет данных)")
    lines.append("")

    exercises = data.get("exercises") or []
    lines.append(f"[УПРАЖНЕНИЯ] — {len(exercises)} записей")
    if exercises:
        for date_str, description in exercises:
            lines.append(f"  {human_date(date_str)}: {description}")
    else:
        lines.append("  (нет данных)")
    lines.append("")

    sleeps = data.get("sleeps") or []
    lines.append(f"[СОН] — {len(sleeps)} сеансов")
    if sleeps:
        for start, end, duration in sleeps:
            if end is None:
                lines.append(f"  {start} — ещё спит")
            else:
                lines.append(f"  {start} → {end}  ({format_duration(duration)})")
    else:
        lines.append("  (нет данных)")
    lines.append("")

    lines.append("=" * 50)
    lines.append("ПРОМПТ ДЛЯ GPT:")
    lines.append("Проанализируй эти данные о тренировках, питании и сне за 30 дней.")
    lines.append("Дай рекомендации по питанию, режиму тренировок и качеству сна.")
    lines.append("Выдели тренды и предложи план улучшений.")
    lines.append("=" * 50)

    return "\n".join(lines)


def build_today_summary(
    *,
    weight: float | None,
    calories: int,
    exercises: list[str],
    is_sleeping: bool,
) -> str:
    """Короткая сводка за сегодня."""
    lines = [f"Данные за {human_date(datetime.now().strftime('%Y-%m-%d'))}:", ""]
    lines.append(f"Вес: {weight} кг" if weight is not None else "Вес: не указан")
    lines.append(f"Калории за сегодня: {calories} ккал")

    if exercises:
        lines.append(f"Упражнения: {', '.join(exercises)}")
    else:
        lines.append("Упражнения: не указано")

    lines.append("Статус: Спите" if is_sleeping else "Статус: Проснулись")
    lines.append("")

    return "\n".join(lines)
