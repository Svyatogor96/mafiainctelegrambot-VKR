import asyncio
from aiogram import Router, types, F, html
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

import bot.bot
from bot.callbacks import UserCallback
from bot.keyboards import *
from bot.states import UserState
from database.database import *
from bot.middlewares.authorization import PersonIsAdmin
from apscheduler.schedulers.asyncio import AsyncIOScheduler

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')

router = Router(name=__name__)

# Объект блокировки.
# Используем его для выполнения кода, который не должен выполняться несколько раз
# 27.05.2025 Попытка решить проблему задвоенния записей на игру, предположительно из-за плохой связи
# и поттупливания. Пользователи нажимают многократно кнопку, не получив реакцию
lock = asyncio.Lock()

async def DebugMessage(message: str) -> None:
    await bot.bot.MafiaBot.send_message(chat_id=438204704, text=message)



async def ResetState(state: FSMContext):
    await state.clear()
    await state.set_state(UserState.start)


async def CheckState(message: types.Message, state: FSMContext, session: AsyncSession) -> bool:
    _state: str | None = await state.get_state()
    if _state is not None and _state != UserState.start:
        StateClassName = _state.split(":")[0]
        if StateClassName == "SMRegistration":
            await message.answer(text=f"Вы не завершили регистрацию.")
            return False
        if StateClassName == "AdminState":
            await message.answer(text=f"Выйдите из режима ведущего игр")
            return False
        if StateClassName == "SUState":
            await message.answer(text=f"Босс, сначала нужно выйти из режима суперадмина.")
            return False
    return True


async def CheckClearMessage(message: types.Message):
    try:
        await message.chat.delete_message(message.message_id - 1)
    except TelegramBadRequest:
        pass


@router.callback_query(StateFilter(UserState.start), UserCallback.filter(F.action.startswith("U_")))
async def CommonUserCallBackHandler(callback: CallbackQuery,
                                    callback_data: UserCallback,
                                    state: FSMContext,
                                    session: AsyncSession) -> None:
    match callback_data.action:
        case "U_SUGGEST_CITY":
            await SuggestCity(callback=callback, session=session, state=state, edit=True)
            return

        case "U_SELECT_CITY":
            await ChangeCity(callback=callback, callback_data=callback_data, state=state, session=session, edit=True)
            return

        case "U_BILLBOARDS":
            await GetBillboards(message=callback.message, state=state, session=session)
            return

        case "U_PAY":
            # await SelectPay(callback=callback, callback_data=callback_data, state=state, session=session, edit=True)
            await callback.message.answer("Оплата через бота пока недоступна. Но мы уже работаем над этим.")
            return

        case "U_PROFILE":
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                pass
            await Profile(message=callback.message, session=session, state=state)
            return

        case "U_CANCEL":
            TgBM: CTelegramBotMessage = await DB_GetRandomTelegramBotMessageFromGroup(session=session,
                                                                                      group="_START_MESSAGES_")
            data = await state.get_data()
            id_person: int = data["id_person"]
            Person: CPerson | None = await session.get(CPerson, id_person)
            StartMessage = await TgBM.Message
            await state.set_state(UserState.start)
            await GoToUserMainMenu(message=callback.message, message_text=str(StartMessage).format(Person.FormatName),
                                   state=state, session=session, edit=True)
            return


async def DropState(state: FSMContext) -> None:
    data = await state.get_data()

    telegram_id: int | None = None
    id_telegram: int | None = None
    id_person: int | None = None
    id_city: int | None = None

    if "telegram_id" in data:
        telegram_id = data["telegram_id"]
    if "id_telegram" in data:
        id_telegram = data["id_telegram"]
    if "id_person" in data:
        id_person = data["id_person"]
    if "id_city" in data:
        id_city = data["id_city"]

    await state.clear()

    if telegram_id is not None:
        data["telegram_id"] = telegram_id
    if id_telegram is not None:
        data["id_telegram"] = id_telegram
    if id_person is not None:
        data["id_person"] = id_person
    if id_city is not None:
        data["id_city"] = id_city

    await state.set_data(data=data)
    await state.set_state(UserState.start)


async def GoToUserMainMenu(message: types.Message, message_text: str, state: FSMContext, session: AsyncSession,
                           edit: bool = False) -> None:
    _check: bool = await CheckState(message=message, state=state, session=session)
    if _check:
        await DropState(state)
        if edit:
            if message.from_user.id == bot.bot.MafiaBot.id and message.reply_markup is not None:
                try:
                    await message.edit_text(text=message_text, reply_markup=UserMainMenuKeyboard())
                except TelegramBadRequest:
                    await message.answer(text=message_text, reply_markup=UserMainMenuKeyboard())
            else:
                await message.answer(text=message_text, reply_markup=UserMainMenuKeyboard())
        else:
            await message.answer(text=message_text, reply_markup=UserMainMenuKeyboard())


