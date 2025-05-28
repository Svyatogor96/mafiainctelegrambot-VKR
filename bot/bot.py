import os
import sys
import aiogram
import sqlalchemy
from asyncmy import version as mysqlasyncver
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.enums import ParseMode
import database.database
from .routers import router as main_router
from .middlewares import (DbSessionMiddleware, AuthorizationMiddlewareMessage, AuthorizationMiddlewareCallback,
                          CSchedulerMiddleware, CSUAuthorizationMiddlewareMessage, CSUAuthorizationMiddlewareCallback,
                          CThrottlingMiddlewareMessage, CThrottlingMiddlewareCallback, UpdateAdmins)
from database.database import *
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import logging

from .version import __version

MafiaBot = Bot(token=GlobalSettings.BOT_TOKEN,
               default=DefaultBotProperties(parse_mode=ParseMode.HTML))

MafiaBot.my_admins_list = []
MafiaBotDispatcher = Dispatcher()
Scheduler = AsyncIOScheduler()

MafiaBotDispatcher.update.middleware(middleware=DbSessionMiddleware(session_pool=async_session_factory))
MafiaBotDispatcher.update.middleware(middleware=CSchedulerMiddleware(scheduler=Scheduler))

MafiaBotDispatcher.message.middleware(middleware=AuthorizationMiddlewareMessage())
MafiaBotDispatcher.message.middleware(middleware=CSUAuthorizationMiddlewareMessage())
MafiaBotDispatcher.message.middleware(middleware=CThrottlingMiddlewareMessage())

MafiaBotDispatcher.callback_query.middleware(middleware=AuthorizationMiddlewareCallback())
MafiaBotDispatcher.callback_query.middleware(middleware=CSUAuthorizationMiddlewareCallback())
MafiaBotDispatcher.callback_query.middleware(middleware=CThrottlingMiddlewareCallback())

MafiaBotDispatcher.include_router(main_router)


async def on_startup():
    if GlobalSettings.LOGGING:
        logging.getLogger().info('Бот запущен')
    if GlobalSettings.DROP_DB:
        await database.database.init_models()
        await database.database.init_first_data()

    bot_commands = [
        BotCommand(command="/menu", description="Начальное меню"),
        BotCommand(command="/afisha", description="Расписание игр"),
        BotCommand(command="/profile", description="Профиль"),
        BotCommand(command="/help", description="Помощь")
    ]
    await MafiaBot.set_my_commands(commands=bot_commands, scope=BotCommandScopeDefault())

    # Загрузка словаря ведущих игр
    await UpdateAdmins()

    Scheduler.add_job(func=DB_PaymentStatusUpdater, trigger='interval', minutes=15)
    Scheduler.start()

    async with async_session_factory() as session:
        await DB_RestorePayReminder(session=session, apscheduler=Scheduler)
        await DB_RestoreGameStatusSwitcher(session=session, apscheduler=Scheduler)


    await MafiaBot.send_message(chat_id=339947035, text=f'Бот бот запущен. Версия: {__version}\n'
                                                        f'aiogram v. {aiogram.__version__}\n'
                                                        f'aiogram api v. {aiogram.__api_version__}\npython {sys.version}\n'
                                                        f'sqlalchemy v. {sqlalchemy.__version__}\n'
                                                        f'asyncmy v. {mysqlasyncver.__VERSION__}')


async def on_shutdown():
    if GlobalSettings.LOGGING:
        logging.getLogger().warning('Бот останавливается.')
        logging.getLogger().warning('Бот остановлен.')
        await MafiaBot.send_message(chat_id=339947035, text='Бот остановлен.')


async def StartBot() -> None:
    if platform.system() == "Linux":
        if os.path.exists("/opt/MafiaIncTelegramBot/update.info"):
            with open("/opt/MafiaIncTelegramBot/update.info", encoding='utf8') as f:
                message_str: str = ""
                for line in f:
                    message_str += line
                await MafiaBot.send_message(chat_id=339947035, text=message_str)
            os.remove("/opt/MafiaIncTelegramBot/update.info")

        if os.path.exists("/var/log/bot_updater.log"):
            with open("/var/log/bot_updater.log", encoding='utf8') as f:
                for line in f:
                    message_str += line
                await MafiaBot.send_message(chat_id=339947035, text=message_str)

    if GlobalSettings.LOGGING:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s ',
                            stream=sys.stdout)

    await MafiaBot.delete_webhook(drop_pending_updates=True)
    MafiaBotDispatcher.startup.register(on_startup)
    MafiaBotDispatcher.shutdown.register(on_shutdown)
    await MafiaBotDispatcher.start_polling(MafiaBot)
