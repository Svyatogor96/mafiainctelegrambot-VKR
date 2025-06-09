from typing import Any
from dateutil.parser import parse
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from bot.callbacks import UserCallback
from bot.keyboards import *
from bot.states import UserState
from backendapi.database import *

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')

router = Router(name=__name__)


@router.callback_query(StateFilter(UserState.start, None), UserCallback.filter(F.action == "EDIT_PROFILE_ENTRY"))
async def EditProfileEntry(callback: CallbackQuery, callback_data: UserCallback, state: FSMContext,
                           session: AsyncSession) -> None:
    await state.set_state(UserState.edit_profile)
    await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)


@router.callback_query(StateFilter(UserState.edit_profile), UserCallback.filter(F.action == "U_EDIT_PROFILE_EXIT"))
async def EditProfileExit(callback: CallbackQuery, callback_data: UserCallback, state: FSMContext,
                          session: AsyncSession) -> None:
    try:
        await callback.message.delete()
    finally:
        await callback.message.answer("Вы покинули режим редактирования профиля.")
        await state.set_state(UserState.start)
    return


@router.callback_query(StateFilter(UserState.edit_profile,
                                   UserState.edit_family,
                                   UserState.edit_name,
                                   UserState.edit_father_name,
                                   UserState.edit_sex,
                                   UserState.edit_birthdate,
                                   UserState.edit_phone,
                                   UserState.edit_phone_add,
                                   UserState.edit_phone_del,
                                   UserState.edit_phone_edt,
                                   UserState.edit_email,
                                   UserState.edit_email_add,
                                   UserState.edit_email_del,
                                   UserState.edit_email_edt,
                                   UserState.edit_nickname,
                                   UserState.edit_nickname_add,
                                   UserState.edit_nickname_del,
                                   UserState.edit_nickname_edt),
                       UserCallback.filter(F.action.startswith("U_EDIT_")))
async def CommonUserEditCallBackHandler(callback: CallbackQuery,
                                        callback_data: UserCallback,
                                        state: FSMContext,
                                        session: AsyncSession) -> None:
    match callback_data.action:
        case "U_EDIT_PROFILE":
            await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case value if value.startswith("U_EDIT_PROFILE_"):
            await ChangeProfileValueAsk(callback=callback, callback_data=callback_data, state=state, session=session)
            return

        case "U_EDIT_CANCEL":
            try:
                await callback.message.delete()
            finally:
                await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)
            return


"""
Обработка нажатия кнопки Отмена при редактировании ников, если пользователь отказывается вводить ник.
"""
@router.callback_query(StateFilter(UserState.edit_nickname_add,
                                   UserState.edit_nickname_edt),
                       UserCallback.filter(F.action.__eq__("CANCEL")))
async def NicknamesEditCancel(callback: CallbackQuery, callback_data: UserCallback,
                              state: FSMContext, session: AsyncSession) -> None:
    await EditProfileEntry(callback=callback, callback_data=callback_data, state=state, session=session)