async def SuggestToRegister(message: types.Message, session: AsyncSession) -> None:
    TgBM: CTelegramBotMessage = await DB_GetRandomTelegramBotMessageFromGroup(session=session,
                                                                              group="_START_MESSAGES_")
    StartMessage = await TgBM.Message
    if StartMessage is not None:
        await message.answer(text=str(StartMessage).format(message.from_user.full_name))
    await message.answer(text="Предлагаем пройти регистрацию, чтобы пользоваться всеми преимуществами клуба.",
                         reply_markup=InlineKeyboard_Yes_No_For_Registration())

"""
Обработка текстовых команд /start и /menu
Работают при состояниях None или UserState.start
"""
@router.message(StateFilter(None, UserState.start), Command(commands=["start", "menu"]))
async def StartHandler(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    user: types.User = message.from_user
    if user.is_bot:
        await message.reply(text="Пока не умею работать с ботами.")
        return
    await CheckClearMessage(message=message)
    await state.update_data(telegram_id=user.id)
    Telegram: CTelegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=message.from_user.id)
    if Telegram is not None:
        await state.update_data(id_telegram=Telegram.id)
        Person: CPerson = await Telegram.Person
        if Person is not None:
            await state.update_data(id_person=Person.id)
            await state.update_data(id_city=Person.city.id)
            Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
            if len(Nicknames) > 0 and Person.family is not None and Person.name is not None:
                TgBM: CTelegramBotMessage = await DB_GetRandomTelegramBotMessageFromGroup(session=session,
                                                                                          group="_START_MESSAGES_")
                StartMessage = await TgBM.Message
                await GoToUserMainMenu(message=message, message_text=str(StartMessage).format(Person.FormatName),
                                       state=state, session=session)
                # убери потом
                if Telegram.telegram_url is None:
                    Telegram.telegram_url = user.url
                    await session.commit()
                ######

            else:
                await message.answer(text="Ваш профиль не заполнен. Необходимо завершить процедуру регистрации.")
                await SuggestToRegister(message=message, session=session)
        else:
            await SuggestToRegister(message=message, session=session)
    else:
        await SuggestToRegister(message=message, session=session)

