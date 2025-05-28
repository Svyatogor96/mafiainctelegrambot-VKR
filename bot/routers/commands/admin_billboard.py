from typing import Any
from aiogram import html
from aiogram.utils.formatting import Bold, as_list, as_marked_section, as_key_value, HashTag
from aiogram import Router, types, F, flags
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import StateFilter

from dateutil.parser import *

import bot.bot
from bot.keyboards.admin_keyboards import *
from bot.states import AdminState
from bot.callbacks import UserCallback
from database.database import *
from .admin_commands import GoToMainMenu
from bot.keyboards import IKBM_User_ByDict_UserCallbackData

router = Router(name=__name__)

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')


async def DebugMessage(message: str) -> None:
    await bot.bot.MafiaBot.send_message(chat_id=339947035, text=f"{__name__}:  {message}")


async def dict_to_string(state: FSMContext, Key: str) -> str | None:
    data = await state.get_data()
    if Key in data:
        dictionary = data[Key]
        if isinstance(dictionary, dict):
            if len(dictionary):
                result = ""
                for index, (key, value) in enumerate(dictionary.items()):
                    result += f"{index + 1}. {value}\n"
                return result
            else:
                return None
        else:
            return None
    else:
        return None


async def DropState(state: FSMContext) -> None:
    data = await state.get_data()
    if "new" in data:
        del data["new"]
    if "id_game" in data:
        del data["id_game"]
    if "id_place" in data:
        del data["id_place"]
    if "id_game_type" in data:
        del data["id_game_type"]
    if "game_start" in data:
        del data["game_start"]
    if "price" in data:
        del data["price"]
    if "game_actions" in data:
        del data["game_actions"]
    if "poster" in data:
        del data["poster"]
    await state.set_data(data=data)
    await state.set_state(AdminState.start)

"""
Подготовка к состоянию "Новая игра" (создание афиши)
"""
async def set_new(state: FSMContext) -> None:
    data = await state.get_data()
    data["new"] = True
    data["id_game"] = 0
    data["id_place"] = 0
    data["id_game_type"] = 0
    data["game_start"] = datetime.now()
    data["price"] = 0
    data["game_actions"] = {}
    data["poster"] = "0"
    await state.set_data(data=data)


"""
Подготовка к состоянию редактирования объявленной игры
"""
async def set_not_new(state: FSMContext, id_game: int, session: AsyncSession) -> None:
    data = await state.get_data()
    data["new"] = False
    data["id_game"] = id_game
    Game: CGame | None = await session.get(CGame, id_game)
    data["id_game_type"] = Game.id_game_type
    data["id_place"] = Game.id_place
    data["game_start"] = Game.start_date
    data["price"] = Game.price
    Properties: CGameProperties = await Game.awaitable_attrs.properties
    data["poster"] = Properties.telegram_file_id

    GameStatusAssociations: list[CGameStatusAssociation] = await Game.awaitable_attrs.statuses_acc
    game_status: dict[datetime, int] = {}
    if len(GameStatusAssociations) > 0:
        for Association in GameStatusAssociations:
            Status: CStatus = Association.status
            status_date = Association.assign_date
            game_status[status_date] = Status.id
    data["game_status"] = game_status

    game_actions: dict[int, str] = {}
    GameActionAssociations: list[CGameActionAssociation] = await Game.awaitable_attrs.actions_acc
    if len(GameActionAssociations) > 0:
        for Association in GameActionAssociations:
            Action: CAction = Association.action
            game_actions[Action.id] = Action.title
    data["game_actions"] = game_actions
    await state.set_data(data=data)


"""
Проверка состояния. Новая игра или редактирование старой.
"""
async def is_new(state: FSMContext) -> bool:
    data = await state.get_data()
    return "new" in data and data["new"] is True


async def GameTypesButtons(id_place: int, session: AsyncSession) -> dict[int, str]:
    Place: CPlace | None = await session.get(CPlace, id_place)
    associations: list[CPlaceGameTypeAssociation] = await Place.awaitable_attrs.game_types_acc
    Types: dict[int, str] = {}
    if len(associations) > 0:
        for association in associations:
            GameType: CGameType = association.game_type
            Types[GameType.id] = GameType.title
    else:
        Types = await DB_GetAllGameTypesAsDict(session=session)
    return Types


async def GamePlacesButtons(id_city: int, session: AsyncSession) -> dict[str, AdminCallback] | None:
    places: list[CPlace] = await DB_GetPlacesByCityID(session=session, id_city=id_city)
    if len(places) > 0:
        result = {place.title: AdminCallback(action="BB_SET_GAME_PLACE", id_place=place.id) for place in places}
        result["Отмена"] = AdminCallback(action="BB_CANCEL", id_place=0)
        return result
    else:
        return None


async def GameActionsButtons(session: AsyncSession,
                             state: FSMContext,
                             action: str,
                             AllButton: bool = False,
                             CancelButton: bool = False,
                             CancelButtonCaption: str = "Отмена",
                             DeleteMode: bool = False
                             ) -> dict[str, AdminCallback]:
    all_actions = await DB_GetAllActions_as_dict(session=session)
    data = await state.get_data()
    game_actions: dict[int, str] = data["game_actions"]
    if DeleteMode:
        result = {value: AdminCallback(action=action, id_action=key) for key, value in game_actions.items()}
    else:
        actions = dict(sorted(dict(all_actions.items() - game_actions.items()).items()))
        result = {title: AdminCallback(action=action, id_action=key) for key, title in actions.items()}
    if AllButton:
        result["Все"] = AdminCallback(action=action, id_action=-1)
    if CancelButton:
        result[CancelButtonCaption] = AdminCallback(action=action, id_action=0)
    return result