async def EditProfileSelector(callback: CallbackQuery, callback_data: UserCallback,
                              state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    id_person: int = data["id_person"]

    Person: CPerson | None = await session.get(CPerson, id_person)
    PersonInfo: str = await Person.PersonInfo
    await AskSelectKBM(message=callback.message, message_text=PersonInfo + "Выберите для редактирования.", state=state,
                       edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                       next_state=UserState.edit_profile)


async def ChangeProfileValueAsk(callback: CallbackQuery, callback_data: UserCallback,
                                state: FSMContext, session: AsyncSession):
    action = callback_data.action.replace("U_EDIT_PROFILE_", "")
    Person: CPerson | None = await session.get(CPerson, callback_data.id_person)
    match action:
        case "FAMILY":
            await callback.message.delete()
            if Person.family is not None:
                message_text = f"Введите новую фамилию вместо {Person.family}."
            else:
                message_text = "Введите фамилию."

            await Ask(message=callback.message, message_text=message_text,
                      next_state=UserState.edit_family, state=state, edit=True, action_code="U_EDIT_CANCEL")
        case "NAME":
            await callback.message.delete()
            if Person.name is not None:
                message_text = f"Введите новое имя вместо {Person.name}."
            else:
                message_text = "Введите имя."

            await Ask(message=callback.message, message_text=message_text,
                      next_state=UserState.edit_name, state=state, edit=True, action_code="U_EDIT_CANCEL")
        case "FATHER_NAME":
            await callback.message.delete()
            if Person.father_name is not None:
                message_text = f"Введите новое отчество вместо {Person.father_name}."
            else:
                message_text = "Введите отчество."

            await Ask(message=callback.message, message_text=message_text,
                      next_state=UserState.edit_father_name, state=state, edit=True, action_code="U_EDIT_CANCEL")

        case "SEX":
            data = {"Мужской": UserCallback(action="U_EDIT_PROFILE_SET_SEX_M"),
                    "Женский": UserCallback(action="U_EDIT_PROFILE_SET_SEX_F"),
                    "Отмена": UserCallback(action="U_EDIT_CANCEL")}
            await AskSelect(message=callback.message,
                            message_text="Мы не в Европе, поэтому пола могу предложить только два.", state=state,
                            next_state=UserState.edit_sex, edit=True, data=data)
            return

        case "SET_SEX_M" | "SET_SEX_F":
            await callback.message.delete()
            await ProfileEdit_SetSex(callback=callback, callback_data=callback_data, session=session, state=state,
                                     Literal=action.replace("SET_SEX_", ""))
            return

        case "BIRTHDATE":
            await callback.message.delete()
            if Person.birthdate is not None:
                message_text = f"Введите новую дату рождения вместо {Person.birthdate.strftime('%d %B %Y')}."
            else:
                message_text = "Введите дату рождения."
            await Ask(message=callback.message, message_text=message_text,
                      next_state=UserState.edit_birthdate, state=state, edit=True, action_code="U_EDIT_CANCEL")
            return

        case "PHONE":
            await callback.message.delete()
            data = {"Добавить номер": UserCallback(action="U_EDIT_PROFILE_PHONE_ADD"),
                    "Удалить номер": UserCallback(action="U_EDIT_PROFILE_PHONE_DEL"),
                    "Редактировать номер": UserCallback(action="U_EDIT_PROFILE_PHONE_EDT"),
                    "Отмена": UserCallback(action="U_EDIT_CANCEL")}
            phones: list[CPhone] = await Person.awaitable_attrs.phones
            if phones is None or len(phones) == 0:
                del data["Удалить номер"]
                del data["Редактировать номер"]
            await AskSelect(message=callback.message, message_text="Выберите действие", state=state,
                            next_state=UserState.edit_phone,
                            data=data, edit=True)
            return

        case "PHONE_ADD":
            await ProfileEdit_AddPhone(message=callback.message, state=state)
            return

        case "PHONE_DEL":
            await ProfileEdit_PhoneEmailNickSelector(callback=callback, state=state, session=session,
                                                     action="DELETE_PHONE_NUMBER", next_state=UserState.edit_phone_del)
            return

        case "PHONE_EDT":
            await ProfileEdit_PhoneEmailNickSelector(callback=callback, state=state, session=session,
                                                     action="EDIT_PHONE_NUMBER", next_state=UserState.edit_phone_edt)
            return

        case "EMAIL":
            await callback.message.delete()
            data = {"Добавить email": UserCallback(action="U_EDIT_PROFILE_EMAIL_ADD"),
                    "Удалить email": UserCallback(action="U_EDIT_PROFILE_EMAIL_DEL"),
                    "Редактировать email": UserCallback(action="U_EDIT_PROFILE_EMAIL_EDT"),
                    "Отмена": UserCallback(action="U_EDIT_CANCEL")}
            phones: list[CPhone] = await Person.awaitable_attrs.phones
            if phones is None or len(phones) == 0:
                del data["Удалить email"]
                del data["Редактировать email"]
            await AskSelect(message=callback.message, message_text="Выберите действие", state=state,
                            next_state=UserState.edit_email,
                            data=data, edit=True)
            return

        case "EMAIL_ADD":
            await ProfileEdit_AddEmail(message=callback.message, state=state)
            return

        case "EMAIL_DEL":
            await ProfileEdit_PhoneEmailNickSelector(callback=callback, state=state, session=session,
                                                     action="DELETE_EMAIL", next_state=UserState.edit_email_del)
            return

        case "EMAIL_EDT":
            await ProfileEdit_PhoneEmailNickSelector(callback=callback, state=state, session=session,
                                                     action="EDIT_EMAIL", next_state=UserState.edit_email_edt)
            return

        case "NICKNAME":
            await callback.message.delete()
            data = {"Добавить псевдоним": UserCallback(action="U_EDIT_PROFILE_NICKNAME_ADD"),
                    "Удалить псевдоним": UserCallback(action="U_EDIT_PROFILE_NICKNAME_DEL"),
                    "Редактировать псевдоним": UserCallback(action="U_EDIT_PROFILE_NICKNAME_EDT"),
                    "Отмена": UserCallback(action="U_EDIT_CANCEL")}
            nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames

            if nicknames is None or len(nicknames) == 0:
                del data["Удалить псевдоним"]
                del data["Редактировать псевдоним"]
            elif len(nicknames) == 1:
                del data["Удалить псевдоним"]
            elif len(nicknames) == 3:
                del data["Добавить псевдоним"]

            message_text = ""
            if len(nicknames) > 0:
                message_text += "У вас есть следующие псевдонимы: "
                for index, nick in enumerate(nicknames):
                    if index < len(nicknames) - 1:
                        message_text += f"{nick.name}, "
                    else:
                        message_text += f"{nick.name}"

            message_text += "\nВыберите действие."

            await AskSelect(message=callback.message, message_text=message_text, state=state,
                            next_state=UserState.edit_nickname,
                            data=data, edit=True)
            return

        case "NICKNAME_ADD":
            await ProfileEdit_AddNickname(message=callback.message, state=state)
            return

        case "NICKNAME_DEL":
            await ProfileEdit_PhoneEmailNickSelector(callback=callback, state=state, session=session,
                                                     action="DELETE_NICKNAME", next_state=UserState.edit_nickname_del)
            return

        case "NICKNAME_EDT":
            await ProfileEdit_PhoneEmailNickSelector(callback=callback, state=state, session=session,
                                                     action="EDIT_NICKNAME", next_state=UserState.edit_nickname_select)
            return


async def ProfileEdit_AddPhone(message: types.Message, state: FSMContext):
    await Ask(message=message, message_text="Введите номер телефона.", state=state,
              next_state=UserState.edit_phone_add, edit=True, action_code="U_EDIT_CANCEL")


async def ProfileEdit_AddEmail(message: types.Message, state: FSMContext):
    await Ask(message=message, message_text="Введите email.", state=state,
              next_state=UserState.edit_email_add, edit=True, action_code="U_EDIT_CANCEL")


async def ProfileEdit_AddNickname(message: types.Message, state: FSMContext):
    await Ask(message=message, message_text="Введите псевдоним.", state=state,
              next_state=UserState.edit_nickname_add, edit=True, action_code="U_EDIT_CANCEL")


async def ProfileEdit_PhoneEmailNickSelector(callback: CallbackQuery, state: FSMContext, session: AsyncSession,
                                             action: str, next_state: State):
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Person: CPerson | None = await session.get(CPerson, id_person)
    message_text = ""
    if await state.get_state() == UserState.edit_phone:
        phones: list[CPhone] = await Person.awaitable_attrs.phones
        data = {phone.phone_number: UserCallback(action=action, id_phone=phone.id) for phone in phones}
        if next_state == UserState.edit_phone_del:
            message_text = "Какой номер удаляем?"
        if next_state == UserState.edit_phone_edt:
            message_text = "Какой номер редактируем?"

    if await state.get_state() == UserState.edit_email:
        emails: list[CEmail] = await Person.awaitable_attrs.emails
        data = {email.email_address: UserCallback(action=action, id_email=email.id) for email in emails}
        if next_state == UserState.edit_email_del:
            message_text = "Какой email удаляем?"
        if next_state == UserState.edit_email_edt:
            message_text = "Какой email редактируем?"

    if await state.get_state() == UserState.edit_nickname:
        nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
        data = {nickname.name: UserCallback(action=action, id_nickname=nickname.id) for nickname in nicknames}
        if next_state == UserState.edit_nickname_del:
            message_text = "Какой псевдоним удаляем?"
        if next_state == UserState.edit_nickname_select:
            message_text = "Какой псевдоним редактируем?"

    data["Отмена"] = UserCallback(action="U_EDIT_CANCEL")

    await AskSelect(message=callback.message, message_text=message_text, state=state,
                    next_state=next_state, data=data, edit=True)


@router.callback_query(UserCallback.filter(F.action == "DELETE_PHONE_NUMBER"), UserState.edit_phone_del)
async def ProfileEdit_DeletePhoneNumber(callback: CallbackQuery, callback_data: UserCallback,
                                        state: FSMContext, session: AsyncSession):
    id_phone: int = int(callback_data.id_phone)
    Phone: CPhone | None = await session.get(CPhone, id_phone)
    id_person = Phone.id_person
    error, result = await DB_DeletePhone(session=session, id_phone=id_phone)
    if result:
        Person: CPerson | None = await session.get(CPerson, id_person)
        PersonInfo: str = await Person.PersonInfo
        await AskSelectKBM(message=callback.message, message_text=PersonInfo + "Номер телефона удалён. "
                                                                               "Выберите для редактирования.",
                           state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=Person.id),
                           next_state=UserState.edit_profile)
    else:
        await bot.bot.MafiaBot.send_message(chat_id=callback.message.chat.id,
                                            text=f"Не удалось сохранить данные: {error}")
        await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)