"""
Обработка текстовой команды /afisha
Работает при состояниях None или UserState.start
"""
@router.message(StateFilter(UserState.edit_profile), Command("afisha"))
async def Timetable(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
        await message.answer(text="Вы в режиме редактирования профиля")

@router.message(StateFilter(None, UserState.start), Command("afisha"))
async def Timetable(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    await TryLoadProfile(TelegramID=message.chat.id, state=state, session=session)
    Telegram: CTelegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=message.from_user.id)
    if Telegram is not None:
        await state.update_data(id_telegram=Telegram.id)
        await state.update_data(telegram_id=Telegram.telegram_id)
        Person = await Telegram.Person
        if Person is not None:
            await state.update_data(id_person=Person.id)
            City: CCity = await Person.awaitable_attrs.city
            await state.update_data(id_city=City.id)

            Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
            if len(Nicknames) > 0 and Person.family is not None and Person.name is not None:
                await state.set_state(UserState.start)
                await GetBillboards(message=message, state=state, session=session)
            else:
                await message.answer(text="Ваш профиль не заполнен. Необходимо завершить процедуру регистрации.")
                await SuggestToRegister(message=message, session=session)
        else:
            await message.answer(text="Вы не завершили процедуру регистрации.")
            await SuggestToRegister(message=message, session=session)
    else:
        await SuggestToRegister(message=message, session=session)


"""
Обработка текстовой команды /profile для перехода в режим редактирования профиля
"""
@router.message(StateFilter(None, UserState.start), Command("profile"))
async def Profile(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    await TryLoadProfile(TelegramID=message.chat.id, state=state, session=session)
    data = await state.get_data()
    Person: CPerson | None = None
    if "id_telegram" not in data:
        Telegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=message.from_user.id)
        if Telegram is not None:
            await state.update_data(id_telegram=Telegram.id)
            await state.update_data(telegram_id=Telegram.telegram_id)
            data = await state.get_data()
            Person = await Telegram.Person
            if Person is not None:
                if "id_person" not in data:
                    await state.update_data(id_person=Person.id)
                if "id_city" not in data:
                    City: CCity = await Person.awaitable_attrs.city
                    await state.update_data(id_city=City.id)
                data = await state.get_data()
                await state.set_state(UserState.start)
            else:
                await SuggestToRegister(message=message, session=session)
                return
        else:
            await SuggestToRegister(message=message, session=session)
            return

    if "id_person" in data:
        id_person: int = data["id_person"]
        if Person is None:
            Person = await session.get(CPerson, id_person)
        is_admin = PersonIsAdmin(id_person=id_person)
        Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
        if len(Nicknames) > 0 and Person.family is not None and Person.name is not None:
            await state.set_state(UserState.start)
            await AskSelectKBM(message=message, message_text="Основное меню профиля", state=state,
                               edit=False, kbm=UserProfileKeyboard(id_person=id_person, is_admin=is_admin),
                               next_state=None)
        else:
            await message.answer(text="Вы не завершили регистрацию.")
            await SuggestToRegister(message=message, session=session)
    else:
        await message.answer(text="Этот раздел доступен только зарегистрированным пользователям.")


@router.message(Command("help"))
async def Help(message: types.Message, session: AsyncSession) -> None:
    await message.answer(text="Здесь должно быть сообщение со справкой.")

@router.message(Command("clear"))
async def ClearMessages(message: types.Message) -> None:
    try:
        # Все сообщения, начиная с текущего и до первого (message_id = 0)
        for i in range(message.message_id, 0, -1):
            await bot.bot.MafiaBot.delete_message(message.from_user.id, i)
    except TelegramBadRequest as ex:
        # Если сообщение не найдено (уже удалено или не существует),
        # код ошибки будет "Bad Request: message to delete not found"
        if ex.message == "Bad Request: message to delete not found":
            print("Все сообщения удалены")




@router.callback_query(UserCallback.filter(F.action.__eq__("MAIN_MENU")))
async def ToMainMenuHandler(callback: CallbackQuery,
                            callback_data: UserCallback,
                            state: FSMContext,
                            session: AsyncSession) -> None:
    await GoToUserMainMenu(message=callback.message, message_text="Выберите действие.", state=state, session=session,
                           edit=False)


@router.callback_query(UserCallback.filter(F.action.__eq__("INVOICE")), UserState.get_invoice)
async def SendInvoice(callback: CallbackQuery,
                      callback_data: UserCallback,
                      state: FSMContext,
                      session: AsyncSession) -> None:
    if callback_data.key == 0:
        await state.set_state(UserState.start)
        await callback.message.answer(text="Жду команды.")
        return

    if GlobalSettings.PAY_TOKEN.split(':')[1] == 'TEST':
        await bot.bot.MafiaBot.send_message(chat_id=callback.message.chat.id, text="Тестовая оплата")

    id_telegram = callback.message.chat.id
    id_payment = callback_data.id_payment
    id_person = callback_data.id_person
    id_game = callback_data.id_game
    id_place = callback_data.id_place
    id_nickname = callback_data.id_nickname
    id_city = callback_data.id_city

    Game = await session.get(CGame, id_game)
    Place = await session.get(CPlace, id_place)
    City = await session.get(CCity, id_city)

    Payment = await session.get(CPayment, id_payment)
    Person = await session.get(CPerson, id_person)
    Nickname = await session.get(CNickname, id_nickname)

    PRICE = types.LabeledPrice(label='Запись на игру в мафию', amount=Game.price * 100)

    title = (f"Оплата записи на игру "
             f"{Game.start_date.strftime('%A, %d.%m.%Y, %H:%M')}, "
             f"{City.name}")
    await bot.bot.MafiaBot.send_invoice(id_telegram,
                                        title=title,
                                        description=f"{Place.title}, {Place.address}",
                                        provider_token=GlobalSettings.PAY_TOKEN,
                                        currency='rub',
                                        photo_url="https://img.freepik.com/premium-vector/mafia-logo_74829-29.jpg",
                                        photo_height=512,  # !=0/None, иначе изображение не покажется
                                        photo_width=512,
                                        photo_size=512,
                                        is_flexible=False,  # True если конечная цена зависит от способа доставки
                                        prices=[PRICE],
                                        start_parameter='pay-example',
                                        payload=f'{id_telegram}:{Payment.id}:{Person.id}:'
                                                f'{Game.id}:{Place.id}:{Nickname.id}'
                                        )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.bot.MafiaBot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message, session: AsyncSession):
    payment_info = message.successful_payment
    total_amount = message.successful_payment.total_amount // 100
    currency = message.successful_payment.currency
    payload = payment_info.invoice_payload
    info = payload.split(":")
    id_telegram = int(info[0])
    id_payment = int(info[1])
    id_person = int(info[2])
    id_game = int(info[3])
    id_place = int(info[4])
    id_nickname = int(info[5])

    Telegram = await session.get(CTelegram, id_telegram)
    Person = await session.get(CPerson, id_person)
    Payment = await session.get(CPayment, id_payment)
    Game = await session.get(CGame, id_game)
    Place = await session.get(CPlace, id_place)
    Nickname = await session.get(CNickname, id_nickname)

    Status = await DB_GetStatusByCode(session=session, Code="PAY_PROVIDED")
    Payment.status = Status
    await session.commit()
    answer_text = (f"{Person.FormatName}, мы получили вашу оплату {total_amount} {currency}. Спасибо большое! "
                   f"Ваше место на игре закреплено за вами. Ждём вас!")
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    await bot.bot.MafiaBot.send_message(chat_id=id_telegram, text=answer_text)
    await NotifyModerator_PlayerAdded(session=session, Nickname=Nickname, Game=Game)


