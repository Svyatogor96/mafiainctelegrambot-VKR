from typing import Any
from aiogram.types import CallbackQuery
from aiogram import Router, types, F, flags
from bot.keyboards.admin_keyboards import *
from bot.states import AdminState
from .admin_commands import GoToMainMenu

router = Router(name=__name__)


async def set_new(state: FSMContext) -> None:
    data = await state.get_data()
    data["new"] = True
    data["id_place"] = 0
    data["game_types"] = {}
    await state.set_data(data=data)


async def set_not_new(state: FSMContext, id_place: int, session: AsyncSession) -> None:
    data = await state.get_data()
    data["new"] = False
    data["id_place"] = id_place
    Place: CPlace | None = await session.get(CPlace, id_place)
    data["title"] = Place.title
    data["address"] = Place.address
    data["seats"] = Place.seats
    GameTypes: list[CPlaceGameTypeAssociation] = Place.game_types_acc
    if len(GameTypes) > 0:
        data["game_types"] = {item.id_game_type: item.game_type.title for item in GameTypes}
    else:
        data["game_types"] = {}
    await state.set_data(data=data)


async def is_new(state: FSMContext) -> bool:
    data = await state.get_data()
    return "new" in data and data["new"] is True


async def GameTypesButtons(state: FSMContext,
                           session: AsyncSession,
                           action: str,
                           AllButton: bool = False,
                           CancelButton: bool = False,
                           CancelButtonCaption: str = "Отмена",
                           DeleteMode: bool = False) -> dict[str, AdminCallback]:
    data = await state.get_data()
    game_types: dict[int, str] = data["game_types"]
    if DeleteMode:
        result = {value: AdminCallback(action=action, id_game_type=key) for key, value in game_types.items()}
    else:
        all_game_types: dict[int, str] = await DB_GetAllGameTypesAsDict(session=session)
        all_game_types = dict(sorted(dict(all_game_types.items() - game_types.items()).items()))
        result = {value: AdminCallback(action=action, id_game_type=key) for key, value in all_game_types.items()}

    if AllButton:
        result["Выбрать все"] = AdminCallback(action=action, id_game_type=-1)
    if CancelButton:
        result[CancelButtonCaption] = AdminCallback(action=action, id_game_type=0)
    return result


