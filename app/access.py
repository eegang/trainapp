"""Личный бот: отвечаем только владельцу (ALLOWED_USER_IDS).

Посторонним не отвечаем вообще — даже «доступ запрещён», чтобы бот не
отвечал на чужие сообщения и не подтверждал своё существование.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class AllowList:
    """Множество разрешённых user_id. Можно дополнять на лету (нужно тестам)."""

    def __init__(self, user_ids: Iterable[int] = ()) -> None:
        self._ids = set(user_ids)

    def allow(self, user_id: int) -> None:
        self._ids.add(user_id)

    def __contains__(self, user_id: object) -> bool:
        return user_id in self._ids


class OwnerOnly(BaseMiddleware):
    """Пропускает апдейт дальше только для разрешённых пользователей."""

    def __init__(self, allowlist: AllowList) -> None:
        self.allowlist = allowlist

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id not in self.allowlist:
            logger.warning("игнорирую апдейт от постороннего user_id=%s", getattr(user, "id", None))
            return None
        return await handler(event, data)