async def ShowPlayersList(session: AsyncSession, id_game: int, chat_id):
    Game: CGame | None = await session.get(CGame, id_game)
    Payments: list[CPayment] = await Game.PaymentsWithStatus(StatusCodes=["PAY_PROVIDED"])

    message_text = f"В игре {Game.start_date.strftime('%d.%m.%Y, %H:%M')} "
    if len(Payments) > 0:
        message_text += "будут участвовать:\n"
        PlayerList: dict[int, list[str]] = {}
        for Payment in Payments:
            Player: CPlayer | None = await Payment.awaitable_attrs.player
            Nickname: CNickname | None = await Player.awaitable_attrs.nickname
            if Player.id not in PlayerList:
                PlayerList[Player.id] = list[str]()
                PlayerList[Player.id].append(Nickname.name)
            else:
                PlayerList[Player.id].append(f"{Nickname.name} + 1")
        common_counter: int = 0
        for value in PlayerList.values():
            for nick in value:
                common_counter += 1
                message_text += f"{common_counter}. {nick}\n"
    else:
        message_text += "пока никто не участвует."
    await bot.bot.MafiaBot.send_message(chat_id=chat_id, text=message_text)


async def NotifyModerator_PlayerAdded(session: AsyncSession, Nickname: CNickname | None, Game: CGame | None):
    Place = await Game.Place
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    Person: CPerson = await Moderator.Person
    Telegram = Person.telegrams[0]
    await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id,
                                        text=f"Игрок, {Nickname.name} успешно оплатил игру в {Place.title}, "
                                             f"{Place.address} "
                                             f"{Game.start_date.strftime('%A, %d.%m.%Y, %H:%M')}"
                                             f" через Telegram-бота.Статус обновлён."
                                        )


async def NotifyModerator_PlayerSigned(session: AsyncSession, Nickname: CNickname | None, Game: CGame | None,
                                       Amount: int = 1):
    Place = await Game.Place
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    Telegram: CTelegram = await Moderator.Telegram

    PlayerPerson: CPerson = await Nickname.Person
    PlayerTelegram: CTelegram = await PlayerPerson.MainTelegram

    html_user_link: str | None = None

    if PlayerTelegram is not None and PlayerTelegram.telegram_name is not None:
        html_user_link = html.link(value=Nickname.name,
                                   link=html.quote(f'https://t.me/{PlayerTelegram.telegram_name}'))

    if PlayerTelegram is not None and PlayerTelegram.telegram_url is not None and html_user_link is None:
        html_user_link = html.link(value=Nickname.name, link=html.quote(PlayerTelegram.telegram_url))

    if PlayerTelegram is not None and PlayerTelegram.telegram_id is not None and html_user_link is None:
        html_user_link = html.link(value=Nickname.name,
                                   link=html.quote(f'tg://user?id={PlayerTelegram.telegram_id}'))

    PlayerFN: str = PlayerPerson.FormatNameFamily
    if Amount > 1:
        if html_user_link is not None:
            notify_message = f"Игрок {html_user_link} ({PlayerFN})  + {Amount - 1} записаны "
        else:
            notify_message = f"Игрок {Nickname.name} ({PlayerFN}) + {Amount - 1} записаны "
    else:
        if html_user_link is not None:
            notify_message = f"Игрок {html_user_link} ({PlayerFN}) записан "
        else:
            notify_message = f"Игрок {Nickname.name} ({PlayerFN}) записан "

    notify_message += (f"на игру {Place.title}, {Place.address} {Game.start_date.strftime('%A, %d.%m.%Y, %H:%M')} "
                       f"через Telegram-бота.")
    await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id, text=notify_message)


async def GameInfoAndSuggestion(chat_id: int, id_game: int, message_text: str, state: FSMContext,
                                session: AsyncSession):
    state_data = await state.get_data()
    Nick: CNickname | None = None
    if "id_person" in state_data:
        id_person: int = int(state_data["id_person"])
        Nick: CNickname | None = await DB_CheckSigned(session=session, id_game=id_game, id_person=id_person)
    if Nick is not None:
        data = {"Список игроков": UserCallback(action="PLAYER_LIST", key=id_game, id_game=id_game),
                "В главное меню": UserCallback(action="MAIN_MENU")}
        message_text = f"Вы записаны на эту игру как {Nick.name}\n" + message_text
    else:
        data = {"Записаться": UserCallback(action="USER_CHOOSE_NICK", key=id_game, id_game=id_game),
                "Список игроков": UserCallback(action="PLAYER_LIST", key=id_game, id_game=id_game),
                "В главное меню": UserCallback(action="MAIN_MENU")}
    kbm = IKBM_User_ByDict_UserCallbackData(callback_data_dict=data)

    Game: CGame | None = await session.get(CGame, id_game)
    GameProperties: CGameProperties = await Game.awaitable_attrs.properties

    if GameProperties is not None and GameProperties.telegram_file_id is not None:
        await bot.bot.MafiaBot.send_photo(chat_id=chat_id,
                                          photo=GameProperties.telegram_file_id,
                                          caption=message_text,
                                          reply_markup=kbm)
    else:
        await bot.bot.MafiaBot.send_message(chat_id=chat_id, text=message_text, reply_markup=kbm)