@router.callback_query(UserCallback.filter(F.action.__eq__("DELETE_EMAIL")), UserState.edit_email_del)
async def ProfileEdit_DeleteEmail(callback: CallbackQuery, callback_data: UserCallback,
                                  state: FSMContext, session: AsyncSession):
    id_email: int = int(callback_data.id_email)
    Email: CEmail | None = await session.get(CEmail, id_email)
    id_person = Email.id_person
    error, result = await DB_DeleteEmail(session=session, id_email=id_email)
    if result:
        Person: CPerson | None = await session.get(CPerson, id_person)
        PersonInfo: str = await Person.PersonInfo
        await AskSelectKBM(message=callback.message, message_text=PersonInfo + "Email удалён. "
                                                                               "Выберите для редактирования.",
                           state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=Person.id),
                           next_state=UserState.edit_profile)
    else:
        await bot.bot.MafiaBot.send_message(chat_id=callback.message.chat.id,
                                            text=f"Не удалось сохранить данные: {error}")
        await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)


@router.callback_query(UserCallback.filter(F.action.__eq__("DELETE_NICKNAME")), UserState.edit_nickname_del)
async def ProfileEdit_DeleteNickname(callback: CallbackQuery, callback_data: UserCallback,
                                     state: FSMContext, session: AsyncSession):
    id_nickname: int = int(callback_data.id_nickname)
    Nickname: CNickname | None = await session.get(CNickname, id_nickname)
    id_person = Nickname.id_person
    error, result = await DB_DeleteNickname(session=session, id_nickname=id_nickname)
    if result:
        Person: CPerson | None = await session.get(CPerson, id_person)
        PersonInfo: str = await Person.PersonInfo
        await AskSelectKBM(message=callback.message, message_text=PersonInfo + "Псевдоним удалён. "
                                                                               "Выберите для редактирования.",
                           state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=Person.id),
                           next_state=UserState.edit_profile)
    else:
        await bot.bot.MafiaBot.send_message(chat_id=callback.message.chat.id,
                                            text=f"Не удалось сохранить данные: {error}")
        await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)