async def GameTypeSelector(callback: CallbackQuery,
                           callback_data: AdminCallback,
                           state: FSMContext,
                           session: AsyncSession,
                           action: str,
                           edit: bool = False) -> None:
    if action == "PE_PLAСE_EDIT_GAME_TYPES_DEL":
        kbm = await GameTypesButtons(state=state,
                                     session=session,
                                     action="PE_PROCESS_DEL_GAME_TYPE",
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
            await ConfirmPlaceRecord(message=callback.message, state=state,
                                     additional_answer_text="Нечего удалять.", edit=edit)
            return

    if action == "PE_PLAСE_EDIT_GAME_TYPES_ADD":
        kbm = await GameTypesButtons(state=state,
                                     session=session,
                                     action="PE_PROCESS_ADD_GAME_TYPE",
                                     AllButton=True,
                                     CancelButton=True,
                                     CancelButtonCaption="Достаточно",
                                     DeleteMode=False)
        await AskSelect(message_text="Выберите для добавления.",
                        message=callback.message,
                        state=state,
                        next_state=None,
                        cb_data_dict=kbm,
                        edit=edit)
        return


@router.callback_query(AdminCallback.filter(F.action.startswith("PE_")))
@flags.authorization(admin_only=True, su_only=False)
async def CommonAdminPlacesEditorHandler(callback: CallbackQuery,
                                         callback_data: AdminCallback,
                                         state: FSMContext,
                                         session: AsyncSession) -> None:
    match callback_data.action:
        case "PE_NEW":
            # добавление нового места для игры
            await set_new(state=state)
            await state.set_state(AdminState.add_place)
            await Ask(message=callback.message, message_text="Введите название.", state=state,
                      next_state=AdminState.setting_place_title, action_code="PE_CANCEL")
            return
        case "PE_COMMIT":
            data = await state.get_data()
            if await is_new(state):
                result, error = await AddNewPlace(session=session, data=data, id_city=data["id_city"])
            else:
                result, error = await UpdatePlace(session=session, data=data, id_place=data["id_place"],
                                                  id_city=data["id_city"])
            if not result:
                answer_str = f"Не удалось сохранить: {error}"
            else:
                answer_str = "Успешно. Что дальше?"
            await GoToMainMenu(message=callback.message, message_text=answer_str, state=state, edit=True)
            return
        case "PE_EDIT_PLACE":
            # редактирование имеющегося места для игры
            data = await state.get_data()
            id_moderator = data["id_moderator"]
            places = await DB_GetPlacesByModeratorID(session=session, id_moderator=id_moderator)
            if len(places) > 0:
                buttons = {place.title: AdminCallback(action="PE_SELECT_PLACE", id_place=place.id) for place in places}
                buttons["Отмена"] = AdminCallback(action="PE_CANCEL", id_place=0)
                await AskSelect(message=callback.message, state=state,
                                message_text="Выберите место для редактирования.",
                                cb_data_dict=buttons, next_state=AdminState.edit_place, edit=True)
            else:
                await callback.message.answer(text="А нечего пока редактировать. Нужно добавить "
                                                   "места для проведения игр.")
                await GoToMainMenu(message=callback.message, message_text="Что требуется?", state=state)
            return

        case "PE_SELECT_PLACE":
            id_place: int = int(callback_data.id_place)
            await set_not_new(state=state, id_place=id_place, session=session)
            await WhatToEdit(message=callback.message, state=state, edit=True)
            return

        case "PE_CORRECT_PLACE":
            # корректировка текущего места игры
            await WhatToEdit(message=callback.message, state=state, edit=True)
            return
        case "PE_PLACE_EDIT_TITLE":
            data = await state.get_data()
            message_text = f"Введите новое название вместо \"{data['title']}\""
            await Ask(message=callback.message, message_text=message_text, state=state,
                      next_state=AdminState.setting_place_title, action_code="PE_CANCEL")
            return
        case "PE_PLACE_EDIT_ADDRESS":
            data = await state.get_data()
            message_text = f"Введите новый адрес вместо \"{data['address']}\""
            await Ask(message=callback.message, message_text=message_text, state=state,
                      next_state=AdminState.setting_place_address, action_code="PE_CANCEL")
            return
        case "PE_PLACE_EDIT_SEATS":
            data = await state.get_data()
            message_text = f"Введите другое число мест вместо \"{data['seats']}\""
            await Ask(message=callback.message, message_text=message_text, state=state,
                      next_state=AdminState.setting_place_seats, action_code="PE_CANCEL")
            return
        case "PE_PLAСE_EDIT_GAME_TYPES":
            await OnEditGameTypesButtonClick(callback=callback, callback_data=callback_data, state=state,
                                             session=session)
            return

        case value if value.startswith("PE_PLAСE_EDIT_GAME_TYPES"):
            await GameTypeSelector(action=value, callback=callback, callback_data=callback_data,
                                   state=state, session=session, edit=True)
            return
        case "PE_PROCESS_ADD_GAME_TYPE":
            await AddGameType(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "PE_PROCESS_DEL_GAME_TYPE":
            await DeleteGameType(callback=callback, callback_data=callback_data, state=state, session=session)
            return
        case "PE_DELETE_PLACE":
            # удаление места для игры
            return
        case "PE_CANCEL":
            await GoToMainMenu(message=callback.message, message_text="Отменили. Что теперь?",
                               state=state, edit=True)
            return


async def AddGameType(callback: CallbackQuery,
                      callback_data: AdminCallback, state: FSMContext, session: AsyncSession):
    id_game_type: int = int(callback_data.id_game_type)
    # Нажали "Все"
    if id_game_type == -1:
        data = await state.get_data()
        all_types = await DB_GetAllGameTypes(session=session)
        data["game_types"] = {item.id: item.title for item in all_types}
        await state.set_data(data=data)
        await ConfirmPlaceRecord(message=callback.message, state=state, additional_answer_text="Ок.", edit=True)
        return
    # Нажали "Достаточно"
    if id_game_type == 0:
        await ConfirmPlaceRecord(message=callback.message, state=state, additional_answer_text="Ок.", edit=True)
        return
    GameType: CGameType | None = await session.get(CGameType, id_game_type)
    data = await state.get_data()
    game_types = data["game_types"]
    game_types[GameType.id] = GameType.title
    await state.set_data(data=data)
    kbm = await GameTypesButtons(state=state, session=session,
                                 action="PE_PROCESS_ADD_GAME_TYPE",
                                 AllButton=True, CancelButton=True,
                                 CancelButtonCaption="Достаточно", DeleteMode=False)
    await AskSelect(message=callback.message, message_text="Ещё добавить?",
                    state=state, next_state=None, cb_data_dict=kbm, edit=True)


async def DeleteGameType(callback: CallbackQuery,
                         callback_data: AdminCallback, state: FSMContext, session: AsyncSession):
    id_game_type: int = int(callback_data.id_game_type)
    if id_game_type == 0:
        await ConfirmPlaceRecord(message=callback.message, state=state, additional_answer_text="Ок.", edit=True)
        return
    data = await state.get_data()
    if id_game_type == -1:
        data["game_types"] = {}
        await ConfirmPlaceRecord(message=callback.message, state=state, additional_answer_text="Более нечего удалять.",
                                 edit=True)
        return

    game_types = data["game_types"]
    if id_game_type > 0:
        del game_types[id_game_type]
        await state.set_data(data=data)

    kbm = await GameTypesButtons(state=state, session=session,
                                 action="PE_PROCESS_DEL_GAME_TYPE",
                                 AllButton=True, CancelButton=True,
                                 CancelButtonCaption="Достаточно", DeleteMode=True)
    await AskSelect(message=callback.message, message_text="Ещё удалить?",
                    state=state, next_state=None, cb_data_dict=kbm, edit=True)


@router.message(AdminState.setting_place_title)
@flags.authorization(admin_only=True, su_only=False)
async def OnInputPlaceTitle(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    id_city = data["id_city"]
    title = message.text
    City: CCity | None = await session.get(CCity, id_city)
    check: bool = await DB_CheckPlaceTitleInCity(session=session, id_city=id_city, title=title)
    if not check:
        await message.answer(text=f"Место для проведения игр с названием \"{title}\" в городе {City.name} "
                                  f"уже существует.")
        return
    data["title"] = title
    await state.set_data(data=data)
    if await is_new(state):
        await Ask(message=message, message_text="Введите адрес места", state=state,
                  next_state=AdminState.setting_place_address, action_code="PE_CANCEL")
    else:
        await ConfirmPlaceRecord(message=message, state=state)


@router.message(AdminState.setting_place_address)
@flags.authorization(admin_only=True, su_only=False)
async def OnInputPlaceAddress(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    address = message.text
    data["address"] = address
    await state.set_data(data=data)
    if await is_new(state):
        await Ask(message=message, message_text="Введите количество мест.", state=state,
                  next_state=AdminState.setting_place_seats, action_code="PE_CANCEL")
    else:
        await ConfirmPlaceRecord(message=message, state=state)


@router.message(AdminState.setting_place_seats)
@flags.authorization(admin_only=True, su_only=False)
async def OnInputPlaceSeats(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        seats: int = int(message.text)
    except ValueError:
        await message.answer(text=f"\"{message.text}\" как число мест не подойдёт. Давайте попробуем что-то другое.")
        return
    if seats < 0 or seats > 25:
        await message.answer(text=f"\"{seats}\" игроков. Хорошая шутка. Давайте попробуем что-то другое.")
        return
    data["seats"] = seats
    await state.set_data(data=data)
    if await is_new(state):
        kbm = await GameTypesButtons(action="PE_PROCESS_ADD_GAME_TYPE",
                                     state=state,
                                     session=session,
                                     CancelButton=True,
                                     AllButton=True,
                                     CancelButtonCaption="Достаточно",
                                     DeleteMode=False)
        await AskSelect(message=message,
                        message_text=f"Задайте виды игр, которые можно проводить в \"{data['title']}\".",
                        state=state,
                        next_state=AdminState.setting_place_game_types,
                        cb_data_dict=kbm)
    else:
        await ConfirmPlaceRecord(message=message, state=state)


async def WhatToEdit(message: types.Message, state: FSMContext, edit: bool = False) -> None:
    data = await state.get_data()
    id_place = data["id_place"]
    message_text = "Что будем редактировать?\n"

    game_types: dict[int, str] = data["game_types"]

    types_str = "Можно проводить следующие типы игр:\n"
    for key, value in game_types.items():
        types_str += f"{value}\n"

    message_text += (f"<b>Наименование:</b> {data['title']}\n"
                     f"<b>Адрес</b> {data['address']}\n"
                     f"<b>Число мест</b> {data['seats']}\n"
                     + types_str)

    kbm = {"Название": AdminCallback(action="PE_PLACE_EDIT_TITLE", id_place=id_place),
           "Адрес": AdminCallback(action="PE_PLACE_EDIT_ADDRESS", id_place=id_place),
           "Число мест": AdminCallback(action="PE_PLACE_EDIT_SEATS", id_place=id_place),
           "Виды игр": AdminCallback(action="PE_PLAСE_EDIT_GAME_TYPES", id_place=id_place),
           "Отмена": AdminCallback(action="PE_CANCEL")}

    await AskSelect(message=message,
                    state=state,
                    cb_data_dict=kbm,
                    next_state=AdminState.edit_place, message_text=message_text, edit=edit)


async def AddNewPlace(session: AsyncSession, data: dict[str, Any], id_city: int) -> tuple[bool, str]:
    return await DB_AddNewPlace(session=session, title=data["title"], address=data["address"],
                                seats=data["seats"], game_types=data["game_types"], id_city=id_city)


async def UpdatePlace(session: AsyncSession, data: dict[str, Any], id_place: int, id_city: int) -> tuple[bool, str]:
    return await DB_UpdatePlace(session=session, title=data["title"], address=data["address"],
                                seats=data["seats"], game_types=data["game_types"], id_city=id_city, id_place=id_place)


@flags.authorization(admin_only=True, su_only=False)
async def ConfirmPlaceRecord(message: types.Message, state: FSMContext, additional_answer_text: str = None,
                             edit: bool = False) -> None:
    data = await state.get_data()
    id_place: int = data["id_place"]
    kbm = {"Сохранить": AdminCallback(action="PE_COMMIT", id_place=id_place),
           "Редактировать": AdminCallback(action="PE_CORRECT_PLACE", id_place=id_place),
           "Отмена": AdminCallback(action="PE_CANCEL")}

    game_types: dict[int, str] = data["game_types"]

    types_str = "Можно проводить следующие типы игр:\n"
    for index, (key, value) in enumerate(game_types.items()):
        types_str += f"{index + 1}. {value}\n"

    if additional_answer_text is not None:
        answer_str = f"{additional_answer_text}\n"
    else:
        answer_str = ""

    if await is_new(state):
        answer_str += f"Принято.\nНовое место для проведения игр.\n"
    else:
        answer_str += f"Принято.\nСледующие изменения.\n"
    answer_str += (f"<b>Наименование:</b> {data['title']}\n"
                   f"<b>Адрес</b> {data['address']}\n"
                   f"<b>Число мест</b> {data['seats']}\n"
                   + types_str + f"Сохранить эти данные?")
    await state.set_state(AdminState.save_place)
    if edit:
        await message.edit_text(text=answer_str,
                                reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))
    else:
        await message.answer(text=answer_str, reply_markup=InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=kbm))


async def OnEditGameTypesButtonClick(callback: CallbackQuery,
                                     callback_data: AdminCallback,
                                     state: FSMContext,
                                     session: AsyncSession) -> None:
    id_place: int = int(callback_data.id_place)
    data = await state.get_data()
    data['mode'] = 'edit_place_game_types'
    await state.set_data(data=data)
    await state.set_state(AdminState.setting_place_game_types)
    kbm = {"Добавляем": AdminCallback(action="PE_PLAСE_EDIT_GAME_TYPES_ADD", id_place=id_place),
           "Удаляем": AdminCallback(action="PE_PLAСE_EDIT_GAME_TYPES_DEL", id_place=id_place),
           "Отмена": AdminCallback(action="PE_CORRECT_PLACE", id_place=id_place)}

    await AskSelect(message=callback.message, message_text="Добавляем или удаляем?",
                    state=state, next_state=AdminState.setting_place_game_types, cb_data_dict=kbm, edit=True)