@router.callback_query(UserCallback.filter(F.action.__eq__("USER_CHOOSE_CITY")))
async def OnSelectCity(callback: CallbackQuery,
                       callback_data: UserCallback,
                       state: FSMContext,
                       session: AsyncSession) -> None:
    id_city = callback_data.id_city
    City: CCity | None = await session.get(CCity, id_city)
    Games = await DB_GetGamesAfterDate(session=session, City=City, after_date=datetime.now())
    id_person = callback_data.id_person

    if len(Games) > 0:
        answer_str = "Ближайшее время открыты следующие записи на игры:\n"
        for Game in Games:
            Place = await Game.Place
            answer_str += (f" {Game.start_date.strftime('%A, %d %B, %H:%M')} по адресу: {Place.address}, "
                           f"{Place.title}, стоимость {Game.price}\n")
        await callback.message.answer(text=answer_str)
    else:
        await callback.message.answer(text=f"В городе {City.name} нет игр в ближайшее время.")

    data = await state.get_data()
    data["id_city"] = id_city
    await state.set_data(data=data)

    if id_person == 0:
        await callback.message.answer(text="Запись на игру без регистрации недоступна.")


@router.callback_query(UserCallback.filter(F.action.__eq__('PLAYER_LIST')))
async def OnPlayerList(callback: CallbackQuery,
                       callback_data: UserCallback,
                       state: FSMContext,
                       session: AsyncSession) -> None:
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await ShowPlayersList(session=session,
                          id_game=callback_data.id_game,
                          chat_id=callback.message.chat.id)


async def TryLoadProfile(TelegramID: int, state: FSMContext, session: AsyncSession) -> bool:
    if TelegramID != bot.bot.MafiaBot.id:
        try:
            data = await state.get_data()
            if "id_telegram" not in data:
                Telegram: CTelegram | None = await DB_GetTelegramByTelegramID(session=session, TelegramID=TelegramID)
                if Telegram is None:
                    return False
                else:
                    await state.update_data(id_telegram=Telegram.id)
                    Person: CPerson = await Telegram.Person
                    if Person is None:
                        return False
                    await state.update_data(id_person=Person.id)
                    await state.update_data(id_city=Person.id_city)
        except Exception:
            return False
        return True
    else:
        return False

#@router.callback_query(StateFilter(UserState.edit_profile, None))
#async def OnSelectNick(callback: CallbackQuery) -> None:
#    await callback.message.answer(text="Вы находитесь в режиме редактирования профиля. Выйдите из него, нажав кнопку Выход или воспользуйтесь командой /reset.")
#    return

@router.callback_query(StateFilter(UserState.start, None), UserCallback.filter(F.action.__eq__("USER_CHOOSE_NICK")))
async def OnSelectNick(callback: CallbackQuery,
                       callback_data: UserCallback,
                       state: FSMContext,
                       session: AsyncSession) -> None:
    data = await state.get_data()

    if "id_person" not in data:
        result = await TryLoadProfile(TelegramID=callback.message.chat.id, state=state, session=session)
        if not result:
            await callback.message.answer(text="Только зарегистрированные пользователи могут записаться на игру.")
            return
        else:
            data = await state.get_data()

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    id_person: int = data["id_person"]
    id_game: int = int(callback_data.id_game)
    data["id_game"] = id_game

    Game: CGame | None = await session.get(CGame, id_game)
    Status = await Game.ActualStatus()

    if str(Status.code) == str('GAME_IN_PROVIDE'):
        await callback.message.answer(text="Игра проводится и записаться на неё нельзя.")
        return

    if str(Status.code) == str('GAME_OVER'):
        await callback.message.answer(text="Игра уже закончилась и записаться на неё нельзя.")
        return


    await state.set_state(UserState.sign_up_to_game)
    await state.set_data(data=data)
    Person: CPerson | None = await session.get(CPerson, id_person)

    SignedNicks = await DB_CheckSigned2(session=session, id_game=id_game, id_person=Person.id)
    #if SignedNick is not None:
    if len(SignedNicks) > 0:
        await callback.message.answer(text=f"Вы уже записаны на эту игру под псевдонимом {SignedNicks[0].name}")
        await state.set_state(UserState.start)
        return
    else:
        Nicknames = await Person.awaitable_attrs.nicknames
        if len(Nicknames) > 0:
            buttons = {Nickname.id: Nickname.name for Nickname in Nicknames}
            kbm = IKBM_User_ByDict_KeyValue(action="SIGN_UP_TO_GAME", data=buttons, CancelButton=True,
                                            CancelButtonCaption="Отмена")
            await callback.message.answer(text="Выберите псевдоним для записи", reply_markup=kbm)
        else:
            await callback.message.answer(text="Вас нет псевдонимов для записи на игру. Вызовите начальное меню "
                                               "(команда /menu), перейдите в \"Профиль\", выберите \"Редактировать\", "
                                               "а затем \"Псевдонимы\". Нажмите кнопку \"Добавить псевдоним\". Введите "
                                               "новый псевдоним. Готово. Всего можно задать не более трёх псевдонимов. "
                                               "Они должны быть уникальны в пределах города, в котором вы играете.")
            await state.set_state(UserState.start)