@router.callback_query(UserCallback.filter(F.action.__eq__("EDIT_PHONE_NUMBER")), UserState.edit_phone_edt)
async def ProfileEdit_EditPhone(callback: CallbackQuery, callback_data: UserCallback,
                                state: FSMContext, session: AsyncSession):
    id_phone: int = int(callback_data.id_phone)
    Phone: CPhone | None = await session.get(CPhone, id_phone)

    data = await state.get_data()
    data["id_phone"] = id_phone
    await state.set_data(data=data)

    await Ask(message=callback.message, message_text=f"Введите новый номер вместо {Phone.phone_number}",
              state=state, next_state=UserState.edit_phone_edt, edit=True, action_code="U_EDIT_CANCEL")


@router.callback_query(UserCallback.filter(F.action.__eq__("EDIT_EMAIL")), UserState.edit_email_edt)
async def ProfileEdit_EditEmail(callback: CallbackQuery, callback_data: UserCallback,
                                state: FSMContext, session: AsyncSession):
    id_email: int = int(callback_data.id_email)
    Email: CEmail | None = await session.get(CEmail, id_email)

    data = await state.get_data()
    data["id_email"] = id_email
    await state.set_data(data=data)

    await Ask(message=callback.message, message_text=f"Введите новый email вместо {Email.email_address}",
              state=state, next_state=UserState.edit_email_edt, edit=True, action_code="U_EDIT_CANCEL")


