from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from aiogram.dispatcher.flags import get_flag
from aiogram.types import Message, TelegramObject
from database import async_session_factory, DB_GetAllModerators, CModerator, CPerson, CTelegram

ADMINS: dict[int, dict[int, list[int]]] = {}


def AuthorizationGetAdminPerson(telegram_id: int) -> dict[int, list[int]] | None:
    if telegram_id in ADMINS:
        return ADMINS[telegram_id]
    else:
        return None


async def UpdateAdmins():
    global ADMINS
    ADMINS = {}
    async with async_session_factory() as session:
        ModeratorsList: list[tuple[CModerator, CPerson, CTelegram]] = await DB_GetAllModerators(session=session)
        for Moderator, Person, Telegram in ModeratorsList:
            if Telegram.telegram_id not in ADMINS:
                ADMINS[Telegram.telegram_id] = {Person.id: [Moderator.id]}
            else:
                _person = ADMINS[Telegram.telegram_id]
                _person[Person.id].append(Moderator.id)


def PersonIsAdmin(id_person: int) -> bool:
    for key, person_dict in ADMINS.items():
        for p_id, m_id in person_dict.items():
            if p_id == id_person:
                return True
    return False


class AuthorizationMiddlewareMessage(BaseMiddleware):
    """
    Промежуточный слой для проверки авторизованного пользователя
    """

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        authorization = get_flag(data, "authorization")
        if authorization is not None:
            if authorization["admin_only"]:
                if event.from_user.id in ADMINS:
                    return await handler(event, data)
                else:
                    await event.answer(text=f"Вы не авторизованы выполнять эту операцию. "
                                            f"{event.from_user.username} ({event.from_user.id})")
                    return None
            else:
                return await handler(event, data)
        else:
            return await handler(event, data)


class AuthorizationMiddlewareCallback(BaseMiddleware):
    """
    Промежуточный слой для проверки авторизованного пользователя
    """

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: CallbackQuery,
            data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        authorization = get_flag(data, "authorization")
        if authorization is not None:
            if authorization["admin_only"]:
                if event.from_user.id in ADMINS:
                    return await handler(event, data)
                else:
                    await event.message.answer(text=f"Вы не авторизованы выполнять эту операцию. "
                                                    f"{event.from_user.username} ({event.from_user.id})")
                    return None
            else:
                return await handler(event, data)
        else:
            return await handler(event, data)


class CSUAuthorizationMiddlewareMessage(BaseMiddleware):
    """
    Промежуточный слой для проверки авторизованного пользователя
    """

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        authorization = get_flag(data, "authorization")
        if authorization is not None:
            if authorization["su_only"]:
                username: str = event.from_user.username
                if username == "avkushnarenko" or username == "mafia_inc_boss" or username == "shiro_96":
                    return await handler(event, data)
                else:
                    await event.answer(text=f"Вы не Босс, извините. "
                                            f"{event.from_user.username} ({event.from_user.id})")
                    return None
            else:
                return await handler(event, data)
        else:
            return await handler(event, data)


class CSUAuthorizationMiddlewareCallback(BaseMiddleware):
    """
    Промежуточный слой для проверки авторизованного пользователя
    """

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: CallbackQuery,
            data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        authorization = get_flag(data, "authorization")
        if authorization is not None:
            if authorization["su_only"]:
                username: str = event.from_user.username
                if username == "avkushnarenko" or username == "mafia_inc_boss" or username == "shiro_96":
                    return await handler(event, data)
                else:
                    await event.message.answer(text=f"Вы не Босс, извините. "
                                                    f"{event.from_user.username} ({event.from_user.id})")
                    return None
            else:
                return await handler(event, data)
        else:
            return await handler(event, data)