@router.callback_query(StateFilter(UserState.sign_up_to_game), UserCallback.filter(F.action.__eq__("SIGN_UP_TO_GAME")))
async def SignUpGameSelect(callback: CallbackQuery, callback_data: UserCallback, state: FSMContext,
                           session: AsyncSession,
                           apscheduler: AsyncIOScheduler) -> None:
    id_nickname: int = callback_data.key
    if id_nickname == 0:
        await state.set_state(UserState.start)
        await callback.message.answer(text="Процедура записи отменена.")
        return

    data = await state.get_data()
    id_game: int = int(data["id_game"])

    buttons = {"Только себя": UserCallback(action="SIGN_UP_TO_GAME_ONLY_ME", id_game=id_game,
                                           id_nickname=id_nickname),
               "Со мной + 1": UserCallback(action="SIGN_UP_TO_GAME_ME_PLUS_ONE", id_game=id_game,
                                           id_nickname=id_nickname),
               "Со мной + 2": UserCallback(action="SIGN_UP_TO_GAME_ME_PLUS_TWO", id_game=id_game,
                                           id_nickname=id_nickname),
               "Со мной + 3": UserCallback(action="SIGN_UP_TO_GAME_ME_PLUS_THREE", id_game=id_game,
                                           id_nickname=id_nickname),
               "Отмена": UserCallback(action="U_CANCEL")
               }
    await AskSelect(message=callback.message, message_text="Выберите для записи на игру.", next_state=None,
                    state=state, edit=True, data=buttons)


@router.callback_query(StateFilter(UserState.sign_up_to_game), UserCallback.filter(F.action.__eq__("U_CANCEL")))
async def CancelSignupGame(callback: CallbackQuery, callback_data: UserCallback, state: FSMContext,
                           session: AsyncSession,
                           apscheduler: AsyncIOScheduler) -> None:
    await state.set_state(UserState.start)
    await callback.message.answer(text="Процедура записи отменена.")


