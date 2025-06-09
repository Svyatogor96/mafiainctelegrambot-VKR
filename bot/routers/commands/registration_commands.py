import re
from typing import Any

from dateutil.parser import *
from aiogram import Router, types, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ReplyKeyboardRemove
from aiogram.enums import MessageEntityType
from aiogram.utils.formatting import PhoneNumber
from aiogram.filters import StateFilter, Command
from bot.callbacks import RegistrationCallback
from bot.keyboards import *
from bot.states import SMRegistration, UserState
from backendapi.database import *

router = Router(name=__name__)


@router.callback_query(RegistrationCallback.filter(F.action == "YES"))
async def RegistrationCallbackHandler_YES(callback: CallbackQuery, callback_data: RegistrationCallback,
                                          state: FSMContext,
                                          session: AsyncSession) -> None:
    cities = await DB_GetAllCities(session)
    data_dict = {city.name: RegistrationCallback(action="set_city", city_id=city.id) for city in cities}
    kbm = InlineKeyboard_ByDict_CallbackData(cb_data_dict=data_dict)
    await callback.message.answer(text="Очень хорошо! Начнём с выбора города, в котором вы, в основном, будете играть. "
                                       "Играть можно и в других городах, но нам необходимо знать, сообщения о играх "
                                       "в каком городе вы хотели бы получать в первую очередь.", reply_markup=kbm)
    await state.set_state(SMRegistration.choosing_city)


@router.callback_query(RegistrationCallback.filter(F.action == "NO"))
async def RegistrationCallbackHandler_NO(callback: CallbackQuery, callback_data: RegistrationCallback,
                                         state: FSMContext) -> None:
    await callback.message.answer(text="Вы отказались от регистрации. Это означает, что мы не сможем предоставить вам "
                                       "скидки, акции, подарки, поздравления от клуба, вы не сможете участвовать "
                                       "в рейтинге.")
    await state.clear()


@router.callback_query(RegistrationCallback.filter(F.action == "set_city"), StateFilter(SMRegistration.choosing_city))
async def RegistrationCallbackHandler_SetCity(callback: CallbackQuery, callback_data: RegistrationCallback,
                                              state: FSMContext,
                                              session: AsyncSession) -> None:
    City: CCity = await DB_GetCityById(session=session, ID=callback_data.city_id)
    if City is not None:
        Person: CPerson = CPerson()
        Person.city = City
        await state.update_data(id_city=City.id)

        TelegramUserName: str | None = callback.from_user.username
        TelegramUserID: int = callback.from_user.id
        TelegramUserURL: str | None = callback.from_user.url

        Telegram: CTelegram = CTelegram(telegram_name=TelegramUserName, telegram_id=TelegramUserID)
        Telegram.telegram_url = TelegramUserURL
        Telegram.person = Person
        session.add_all([Person, Telegram])
        # У пользователя могут быть другие попытки зарегистрироваться.
        try:
            await session.commit()
            await state.update_data(id_telegram=Telegram.id)
            await state.update_data(telegram_id=Telegram.telegram_id)
            await callback.message.answer(text=f"Отлично! Мы запомнили, что ваш основной город <b>{City.name}</b>. ")
        except IntegrityError:
            await session.rollback()
            Telegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=TelegramUserID)
            Person = await Telegram.Person
            Person.city = City
            await session.commit()
            await state.update_data(id_telegram=Telegram.id)
            await state.update_data(telegram_id=Telegram.telegram_id)
            await callback.message.answer(text=f"Мы запомнили, что ваш основной город <b>{City.name}</b>. ")

        await state.update_data(id_person=Person.id)

        Messages = await DB_GetTelegramBotMessagesLikeCode(session=session, group="_NOTES_MESSAGES_",
                                                           like_code="REGISTRATION_LAW_",
                                                           order=True)
        for mess in Messages:
            await callback.message.answer(text=mess.message)
        data_dict = {"Подтверждаю": RegistrationCallback(action="apply_reg"),
                     "Отклоняю": RegistrationCallback(action="refuse_reg")}
        kbm = InlineKeyboard_ByDict_CallbackData(cb_data_dict=data_dict)
        await callback.message.answer(text="Подтверждаете согласие на обработку персональных данных?", reply_markup=kbm)
        await state.set_state(SMRegistration.wait_apply_registration)


