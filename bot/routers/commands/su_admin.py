from typing import Any

from aiogram import Router, types, F, flags
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery

import bot.bot
from bot.keyboards.su_admin_keyboards import *
from bot.states import SUState
from backendapi.database import *
from bot.middlewares import UpdateAdmins

import subprocess
import os


router = Router(name=__name__)


@router.message(Command(commands=["su", "sudo", "super_admin"], ignore_case=True))
@flags.authorization(admin_only=False, su_only=True)
async def StartHandler(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    await message.answer(text="Да, Босс.")
    await state.set_state(state=SUState.start)
    await message.answer(text="Что будем делать?", reply_markup=SU_Main_Keyboard())


@router.message(Command("settimer"))
@flags.authorization(admin_only=False, su_only=True)
async def su_command(message: Message, command: CommandObject):
    # Если не переданы никакие аргументы, то
    # command.args будет None
    if command.args is None:
        await message.answer("Ошибка: не переданы аргументы")
        return
    # Пробуем разделить аргументы на две части по первому встречному пробелу
    try:
        delay_time, text_to_send = command.args.split(" ", maxsplit=1)
    # Если получилось меньше двух частей, вылетит ValueError
    except ValueError:
        await message.answer("Ошибка: неправильный формат команды. Пример:\n" "/settimer <time> <message>")
        return
    await message.answer(f"Таймер добавлен!\n Время: {delay_time}\nТекст: {text_to_send}")


async def SU_GoMainMenu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(state=SUState.start)
    await callback.message.answer(text="Что будем делать?", reply_markup=SU_Main_Keyboard())


@router.callback_query(CSUCallBack.filter(F.action.startswith("SU_")))
@flags.authorization(admin_only=False, su_only=True)
async def SU_MainCallbackHandler(callback: CallbackQuery,
                                 callback_data: CSUCallBack,
                                 state: FSMContext,
                                 session: AsyncSession) -> None:
    code: str = callback_data.action.replace("SU_", "")
    match code:
        case "MODERATORS":
            await SU_ModeratorsMenu(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "MESSAGES":
            await callback.message.answer(text="В разработке")
            return
        case "OPTIONS":
            await callback.message.answer(text="В разработке")
            return
        case "EXIT":
            await ExitSU(callback=callback, state=state)
            return


@router.callback_query(CSUCallBack.filter(F.action.startswith("MODERATOR_")))
@flags.authorization(admin_only=False, su_only=True)
async def SU_ModeratorMenuHandler(callback: CallbackQuery,
                                  callback_data: CSUCallBack,
                                  state: FSMContext,
                                  session: AsyncSession) -> None:
    code: str = callback_data.action.replace("MODERATOR_", "")
    match code:
        case "ADD":
            await SU_AddModeratorMenu(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "REPLACE":
            await SU_City(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "CHANGE_TO":
            await SU_ChangeModeratorTo(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "EDIT":
            await SU_ListModeratorsMenu(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "ADD_CITY":
            await SU_AddCityToModerator(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "SELECT":
            await SU_SelectModerator(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "DEL_CITY":
            await SU_ModeratorCityDelete(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "SELECT_CITY":
            await SU_SelectCity(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "SELECT_GAME":
            await SU_SelectGame(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "BACK":
            await GoBack(callback=callback, state=state, session=session)
            return
        case "CONFIRM":
            await SU_ConfirmModerator(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "COMMIT":
            await SU_CommitModerator(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "CANCEL":
            await SU_GoMainMenu(callback=callback, state=state)
            return


async def GoBack(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if await state.get_state() == SUState.moderators:
        await callback.message.delete()
        await SU_GoMainMenu(callback=callback, state=state)
        return
    else:
        await SU_ModeratorsMenu(callback=callback, state=state, session=session, callback_data=None)
        return


async def SU_ModeratorsMenu(callback: CallbackQuery, callback_data: CSUCallBack | None, state: FSMContext,
                            session: AsyncSession, message_text: str = "Меню работы с ведущими игр."):
    await state.set_state(SUState.moderators)
    await callback.message.edit_text(text=message_text, reply_markup=await SU_Moderators_Menu_Keyboard())


async def SU_ListModeratorsMenu(callback: CallbackQuery, callback_data: CSUCallBack | None, state: FSMContext,
                                session: AsyncSession):
    AllModeratorPersons = await DB_GetAllPersonsModeratorsDistinct(session=session)
    await state.set_state(SUState.moderators)
    await callback.message.edit_text(text="Босс, выберите ведущего.",
                                     reply_markup=await SU_Moderators_List_Keyboard(Persons=AllModeratorPersons))


async def SU_AddModeratorMenu(callback: CallbackQuery, callback_data: CSUCallBack, state: FSMContext,
                              session: AsyncSession):
    await state.set_state(state=SUState.moderator_add_input_phone)
    await callback.message.edit_text(text="Босс, введите номер телефона зарегистрированного пользователя.",
                                     reply_markup=SU_Back_Keyboard(action="MODERATOR_BACK"))


async def SU_AddCityToModerator(callback: CallbackQuery, callback_data: CSUCallBack, state: FSMContext,
                                session: AsyncSession):
    id_city: int = callback_data.id_city
    id_person: int = callback_data.id_person
    City: CCity | None = await session.get(CCity, id_city)
    data: dict[str, Any] = await state.get_data()
    if "city_list" not in data:
        data["city_list"] = dict[int, str]()
    city_list: dict[int, str] = data["city_list"]
    city_list[id_city] = await City.awaitable_attrs.name

    data["city_list"] = city_list

    await state.set_data(data=data)

    Cities: list[CCity] = await DB_GetAllCities(session=session)
    buttons = {City.name: CSUCallBack(action="MODERATOR_ADD_CITY", id_person=id_person, id_city=City.id)
               for City in Cities if City.id not in city_list}
    buttons["Готово"] = CSUCallBack(action="MODERATOR_CONFIRM")
    await AskSelect(message=callback.message, message_text=f"Ещё один город", cb_data_dict=buttons, state=state,
                    next_state=SUState.moderator_add_city, edit=True)


async def ExitSU(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(text="Я никому не скажу, что вы были здесь, Босс.")
    await callback.message.delete()


@router.message(SUState.moderator_add_input_phone)
@flags.authorization(admin_only=False, su_only=True)
async def SU_ReadPhoneNumber(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    PhoneNumber: str = message.text
    if validate_mobile_number(PhoneNumber):
        data["phone"] = PhoneNumber
        Person: CPerson = await DB_GetPersonByPhone(session=session, phone=PhoneNumber)
        if Person is None:
            await message.answer(text="Босс, вашего приятеля с такой мобилой нет в нашей команде.",
                                 reply_markup=SU_Back_Keyboard(action="MODERATOR_BACK"))
        else:
            data["id_person"] = Person.id
            Moderators: list[CModerator] = await Person.awaitable_attrs.moderators
            city_list: dict[int, str] = {}
            if Moderators is not None and len(Moderators) > 0:
                for Moderator in Moderators:
                    City = await Moderator.City
                    city_list[Moderator.id_city] = City.name

            data["city_list"] = city_list
            data["new"] = True

            await state.set_data(data=data)

            Cities: list[CCity] = await DB_GetAllCities(session=session)
            buttons = {City.name: CSUCallBack(action="MODERATOR_ADD_CITY", id_person=Person.id, id_city=City.id)
                       for City in Cities if City.id not in city_list}
            buttons["Назад"] = CSUCallBack(action="MODERATOR_BACK")
            await AskSelect(message=message, message_text=f"Вот что я нашёл.\n{await Person.PersonInfo}\nНадо выбрать "
                                                          f"города, для ведущего.", cb_data_dict=buttons, state=state,
                            next_state=SUState.moderator_add_city, edit=False)
            await message.delete()
    else:
        await message.answer("Похоже, Босс это не номер телефона. Попробуйте снова.")


async def SU_ConfirmModerator(callback: CallbackQuery, callback_data: CSUCallBack, state: FSMContext,
                              session: AsyncSession):
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    city_list: dict[int, str] = data["city_list"]
    Person: CPerson | None = await session.get(CPerson, id_person)

    if "new" in data and data["new"] is True:
        message_text = "Добавляется модератор.\n"
    else:
        message_text = "Редактируется модератор.\n"
    message_text += await Person.PersonInfo + "\n"
    message_text += "<b>Города:</b> "
    for index, (key, value) in enumerate(city_list.items()):
        if index < len(city_list) - 1:
            message_text += f"{value}, "
        else:
            message_text += f"{value}"

    kbm = {"Сохранить": CSUCallBack(action="MODERATOR_COMMIT"),
           "Редактировать": CSUCallBack(action="MODERATOR_CORRECT"),
           "Отмена": CSUCallBack(action="MODERATOR_CANCEL")}

    await callback.message.edit_text(text=message_text, reply_markup=await SU_KB_CB_by_dict(cb_data_dict=kbm))


async def SU_ChangeModeratorTo(callback: CallbackQuery, callback_data: CSUCallBack, state: FSMContext,
                               session: AsyncSession):
    id_game: int = int(callback_data.id_game)
    id_moderator: int = int(callback_data.id_moderator)

    result, error = await DB_ChangeModerator(session=session, id_game=id_game, id_moderator=id_moderator)
    if result:
        await callback.message.answer("Всё, ок, Босс. Другой ведущий назначен.")
    else:
        await callback.message.answer(text=f"{error}")


async def SU_CommitModerator(callback: CallbackQuery, callback_data: CSUCallBack, state: FSMContext,
                             session: AsyncSession):
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    city_list: dict[int, str] = data["city_list"]
    if "new" in data and data["new"] is True:
        result, error = await DB_NewModerator(session=session, id_person=id_person, city_list=list(city_list.keys()))
        if result:
            await UpdateAdmins()
            await NotifyAdminAdded(id_person=id_person, session=session)
            await callback.message.answer("Всё, ок, Босс. Новый ведущий назначен.")
            await callback.message.delete()
        else:
            await callback.message.answer(text=f"{error}")
    else:
        pass
    await SU_GoMainMenu(callback=callback, state=state)


async def NotifyAdminAdded(id_person: int, session: AsyncSession):
    Person: CPerson | None = await session.get(CPerson, id_person)
    Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
    message_text = "Вы назначены ведущим игр в городах:\n"
    moderators: list[CModerator] = await Person.awaitable_attrs.moderators
    for index, moderator in enumerate(moderators):
        City: CCity = await moderator.awaitable_attrs.city
        if index < len(moderators) - 1:
            message_text += f"{City.name}, "
        else:
            message_text += f"{City.name}\n"

    for Telegram in Telegrams:
        await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_text)


async def NotifyAdminRemoved(id_person: int, session: AsyncSession):
    Person: CPerson | None = await session.get(CPerson, id_person)
    Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
    message_text = "Вы исключены ведущим игр в городах:\n"
    moderators: list[CModerator] = await Person.awaitable_attrs.moderators
    for index, moderator in enumerate(moderators):
        City: CCity = await moderator.awaitable_attrs.city
        if index < len(moderators) - 1:
            message_text += f"{City.name}, "
        else:
            message_text += f"{City.name}\n"

    for Telegram in Telegrams:
        await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=message_text)


async def SU_SelectModerator(callback: CallbackQuery, callback_data: CSUCallBack,
                             state: FSMContext, session: AsyncSession):
    id_person: int = callback_data.id_person
    Person: CPerson | None = await session.get(CPerson, id_person)
    data = await state.get_data()
    data["id_person"] = id_person
    Moderators: list[CModerator] = await Person.awaitable_attrs.moderators
    city_list: dict[int, str] = {}
    buttons: dict[str, CSUCallBack] = {}
    for Moderator in Moderators:
        City = await Moderator.City
        city_list[Moderator.id_city] = City.name
        buttons[City.name] = CSUCallBack(action="MODERATOR_DEL_CITY", id_moderator=Moderator.id,
                                         id_person=Person.id, id_city=City.id)
    buttons["Отмена"] = CSUCallBack(action="MODERATOR_BACK")
    data["city_list"] = city_list
    data["new"] = False
    await state.set_data(data=data)
    await AskSelect(message=callback.message, message_text=f"Какой город у ведущего "
                                                           f"{Person.FormatFullName} удаляем?",
                    next_state=SUState.moderator_select_city, state=state, cb_data_dict=buttons, edit=True)


async def SU_SelectCity(callback: CallbackQuery, callback_data: CSUCallBack,
                        state: FSMContext, session: AsyncSession):
    id_city: int = int(callback_data.id_city)
    City: CCity | None = await session.get(CCity, id_city)
    Games: list[CGame] = await DB_GetGamesAfterDate(session=session, City=City, after_date=datetime.now())
    if len(Games) > 0:
        buttons = {await Game.FormatGameStr: CSUCallBack(action="MODERATOR_SELECT_GAME", id_game=Game.id) for Game in Games}
        buttons["Отмена"] = CSUCallBack(action="MODERATOR_BACK")
        await AskSelect(message=callback.message, message_text=f"Босс, выберите игру, в которой будем заменять "
                                                               f"ведущего?", next_state=None, state=state,
                        cb_data_dict=buttons, edit=True)
    else:
        await SU_ModeratorsMenu(callback=callback, session=session, callback_data=callback_data, state=state,
                                message_text=f"В городе {City.name} нет запланированных игр.")


async def SU_SelectGame(callback: CallbackQuery, callback_data: CSUCallBack,
                        state: FSMContext, session: AsyncSession):
    id_game: int = int(callback_data.id_game)
    Game: CGame | None = await session.get(CGame, id_game)
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    City: CCity = await Game.City
    Moderators: list[CModerator] = await City.awaitable_attrs.moderators
    buttons: dict[str, CSUCallBack] = {}
    for index, _moderator in enumerate(Moderators):
        if _moderator.id != Moderator.id:
            Person: CPerson = await _moderator.Person
            buttons[Person.FormatName] = CSUCallBack(action="MODERATOR_CHANGE_TO",
                                                     id_moderator=_moderator.id,
                                                     id_game=id_game)
    buttons["Отмена"] = CSUCallBack(action="MODERATOR_BACK")
    await AskSelect(message=callback.message, message_text=f"Босс, кому мы доверим проведение этой игры?",
                    next_state=None, state=state,
                    cb_data_dict=buttons, edit=True)


async def SU_City(callback: CallbackQuery, callback_data: CSUCallBack,
                  state: FSMContext, session: AsyncSession):
    Cities: list[CCity] = await DB_GetAllCities(session=session)
    buttons = {City.name: CSUCallBack(action="MODERATOR_SELECT_CITY", id_city=City.id) for City in Cities}
    buttons["Отмена"] = CSUCallBack(action="MODERATOR_BACK")
    await AskSelect(message=callback.message, message_text=f"Босс, в каком городе будем заменять "
                                                           f"ведущего?", next_state=None, state=state,
                    cb_data_dict=buttons, edit=True)


async def SU_ModeratorCityDelete(callback: CallbackQuery, callback_data: CSUCallBack,
                                 state: FSMContext, session: AsyncSession):
    id_moderator: int = callback_data.id_moderator
    id_person: int = callback_data.id_person
    Person: CPerson | None = await session.get(CPerson, id_person)
    id_city: int = callback_data.id_city
    City: CCity | None = await session.get(CCity, id_city)

    Moderator: CModerator | None = await session.get(CModerator, id_moderator)

    Games: list[CGame] = await Moderator.awaitable_attrs.games
    # проверка на открытые к записи игры
    can_delete = True
    games_str = ""
    if len(Games) > 0:
        count = 0
        for game in Games:
            GameStatusAssociations: list[CGameStatusAssociation] = await game.awaitable_attrs.statuses_acc
            GameStatusAssociation = GameStatusAssociations[0]
            Status: CStatus = await GameStatusAssociation.awaitable_attrs.status
            if Status.code == 'GAME_ANNOUNCED':
                count += 1
                can_delete = False
                games_str += f"{count}. {await game.FormatGameStr}\n"

    if can_delete:
        result, error = await DB_DeleteModerator(session=session, id_moderator=id_moderator)
        if result:
            await UpdateAdmins()
            #await NotifyAdminRemoved(id_person=id_person, session=session)
            await callback.message.answer(
                f"Всё, ок, Босс. {Person.FormatFullName} больше не ведущий в городе {City.name}")
            await state.set_state(SUState.moderator_select)
            await SU_ModeratorsMenu(callback=callback, session=session, state=state, callback_data=callback_data)
        else:
            await callback.message.answer(text=f"{error}")
    else:
        await callback.message.answer(text=f"Босс, нельзя убрать ведущего от дел. Пусть завершит их:\n" + games_str)
        await state.set_state(SUState.moderator_select)
        await SU_ModeratorsMenu(callback=callback, session=session, state=state, callback_data=callback_data)


@router.message(Command(commands=["update", "upgrade"], ignore_case=True))
@flags.authorization(admin_only=False, su_only=True)
async def Elevator(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    await message.answer(text="Начинаю процедуру обновления...")
    subprocess.run(['nohup', 'python3', '/opt/MafiaIncTelegramBot/elevator.py'], check=False, user="daemon")
    return
