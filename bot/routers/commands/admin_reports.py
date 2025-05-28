import locale

from aiogram import Router, F, flags
from aiogram.types import CallbackQuery
from aiogram import html
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

import bot.bot
from bot.states import AdminState
from bot.middlewares import AuthorizationGetAdminPerson

from bot.callbacks.cb_registration import AdminCallback
from .admin_commands import GoToMainMenu
from bot.keyboards.admin_keyboards import *

from database.database import *

router = Router(name=__name__)

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')


@flags.authorization(admin_only=True, su_only=False)
async def GoToAdminReportMenu(message: Message, message_text: str, state: FSMContext, edit: bool = False) -> None:
    await AskSelectKBM(message=message, message_text=message_text, state=state, next_state=None, edit=edit,
                       kbm=InlineKeyboard_Admin_Report_Keyboard())


@router.callback_query(AdminCallback.filter(F.action.startswith("ADM_REPORT_")))
@flags.authorization(admin_only=True, su_only=False)
async def CommonAdminReportsHandler(callback: CallbackQuery,
                                    callback_data: AdminCallback,
                                    state: FSMContext,
                                    session: AsyncSession,
                                    apscheduler: AsyncIOScheduler) -> None:
    code: str = callback_data.action.replace("ADM_REPORT_", "")
    match code:
        case "MAIN":
            await GoToAdminReportMenu(message=callback.message, message_text="Основное меню отчётов ведущего.",
                                      state=state, edit=True)
            return
        case "GAMES":
            await ReportGames(callback=callback, state=state, session=session)
            return
        case "PLAYERS":
            await ReportPlayers(callback=callback, state=state, session=session)
            return
        case "PLACES":
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                pass
            await callback.message.answer("Тут наверняка может быть что-то полезное. Какой-нибудь отчёт по "
                                          "местам проведения игр.")
            await GoToAdminReportMenu(message=callback.message, message_text="Отчёты смотреть иногда бывает "
                                                                             "очень интересно.", state=state,
                                      edit=False)
            return
        case "EXIT":
            await GoToMainMenu(message=callback.message, message_text="Главное меню ведущего игр.",
                               state=state, edit=True)
            return


async def ReportGames(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    id_moderator: int = data["id_moderator"]
    Moderator: CModerator | None = await session.get(CModerator, id_moderator)

    Games: list[CGame] = await Moderator.awaitable_attrs.games
    if len(Games) > 0:
        for Game in Games:
            Place: CPlace = await Game.awaitable_attrs.place
            GameType: CGameType = await Game.awaitable_attrs.game_type
            message_text = "********Игра********\n"
            message_text += f"<b>Тип:</b> {GameType.title}\n"
            message_text += f"<b>Дата и время начала:</b> {Game.start_date.strftime('%A, %d %B %Y %H:%M')}\n"
            message_text += f"<b>Место:</b> {Place.title}\n"
            message_text += f"<b>Число мест:</b> {Place.seats}\n"

            Payments: list[CPayment] = await Game.PaymentsWithStatus(["PAY_RESERVED", "PAY_PROVIDED"])
            message_text += f"<b>Записалось игроков:</b> {len(Payments)}\n"

            Payments: list[CPayment] = await Game.PaymentsWithStatus(["PAY_PROVIDED"])
            message_text += f"<b>Фактически игроков:</b> {len(Payments)}\n"
            message_text += f"<b>Стоимость:</b> {Game.price}\n"

            actions_txt = "\n"
            ActionAssociations: list[CGameActionAssociation] = await Game.awaitable_attrs.actions_acc
            for index, ActionAssociation in enumerate(ActionAssociations):
                Action: CAction = await ActionAssociation.awaitable_attrs.action
                actions_txt += f"{index + 1}. {Action.title}\n"
            message_text += f"<b>Акции:</b> {actions_txt}"

            statuses_txt = "\n"
            StatusAssociations: list[CGameStatusAssociation] = await Game.awaitable_attrs.statuses_acc
            for index, StatusAssociation in enumerate(StatusAssociations):
                statuses_txt += (f"{index + 1}. {StatusAssociation.status.title} "
                                 f"({StatusAssociation.assign_date.strftime('%d.%m.%Y %H:%M')})\n")
            message_text += f"<b>Статусы:</b> {statuses_txt}"
            message_text += "\n\n"
            await callback.message.answer(text=message_text)
        await GoToAdminReportMenu(message=callback.message, message_text="Не пора ли выпить чаю?", state=state,
                                  edit=False)
    else:
        await callback.message.answer("Пока нет игр, по которым можно было бы построить отчёт. "
                                      "Надо бы объявить регистрацию на игру.")
        await GoToAdminReportMenu(message=callback.message, message_text="Не пора ли выпить чаю?", state=state,
                                  edit=False)


async def ReportPlayers(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    id_moderator: int = data["id_moderator"]
    Moderator: CModerator | None = await session.get(CModerator, id_moderator)
    City: CCity = await Moderator.City

    Persons: list[CPerson] = await DB_GetPersonListOfCityId(session=session, id_city= Moderator.id_city)

    if len(Persons) > 0:
        message_text = f"Игроки г. {City.name}\n"
        count: int = 0
        for index, Person in enumerate(Persons):
            count += 1
            Telegram: CTelegram | None = await Person.MainTelegram
            Phones: list[CPhone] = await Person.awaitable_attrs.phones
            PhoneNumber: str = "Нет данных"

            if len(Phones) > 0:
                PhoneNumber = Phones[0].phone_number

            html_user_link: str | None = None

            if Telegram is not None and Telegram.telegram_name is not None:
                html_user_link = html.link(value=Person.FormatNameFamily,
                                           link=html.quote(f'https://t.me/{Telegram.telegram_name}'))

            if Telegram is not None and Telegram.telegram_url is not None and html_user_link is None:
                html_user_link = html.link(value=Person.FormatNameFamily, link=html.quote(Telegram.telegram_url))

            if Telegram is not None and Telegram.telegram_id is not None and html_user_link is None:
                html_user_link = html.link(value=Person.FormatNameFamily,
                                           link=html.quote(f'tg://user?id={Telegram.telegram_id}'))
            if html_user_link is None:
                message_text += f"{index + 1}. {Person.FormatNameFamily} ("
            else:
                message_text += f"{index + 1}. {html_user_link} ("
            Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
            for nn_index, Nickname in enumerate(Nicknames):
                if nn_index < len(Nicknames) - 1:
                    message_text += f"{Nickname.name}, "
                else:
                    message_text += f"{Nickname.name}"
            message_text += f") {PhoneNumber}\n"
            if count >= 20:
                await callback.message.answer(text=message_text)
                message_text = ""
                count = 0
        await callback.message.answer(text=message_text)
    else:
        await callback.message.answer(text="Пока ни один игрок не зарегистрирован.")

    await GoToAdminReportMenu(message=callback.message, message_text="Не пора ли выпить чаю?", state=state,
                              edit=False)
