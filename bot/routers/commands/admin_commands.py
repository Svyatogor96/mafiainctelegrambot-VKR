from aiogram import Router, types, F, flags
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, StateFilter
import bot.bot
from bot.callbacks import UserCallback
from bot.keyboards.admin_keyboards import *
from bot.states import AdminState, UserState

from bot.middlewares import AuthorizationGetAdminPerson
from backendapi.database import *
import locale

router = Router(name=__name__)

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')


async def DebugMessage(message: str) -> None:
    await bot.bot.MafiaBot.send_message(chat_id=438204704, text=message)


async def LoggedIn(state: FSMContext) -> bool:
    data = await state.get_data()
    return "logged_in" in data and data["logged_in"] is True


async def DropState(state: FSMContext) -> None:
    await state.set_state(AdminState.start)


@flags.authorization(admin_only=True, su_only=False)
async def AdminMainMenu(chat_id: int, message_text: str) -> None:
    await bot.bot.MafiaBot.send_message(chat_id=chat_id, text=message_text,
                                        reply_markup=InlineKeyboard_Admin_Keyboard())


@flags.authorization(admin_only=True, su_only=False)
async def GoToMainMenu(message: types.Message, message_text: str, state: FSMContext, edit: bool = False) -> None:
    await DropState(state)
    if edit:
        try:
            await message.edit_text(text=message_text, reply_markup=InlineKeyboard_Admin_Keyboard())
        except TelegramBadRequest:
            await message.answer(text=message_text, reply_markup=InlineKeyboard_Admin_Keyboard())
    else:
        await message.answer(text=message_text, reply_markup=InlineKeyboard_Admin_Keyboard())


@router.callback_query(UserCallback.filter(F.action.__eq__("ADMIN_LOG_IN")))
async def LoginAdmin(callback: CallbackQuery,
                     callback_data: UserCallback,
                     state: FSMContext,
                     session: AsyncSession):
    # нужно придумать элегантный способ входа админ-панель
    telegram_id: int = int(callback.message.chat.id)
    _adm_persons = AuthorizationGetAdminPerson(telegram_id)
    ids_person = list(_adm_persons.keys())
    if len(ids_person) > 1:
        print("При обработке входа в админ-меню обнаружено нарушение: более 1 привязки CPerson к одному telegram_id!")
        print(*_adm_persons, sep="\n")
        await callback.message.answer("Отказ допуска в админ-панель.")
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        return
    list_of_ids = _adm_persons[ids_person[0]]
    Moderators: list[CModerator] = await DB_GetModeratorsByIdList(session=session, list_of_ids=list_of_ids)
    buttons: dict[str, AdminCallback] = {}
    for Moderator in Moderators:
        City = await Moderator.City
        buttons[City.name] = AdminCallback(action="CHOOSE_CITY_IN_LOGIN",
                                           id_admin=int(telegram_id),
                                           id_city=City.id,
                                           id_moderator=Moderator.id)
    kbm = InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=buttons)
    await callback.message.answer(text="Выберите город для логина", reply_markup=kbm)
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


async def LogoutAdmin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_data(data={})
    await state.set_state(UserState.start)
    await callback.message.answer(text="Вы покинули режим ведущего игр.")
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


@router.message(StateFilter(AdminState), Command("profile", "menu", "afisha", "start"))
async def AdmProfile(message: types.Message, state: FSMContext) -> None:
    await GoToMainMenu(message=message, message_text="Основное меню ведущего игр.", state=state, edit=False)


@router.callback_query(AdminCallback.filter(F.action.__eq__("CHOOSE_CITY_IN_LOGIN")))
@flags.authorization(admin_only=True, su_only=False)
async def AdminLogin_ChooseCity(callback: CallbackQuery,
                                callback_data: AdminCallback,
                                state: FSMContext,
                                session: AsyncSession) -> None:
    id_moderator: int = int(callback_data.id_moderator)
    Moderator: CModerator | None = await session.get(CModerator, id_moderator)

    await state.set_state(AdminState.start)
    data = await state.get_data()
    data["id_city"] = Moderator.id_city
    data["id_moderator"] = Moderator.id
    data["logged_in"] = True
    City: CCity = await Moderator.City

    await state.update_data(data=data)
    await AdminMainMenu(chat_id=callback.message.chat.id, message_text=f"Вы вошли в панель ведущего игр в городе "
                                                                       f"{City.name}. Выберите действие.")
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