@router.callback_query(UserCallback.filter(F.action.__eq__("EDIT_NICKNAME")), UserState.edit_nickname_select)
async def ProfileEdit_EditNickname(callback: CallbackQuery, callback_data: UserCallback,
                                   state: FSMContext, session: AsyncSession):
    id_nickname: int = int(callback_data.id_nickname)
    Nickname: CNickname | None = await session.get(CNickname, id_nickname)

    data = await state.get_data()
    data["id_nickname"] = id_nickname
    await state.set_data(data=data)

    await Ask(message=callback.message, message_text=f"Введите новый псевдоним вместо {Nickname.name}",
              state=state, next_state=UserState.edit_nickname_edt, edit=True, action_code="U_EDIT_CANCEL")


@router.message(UserState.edit_family)
async def ProfileEdit_GetFamily(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    NewFamily: str = message.text
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    if await DB_BlackFilter(session=session, AnyText=NewFamily):
        if len(NewFamily) <= 50:
            Person = await session.get(CPerson, id_person)
            if Person is not None:
                PersonInfo: str = await Person.PersonInfo
                Person.family = NewFamily
                try:
                    await session.commit()
                    PersonInfo: str = await Person.PersonInfo
                    await AskSelectKBM(message=message, message_text=PersonInfo + "Успешно сохранили вашу фамилию. "
                                                                                  "Выберите для редактирования.",
                                       state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                       next_state=UserState.edit_profile)

                except SQLAlchemyError as E:
                    await bot.bot.MafiaBot.send_message(chat_id=message.chat.id,
                                                        text=f"Не удалось сохранить данные: {E.args}")
                    await AskSelectKBM(message=message,
                                       message_text=PersonInfo + "Выберите для редактирования.", state=state,
                                       edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                       next_state=UserState.edit_profile)
            else:
                pass  # Ошибочная ситуация.
        else:
            await message.answer("Ваша фамилия длиннее 50 символов. Давайте попробуем ещё раз. Итак, Ваша фамилия?")
    else:
        await message.answer("О нет. Такое я пропустить не могу. Итак, Ваша фамилия?")


@router.message(UserState.edit_name)
async def ProfileEdit_GetName(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    NewName: str = message.text
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    if await DB_BlackFilter(session=session, AnyText=NewName):
        if len(NewName) <= 50:
            Person = await session.get(CPerson, id_person)
            if Person is not None:
                PersonInfo: str = await Person.PersonInfo
                Person.name = NewName
                try:
                    await session.commit()
                    PersonInfo: str = await Person.PersonInfo
                    await AskSelectKBM(message=message, message_text=PersonInfo + "Успешно сохранено ваше новое имя. "
                                                                                  "Выберите для редактирования.",
                                       state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                       next_state=UserState.edit_profile)

                except SQLAlchemyError as E:
                    await bot.bot.MafiaBot.send_message(chat_id=message.chat.id,
                                                        text=f"Не удалось сохранить данные: {E.args}")
                    await AskSelectKBM(message=message,
                                       message_text=PersonInfo + "Выберите для редактирования.", state=state,
                                       edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                       next_state=UserState.edit_profile)

            else:
                pass  # Ошибочная ситуация.
        else:
            await message.answer("Ваше новое имя длиннее 50 символов. Давайте попробуем ещё раз. Итак, Ваше новое имя?")
    else:
        await message.answer("О нет. Такое я пропустить не могу. Итак, Ваше новое имя?")


@router.message(UserState.edit_father_name)
async def ProfileEdit_GetFatherName(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    NewFatherName: str = message.text
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    if await DB_BlackFilter(session=session, AnyText=NewFatherName):
        if len(NewFatherName) <= 50:
            Person = await session.get(CPerson, id_person)
            PersonInfo: str = await Person.PersonInfo
            if Person is not None:
                if NewFatherName == "-":
                    Person.father_name = None
                else:
                    Person.father_name = NewFatherName
                try:
                    await session.commit()
                    PersonInfo: str = await Person.PersonInfo
                    await AskSelectKBM(message=message, message_text=PersonInfo + "Успешно сохранено ваше новое "
                                                                                  "отчество. Выберите для "
                                                                                  "редактирования.",
                                       state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                       next_state=UserState.edit_profile)

                except SQLAlchemyError as E:
                    await bot.bot.MafiaBot.send_message(chat_id=message.chat.id,
                                                        text=f"Не удалось сохранить данные: {E.args}")
                    await AskSelectKBM(message=message,
                                       message_text=PersonInfo + "Выберите для редактирования.", state=state,
                                       edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                       next_state=UserState.edit_profile)

            else:
                pass  # Ошибочная ситуация.
        else:
            await message.answer("Ваше новое отчество длиннее 50 символов. Давайте попробуем ещё раз. "
                                 "Итак, Ваше новое отчество?")
    else:
        await message.answer("О нет. Такое я пропустить не могу. Итак, Ваше новое отчество?")


async def ProfileEdit_SetSex(callback: CallbackQuery, callback_data: UserCallback,
                             state: FSMContext, session: AsyncSession, Literal: str):
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Person = await session.get(CPerson, id_person)
    if Person is not None:
        Person.sex = Literal
        try:
            await session.commit()
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=callback.message, message_text=PersonInfo + "Ваши успешно данные сохранены. "
                                                                                   "Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        except SQLAlchemyError as E:
            await bot.bot.MafiaBot.send_message(chat_id=callback.message.chat.id,
                                                text=f"Не удалось сохранить данные: {E.args}")
            await EditProfileSelector(callback=callback, callback_data=callback_data, state=state, session=session)
    else:
        pass  # Ошибочная ситуация. На предыдущем шаге всё должно быть успешно новый CPerson должен был сохраниться


@router.message(UserState.edit_birthdate)
async def ProfileEdit_GetBirthDate(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Person = await session.get(CPerson, id_person)
    if Person is not None:
        PersonInfo: str = await Person.PersonInfo
        try:
            BirthDate = parse(timestr=message.text, dayfirst=True, fuzzy=True).date()
        except ValueError:
            await message.answer(f"Кажется Вы ввели дату не в том формате: \"{message.text}\"."
                                 f"Давайте попробуем ещё раз, в другом формате.")
            return
        Person.birthdate = BirthDate
        try:
            await session.commit()
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=message,
                               message_text=PersonInfo + "Успешно сохранен Ваш день рождения. "
                                                         "Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        except SQLAlchemyError as E:
            await bot.bot.MafiaBot.send_message(chat_id=message.chat.id, text=f"Не удалось сохранить данные: {E.args}")
            await AskSelectKBM(message=message,
                               message_text=PersonInfo + "Выберите для редактирования.", state=state,
                               edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)

    else:
        pass  # Ошибочная ситуация. На предыдущем шаге всё должно быть успешно новый CPerson должен был сохраниться


@router.message(UserState.edit_phone_add)
async def ProfileEdit_AddNewPhone(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    PhoneNumber: str = message.text
    if validate_mobile_number(PhoneNumber):
        error, result = await DB_SetPhoneForPerson(session=session, id_person=id_person, phone=PhoneNumber)
        if result:
            Person = await session.get(CPerson, id_person)
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=message, message_text=PersonInfo + "Ваши новый номер телефона успешно сохранён. "
                                                                          "Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text="Пользователь с таким номером уже зарегистрирован.")
            else:
                await message.answer(text="Ошибка при сохранении номера телефона.")
    else:
        await message.answer("Похоже, что Вы ввели не номер телефона. Попробуйте снова.")


@router.message(UserState.edit_phone_edt)
async def ProfileEdit_EditPhone(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    id_phone: int = data["id_phone"]
    PhoneNumber: str = message.text
    if validate_mobile_number(PhoneNumber):
        error, result = await DB_UpdatePhoneForPerson(session=session, id_phone=id_phone, Number=PhoneNumber)
        if result:
            Person = await session.get(CPerson, id_person)
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=message, message_text=PersonInfo + "Номер телефона успешно изменён. "
                                                                          "Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text="Пользователь с таким номером уже зарегистрирован.")
            else:
                await message.answer(text="Ошибка при сохранении номера телефона.")
    else:
        await message.answer("Похоже, что Вы ввели не номер телефона. Попробуйте снова.")


@router.message(UserState.edit_email_add)
async def ProfileEdit_AddNewEmail(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    email_address: str = message.text
    if validate_email_address(email_address):
        error, result = await DB_SetEmailForPerson(session=session, person_id=id_person, email=email_address)
        if result:
            Person = await session.get(CPerson, id_person)
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=message, message_text=PersonInfo + "Новый адрес электронной почты успешно "
                                                                          "сохранён. Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text="Пользователь с таким email уже зарегистрирован.")
            else:
                await message.answer(text="Ошибка при сохранении email.")
    else:
        await message.answer("Похоже, что Вы ввели не адрес электронной почты. Попробуйте снова.")


@router.message(UserState.edit_email_edt)
async def ProfileEdit_EditEmail(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    id_email: int = data["id_email"]
    EmailAddress: str = message.text
    if validate_mobile_number(EmailAddress):
        error, result = await DB_UpdateEmailForPerson(session=session, id_email=id_email, email_address=EmailAddress)
        if result:
            Person = await session.get(CPerson, id_person)
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=message, message_text=PersonInfo + "Адрес электронной почты успешно изменён. "
                                                                          "Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text="Пользователь с таким email уже зарегистрирован.")
            else:
                await message.answer(text="Ошибка при сохранении адреса электронной почты.")
    else:
        await message.answer("Похоже, что Вы ввели не адрес электронной почты. Попробуйте снова.")


@router.message(UserState.edit_nickname_add)
async def ProfileEdit_AddNewNickname(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Person: CPerson | None = await session.get(CPerson, id_person)

    Nickname: str = message.text

    if await DB_BlackFilter(session=session, AnyText=Nickname):
        error, result = await DB_AddNickToPerson(session=session, id_person=id_person, NickName=Nickname)
        if result:
            PersonInfo: str = await Person.PersonInfo
            if error == "MAX_LIMIT":
                message_text = PersonInfo + ("Новый псевдоним успешно сохранён. Достигнуто максимальное количество "
                                             "псевдонимов. Выберите для редактирования.")
            else:
                message_text = PersonInfo + "Новый псевдоним успешно сохранён. Выберите для редактирования."

            await AskSelectKBM(message=message, message_text=message_text, state=state, edit=True,
                               kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text=f"Псевдоним {Nickname} уже используется в вашем городе. "
                                          f"Введите другой псевдоним.")
            elif error == "MAX_LIMIT":
                PersonInfo: str = await Person.PersonInfo
                await AskSelectKBM(message=message, message_text=PersonInfo + "Достигнуто максимальное количество "
                                                                              "псевдонимов. Выберите для редактирования.",
                                   state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                   next_state=UserState.edit_profile)

            elif error == "ERROR":
                await message.answer(text="Ошибка при сохранении псевдонима.")
                PersonInfo: str = await Person.PersonInfo
                await AskSelectKBM(message=message,
                                   message_text=PersonInfo + "Выберите для редактирования.", state=state,
                                   edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                   next_state=UserState.edit_profile)

            else:
                await message.answer(text=f"Ошибка {error}")
                PersonInfo: str = await Person.PersonInfo
                await AskSelectKBM(message=message,
                                   message_text=PersonInfo + "Выберите для редактирования.", state=state,
                                   edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                                   next_state=UserState.edit_profile)
    else:
        await Ask(message=message, message_text="Такой ник нельзя присвоить. Давайте попробуем другой.", state=state,
                  next_state=UserState.edit_nickname_edt, edit=False)
        return


@router.message(UserState.edit_nickname_edt)
async def ProfileEdit_EditNickname(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    id_nickname: int = data["id_nickname"]

    Nickname: str = message.text

    if await DB_BlackFilter(session=session, AnyText=Nickname):
        error, result = await DB_UpdateNicknameForPerson(session=session, id_nickname=id_nickname, Name=Nickname)
        if result:
            Person = await session.get(CPerson, id_person)
            PersonInfo: str = await Person.PersonInfo
            await AskSelectKBM(message=message, message_text=PersonInfo + "Псевдоним успешно изменён. "
                                                                          "Выберите для редактирования.",
                               state=state, edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                               next_state=UserState.edit_profile)
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text="Пользователь с таким псевдонимом уже зарегистрирован в вашем городе.")
            else:
                await message.answer(text="Ошибка при сохранении псевдонима.")
    else:
        await Ask(message=message, message_text="Такой ник нельзя присвоить. Давайте попробуем другой.", state=state,
                  next_state=UserState.edit_nickname_edt, edit=False)
        return



async def Ask(message: types.Message, message_text: str, state: FSMContext,
                  next_state: State, edit: bool = False, action_code: str = "CANCEL") -> None:
    data = {"Отмена": UserCallback(action=action_code)}
    kbm = UserCBKeyboard(callbacks=data)
    if edit:
        if message.from_user.id == bot.bot.MafiaBot.id:
            try:
                await message.edit_text(text=message_text, reply_markup=kbm)
            except TelegramBadRequest:
                await message.answer(text=message_text, reply_markup=kbm)
        else:
            await message.answer(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    await state.set_state(next_state)



async def AskSelect(message: types.Message, message_text: str, state: FSMContext,
                    next_state: State | None, data: dict[str, UserCallback], edit: bool = False) -> None:
    kbm = UserCBKeyboard(callbacks=data)
    if edit:
        if message.from_user.id == bot.bot.MafiaBot.id:
            try:
                await message.edit_text(text=message_text, reply_markup=kbm)
            except TelegramBadRequest:
                await message.answer(text=message_text, reply_markup=kbm)
        else:
            await message.answer(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    if next_state is not None:
        await state.set_state(next_state)


async def AskSelectKBM(message: types.Message, message_text: str, state: FSMContext,
                       next_state: State | None, kbm: InlineKeyboardMarkup, edit: bool = False) -> None:
    if edit:
        if message.from_user.id == bot.bot.MafiaBot.id:
            try:
                await message.edit_text(text=message_text, reply_markup=kbm)
            except TelegramBadRequest:
                await message.answer(text=message_text, reply_markup=kbm)
        else:
            await message.answer(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    if next_state is not None:
        await state.set_state(next_state)


@router.message(StateFilter(UserState.edit_profile,
                            UserState.edit_family,
                            UserState.edit_name,
                            UserState.edit_father_name,
                            UserState.edit_sex,
                            UserState.edit_birthdate,
                            UserState.edit_phone,
                            UserState.edit_phone_add,
                            UserState.edit_phone_del,
                            UserState.edit_phone_edt,
                            UserState.edit_email,
                            UserState.edit_email_add,
                            UserState.edit_email_del,
                            UserState.edit_email_edt,
                            UserState.edit_nickname,
                            UserState.edit_nickname_add,
                            UserState.edit_nickname_del,
                            UserState.edit_nickname_edt), Command("profile", "menu", "afisha", "start"))
async def AnyMenuItem(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    id_person: int = data["id_person"]

    Person: CPerson | None = await session.get(CPerson, id_person)
    PersonInfo: str = await Person.PersonInfo
    await AskSelectKBM(message=message, message_text=PersonInfo + "Выберите для редактирования.", state=state,
                       edit=True, kbm=UserEditProfileKeyboard(id_person=id_person),
                       next_state=UserState.edit_profile)