@router.message(StateFilter(UserState.sign_up_to_game), Command(commands=["start", "menu", "afisha", "profile"]))
async def MenuHandler_WhenSignGame(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    await state.set_state(UserState.start)
    await message.answer(text="Процедура записи отменена.")


"""
Записаться на игру
"""
@router.callback_query(StateFilter(UserState.sign_up_to_game),
                       UserCallback.filter(F.action.startswith("SIGN_UP_TO_GAME_")))
async def SignUpGame(callback: CallbackQuery, callback_data: UserCallback, state: FSMContext,
                     session: AsyncSession,
                     apscheduler: AsyncIOScheduler) -> None:
    data = await state.get_data()
    if "id_game" not in data:
        await callback.message.answer(text="Внутренняя ошибка бота. Разработчик уведомлен.")
        await bot.bot.MafiaBot.send_message(chat_id=438204704,
                                            text=f"Пользователь {callback.message.from_user.id}\n"
                                                 f"{__name__} async def SignUpGame\n"
                                                 f"{data}")
        return

    id_game: int = int(data["id_game"])
    Game: CGame | None = await session.get(CGame, id_game)
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    id_nickname: int = int(callback_data.id_nickname)

    if id_nickname == 0:
        await state.set_state(UserState.start)
        await callback.message.answer(text="Процедура записи отменена.")
        return


    Amount: int = 1
    VALUE: str = callback_data.action
    match VALUE:
        case "SIGN_UP_TO_GAME_ME_PLUS_ONE":
            Amount = 2
        case "SIGN_UP_TO_GAME_ME_PLUS_TWO":
            Amount = 3
        case "SIGN_UP_TO_GAME_ME_PLUS_THREE":
            Amount = 4

    """ Формирование записи на игру в БД """
    #async with lock:
    result, error, id_player = await DB_SignUpPlayer(session=session, id_game=id_game, id_nickname=id_nickname,
                                                        Amount=Amount)
    if result:
        Nickname: CNickname | None = await session.get(CNickname, id_nickname)
        Player: CPlayer | None = await session.get(CPlayer, id_player)
        Payments: list[CPayment] = await Player.awaitable_attrs.payments

        Person: CPerson = await Nickname.Person
        # NOW = NowConvertFromServerDateTime(tz=City.tz)
        last_date: datetime = Game.start_date - timedelta(hours=6)

        await DB_SchedulePayReminder(session=session, id_game=id_game, id_payment=Payments[0].id,apscheduler=apscheduler)
        if Amount > 1:
            answer_str = (f"{Person.FormatName}, вы успешно записались на игру! Вместе с вами записано ещё "
                          f"{Amount - 1} игроков. Пока места за вами забронированы. Игру нужно оплатить не позднее, "
                          f"чем {last_date.strftime('%d.%m.%Y %H:%M')}, иначе Ваша бронь будет отменена автоматически."
                          f"\n")
        else:
            answer_str = (f"{Person.FormatName}, вы успешно записались на игру! Пока место за вами забронировано. "
                          f"Игру нужно оплатить не позднее, чем {last_date.strftime('%d.%m.%Y %H:%M')}, иначе Ваша "
                          f"бронь будет отменена автоматически.\n")
        if Moderator is not None and Moderator.pay_detail is not None:
            answer_str += Moderator.pay_detail

        await NotifyModerator_PlayerSigned(session=session, Game=Game, Nickname=Nickname, Amount=Amount)
    else:
        answer_str = "Не удалось выполнить запись на игру. Разработчики уже уведомлены об этой ошибке."

    await state.set_state(UserState.start)

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await callback.message.answer(text=answer_str)

"""
Напоминание о об оплате. Вызывается планировщиком.
"""
async def UserPayReminder(chat_id: int, id_player: int, id_payment):
    async with async_session_factory() as session:
        Player: CPlayer | None = await session.get(CPlayer, id_player)
        Payment: CPayment | None = await session.get(CPayment, id_payment)
        PaymentStatus: CStatus = await Payment.awaitable_attrs.status
        Game: CGame = await Player.awaitable_attrs.game

        if PaymentStatus.code == 'PAY_RESERVED':
            GameDateTime: datetime = Game.start_date
            Place: CPlace = await Game.awaitable_attrs.place
            await bot.bot.MafiaBot.send_message(chat_id=chat_id,
                                                text="Напоминаем вам о необходимости оплаты игры. "
                                                     f"Вы записались на игру "
                                                     f"{GameDateTime.strftime('%d.%m, %A, %H:%M')}, "
                                                     f"{Place.title}, {Place.address}. ")


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


"""
Показать клавиатуру
"""
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


async def SuggestCity(callback: CallbackQuery, state: FSMContext, session: AsyncSession, edit: bool = False):
    data = await state.get_data()
    if "id_city" in data:
        id_city: int = data["id_city"]
    else:
        telegram_id: int = callback.message.from_user.id
        Telegram: CTelegram = await DB_GetTelegramByTelegramID(session=session, TelegramID=telegram_id)
        Person: CPerson = await Telegram.Person
        id_city = Person.id_city
        data["id_city"] = id_city
        await state.set_data(data=data)

    Cities: list[CCity] = await DB_GetAllCities(session=session)
    buttons = {City.name: UserCallback(action="U_SELECT_CITY", id_city=City.id) for City in Cities if
               City.id != id_city}
    buttons["Отмена"] = UserCallback(action="U_CANCEL", id_city=0)
    await AskSelect(message=callback.message, message_text="Выберите город", state=state, next_state=None,
                    data=buttons, edit=edit)


"""
Смена города пользователем через главное меню
"""
async def ChangeCity(callback: CallbackQuery, callback_data: UserCallback,
                     state: FSMContext, session: AsyncSession, edit: bool = False):
    id_city: int = int(callback_data.id_city)
    City: CCity | None = await session.get(CCity, id_city)
    message_text = (f"Вы сменили город на <b>{City.name}</b>. Чтобы вернуться к настройкам по-умолчанию, "
                    f"вызовите команду /start.")
    await state.update_data(id_city=City.id)
    await GoToUserMainMenu(message=callback.message, message_text=message_text, state=state, session=session, edit=edit)


"""
Получить все афиши на игру на текущий момент времени
"""
async def GetBillboards(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()

    if "id_city" not in data:
        result: bool = await TryLoadProfile(TelegramID=message.chat.id, session=session, state=state)
        if not result:
            await DebugMessage(message=f"Пользователь {message.from_user.id} умудрился зайти в профиль и оттуда, "
                                       f"нажав кнопку \"Афиша\", схлопотать в данных состояния отсутствие id_city. "
                                       f"Профиль прогрузить не удалось.\n "
                                       f"data = {data}.")
            return
        else:
            await DebugMessage(message=f"Пользователь {message.from_user.id} умудрился зайти в профиль и оттуда, "
                                       f"нажав кнопку \"Афиша\", схлопотать в данных состояния отсутствие id_city.\n"
                                       f"Профиль прогружен успешно.\n "
                                       f"data = {data}.")

    data = await state.get_data()
    id_city: int = data["id_city"]

    City: CCity | None = await session.get(CCity, id_city)

    NOW = NowConvertFromServerDateTime(tz=City.tz)

    Games = await DB_GetGamesAfterDate(session=session, City=City, after_date=NOW)
    if len(Games) > 0:
        available_games: dict[int, str] = {}
        await message.answer(text=f"Ближайшее время, г. <b>{City.name}</b>, есть информация о следующих играх.")
        idx = 0
        for index, Game in enumerate(Games):
            Status: CStatus = await Game.ActualStatus()

            if Status.code == "GAME_ANNOUNCED":
                idx += 1
            else:
                continue

            Place = await Game.Place
            Payments: list[CPayment] = await Game.PaymentsWithStatus(["PAY_PROVIDED"])
            count_players = len(Payments)
            answer_str = (f"{idx}. "
                          f"{Game.start_date.strftime('%A, %d.%m.%Y, <b>%H:%M</b>')}\n"
                          f"По адресу: {Place.address}, {Place.title}.\n"
                          f"Стоимость <b>{Game.price} руб.</b>\n")
            if count_players < Place.seats:
                available_games[Game.id] = f"{Game.start_date.strftime('%d.%m.%Y %H:%M')}, {Place.title}"
                answer_str += f"Занято мест <b>{count_players}</b> из {Place.seats}. \n\n"

                ActionAssociations: list[CGameActionAssociation] = await Game.awaitable_attrs.actions_acc
                if len(ActionAssociations) == 1:
                    Action: CAction = ActionAssociations[0].action
                    answer_str += f"Действует акция \"{Action.title}\""
                elif len(ActionAssociations) > 1:
                    answer_str += "Действуют акции "
                    for i, association in enumerate(ActionAssociations):
                        answer_str += association.action.title
                        if i < len(ActionAssociations) - 1:
                            answer_str += ", "

                await GameInfoAndSuggestion(chat_id=message.chat.id,
                                            id_game=Game.id,
                                            message_text=answer_str,
                                            state=state, session=session)
            else:
                answer_str += "Свободных мест, к сожалению, нет.\n\n"
                data = {"Список игроков": UserCallback(action="PLAYER_LIST", key=Game.id, id_game=Game.id)}
                kbm = IKBM_User_ByDict_UserCallbackData(callback_data_dict=data)
                await message.answer(text=answer_str, reply_markup=kbm)
    else:
        await message.answer(text=f"В городе {City.name} нет игр ближайшее время.")


async def SelectPay(callback: CallbackQuery, callback_data: UserCallback,
                    state: FSMContext, session: AsyncSession, edit: bool = False):
    # данные тестовой карты: 1111 1111 1111 1026, 12/22, CVC 000.
    bills: list[tuple[CPayment, CPerson, CGame, CNickname]] = \
        await DB_CheckBills(session=session, id_telegram=callback.message.from_user.id)
    keyboard_data: dict[str, UserCallback] = {}
    if len(bills) > 0:
        for Payment, Person, Game, Nickname in bills:
            Place = await Game.Place
            City = await Place.City
            keyboard_data[await Game.FormatGameStr] = UserCallback(action="INVOICE",
                                                                   id_person=Person.id,
                                                                   id_city=City.id,
                                                                   id_game=Game.id,
                                                                   id_place=Place.id,
                                                                   id_payment=Payment.id,
                                                                   id_nickname=Nickname.id,
                                                                   key=Payment.id)
        keyboard_data["Отмена"] = UserCallback(action="INVOICE", key=0)
        await AskSelect(message=callback.message, message_text="Есть следующие записи на оплату.",
                        state=state, next_state=UserState.get_invoice, data=keyboard_data, edit=True)
    else:
        await GoToUserMainMenu(message=callback.message, message_text="У вас не записей на оплату.", state=state,
                               session=session, edit=True)

@router.message(StateFilter(UserState.start, None), ~F.text.startswith('/') )
async def AnyMessageAnswer(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    message_text: str = message.text.lower()
    if 'привет' in message_text:
        await message.answer("Привет! Если хотите поиграть в мафию, то нужно зарегистрироваться. "
                             "Воспользуйтесь командами /start или /menu")
    elif 'пока' in message_text:
        await message.answer("До свидания!")
    elif 'что ты умеешь?' in message_text:
        await message.answer("Я бот для автоматизации записи на игры в клубе MafiaInc. "
                             "У нас есть филиалы в Кемерово, Красноярске, Новосибирске, Томске, Новокузнецке, "
                             "Санкт-Петербурге. Нужно пройти регистрацию и я расскажу где можно поиграть."
                             "Воспользуйтесь командами /start или /menu")
    else:
        await message.answer("Я не совсем понял ваш вопрос. Можете переформулировать?")