@router.callback_query(RegistrationCallback.filter(F.action == "apply_reg"),
                       StateFilter(SMRegistration.wait_apply_registration))
async def RegistrationCallbackHandler_ApplyRegistration(callback: CallbackQuery, callback_data: RegistrationCallback,
                                                        state: FSMContext,
                                                        session: AsyncSession) -> None:
    await callback.message.answer(text=f"Отлично! Вы всегда сможете отредактировать Ваши персональные данные "
                                       f"(команда /profile) или "
                                       f"потребовать их удаления. Мы последуем Вашему требованию неукоснительно. "
                                       f"Позднее Вы также сможете удалить Ваши персональные "
                                       f"данные самостоятельно в разделе \"Профиль\" основного меню, "
                                       f"следуя инструкции.")
    await state.set_state(SMRegistration.choosing_person_sex)
    data_dict = {"Мужской": RegistrationCallback(action="set_sex", person_sex="M"),
                 "Женский": RegistrationCallback(action="set_sex", person_sex="F")}
    kbm = InlineKeyboard_ByDict_CallbackData(cb_data_dict=data_dict)
    await callback.message.answer(text="Выберите ваш пол.", reply_markup=kbm)


@router.callback_query(RegistrationCallback.filter(F.action == "refuse_reg"),
                       StateFilter(SMRegistration.wait_apply_registration))
async def RegistrationCallbackHandler_RefuseRegistration(callback: CallbackQuery, callback_data: RegistrationCallback,
                                                         state: FSMContext,
                                                         session: AsyncSession) -> None:
    await callback.message.answer(text=f"Для полноценного использования данного бота необходима завершённая "
                                       f"процедура регистрации, включая обработку персональных данных.")
    await state.clear()


@router.callback_query(RegistrationCallback.filter(F.action == "set_sex"),
                       StateFilter(SMRegistration.choosing_person_sex))
