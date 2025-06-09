from datetime import datetime

import sqlalchemy.exc
from aiogram import Router, types, html
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Chat
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import bot.bot
from bot.states import UserState
from backendapi.database import *

from subprocess import Popen

import logging

router = Router(name=__name__)

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')

version: str = "1.0.43"

UPDATE_MESSAGE: str = (f"Уважаемые пользователи! Наш бот обновлён до версии {version}. "
                       f"В этой версии мы улучшили процедуру регистрации. Даже телефон теперь можно передать из "
                       f"профиля Telegram, дав соответсвующее разрешение. "
                       f"Исправили ошибки и повысили стабильность работы: внедрили анти спам фильтр, обрабатывающий "
                       f"многократные нажатия кнопок и ввода команд. Это должно исключить случайные многократные "
                       f"записи на игру. Сделали улучшения для ведущих игр.")


@router.message(Command("info"))
async def DefaultMessageHandler(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    ID: int = message.from_user.id
    answer_txt: str = (f"Telegram ID : {ID}\n"
                       f"Имя пользователя Telegram: {message.from_user.username}\n"
                       f"Полное имя Telegram: {message.from_user.full_name}\n"
                       f"Первое имя Telegram : {message.from_user.first_name}\n"
                       f"Последнее имя Telegram : {message.from_user.last_name}\n"
                       f"Премиум? : {message.from_user.is_premium}\n"
                       f"Ссылка Telegram : {html.quote(message.from_user.url)}\n"
                       f"Код языка Telegram : {message.from_user.language_code}\n"
                       f"state : {await state.get_state()}\n"
                       f"data : {await state.get_data()}\n")
    try:
        Telegram: CTelegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=ID)
        answer_txt += f"CTelegram: ({Telegram.id}, {Telegram.telegram_name}, id_person: {Telegram.id_person})"
    except sqlalchemy.exc.MultipleResultsFound:
        answer_txt += "CTelegram : Ошибка дубликата записи"
        await message.answer(text=answer_txt)
        return
    await message.answer(text=answer_txt)


@router.message(Command("reset"))
async def Reset(message: types.Message, session: AsyncSession, state: FSMContext) -> None:
    ID: int = message.from_user.id
    NOW: datetime = datetime.now()
    STR_NOW: str = NOW.strftime('%a, %Y-%m-%d %H:%M')
    str_state: str | None = await state.get_state()
    data = await state.get_data()
    await bot.bot.MafiaBot.send_message(chat_id=438204704,
                                        text=f"[{STR_NOW}] Пользователь запросил команду сброса состояния\n"
                                             f"id: {ID}\n"
                                             f"state: {str_state}\n"
                                             f"data: {data}\n")
    await state.clear()
    data = await state.get_data()

    NOW = datetime.now()
    STR_NOW = NOW.strftime('%a, %Y-%m-%d %H:%M')

    Telegram: CTelegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=ID)
    if Telegram is not None:
        data["telegram_id"] = Telegram.telegram_id
        data["id_telegram"] = Telegram.id
        Person: CPerson = await Telegram.Person
        if Person is not None:
            data["id_person"] = Person.id
            City: CCity = await Person.awaitable_attrs.city
            if City is not None:
                data["id_city"] = City.id

    await state.set_state(UserState.start)
    await state.set_data(data=data)
    str_state = await state.get_state()
    await bot.bot.MafiaBot.send_message(chat_id=438204704,
                                        text=f"[{STR_NOW}] Загружено\ndate: {data}\n"
                                             f"state: {str_state}\n")


@router.message(Command("log"))
async def get_log(message: types.Message, session: AsyncSession, state: FSMContext) -> None:
    UID: int = 438204704
    if message.from_user.id == UID:
        if platform.system() == "Linux":
            line_list: list[str] = []
            with open('/home/avkushnarenko/mafia-bot.log', encoding='utf8') as f:
                for line in f:
                    line_list.append(line)
                    if len(line_list) == 20:
                        await bot.bot.MafiaBot.send_message(chat_id=UID, text=''.join(line_list))
                        line_list.clear()


@router.message(Command("update"))
async def get_log(message: types.Message, session: AsyncSession, state: FSMContext) -> None:
    UID: int = 438204704
    if message.from_user.id == UID:
        if platform.system() == "Linux":
            Popen(['python3', '/opt/MafiaIncTelegramBot/elevator.py'], user='avkushnarenko')


@router.message(Command("update_message"))
async def get_log(message: types.Message, session: AsyncSession, state: FSMContext) -> None:
    UID: int = 438204704
    if message.from_user.id == UID:
        query = select(CTelegram).where(CTelegram.telegram_id is not None)
        result = await session.execute(query)
        Telegrams: list[CTelegram] = list(result.scalars().all())
        for Telegram in Telegrams:
            try:
                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=UPDATE_MESSAGE)
            except TelegramForbiddenError:
                await bot.bot.MafiaBot.send_message(chat_id=UID, text=f"Пользователь {Telegram.telegram_id} "
                                                                      f"{Telegram.telegram_name} забанил бот.")

