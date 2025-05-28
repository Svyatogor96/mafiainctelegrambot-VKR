from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from cachetools import TTLCache


class CThrottlingMiddlewareMessage(BaseMiddleware):
    cache: TTLCache = TTLCache(maxsize=10_000, ttl=1)

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.id in self.cache:
                return await event.answer(text="Зачем так торопиться? Мы успеем.")
            else:
                self.cache[event.chat.id] = None
            return await handler(event, data)


class CThrottlingMiddlewareCallback(BaseMiddleware):
    cache: TTLCache = TTLCache(maxsize=10_000, ttl=1)

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: CallbackQuery,
            data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            if event.from_user.id in self.cache:
                return await event.answer(text="Классная кнопка, правда? Но зачем так много её нажимать?")
            else:
                self.cache[event.from_user.id] = None
            return await handler(event, data)