async def RegistrationCallbackHandler_SetSex(callback: CallbackQuery, callback_data: RegistrationCallback,
                                             state: FSMContext,
                                             session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Person = await session.get(CPerson, id_person)
    if Person is not None:
        SexLiteral = callback_data.person_sex
        Person.sex = SexLiteral
        await session.commit()
        await callback.message.answer(text="Спасибо! Сохранили Ваши данные.")
        if Person.sex == "F":
            await callback.message.answer(text="Теперь мы знаем, что вас можно поздравлять с праздником 8 марта! "
                                               "\U0001F469")
        if Person.sex == "M":
            await callback.message.answer(text="Теперь мы знаем, что вас можно поздравлять с праздником 23 февраля! ️"
                                               "\U0001F468")

        answer_str: str = "Введите, пожалуйста, вашу фамилию."

        caption_list: list[str] = []

        try:
            user_last_name: str | None = callback.from_user.last_name
            if user_last_name is not None and len(user_last_name) > 0:
                if await DB_BlackFilter(session=session, AnyText=user_last_name):
                    caption_list.append(user_last_name)
        except Exception as E:
            caption_list.clear()

        if len(caption_list) > 0:
            await callback.message.answer(text=answer_str,
                                          reply_markup=ReplyKeyboard_ByList(caption_list))
        else:
            await callback.message.answer(text=answer_str)

        await state.set_state(SMRegistration.choosing_person_family)
    else:
        pass  # Ошибочная ситуация.


@router.message(StateFilter(SMRegistration.choosing_person_family))
async def RegistrationCallbackHandler_SetFamily(message: types.Message, state: FSMContext,
                                                session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Family: str = message.text
    if await DB_BlackFilter(session=session, AnyText=Family):
        if len(Family) <= 50:
            Person = await session.get(CPerson, id_person)
            if Person is not None:
                Person.family = Family
                await session.commit()

                answer_str: str = "Спасибо. Сохранили Вашу фамилию. Теперь введите имя."

                caption_list: list[str] = []
                try:
                    user_first_name: str | None = message.from_user.first_name
                    if user_first_name is not None and len(user_first_name) > 0:
                        if await DB_BlackFilter(session=session, AnyText=user_first_name):
                            caption_list.append(user_first_name)
                except Exception as E:
                    caption_list.clear()

                if len(caption_list) > 0:
                    await message.answer(text=answer_str,
                                         reply_markup=ReplyKeyboard_ByList(caption_list))
                else:
                    await message.answer(text=answer_str)
                await state.set_state(SMRegistration.choosing_person_name)
            else:
                pass  # Ошибочная ситуация. На предыдущем шаге всё должно быть успешно новый CPerson должен был сохраниться
        else:
            await message.answer("Ваша фамилия длиннее 50 символов. Давайте попробуем ещё раз. Итак, Ваша фамилия?")
    else:
        await message.answer("О нет. Такое я пропустить не могу. Итак, Ваша фамилия?")


@router.message(StateFilter(SMRegistration.choosing_person_name))
async def RegistrationCallbackHandler_SetName(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]

    Name: str = message.text

    if await DB_BlackFilter(session=session, AnyText=Name):
        if len(Name) <= 50:
            Person: CPerson | None = await session.get(CPerson, id_person)
            if Person is not None:
                Person.name = Name
                await session.commit()
                # await message.answer(text="Спасибо. Сохранили Ваше имя. Теперь введите отчество. "
                #                          "Если отчества у Вас нет, то отправьте знак - (минус).",
                #                     reply_markup=ReplyKeyboardRemove())
                # await state.set_state(SMRegistration.choosing_person_father_name) # решили отказаться от отчества

                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                                     keyboard=[[types.KeyboardButton(text="Предоставить номер телефона",
                                                                                     request_contact=True)]])
                await message.answer(text="Введите Ваш номер телефона в формате +79876543210. Или позвольте "
                                          "прочитать из вашего профиля",
                                     reply_markup=keyboard)
                await state.set_state(SMRegistration.choosing_person_phone)
            else:
                pass  # Ошибочная ситуация. На предыдущем шаге всё должно быть успешно
        else:
            await message.answer("Ваше имя длиннее 50 символов. Давайте попробуем ещё раз. Итак, Ваше имя?")
    else:
        await message.answer("О нет. Такое я пропустить не могу. Итак, Ваше имя?")


# @router.message(SMRegistration.choosing_person_father_name)
# async def RegistrationCallbackHandler_SetFatherName(message: types.Message, state: FSMContext,
#                                                     session: AsyncSession) -> None:
#     data: dict[str, Any] = await state.get_data()
#     person_id: int = data["person_id"]
#     FatherName: str = message.text
#     if await DB_BlackFilter(session=session, AnyText=FatherName):
#         if len(FatherName) == 1:
#             if FatherName == "-":
#                 await state.set_state(SMRegistration.choosing_person_phone)
#
#                 await message.answer("Хорошо. Запомнили, что отчества нет. Введите Ваш номер "
#                                      "телефона в формате +79876543210.")
#
#                 return
#             else:
#                 await message.answer(f"{FatherName} в качестве отчества не подойдёт. Допустимо - (минус или прочерк). "
#                                      f"Попробуйте ещё раз. Итак, Ваше отчество?")
#         else:
#             if len(FatherName) <= 50:
#                 Person: CPerson | None = await session.get(CPerson, person_id)
#                 if Person is not None:
#                     Person.father_name = FatherName
#                     await session.commit()
#
#                     Phones: list[CPhone] = await Person.awaitable_attrs.phones
#
#                     if len(Phones) == 0:
#                         await state.set_state(SMRegistration.choosing_person_phone)
#                         await message.answer("Спасибо. Сохранили Ваше отчество. Введите Ваш номер телефона "
#                                              "в формате +79876543210.")
#                     else:
#                         await message.answer(f"Похоже, вы уже указывали один из своих номеров: "
#                                              f"{Phones[0].phone_number}. Пропускаем эту стадию.")
#                         await state.set_state(SMRegistration.choosing_person_email)
#                 else:
#                     pass  # Ошибочная ситуация. На предыдущем шаге всё должно быть успешно
#             else:
#                 await message.answer("Ваше отчество длиннее 50 символов. Давайте попробуем ещё раз. Итак, "
#                                      "Ваше отчество?")
#     else:
#         await message.answer("О нет. Такое я пропустить не могу. Итак, Ваше отчество?")


@router.message(StateFilter(SMRegistration.choosing_person_phone), F.contact)
async def RegistrationCallbackHandler_SetPhoneFromContact(message: types.Message, state: FSMContext,
                                                          session: AsyncSession) -> None:
    phone_number = message.contact.phone_number
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    error, result = await DB_SetPhoneForPerson(session=session, id_person=id_person, phone=phone_number)
    if result:
        await state.set_state(SMRegistration.choosing_person_birthdate)
        await message.answer(text="Спасибо. Сохранили Ваш телефон. Введите Ваш дату вашего рождения. "
                             "Например, 28.07.1978, или 2003-02-15, или 1995/06/23. Если я не сумею распознать, то "
                             "сообщу об этом.", reply_markup=ReplyKeyboardRemove())
    else:
        if error == "NOT_UNIQUE":
            await message.answer(text="Пользователь с таким номером уже зарегистрирован.",
                                 reply_markup=ReplyKeyboardRemove())
            await message.answer(text="Введите Ваш дату вашего рождения. Например, 28.07.1978, или 2003-02-15, или "
                                 "1995/06/23. Если я не сумею распознать, то "
                                 "сообщу об этом.", reply_markup=ReplyKeyboardRemove())
            await state.set_state(SMRegistration.choosing_person_birthdate)
        else:
            await message.answer(text="Ошибка при сохранении номера телефона.", reply_markup=ReplyKeyboardRemove())
            await message.answer(text="Введите Ваш дату вашего рождения. Например, 28.07.1978, или 2003-02-15, или "
                                 "1995/06/23. Если я не сумею распознать, то "
                                 "сообщу об этом.", reply_markup=ReplyKeyboardRemove())
            await state.set_state(SMRegistration.choosing_person_birthdate)


@router.message(StateFilter(SMRegistration.choosing_person_phone), F.text)
async def RegistrationCallbackHandler_SetPhone(message: types.Message, state: FSMContext,
                                               session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    phone_number: str = message.text
    if validate_mobile_number(phone_number):
        error, result = await DB_SetPhoneForPerson(session=session, id_person=id_person, phone=phone_number)
        if result:
            # await state.set_state(SMRegistration.choosing_person_email) # Решили отказаться от email
            # await message.answer("Спасибо. Сохранили Ваш телефон. Введите Ваш email в формате mymail@mailserver.ru.")
            await state.set_state(SMRegistration.choosing_person_birthdate)
            await message.answer("Спасибо. Сохранили Ваш телефон. Введите Ваш дату вашего рождения. "
                                 "Например, 28.07.1978, или 2003-02-15, или 1995/06/23. Если я не сумею распознать, то "
                                 "сообщу об этом.", reply_markup=ReplyKeyboardRemove())
        else:
            if error == "NOT_UNIQUE":
                await message.answer(text="Пользователь с таким номером уже зарегистрирован.",
                                     reply_markup=ReplyKeyboardRemove())
                await message.answer("Введите дату Вашего рождения. Например, 28.07.1978, или 2003-02-15, или "
                                     "1995/06/23. Если я не сумею распознать, то "
                                     "сообщу об этом.")
                await state.set_state(SMRegistration.choosing_person_birthdate)
            else:
                await message.answer(text="Ошибка при сохранении номера телефона.",
                                     reply_markup=ReplyKeyboardRemove())
                await message.answer("Введите Ваш дату вашего рождения. Например, 28.07.1978, или 2003-02-15, или "
                                     "1995/06/23. Если я не сумею распознать, то "
                                     "сообщу об этом.")
                await state.set_state(SMRegistration.choosing_person_birthdate)
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                             keyboard=[[types.KeyboardButton(text="Предоставить номер телефона",
                                                                             request_contact=True)]])
        await message.answer(text="Похоже, что Вы ввели не номер телефона. Попробуйте снова.",
                             reply_markup=keyboard)


# @router.message(SMRegistration.choosing_person_email)
# async def RegistrationCallbackHandler_SetEmail(message: types.Message, state: FSMContext,
#                                                session: AsyncSession) -> None:
#     data: dict[str, Any] = await state.get_data()
#     person_id: int = data["person_id"]
#     EmailAddress: str = message.text
#     if validate_email_address(EmailAddress):
#         error, result = await DB_SetEmailForPerson(session=session, email=EmailAddress, person_id=person_id)
#         if result:
#             await state.set_state(SMRegistration.choosing_person_birthdate)
#             await message.answer("Спасибо. Сохранили адрес Вашей электронной почты. Введите Ваш день рождения."
#                                  "Например, 28.07.1978, или 2003-02-15, или 1995/06/23. Если я не сумею распознать, то "
#                                  "сообщу об этом.")
#         else:
#             if error == "NOT_UNIQUE":
#                 await message.answer(text="Пользователь с таким email уже зарегистрирован.")
#             else:
#                 await message.answer(text="Ошибка при сохранении адреса электронной почты.")
#     else:
#         await message.answer("Похоже, что Вы ввели не адрес электронной почты. Попробуйте снова.")


@router.message(StateFilter(SMRegistration.choosing_person_birthdate))
async def RegistrationCallbackHandler_SetBirthdate(message: types.Message, state: FSMContext,
                                                   session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    BirthDateStr: str = message.text
    Person = await session.get(CPerson, id_person)
    if Person is not None:
        try:
            BirthDate = parse(timestr=BirthDateStr, dayfirst=True, fuzzy=True).date()
            Person.birthdate = BirthDate
            await session.commit()

            await message.answer(f"Спасибо. Сохранили дату Вашего рождения: {BirthDate.strftime('%d %B %Y')}")
            answer_text = ("\U0001F389 Регистрация почти завершена и теперь Вы член клуба игры Мафия в премиальном "
                           "формате. \U0001F389")
            await message.answer(text=answer_text)
            await message.answer("Теперь нужно выбрать псевдонимы для игры. Всего можно иметь не более трёх "
                                 "псевдонимов. Они должны быть приличными, не совпадать с игровыми ролями и быть "
                                 "уникальными в пределах клуба города.")
            try:
                Joke = await DB_GetRandomTelegramBotMessageFromGroup(session=session, group="_JOKE_",
                                                                     code="_CHOOSE_NICK_",
                                                                     sex=Person.sex)
                message_txt: str = Joke.message
            except IndexError as E:
                message_txt = "\U0001F92A"

            await message.answer(text=message_txt)
            await message.answer("Итак, ваш первый псевдоним?")
            await state.set_state(SMRegistration.choosing_nickname)
        except ValueError:
            await session.rollback()
            await message.answer(f"Кажется Вы ввели дату не в том формате: \"{message.text}\"."
                                 f"Давайте попробуем ещё раз, в другом формате.")
    else:
        pass  # Ошибочная ситуация. На предыдущем шаге всё должно быть успешно


@router.message(StateFilter(SMRegistration.choosing_nickname))
async def RegistrationSetCallbackHandler_Nickname(message: types.Message, state: FSMContext,
                                                  session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]

    NickName: str = message.text

    if await DB_BlackFilter(session=session, AnyText=NickName):
        error, result = await DB_AddNickToPerson(session=session, id_person=id_person, NickName=NickName)
        if not result:
            if error == "ERROR":
                await message.answer(text=error)
                await message.answer(text="А с этим мы разберёмся чуть позже.")
                await state.clear()
                await state.set_state(UserState.start)
                return
            if error == "NOT_UNIQUE":
                await message.answer(text="Такой псевдоним уже используется в вашем городе.")
                data_dict = {"Достаточно": RegistrationCallback(action="enough_nicks")}
                kbm = InlineKeyboard_ByDict_CallbackData(cb_data_dict=data_dict)
                await message.answer(text="Введите другой псевдоним.", reply_markup=kbm)
                return
            if result == "MAX_LIMIT":
                await message.answer(text="Достигнуто максимальное количество псевдонимов.")
                await state.clear()
                await state.set_state(UserState.start)
                await message.answer(text="Отлично! Вы готовы к играм как никогда!")
                await message.answer(text="Чтобы посмотреть расписание игр, вызовите команду /afisha.")
                return
        else:
            # Person: CPerson | None = await session.get(CPerson, person_id)
            # Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
            # if len(Nicknames) == 0:
            data_dict = {"Да": RegistrationCallback(action="add_nick"),
                         "Нет": RegistrationCallback(action="enough_nicks")}
            kbm = InlineKeyboard_ByDict_CallbackData(cb_data_dict=data_dict)
            await state.set_data(data=data)
            await message.answer(text="Отлично! Сохранили Ваш псевдоним. Добавим ещё?", reply_markup=kbm)
    else:
        await message.answer(text="Такой псевдоним не подойдёт. Он нарушает правила Клуба.")


@router.callback_query(RegistrationCallback.filter(F.action == "add_nick"),
                       StateFilter(SMRegistration.choosing_nickname))
async def On_AddNickname(callback: CallbackQuery, callback_data: RegistrationCallback,
                         state: FSMContext,
                         session: AsyncSession) -> None:
    data: dict[str, Any] = await state.get_data()
    id_person: int = data["id_person"]
    Person: CPerson | None = await session.get(CPerson, id_person)
    Nicks: list[CNickname] = await Person.awaitable_attrs.nicknames
    CountNicks = len(Nicks)
    await callback.message.answer(text=f"Число имеющихся псевдонимов: {CountNicks}")
    if CountNicks >= 3:
        await callback.message.answer(text="Отлично! Вы готовы к играм как никогда!")
        await state.set_state(UserState.start)
        await callback.message.answer(text="Чтобы посмотреть расписание игр, вызовите команду /afisha.")
    else:
        await state.set_state(SMRegistration.choosing_nickname)
        await callback.message.answer(text="Хорошо, введите ещё псевдоним.")


@router.callback_query(RegistrationCallback.filter(F.action == "enough_nicks"),
                       StateFilter(SMRegistration.choosing_nickname))
async def OnEnoughNicknames(callback: CallbackQuery, callback_data: RegistrationCallback,
                            state: FSMContext,
                            session: AsyncSession) -> None:
    await callback.message.answer(text="Отлично! Вы готовы к играм как никогда!")
    await callback.message.answer(text="Чтобы посмотреть расписание игр, вызовите команду /afisha.")
    await state.set_state(UserState.start)


@router.message(StateFilter(SMRegistration), Command("profile", "menu", "afisha", "start"))
async def AnyMenuItem(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    await message.answer(text="Давайте сначала завершим регистрацию.")
