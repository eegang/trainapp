"""Точка входа. Запуск: python main.py"""

import asyncio
import logging

from aiogram.types import BotCommand

from app import handlers
from app.bot import bot, dp
from config import LOG_LEVEL
from db.schema import init_db

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Запуск бота...")

    await init_db()
    handlers.register(dp)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
        ]
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