@router.callback_query(AdminCallback.filter(F.action.__eq__("BB_CLOSE_GAME_REG_YES") ))
@flags.authorization(admin_only=True, su_only=False)
async def CloseGameRegistration(callback: CallbackQuery,
                                 callback_data: AdminCallback,
                                 state: FSMContext,
                                 session: AsyncSession,
                                 apscheduler: AsyncIOScheduler) -> None:
    data = await state.get_data()
    id_game: int = int(data["id_game"])
    result: tuple[bool, str] = await DB_SetGameStatus(session=session, id_game=id_game, GameStatusCode="GAME_REG_CLOSED")
    if result[0]:
        await callback.message.answer("Запись на игру успешно закрыта")
        await NotifyUsersForGameRegistrationClosed(id_game = id_game, session=session)
    else:
        await callback.message.answer(text=result[1], reply_markup=None)
    await state.set_state(AdminState.start)
    await GoToMainMenu(message=callback.message, message_text="Основное меню", state=state, edit=False)


@router.callback_query(AdminCallback.filter(F.action.__eq__("BB_CLOSE_GAME_REG_NO") ))
@flags.authorization(admin_only=True, su_only=False)
async def NoCloseGameRegistration(callback: CallbackQuery,
                                 callback_data: AdminCallback,
                                 state: FSMContext,
                                 session: AsyncSession,
                                 apscheduler: AsyncIOScheduler) -> None:
    await state.set_state(AdminState.start)
    await GoToMainMenu(message=callback.message, message_text="Основное меню", state=state,  edit=False)


