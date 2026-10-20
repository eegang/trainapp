"""Создание объектов Bot и Dispatcher, подключение защиты от посторонних."""

import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from app.access import AllowList, OwnerOnly

logger = logging.getLogger(__name__)

config.validate()

ALLOWED = AllowList(config.ALLOWED_USER_IDS)

storage = MemoryStorage()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

dp.message.outer_middleware(OwnerOnly(ALLOWED))
dp.callback_query.outer_middleware(OwnerOnly(ALLOWED))