@router.callback_query(AdminCallback.filter(F.action.startswith("ADMIN_")))
@flags.authorization(admin_only=True, su_only=False)
async def Admin_MainCallbackHandler(callback: CallbackQuery,
                                    callback_data: AdminCallback,
                                    state: FSMContext,
                                    session: AsyncSession, apscheduler: AsyncIOScheduler) -> None:
    code: str = callback_data.action.replace("ADMIN_", "")
    match code:
        case "GAME_LIST":
            await GameSelector(callback=callback, action="ADMIN_PLAYER_LIST", state=state, session=session,
                               message_text="Выберите игру.")
            return
        case "PLAYER_LIST":
            await PlayerSelector(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "CONFIRM_PAYMENT":
            await ConfirmPayment(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "PLAYER_EDITOR":
            await GameSelector(callback=callback, action="ADMIN_PLAYER_EDITOR_SHOW", state=state, session=session,
                               message_text="Выберите игру.")
            return
        case "BROADCAST_MESSAGE_PREPARE":
            await Ask(message=callback.message, message_text="Введите текст сообщения (не более 1000 символов)",
                      state=state, next_state=AdminState.message_text, edit=True, action_code="ADMIN_CANCEL")
            return
        case "CONFIRM_BROADCAST_MESSAGE":
            await ConfirmBroadcastMessage(message=callback.message, session=session, state=state, edit=True)
            return
        case "SEND_BROADCAST_MESSAGE":
            await SendBroadcastMessage(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "EDIT_BROADCAST_MESSAGE":
            return
        case "PLAYER_EDITOR_SHOW":
            await GoPlayerEditor(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "DELETE_PLAYER":
            await AddPlayerToDelete(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "APPLY_DELETE_PLAYER":
            await DoDeletePlayer(callback=callback, callback_data=callback_data, state=state,
                                 session=session, apscheduler=apscheduler)
            return
        case "CANCEL":
            await GoToMainMenu(message=callback.message, message_text="Главное меню ведущего игр.",
                               state=state, edit=True)
            return
        case "LOGOUT":
            await LogoutAdmin(callback=callback, state=state)
            return

"""
Диалог выбора игры, запись на которую объявлена (используется при выборе отмены игры, редактирования  игры, закрытия записи на игру)
"""
async def GameSelector(callback: CallbackQuery, action: str, state: FSMContext, session: AsyncSession,
                       message_text: str) -> None:
    """
    :param callback: Данные
    :param action: Вид действия
    :param state: Состояние пользователя
    :param session: Сессия БД
    :param message_text: Текст сообщения
    :return:
    """
    data = await state.get_data()
    id_moderator: int  = int(data["id_moderator"])
    id_city: int = int(data["id_city"])
    Games: list[CGame] = await DB_GetGamesOfModeratorAfterDate(session=session,
                                                                   id_moderator=id_moderator,
                                                                   id_city=id_city,
                                                                   after_date=datetime.today())
    if len(Games) > 0:
        buttons = {str(Game): AdminCallback(action=action, id_game=Game.id) for Game in Games}
        buttons["Отмена"] = AdminCallback(action="ADMIN_CANCEL", id_game=0)
        await AskSelect(message=callback.message, message_text=message_text, next_state=None, state=state,
                            cb_data_dict=buttons, edit=True)
    else:
        await GoToMainMenu(message=callback.message, message_text="Нет подходящих игр.", state=state, edit=True)


async def PlayerSelector(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext,
                         session: AsyncSession):
    id_game: int = int(callback_data.id_game)
    Game: CGame | None = await session.get(CGame, id_game)

    buttons: dict[str, AdminCallback] = {}
    Payments: list[CPayment] = await Game.awaitable_attrs.payments
    Players: dict[int, CPlayer] = {}

    for Payment in Payments:
        Status: CStatus = await Payment.awaitable_attrs.status
        Player: CPlayer = await Payment.awaitable_attrs.player
        if Status.code == "PAY_RESERVED":
            if Player.id not in Players:
                Players[Player.id] = Player
    for Key, Player in Players.items():
        _payments: list[CPayment] = await Player.awaitable_attrs.payments
        count = len(_payments)
        if count > 1:
            buttons[f"{Player.nickname.name} (+{count - 1})"] = AdminCallback(action="ADMIN_CONFIRM_PAYMENT",
                                                                              id_player=Player.id)
        else:
            buttons[f"{Player.nickname.name}"] = AdminCallback(action="ADMIN_CONFIRM_PAYMENT",
                                                               id_player=Player.id)
    buttons["Отмена"] = AdminCallback(action="ADMIN_CANCEL")
    await AskSelect(message=callback.message, message_text="Выберите игрока для подтверждения оплаты.",
                    cb_data_dict=buttons, next_state=None, state=state, edit=True)


async def ConfirmPayment(callback: CallbackQuery, callback_data: AdminCallback,
                         state: FSMContext, session: AsyncSession):
    id_player: int = int(callback_data.id_player)

    result, error = await DB_ProvidePaymentsOfPlayer(session=session, id_player=id_player)
    if result:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await NotifyPlayerSuccessfulPaymentPlayer(session=session, id_player=id_player)
        await GoToMainMenu(message=callback.message, message_text="Оплата успешно подтверждена.",
                           state=state, edit=True)

    else:
        await GoToMainMenu(message=callback.message, message_text=f"Не удалось подтвердить оплату: {error}",
                           state=state, edit=True)


async def NotifyPlayerSuccessfulPayment(session: AsyncSession, id_payment: int):
    Payment: CPayment | None = await session.get(CPayment, id_payment)
    await NotifyPlayerSuccessfulPaymentPlayer(session=session, id_player=Payment.id_player)


async def NotifyPlayerSuccessfulPaymentPlayer(session: AsyncSession, id_player: int):
    Player: CPlayer | None = await session.get(CPlayer, id_player)
    Game: CGame = await Player.awaitable_attrs.game
    Nickname: CNickname = await Player.awaitable_attrs.nickname
    Person: CPerson = await Nickname.awaitable_attrs.person

    Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
    if len(Telegrams) > 0:
        Telegram: CTelegram = Telegrams[0]
        message_text = (f"Благодарим вас за оплату. Ждём на игру {await Game.FormatGameStr}. Данное уведомление "
                        f"является подтверждением вами оплаты.")
        await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_text)


async def Report(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
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
        await GoToMainMenu(message=callback.message, message_text="Не пора ли выпить чаю?", state=state,
                           edit=False)
    else:
        await callback.message.answer("Пока нет игр, по которым можно было бы построить отчёт.")
        await GoToMainMenu(message=callback.message, message_text="Надо бы объявить регистрацию на игру.", state=state,
                           edit=False)


async def GoPlayerEditor(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext,
                         session: AsyncSession):
    id_game: int = int(callback_data.id_game)

    if id_game == 0:
        await GoToMainMenu(message=callback.message, message_text="Главное меню админа", state=state, edit=True)
        return

    Game: CGame | None = await session.get(CGame, id_game)

    Players: list[CPlayer] = await Game.awaitable_attrs.actual_players
    message_text = ""
    players_dictionary: dict[str, AdminCallback] = {}
    if len(Players) > 0:
        message_text += "Выберите игроков для исключения.\n"
        for index, Player in enumerate(Players):
            Nickname: CNickname = await Player.awaitable_attrs.nickname
            Name = Nickname.name
            Payments: list[CPayment] = await Player.awaitable_attrs.payments
            if len(Payments) > 1:
                CountPays = 0
                for Payment in Payments:
                    PaymentStatus: CStatus = await Payment.awaitable_attrs.status
                    if PaymentStatus.code == "PAY_PROVIDED":
                        CountPays += 1
                Name += f" (+{CountPays - 1})"
            players_dictionary[Name] = AdminCallback(action="ADMIN_DELETE_PLAYER", id_game=id_game, id_player=Player.id)
            message_text += f"{index + 1}. {Name}\n"
        players_dictionary["Отмена"] = AdminCallback(action="ADMIN_CANCEL")
        await AskSelect(message=callback.message, message_text=message_text,
                        state=state, cb_data_dict=players_dictionary, edit=True, next_state=None)
    else:
        await GameSelector(callback=callback, action="ADMIN_PLAYER_EDITOR_SHOW", state=state, session=session,
                           message_text="Эту игру пока никто не оплатил.")


async def AddPlayerToDelete(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext,
                            session: AsyncSession):
    id_player: int = callback_data.id_player
    Player: CPlayer | None = await session.get(CPlayer, id_player)
    Nickname: CNickname = await Player.awaitable_attrs.nickname
    buttons = {"Да": AdminCallback(action="ADMIN_APPLY_DELETE_PLAYER", id_player=id_player),
               "Нет": AdminCallback(action="ADMIN_APPLY_DELETE_PLAYER", id_player=0)}

    await AskSelect(message=callback.message,
                    message_text=f"Вы уверены, что хотите удалить игрока {Nickname.name} из списка?",
                    next_state=None,
                    state=state,
                    cb_data_dict=buttons, edit=True)


async def DoDeletePlayer(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext,
                         session: AsyncSession, apscheduler: AsyncIOScheduler):
    id_player: int = int(callback_data.id_player)
    if id_player == 0:
        await GoToMainMenu(message=callback.message, message_text="Основное меню ведущего игр.", state=state, edit=True)
    else:
        Player: CPlayer | None = await session.get(CPlayer, id_player)
        await DB_DeletePlayer(session=session, id_player=id_player, apscheduler=apscheduler)
        await callback.message.answer(text=f"Игрок {Player.nickname.name} удалён из игры.")
        await GoToMainMenu(message=callback.message, message_text="Основное меню ведущего игр.",
                           state=state, edit=False)


@router.message(AdminState.message_text)
@flags.authorization(admin_only=True, su_only=False)
async def BroadCastMessage(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    data["message"] = {"message": message.text}
    await state.set_data(data=data)
    await Ask(message=message, message_text="Добавьте иллюстрацию", next_state=AdminState.message_pic,
              state=state, action_code="ADMIN_CONFIRM_BROADCAST_MESSAGE", edit=True)


@router.message(F.photo, AdminState.message_pic)
@flags.authorization(admin_only=True, su_only=False)
async def BroadCastMessagePicture(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_info: dict = data["message"]
    message_info["message_file_id"] = message.photo[-1].file_id
    await state.set_data(data=data)
    await state.set_state(AdminState.message_confirm)
    await ConfirmBroadcastMessage(message=message, state=state, session=session, edit=True)


@flags.authorization(admin_only=True, su_only=False)
async def ConfirmBroadcastMessage(message: types.Message, state: FSMContext, session: AsyncSession,
                                  additional_answer_text: str = None, edit: bool = False) -> None:
    data = await state.get_data()
    message_info: dict = data["message"]
    kbm = {"Отправить": AdminCallback(action="ADMIN_SEND_BROADCAST_MESSAGE"),
           "Редактировать": AdminCallback(action="ADMIN_EDIT_BROADCAST_MESSAGE"),
           "Отмена": AdminCallback(action="ADMIN_CANCEL")}

    if "message_file_id" in message_info:
        await message.answer_photo(photo=message_info["message_file_id"],
                                   caption=message_info["message"],
                                   reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))
    else:
        await message.answer(text=message_info["message"],
                             reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))


async def SendBroadcastMessage(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext,
                               session: AsyncSession):
    data = await state.get_data()
    message_info: dict = data["message"]
    id_moderator: int = data["id_moderator"]
    Moderator: CModerator | None = await session.get(CModerator, id_moderator)
    MPerson: CPerson = await Moderator.Person
    MTelegrams: list[CTelegram] = await MPerson.awaitable_attrs.telegrams
    MTelegram: CTelegram = MTelegrams[0]

    await state.set_state(AdminState.start)

    Persons: list[CPerson] = await DB_GetPersonListOfCityId(session=session, id_city=Moderator.id_city)

    for Person in Persons:
        Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
        Telegram: CTelegram = Telegrams[0]
        try:
            if "message_file_id" in message_info:
                await bot.bot.MafiaBot.send_photo(chat_id=Telegram.telegram_id, photo=message_info["message_file_id"],
                                                  caption=message_info["message"])
            else:
                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_info["message"])
        except TelegramForbiddenError:
            await bot.bot.MafiaBot.send_message(chat_id=MTelegram.telegram_id,
                                                text=f"Пользователь "
                                                     f"{Telegram.telegram_id} {Telegram.telegram_name} "
                                                     f"заблокировал бота и не получит сообщение.")
    await GoToMainMenu(message=callback.message, message_text="Сообщение отправлено.", state=state, edit=False)