@router.callback_query(AdminCallback.filter(F.action.startswith("BB_")))
@flags.authorization(admin_only=True, su_only=False)
async def CommonBillBoardHandler(callback: CallbackQuery,
                                 callback_data: AdminCallback,
                                 state: FSMContext,
                                 session: AsyncSession,
                                 apscheduler: AsyncIOScheduler) -> None:
    match callback_data.action:
        case "BB_NEW":
            await set_new(state)
            data = await state.get_data()
            id_city: int = int(data["id_city"])
            buttons = await GamePlacesButtons(id_city=id_city, session=session)

            if buttons is not None:
                await AskSelect(message=callback.message, message_text="Выберите место проведения игры.", state=state,
                                next_state=AdminState.choose_game_place, edit=True, cb_data_dict=buttons)
            else:
                await callback.message.answer("У вас пока нет мест для проведения игр. Их нужно создать.")
                await GoToMainMenu(message=callback.message, message_text="Будем добавлять места?", state=state,
                                   edit=False)
            return


        case "BB_CLOSE":
            await SelectGame(callback=callback, callback_data=callback_data, state=state,
                             next_state=AdminState.close_registration, session=session,
                             message_text="Какую на какую игру будем закрывать запись?")
            return


        case "BB_COMMIT":
            data = await state.get_data()
            if await is_new(state):
                result, error, id_game = await AddNewGame(session=session, data=data, apscheduler=apscheduler)
            else:
                id_game = data["id_game"]
                result, error = await UpdateGame(session=session, data=data)

            if not result:
                answer_str = f"Не удалось сохранить: {error}"
            else:
                answer_str = "Успешно. Что дальше?"
                if await is_new(state):
                    # выше отрабатывает успешно session.commit()
                    # и тут имеем TypeError: '<' not supported between instances of 'str' and 'int'
                    # Воспользоваться session не получается.
                    async with async_session_factory() as session:
                        await NotifyUsersForGameOpened(session=session, id_game=id_game)
                else:
                    async with async_session_factory() as session:
                        await NotifyUsersForGameChanged(session=session, id_game=data["id_game"])
            await GoToMainMenu(message=callback.message, message_text=answer_str, state=state, edit=True)
            return

        case "BB_GAME_CANCEL":
            await CancelGame(callback=callback, callback_data=callback_data, state=state, apscheduler=apscheduler)
            return

        case "BB_EDIT":
            await SelectGame(callback=callback, callback_data=callback_data, state=state, next_state=AdminState.edit_game,
                             session=session, message_text="Какую афишу будем редактировать?")
            return

        case "BB_SELECT_GAME":
            id_game: int = int(callback_data.id_game)
            await set_not_new(state=state, id_game=id_game, session=session)
            if await state.get_state() == AdminState.edit_game:
                await WhatToEditGame(callback=callback, callback_data=callback_data, state=state, session=session)
            if await state.get_state() == AdminState.close_registration:
                await CloseGameRegistration(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_CORRECT":
            await WhatToEditGame(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_EDIT_GAME_PLACE":
            data = await state.get_data()
            id_city = data["id_city"]
            data_dict = await GamePlacesButtons(id_city=id_city, session=session)
            await AskSelect(message=callback.message, message_text="Выберите другое место проведения игры.",
                            state=state, next_state=AdminState.choose_game_place, cb_data_dict=data_dict, edit=True)
            return

        case "BB_SET_GAME_PLACE":
            await SetBillboardPlace(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_EDIT_GAME_TYPE":
            data = await state.get_data()
            id_place = data["id_place"]
            Types: dict[int, str] = await GameTypesButtons(id_place=id_place, session=session)
            kbm = InlineKeyboard_Admin_ByDict_IdGameTypeKeyValue(data=Types, action="BB_SET_GAME_TYPE")
            await AskSelectKBM(message=callback.message, message_text="Выберите тип проводимой игры.", state=state,
                               next_state=AdminState.save_game, kbm=kbm, edit=True)
            return

        case "BB_SET_GAME_TYPE":
            await SetBillboardGameType(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_PRICE_2500" | "BB_PRICE_2000" | "BB_PRICE_1500" | "BB_PRICE_1400" | "BB_PRICE_1200" | "BB_PRICE_1000" \
             | "BB_PRICE_750":
            await SetBillboardGamePrice(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_EDIT_GAME_START":
            data = await state.get_data()
            game_dt: datetime = data["game_start"]
            message_text = f"Введите другое время начала игры вместо \"{game_dt.strftime('%A, %d %B %H:%M')}\""
            data["mode"] = "edit_game_start"
            await state.set_data(data=data)
            await Ask(message=callback.message, message_text=message_text, state=state,
                      next_state=AdminState.choose_game_start, action_code="BB_CANCEL")
            return

        case "BB_EDIT_GAME_PRICE":
            data = await state.get_data()
            price: int = data["price"]
            message_text = f"Введите другую стоимость игры вместо \"{price}\"."
            kbm = {"2500": AdminCallback(action="BB_PRICE_2500", price=2500),
                   "2000": AdminCallback(action="BB_PRICE_2000", price=2000),
                   "1500": AdminCallback(action="BB_PRICE_1500", price=1500),
                   "1400": AdminCallback(action="BB_PRICE_1400", price=1400),
                   "1200": AdminCallback(action="BB_PRICE_1200", price=1200),
                   "1000": AdminCallback(action="BB_PRICE_1000", price=1000),
                   "750": AdminCallback(action="BB_PRICE_750", price=750),
                   "Отмена": AdminCallback(action="BB_CANCEL")}
            await AskSelect(message=callback.message, message_text=message_text, state=state,
                            next_state=AdminState.choose_game_price, cb_data_dict=kbm, edit=True)
            return

        case "BB_EDIT_GAME_ACTIONS":
            await OnEditGameActionsButtonClick(callback=callback, callback_data=callback_data,
                                               state=state, session=session)
            return

        case value if value.startswith("BB_GAME_EDIT_ACTIONS"):
            await GameActionsSelector(action=value, callback=callback, callback_data=callback_data,
                                      state=state, session=session, edit=True)
            return

        case "BB_PROCESS_ADD_GAME_ACTION":
            await AddGameAction(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_PROCESS_DEL_GAME_ACTION":
            await DeleteGameAction(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "BB_CANCEL":
            if await is_new(state=state):
                await DropState(state=state)
                await GoToMainMenu(message=callback.message, message_text="Отменили. Что теперь?", state=state,
                                   edit=True)
            else:
                S = await state.get_state()
                if S == AdminState.start or S == AdminState.edit_game:
                    await DropState(state=state)
                    await GoToMainMenu(message=callback.message, message_text="Отменили. Что теперь?", state=state,
                                       edit=True)
                else:
                    await ConfirmGameRecord(message=callback.message, state=state, session=session, edit=True)
            return


async def SetBillboardPlace(callback: CallbackQuery,
                            callback_data: AdminCallback,
                            state: FSMContext, session: AsyncSession) -> None:
    id_place: int = int(callback_data.id_place)

    if id_place == 0:
        if await is_new(state=state):
            await DropState(state=state)
            await GoToMainMenu(message=callback.message, state=state, message_text="Что будем делать?", edit=True)
        else:
            await ConfirmGameRecord(message=callback.message, state=state, session=session, edit=True)
        return

    data = await state.get_data()
    data["id_place"] = id_place
    await state.set_data(data=data)

    Types: dict[int, str] = await GameTypesButtons(id_place=id_place, session=session)

    kbm = InlineKeyboard_Admin_ByDict_IdGameTypeKeyValue(data=Types, action="BB_SET_GAME_TYPE")

    await AskSelectKBM(message=callback.message, message_text="Выберите тип проводимой игры.", state=state,
                       next_state=AdminState.choose_game_type, edit=True, kbm=kbm)


async def SetBillboardGameType(callback: CallbackQuery,
                               callback_data: AdminCallback,
                               state: FSMContext, session: AsyncSession) -> None:
    id_game_type: int = int(callback_data.id_game_type)

    if id_game_type == 0:
        if await is_new(state=state):
            await DropState(state=state)
            await GoToMainMenu(message=callback.message, state=state, message_text="Что будем делать?", edit=True)
        else:
            await ConfirmGameRecord(message=callback.message, state=state, session=session, edit=True)
        return

    data = await state.get_data()
    data["id_game_type"] = id_game_type
    await state.set_data(data=data)

    if not await is_new(state=state):
        await state.set_state(AdminState.save_game)
        await ConfirmGameRecord(message=callback.message, state=state, session=session, edit=True)
        return
    else:
        await Ask(message=callback.message, message_text="Введите дату и время начала игры. Формат почти любой. Я "
                                                         "попытаюсь распознать.\n"
                                                         "Варианты: 15.05.2024 17:00, 2024-03-08 19:00, 20/06/2024 "
                                                         "17:00",
                  state=state, next_state=AdminState.choose_game_start, edit=True, action_code="BB_CANCEL")


@router.message(StateFilter(AdminState.choose_game_start))
@flags.authorization(admin_only=True, su_only=False)
async def SetBillboardStartDate(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        game_dt: datetime = parse(timestr=message.text, dayfirst=True, fuzzy=True)
    except ValueError:
        await message.answer(text=f"{message.text} не удалось считать как дату и время. Попробуйте изменить формат.")
        return
    if game_dt < datetime.now():
        await message.answer(text="Игру нельзя планировать задним числом.")
        kbm = {"Отмена": AdminCallback(action="BB_CANCEL")}
        await message.answer(text="Введите другую дату и время начала игры. Формат почти любой. Я попытаюсь "
                                  "распознать.\n Варианты: 15.05.2024 17:00, 2024-03-08 19:00, 20/06/2024 17:00",
                             reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))
        return

    data["game_start"] = game_dt
    await state.set_data(data=data)

    await message.answer(text=f"Принято: {game_dt.strftime('%A, %d %B, %H:%M')}")

    if not await is_new(state=state) or ("mode" in data and data["mode"] == "edit_game_start"):
        await state.set_state(AdminState.save_game)
        await ConfirmGameRecord(message=message, state=state, session=session)
        return

    kbm = {"2500": AdminCallback(action="BB_PRICE_2500", price=2500),
           "2000": AdminCallback(action="BB_PRICE_2000", price=2000),
           "1500": AdminCallback(action="BB_PRICE_1500", price=1500),
           "1400": AdminCallback(action="BB_PRICE_1400", price=1400),
           "1200": AdminCallback(action="BB_PRICE_1200", price=1200),
           "1000": AdminCallback(action="BB_PRICE_1000", price=1000),
           "750": AdminCallback(action="BB_PRICE_750", price=750),
           "Отмена": AdminCallback(action="BB_CANCEL")}

    await AskSelect(message=message,
                    message_text="Выберите или введите стоимость в формате, например 1400.",
                    state=state, next_state=AdminState.choose_game_price, cb_data_dict=kbm)


async def SetBillboardGamePrice(callback: CallbackQuery,
                                callback_data: AdminCallback,
                                state: FSMContext, session: AsyncSession) -> None:
    price: int = int(callback_data.price)
    if price == 0:
        if await is_new(state=state):
            await GoToMainMenu(message=callback.message, state=state, message_text="Что будем делать?", edit=True)
        else:
            await ConfirmGameRecord(message=callback.message, state=state, session=session, edit=True)
        return

    data = await state.get_data()
    data["price"] = price
    await state.set_data(data=data)

    if await is_new(state=state):
        await GameActionsSelector(callback=callback, callback_data=callback_data, session=session,
                                  action="BB_GAME_EDIT_ACTIONS_ADD", state=state, edit=True)
    else:
        await ConfirmGameRecord(message=callback.message, state=state, session=session, edit=True)


@router.message(StateFilter(AdminState.choose_game_price))
@flags.authorization(admin_only=True, su_only=False)
async def SetBillboardPrice(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        price: int = int(message.text)
    except ValueError:
        await message.answer(text=f"{message.text} не удалось считать как стоимость. Попробуйте изменить формат.")
        return
    if price < 0:
        await message.answer(
            text=f"{price} в качестве стоимости не подойдёт. Давайте попробуем ещё раз. "
                 f"Введите введите стоимость в формате 1200.")
        return

    data["price"] = price
    await state.set_data(data=data)

    if await is_new(state=state):

        data = await GameActionsButtons(session=session, state=state, action="BB_GAME_EDIT_ACTIONS_ADD",
                                        AllButton=True, CancelButton=True, CancelButtonCaption="Достаточно")
        await AskSelect(message=message, state=state, next_state=AdminState.choose_game_actions,
                        message_text="Выберите акции к игре.", cb_data_dict=data, edit=False)
    else:
        await ConfirmGameRecord(message=message, state=state, session=session, edit=False)


@router.message(F.photo, StateFilter(AdminState.load_poster))
@flags.authorization(admin_only=True, su_only=False)
async def LoadPoster(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    data["poster"] = message.photo[-1].file_id
    await state.set_data(data=data)
    await ConfirmGameRecord(message=message, state=state, session=session, additional_answer_text="Ок.", edit=True)


@flags.authorization(admin_only=True, su_only=False)
async def ConfirmGameRecord(message: types.Message,
                            state: FSMContext,
                            session: AsyncSession,
                            additional_answer_text: str = None,
                            edit: bool = False) -> None:
    data = await state.get_data()
    Place = await session.get(CPlace, data["id_place"])
    GameType = await session.get(CGameType, data["id_game_type"])
    kbm = {"Сохранить": AdminCallback(action="BB_COMMIT", id_admin=message.from_user.id),
           "Редактировать": AdminCallback(action="BB_CORRECT"),
           "Отмена": AdminCallback(action="BB_CANCEL")}

    if additional_answer_text is not None:
        answer_str = f"{additional_answer_text}\n"
    else:
        answer_str = ""

    if await is_new(state):
        answer_str += f"Принято.\nНовая запись на игру.\n"
    else:
        answer_str += f"Принято.\nСледующие изменения.\n"

    actions_str = await dict_to_string(state=state, Key="game_actions")
    if actions_str is None:
        actions_str = "Нет акций."

    answer_str += (html.bold("Тип игры: ") + f"{GameType.title}\n" +
                   html.bold("Дата и время начала: ") + f"{data['game_start'].strftime('%d.%m.%Y %H:%M')}\n" +
                   html.bold("Место проведения: ") + f"{Place.title}\n" +
                   html.bold("Адрес: ") + f"{Place.address}\n" +
                   html.bold("Число мест: ") + f"{Place.seats}\n" +
                   html.bold("Стоимость: ") + f"{data['price']}₽\n" +
                   html.bold("Акции: ") + f"{actions_str}\n" +
                   f"Сохранить эти данные?")
    if edit:
        # await message.edit_text(text=answer_str,
        # reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))
        await message.answer_photo(photo=data["poster"], caption=answer_str,
                                   reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))

    else:
        if "poster" in data:
            await message.answer_photo(photo=data["poster"], caption=answer_str,
                                       reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))
            # await message.answer(text=answer_str,
            # reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))


@flags.authorization(admin_only=True, su_only=False)
async def SelectGame(callback: CallbackQuery,
                     callback_data: AdminCallback,
                     state: FSMContext,
                     next_state : State,
                     session: AsyncSession, message_text: str) -> None:
    data = await state.get_data()
    id_moderator: int = int(data["id_moderator"])
    id_city: int = int(data["id_city"])
    Billboards = await DB_GetEditableBillBoards(session=session, id_city=id_city, id_moderator=id_moderator)
    if len(Billboards) > 0:
        kbm: dict[str, AdminCallback] = {}
        for index, game in enumerate(Billboards):
            start_date: datetime = game.start_date
            str_dt = start_date.strftime("%d.%m.%Y %H:%M")
            kbm[f"{index + 1}. {str_dt}"] = AdminCallback(action="BB_SELECT_GAME", id_game=game.id)
        kbm["Отмена"] = AdminCallback(action="BB_CANCEL")
        await AskSelect(message=callback.message, message_text=message_text, edit=True,
                        next_state=next_state, state=state, cb_data_dict=kbm)
    else:
        await GoToMainMenu(message=callback.message, state=state, message_text="Пока нечего редактировать. Что теперь?")


"""
Закрытие регистрации на игру
"""
@flags.authorization(admin_only=True, su_only=False)
async def CloseGameRegistration(callback: CallbackQuery,
                         callback_data: AdminCallback,
                         state: FSMContext,
                         session: AsyncSession) -> None:
    data = await state.get_data()
    id_place: int = data["id_place"]
    id_game_type: int = data["id_game_type"]
    GameStart: datetime
    if not await is_new(state=state):
        id_game: int = data["id_game"]
        Game: CGame | None = await session.get(CGame, id_game)
        Place: CPlace = await Game.Place
        GameType: CGameType = await Game.awaitable_attrs.game_type
        GameStart: datetime = await Game.awaitable_attrs.start_date
    else:
        GameType: CGameType | None = await session.get(CGameType, id_game_type)
        Place: CPlace | None = await session.get(CPlace, id_place)
        GameStart = data["game_start"]

    GameTypeTitle = GameType.title
    PlaceTitle = Place.title
    PlaceAddress = Place.address
    PlaceSeats = Place.seats
    actions_str = await dict_to_string(state=state, Key="game_actions")
    if actions_str is None:
        actions_str = "Нет акций."

    answer_txt = (html.bold("Тип игры:") + f" {GameTypeTitle}\n" +
                  html.bold("Дата и время начала: ") + f"{GameStart.strftime('%d.%m.%Y %H:%M')}\n" +
                  html.bold("Место проведения:") + f" {PlaceTitle}\n" +
                  html.bold("Адрес:") + f" {PlaceAddress}\n" +
                  html.bold("Число мест:") + f" {PlaceSeats}\n" +
                  html.bold("Стоимость:") + f" {data['price']}₽\n" +
                  html.bold("Акции:") + f" {actions_str}\n"
                                        "Закрыть запись на игру?")

    kbm = {"Да": AdminCallback(action="BB_CLOSE_GAME_REG_YES", id_game=callback_data.id_game),
           "Нет": AdminCallback(action="BB_CLOSE_GAME_REG_NO", id_game=callback_data.id_game),
           "Отмена": AdminCallback(action="BB_CANCEL")
           }

    await AskSelect(message=callback.message, message_text=answer_txt, state=state, next_state=AdminState.close_registration,
                    cb_data_dict=kbm, edit=True)




@flags.authorization(admin_only=True, su_only=False)
async def WhatToEditGame(callback: CallbackQuery,
                         callback_data: AdminCallback,
                         state: FSMContext,
                         session: AsyncSession) -> None:
    data = await state.get_data()
    id_place: int = data["id_place"]
    id_game_type: int = data["id_game_type"]
    GameStart: datetime
    if not await is_new(state=state):
        id_game: int = data["id_game"]
        Game: CGame | None = await session.get(CGame, id_game)
        Place: CPlace = await Game.Place
        GameType: CGameType = await Game.awaitable_attrs.game_type
        GameStart: datetime = await Game.awaitable_attrs.start_date
    else:
        GameType: CGameType | None = await session.get(CGameType, id_game_type)
        Place: CPlace | None = await session.get(CPlace, id_place)
        GameStart = data["game_start"]

    GameTypeTitle = GameType.title
    PlaceTitle = Place.title
    PlaceAddress = Place.address
    PlaceSeats = Place.seats

    actions_str = await dict_to_string(state=state, Key="game_actions")
    if actions_str is None:
        actions_str = "Нет акций."

    answer_txt = (html.bold("Тип игры:") + f" {GameTypeTitle}\n" +
                  html.bold("Дата и время начала: ") + f"{GameStart.strftime('%d.%m.%Y %H:%M')}\n" +
                  html.bold("Место проведения:") + f" {PlaceTitle}\n" +
                  html.bold("Адрес:") + f" {PlaceAddress}\n" +
                  html.bold("Число мест:") + f" {PlaceSeats}\n" +
                  html.bold("Стоимость:") + f" {data['price']}₽\n" +
                  html.bold("Акции:") + f" {actions_str}\n"
                                        "Что будем редактировать?"
                  )
    kbm = {"Место": AdminCallback(action="BB_EDIT_GAME_PLACE", id_game=callback_data.id_game),
           "Тип игры": AdminCallback(action="BB_EDIT_GAME_TYPE", id_game=callback_data.id_game),
           "Дату, время начала": AdminCallback(action="BB_EDIT_GAME_START", id_game=callback_data.id_game),
           "Цену": AdminCallback(action="BB_EDIT_GAME_PRICE", id_game=callback_data.id_game),
           "Акции": AdminCallback(action="BB_EDIT_GAME_ACTIONS", id_game=callback_data.id_game)}
    if not await is_new(state=state):
        kbm["Отмена игры"] = AdminCallback(action="BB_GAME_CANCEL", id_game=callback_data.id_game)

    kbm["Отмена"] = AdminCallback(action="BB_CANCEL")

    await AskSelect(message=callback.message, message_text=answer_txt, state=state, next_state=AdminState.edit_game,
                    cb_data_dict=kbm, edit=True)


@flags.authorization(admin_only=True, su_only=False)
async def NotifyUsersForGameOpened(id_game: int, session: AsyncSession):
    Game: CGame | None = await session.get(CGame, id_game)
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    MPerson: CPerson = await Moderator.Person
    MTelegrams: list[CTelegram] = await MPerson.awaitable_attrs.telegrams
    MTelegram: CTelegram = MTelegrams[0]

    Place: CPlace = await Game.awaitable_attrs.place
    City = await Place.City
    Persons = await DB_GetPersonListOfCityId(session=session, id_city=City.id)
    for Person in Persons:
        Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
        for Telegram in Telegrams:
            tg_message = await DB_GetRandomTelegramBotMessageFromGroup(session=session,
                                                                       group="_ANNOUNCE_")
            month = ""
            if tg_message is not None:
                month = Game.start_date.strftime("%B")

            caption = str(tg_message.message).format(name=Person.FormatName,
                                                     week_day=Game.start_date.strftime("%A"),
                                                     time=f"\U0001F554<b>{Game.start_date.strftime('%H:%M')}</b>"
                                                          f"\U0001F554",
                                                     day=f"{Game.start_date.day}",
                                                     month=f"{month}",
                                                     place=f"<b>{Place.title}</b>",
                                                     address=Place.address,
                                                     price=Game.price)

            GameActionAssociations: list[CGameActionAssociation] = await Game.awaitable_attrs.actions_acc
            if len(GameActionAssociations) == 1:
                Action: CAction = GameActionAssociations[0].action
                caption += f"\nДействует акция \"{Action.title}\". {Action.comment}"
                if Action.code == "ONE_PLUS_ONE":
                    caption = caption.format(Game.price, 2 * Game.price)
            elif len(GameActionAssociations) > 1:
                caption += f"\nДействуют акции "
                for index, association in enumerate(GameActionAssociations):
                    caption += association.action.title
                    if index < len(GameActionAssociations) - 1:
                        caption += ", "
            buttons = {"Записаться": UserCallback(action="USER_CHOOSE_NICK", key=Game.id, id_game=Game.id)}
            kbm = IKBM_User_ByDict_UserCallbackData(callback_data_dict=buttons)
            GameProperties: CGameProperties = await Game.awaitable_attrs.properties

            try:

                if GameProperties is not None:
                    await bot.bot.MafiaBot.send_photo(chat_id=Telegram.telegram_id,
                                                      photo=GameProperties.telegram_file_id,
                                                      caption=caption,
                                                      reply_markup=kbm)
                else:
                    await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id,
                                                        text=str(tg_message.message).
                                                        format(name=Person.FormatName,
                                                               week_day=Game.start_date.strftime("%A"),
                                                               time=f"\U0001F554<b>{Game.start_date.strftime('%H:%M')}</b>"
                                                                    f"\U0001F554",
                                                               day=f"{Game.start_date.day}",
                                                               month=f"{month}",
                                                               place=f"<b>{Place.title}</b>",
                                                               address=Place.address,
                                                               price=Game.price),
                                                        reply_markup=kbm)
            except TelegramForbiddenError:
                await bot.bot.MafiaBot.send_message(chat_id=MTelegram.telegram_id,
                                                    text=f"Пользователь "
                                                         f"{Telegram.telegram_id} {Telegram.telegram_name} "
                                                         f"заблокировал бота и не получит афишу.")


@flags.authorization(admin_only=True, su_only=False)
async def NotifyUsersForGameChanged(id_game: int, session: AsyncSession):
    Game: CGame | None = await session.get(CGame, id_game)
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    MPerson: CPerson = await Moderator.Person
    MTelegrams: list[CTelegram] = await MPerson.awaitable_attrs.telegrams
    MTelegram: CTelegram = MTelegrams[0]
    Place: CPlace = await Game.awaitable_attrs.place
    City = await Place.City
    Persons = await DB_GetPersonListOfCityId(session=session, id_city=City.id)
    for Person in Persons:
        Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
        for Telegram in Telegrams:
            message_text = (f"Вниманию игроков! Произошли изменения в игре "
                            f"{Game.start_date.strftime('%A, %d %B')}\n")
            message_text += html.bold("Дата:") + f" {Game.start_date.strftime('%A, %d.%m.%Y')}\n"
            message_text += html.bold("Время:") + f" {Game.start_date.strftime('%H:%M')}\n"
            message_text += html.bold("Место:") + f" {Place.title}\n"
            message_text += html.bold("Адрес:") + f" {Place.address}\n"
            message_text += html.bold("Стоимость:") + f" {Game.price} р.\n"
            players: list[CPlayer] = await Game.awaitable_attrs.actual_players
            count: int = len(players)
            message_text += html.bold("Занято мест:") + f" {count} из {Place.seats}\n"
            try:
                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_text)
            except TelegramForbiddenError:
                await bot.bot.MafiaBot.send_message(chat_id=MTelegram.telegram_id,
                                                    text=f"Пользователь "
                                                         f"{Telegram.telegram_id} {Telegram.telegram_name} "
                                                         f"заблокировал бота и не получит сообщение о изменении игры.")


@flags.authorization(admin_only=True, su_only=False)
async def NotifyUsersForGameCancelled(id_game: int, session: AsyncSession):
    Game: CGame | None = await session.get(CGame, id_game)
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    MPerson: CPerson = await Moderator.Person
    MTelegrams: list[CTelegram] = await MPerson.awaitable_attrs.telegrams
    MTelegram: CTelegram = MTelegrams[0]
    Place: CPlace = await Game.awaitable_attrs.place
    City = await Place.City
    Persons = await DB_GetPersonListOfCityId(session=session, id_city=City.id)

    message_text = (f"Вниманию игроков! Отмена игры "
                    f"{Game.start_date.strftime('%A, %d %B')}\n")
    message_text += f"<b>Дата:</b> {Game.start_date.strftime('%A, %d.%m.%Y')}\n"
    message_text += f"<b>Время:</b> {Game.start_date.strftime('%H:%M')}\n"
    message_text += f"<b>Место:</b> {Place.title}\n"
    message_text += f"<b>Адрес:</b> {Place.address}\n"

    for Person in Persons:
        for Telegram in Person.telegrams:

            try:
                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_text)
            except TelegramForbiddenError:
                await bot.bot.MafiaBot.send_message(chat_id=MTelegram.telegram_id,
                                                    text=f"Пользователь "
                                                         f"{Telegram.telegram_id} {Telegram.telegram_name} "
                                                         f"заблокировал бота и не получит сообщение об отмене игры.")

@flags.authorization(admin_only=True, su_only=False)
async def NotifyUsersForGameRegistrationClosed(id_game: int, session: AsyncSession):
    Game: CGame | None = await session.get(CGame, id_game)
    Place: CPlace = await Game.awaitable_attrs.place
    City = await Place.City

    message_text = f"Уважаемые игроки! Запись на игру {Game.start_date.strftime('%A, %d %B')}, {Place.title} "
    message_text += f"{Place.address} закрыта."

    Persons: list[CPerson] = await DB_GetPersonListOfCityId(session=session, id_city=City.id)
    for Person in Persons:
        for Telegram in Person.telegrams:
            try:
                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_text)
            except TelegramForbiddenError:
                pass


async def AddNewGame(session: AsyncSession, data: dict[str, Any],
                     apscheduler: AsyncIOScheduler) -> tuple[bool, str, int]:
    result, error, id_game = await DB_AddNewGame(session=session, id_game_type=data["id_game_type"],
                                                 id_moderator=data["id_moderator"], id_place=data["id_place"],
                                                 start_date=data["game_start"], price=data["price"],
                                                 actions=data["game_actions"],
                                                 poster_id=data["poster"])
    if result:
        await DB_ScheduleSwitchGameStatus(session=session, id_game=id_game, apscheduler=apscheduler)

    return result, error, id_game


async def UpdateGame(session: AsyncSession, data: dict[str, Any]) -> tuple[bool, str]:
    return await DB_UpdateGame(session=session, id_game=data["id_game"], id_game_type=data["id_game_type"],
                               id_place=data["id_place"], start_date=data["game_start"], price=data["price"],
                               actions=data["game_actions"])


async def AddGameAction(callback: CallbackQuery,
                        callback_data: AdminCallback, state: FSMContext, session: AsyncSession):
    id_action: int = int(callback_data.id_action)
    data = await state.get_data()
    # Нажали "Все"
    if id_action == -1:
        all_actions = await DB_GetAllActions_as_dict(session=session)
        data["game_actions"] = all_actions
        await state.set_data(data=data)
        if await is_new(state):
            await Ask(message=callback.message, message_text="Загрузите постер.", state=state,
                      next_state=AdminState.load_poster, edit=True, action_code="BB_CANCEL")
        else:
            await ConfirmGameRecord(message=callback.message, state=state,
                                    session=session, additional_answer_text="Ок.", edit=True)
        return
    # Нажали "Достаточно"
    if id_action == 0:
        if await is_new(state):
            await Ask(message=callback.message, message_text="Загрузите постер.", state=state,
                      next_state=AdminState.load_poster, edit=True, action_code="BB_CANCEL")
        else:
            await ConfirmGameRecord(message=callback.message, state=state, session=session,
                                    additional_answer_text="Ок.", edit=True)
        return

    GameAction: CAction | None = await session.get(CAction, id_action)
    data = await state.get_data()
    game_actions = data["game_actions"]
    game_actions[GameAction.id] = GameAction.title
    await state.set_data(data=data)
    kbm = await GameActionsButtons(state=state, session=session,
                                   action="BB_PROCESS_ADD_GAME_ACTION",
                                   AllButton=True, CancelButton=True,
                                   CancelButtonCaption="Достаточно", DeleteMode=False)
    await AskSelect(message=callback.message, message_text="Ещё добавить?",
                    state=state, next_state=None, cb_data_dict=kbm, edit=True)


async def DeleteGameAction(callback: CallbackQuery,
                           callback_data: AdminCallback, state: FSMContext, session: AsyncSession):
    id_action: int = int(callback_data.id_action)
    if id_action == 0:
        await ConfirmGameRecord(message=callback.message, session=session,
                                state=state, additional_answer_text="Ок.", edit=True)
        return
    data = await state.get_data()
    if id_action == -1:
        data["game_actions"] = {}
        await ConfirmGameRecord(message=callback.message, state=state, session=session,
                                additional_answer_text="Более нечего удалять.", edit=True)
        return

    game_actions = data["game_actions"]
    if id_action > 0:
        del game_actions[id_action]
        await state.set_data(data=data)

    kbm = await GameActionsButtons(state=state, session=session,
                                   action="BB_PROCESS_DEL_GAME_ACTION",
                                   AllButton=True, CancelButton=True,
                                   CancelButtonCaption="Достаточно", DeleteMode=True)
    await AskSelect(message=callback.message, message_text="Ещё удалить?",
                    state=state, next_state=None, cb_data_dict=kbm, edit=True)


async def CancelGame(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext,
                     apscheduler: AsyncIOScheduler):
    id_game: int = int(callback_data.id_game)
    async with async_session_factory() as session:
        await DB_CancelGame(session=session, id_game=id_game, apscheduler=apscheduler)
        await NotifyUsersForGameCancelled(session=session, id_game=id_game)
    await GoToMainMenu(message=callback.message, message_text="Игра отменена.", state=state, edit=False)


async def OnEditGameActionsButtonClick(callback: CallbackQuery,
                                       callback_data: AdminCallback,
                                       state: FSMContext,
                                       session: AsyncSession) -> None:
    id_game: int = int(callback_data.id_game)
    data = await state.get_data()
    data['mode'] = 'edit_place_game_actions'
    await state.set_data(data=data)
    await state.set_state(AdminState.choose_game_actions)

    kbm = {"Добавляем": AdminCallback(action="BB_GAME_EDIT_ACTIONS_ADD", id_game=id_game),
           "Удаляем": AdminCallback(action="BB_GAME_EDIT_ACTIONS_DEL", id_game=id_game),
           "Отмена": AdminCallback(action="BB_CORRECT", id_game=id_game)}

    list_of_actions = await dict_to_string(state=state, Key="game_actions")
    message_text = ""
    if list_of_actions is not None:
        message_text += "Сейчас имеется:\n" + list_of_actions
    message_text += "Добавляем или удаляем?"
    await AskSelect(message=callback.message, message_text=message_text,
                    state=state, next_state=AdminState.choose_game_actions, cb_data_dict=kbm, edit=True)


async def GameActionsSelector(callback: CallbackQuery,
                              callback_data: AdminCallback,
                              state: FSMContext,
                              session: AsyncSession,
                              action: str,
                              edit: bool = False) -> None:
    if action == "BB_GAME_EDIT_ACTIONS_DEL":
        kbm = await GameActionsButtons(state=state,
                                       session=session,
                                       action="BB_PROCESS_DEL_GAME_ACTION",
                                       AllButton=True,
                                       CancelButton=True,
                                       CancelButtonCaption="Достаточно",
                                       DeleteMode=True)
        if len(kbm) > 0:
            await AskSelect(message_text="Выберите для удаления.",
                            message=callback.message,
                            state=state,
                            next_state=None,
                            cb_data_dict=kbm,
                            edit=edit)
            return
        else:
            await ConfirmGameRecord(message=callback.message, state=state, session=session,
                                    additional_answer_text="Нечего удалять.", edit=edit)
            return

    if action == "BB_GAME_EDIT_ACTIONS_ADD":
        kbm = await GameActionsButtons(state=state,
                                       session=session,
                                       action="BB_PROCESS_ADD_GAME_ACTION",
                                       AllButton=True,
                                       CancelButton=True,
                                       CancelButtonCaption="Достаточно",
                                       DeleteMode=False)
        await AskSelect(message_text="Выберите акции для добавления.",
                        message=callback.message,
                        state=state,
                        next_state=None,
                        cb_data_dict=kbm,
                        edit=edit)
        return
