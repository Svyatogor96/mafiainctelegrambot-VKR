import re
import datetime
import pytz
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select, delete, func

import bot.bot
from config import GlobalSettings
import logging
from database.model import *
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.model import CPerson
from integration.bitrix import BitrixLeadAdd

# engine = create_engine(url=settings.DATABASE_URL(), echo=True)

engine_async = create_async_engine(url=GlobalSettings.DATABASE_ASYNC_URL, echo=False,
                                   max_overflow=10, pool_size=30, pool_recycle=1800)
async_session_factory = async_sessionmaker(bind=engine_async, expire_on_commit=False)


def ConvertToServerDateTime(Value: datetime, tz: str) -> datetime:
    moscow = pytz.timezone('Europe/Moscow')
    local = pytz.timezone(tz)
    result = local.localize(Value)
    return result.astimezone(tz=moscow).replace(tzinfo=None)


def NowConvertFromServerDateTime(tz: str) -> datetime:
    moscow = pytz.timezone('Europe/Moscow')
    result = moscow.localize(datetime.now())
    return result.astimezone(tz=pytz.timezone(tz)).replace(tzinfo=None)


async def init_models():
    async with engine_async.begin() as conn:
        await conn.run_sync(CBase.metadata.drop_all)
    async with engine_async.begin() as conn:
        await conn.run_sync(CBase.metadata.create_all)


async def init_game_types(session: AsyncSession) -> None:
    session.add_all(
        [
            CGameType(title="Еженедельная, будни", code="EVERY_WEEK_WORKDAY"),
            CGameType(title="Еженедельная, выходные", code="EVERY_WEEKEND"),
            CGameType(title="Родители + дети", code="PARENTS_CHILDREN"),
            CGameType(title="Корпоративная", code="CORPORATE"),
            CGameType(title="День рождения", code="BIRTH_DAY"),
            CGameType(title="Для друзей", code="FOR_FRIENDS"),
            CGameType(title="Детская", code="CHILDREN")
        ]
    )


async def init_cities(session: AsyncSession) -> None:
    session.add_all(
        [
            CCity(name="Кемерово", code="KEM", tz="Asia/Krasnoyarsk"),
            CCity(name="Новокузнецк", code="NVKTZ", tz="Asia/Novokuznetsk"),
            CCity(name="Новосибирск", code="NVSK", tz="Asia/Novosibirsk"),
            CCity(name="Красноярск", code="KRSK", tz="Asia/Krasnoyarsk"),
            CCity(name="Томск", code="TOMSK", tz="Asia/Tomsk")
        ]
    )


async def init_rights(session: AsyncSession) -> None:
    session.add_all(
        [
            CRight(code="__SU__", title="Суперпользователь", notes="Право суперпользователя в системе. Женя - это ты."),
            CRight(code="__ADMIN__", title="Администратор", notes="Права администратора или ведущего игр."),
            CRight(code="__PLAYER__", title="Игрок", notes="Игрок в Мафию.")
        ]
    )


async def init_statuses(session: AsyncSession) -> None:
    session.add_all(
        [
            CStatus(code="GAME_PLANNED", title="Игра игра запланирована"),
            CStatus(code="GAME_PREPARED", title="Игра подготовлена. Ведущий договорился с владельцем места о времени "
                                                "проведения и поддержке."),
            CStatus(code="GAME_ANNOUNCED", title="Игра анонсирована. Объявлена запись."),
            CStatus(code="GAME_REG_CLOSED", title="Запись на игру закрыта"),
            CStatus(code="GAME_ABORTED", title="Игра игра отменена по каким-либо причинам."),
            CStatus(code="GAME_IN_PROVIDE", title="Игра проводится."),
            CStatus(code="GAME_OVER", title="Игра завершена."),
            CStatus(code="PAY_RESERVED", title="Место на игру забронировано."),
            CStatus(code="PAY_PROVIDED", title="Получена оплата места на игру."),
            CStatus(code="PAY_OVERDUE", title="Оплата просрочена. Можно выставить место на продажу."),
            CStatus(code="PAY_ABORTED", title="Оплата не будет производится, о чём и сообщил игрок. "
                                              "Можно выставить место на продажу."),
            CStatus(code="PAY_RETURN", title="Игрок оплатил игру, но участвовать не может. Он исключён из игры.")

        ]
    )


async def init_start_messages(session: AsyncSession) -> None:
    StartingMessageGroup = CTelegramBotMessageGroup(code="_START_MESSAGES_",
                                                    title="Группа сообщений, которые может выдавать "
                                                          "бот при старте.")
    session.add_all(
        [StartingMessageGroup,
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Клуб «MAFIA Inc.» игры в Мафию в премиальном формате приветствует вас, {}."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="{}, здравствуйте. Это бот клуба «MAFIA Inc.». Мафия в премиальном формате."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="{}, добро пожаловать в «MAFIA Inc.» - клуб любителей игры в Мафию премиального формата! "
                     "Мы рады видеть Вас среди наших уважаемых участников."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Приветствуем Вас, {}, в «MAFIA Inc.» - клубе игры в мафию премиального формата! Здесь "
                     "Вы сможете насладиться игрой с лучшими игроками города."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Мы рады приветствовать Вас, {}, на борту «MAFIA Inc.» клуба игры в Мафию премиального формата. "
                     "Здесь Вам гарантированы незабываемые вечера."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Здравствуйте, {}, и добро пожаловать в «MAFIA Inc.» клуб любителей Мафии премиального формата. "
                     "Ваше участие здесь говорит о Вашем статусе."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Приветствуем Вас, {}, в клубе «MAFIA Inc.». Мафия в премиальном формате. Здесь Вы найдете лучших "
                     "игроков и самые изысканные вечера."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Рады видеть Вас, {}, в «MAFIA Inc.»  клубе Мафии премиального формата. Мы гарантируем Вам "
                     "незабываемые вечера в кругу избранных игроков."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Приветствуем, {}, в «MAFIA Inc.» клубе игры в Мафию премиального формата. Здесь Вы "
                     "присоединитесь к сообществу самых искушенных игроков города."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Приветствуем, {}, среди избранных в  клубе «MAFIA Inc.» игры в Мафию премиального формата! "
                     "Здесь Вас ждут лучшие  игроки и незабываемые вечера."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Приветствую Вас, {}, в «MAFIA Inc.» клубе игры в Мафию премиального формата, где Вы сможете "
                     "наслаждаться игрой с высочайшим уровнем мастерства."),
         CTelegramBotMessage(
             message_group=StartingMessageGroup,
             message_code="UNKNOWN_USER",
             message="Здравствуйте, {}, и добро пожаловать на борт «MAFIA Inc.» клуба игры в мафию в премиальном "
                     "формате.")

         ]
    )

    session.add_all(
        [
            CTelegramBotMessage(
                message_group=StartingMessageGroup,
                message_code="KNOWN_USER",
                message="Приветствуем Вас, {}, и добро снова пожаловать в «MAFIA Inc.» - клуб игры в Мафию "
                        "премиального формата!"),
            CTelegramBotMessage(
                message_group=StartingMessageGroup,
                message_code="KNOWN_USER",
                message="Здравствуйте, {}! Рады приветствовать Вас в Телеграм-боте клуба «MAFIA Inc.» игры в мафию "
                        "премиального формата!"),
            CTelegramBotMessage(
                message_group=StartingMessageGroup,
                message_code="KNOWN_USER",
                message="Здравствуйте, {}. Мы счастливы, что Вы присоединились к нашему Телеграм-боту клуба «MAFIA "
                        "Inc.» мафии премиального формата!"),
            CTelegramBotMessage(
                message_group=StartingMessageGroup,
                message_code="KNOWN_USER",
                message="Здравствуйте, {}. Добро пожаловать в наш Телеграм-бот клуба «MAFIA Inc.» игры в мафию "
                        "премиального формата - здесь Вас ждут захватывающие вечера!"),
            CTelegramBotMessage(
                message_group=StartingMessageGroup,
                message_code="KNOWN_USER",
                message="Здравствуйте, {}! Мы рады приветствовать Вас в «MAFIA Inc.» - клубе Мафии премиального "
                        "формата. Надеемся, Вам у нас понравится!")

        ]
    )


async def init_note_messages(session: AsyncSession) -> None:
    NotesMessageGroup = CTelegramBotMessageGroup(code="_NOTES_MESSAGES_",
                                                 title="Нотификационные сообщения общего характера.")

    session.add_all([NotesMessageGroup,
                     CTelegramBotMessage(
                         message_group=NotesMessageGroup,
                         message_code="REGISTRATION_LAW_N1",
                         order_=1,
                         message="Далее нам нужно познакомиться и это связано с вашими персональными "
                                 "данными. Мы – телеграм-бот клуба игры в мафию в премиальном формате, "
                                 "который собирает персональные данные пользователей только и исключительно "
                                 "в соответствии с Законом о персональных данных (Федеральный закон № "
                                 "152-ФЗ).\n\nЭтот закон был создан для защиты прав и свобод каждого человека. "
                                 "Он гарантирует, что все персональные данные, которые мы собираем, будут "
                                 "использоваться только для определённых и законных целей. Это Статья 5 "
                                 "вышеозначенного закона.\n\nСобираемые нами данные включают вашу фамилию, имя, "
                                 "отчество, пол, адрес электронной почты, дату вашего рождения и номер телефона. "
                                 "Все эти данные необходимы для улучшения нашего сервиса и "
                                 "предоставления вам более  качественных услуг. Мы не будем использовать "
                                 "ваши персональные данные для каких-либо других целей или передавать их "
                                 "третьим лицам без вашего согласия. За исключением случаев, предусмотренных законом "
                                 "Российской Федерации.\n\n"
                                 "Мы также гарантируем, что все собранные "
                                 "данные будут храниться в безопасности и конфиденциальности. Если у вас "
                                 "есть какие-либо вопросы или предложения, пожалуйста, свяжитесь с нами. Мы "
                                 "всегда рады помочь вам и ответить на все ваши вопросы."),
                     CTelegramBotMessage(
                         message_group=NotesMessageGroup,
                         message_code="REGISTRATION_LAW_N2",
                         order_=2,
                         message="Для чего мы собираем данные, кроме улучшения сервиса?\n"
                                 "1. Для подтверждения личности: безопасность членов клуба для нас не пустой звук.\n"
                                 "2. Для обработки платежей: персональные данные используются для обработки данных, "
                                 "таких как банковские реквизиты, номера кредитных карт и т.д. Мы хотим, чтобы "
                                 "оплата была удобной. А, если, например, вы по какой-либо причине не сможете"
                                 "участвовать в игре, которую предоплатили, то мы хотим вернуть вам деньги за игру "
                                 "как можно быстрее и "
                                 "безопаснее.\n 3. Аутентификация и авторизация: персональные данные могут быть "
                                 "использованы для аутентификации и авторизации пользователей при входе в систему или "
                                 "использовании услуг.\n 4. Для защиты прав потребителей: персональные данные "
                                 "позволяют нам защищать права потребителей, обеспечивая соблюдение правил и условий "
                                 "использования их услуг.\n 5. Борьба с мошенничеством: персональные данные "
                                 "также помогают бороться с мошенничеством, обеспечивая более надежную проверку "
                                 "личности и предотвращая незаконное использование услуг."),
                     CTelegramBotMessage(
                         message_group=NotesMessageGroup,
                         message_code="REGISTRATION_LAW_N3",
                         order_=3,
                         message="Пожалуйста, подтвердите ваше согласие на обработку персональных данных.\n"
                                 "Нажмите кнопку \"Подтверждаю\", если согласны. Нажмите кнопку \"Отклоняю\", если "
                                 "не согласны.\n")

                     ])


async def init_anecdote_messages(session: AsyncSession) -> None:
    AnecdoteMessageGroup = CTelegramBotMessageGroup(code="_ANEKDOT_",
                                                    title="Анекдоты про мафию.")
    session.add_all([AnecdoteMessageGroup,
                     CTelegramBotMessage(
                         message_group=AnecdoteMessageGroup,
                         message_code="_ANEKDOT_",
                         message="Как известно, в американских анекдотах поляк вместо чукчи. Итак:\n"
                                 "Как узнать, что поляк пришёл на петушиные бои?\n"
                                 "- Он пришёл с уткой.\n"
                                 "Как узнать, что туда пришёл итальянец?\n"
                                 "- Он поставил на утку.\n"
                                 "Как узнать, что во всём этом замешана мафия?\n"
                                 "- Утка выиграла.\n"
                     ),
                     CTelegramBotMessage(
                         message_group=AnecdoteMessageGroup,
                         message_code="_ANEKDOT_",
                         message="В Чикаго американский бизнесмен звонит своему русскому приятелю:\n"
                                 "- Алекс, и почему у нас все так боятся русской мафии? Такие любезные и обходительные "
                                 "парни. Вчера они были у меня в гостях, долго что-то рассказывали и перед уходом даже "
                                 "подарили очень дорогую фигурку собачки из бивня мамонта.\n"
                                 "- А что за собачка?\n"
                                 "- Лохматенькая, с острыми ушками и пушистым хвостом.\n"
                                 "- Джек, уходи оттуда. Это не собачка. Это песец.\n"
                     ),
                     CTelegramBotMessage(
                         message_group=AnecdoteMessageGroup,
                         message_code="_ANEKDOT_",
                         message="Одна женщина была настолько страшной, что специально внедрилась в мафию и потом всех "
                                 "сдала полиции, чтобы сделать пластическую операцию по программе защиты свидетелей."
                     ),
                     CTelegramBotMessage(
                         message_group=AnecdoteMessageGroup,
                         message_code="_ANEKDOT_",
                         message="Студенты в общежитии, играя в \"мафию\", отмыли 3 миллиона долларов."),

                     CTelegramBotMessage(
                         message_group=AnecdoteMessageGroup,
                         message_code="_ANEKDOT_",
                         message="Заядлый игрок в \"Мафию\", случайно оказавшись в казино, не только выиграл местный "
                                 "покерный турнир, но и едва не погиб, точно указав, кто из играющих за покерным "
                                 "столом состоит в мафии, а кто является полицейским под прикрытием..."
                     ),
                     CTelegramBotMessage(
                         message_group=AnecdoteMessageGroup,
                         message_code="_ANEKDOT_",
                         message="Самая жестокая мафия - эстонская. Человек умирает своей смертью, "
                                 "но в постоянном ожидании."),
                     ])


async def init_joke_messages(session: AsyncSession) -> None:
    JokesMessageGroup = CTelegramBotMessageGroup(code="_JOKE_",
                                                 title="Анекдоты про мафию.")
    session.add_all([JokesMessageGroup,
                     CTelegramBotMessage(
                         message_group=JokesMessageGroup,
                         message_code="_CHOOSE_NICK_",
                         sex="M",
                         message="Например, псевдоним \"Вася, 20 см\" не подойдёт. Он будет расценён как реклама."
                     ),
                     CTelegramBotMessage(
                         message_group=JokesMessageGroup,
                         message_code="_CHOOSE_NICK_",
                         sex="F",
                         message="Например, псевдоним \"Маша, голова никогда не болит.\" не подойдёт. Он будет "
                                 "расценён как реклама."
                     )
                     ])


async def init_actions(session: AsyncSession) -> None:
    session.add_all([CAction(code="ONE_PLUS_ONE", title="1 + 1", comment="Бери друга, который не играл в Мафию - "
                                                                         "бронируйте места и платите {}₽, а не {}₽ за "
                                                                         "двоих")])


async def init_announce_messages(session: AsyncSession) -> None:
    AnnouncesMessageGroup = CTelegramBotMessageGroup(code="_ANNOUNCE_",
                                                     title="Шаблоны сообщений для анонсов игр")
    session.add_all([AnnouncesMessageGroup,
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_01",
                         message="Привет, {name}! Приглашаем Вас на захватывающую игру в \"Мафию\", которая состоится "
                                 "в {week_day}, {day} {month}, в {time} по адресу: {address}, {place}. Стоимость "
                                 "участия - {price}₽. Не пропустите это увлекательное событие!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_02",
                         message="Добрый день, {name}! У нас для Вас отличная новость! В {week_day}, {day} {month}, "
                                 "собираемся на вечернюю игру в Мафию, начало в {time}. Место проведения - {place}, "
                                 "{address}. Стоимость участия всего {price}₽, присоединяйтесь!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_03",
                         message="Приветствую, {name} Запланирована увлекательная игра в Мафию на {week_day}, {day} "
                                 "{month}, сбор в {time}, адрес: {address}, {place}. Стоимость участия {price}₽ "
                                 "с человека. Будем рады видеть Вас!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_04",
                         message="Здравствуйте, {name}! Открыта запись на игру в Мафию в {week_day}, {day} {month}, "
                                 "начало в {time} в {place}, {address}. Участие стоит {price}₽ за одного игрока, "
                                 "не пропустите!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_05",
                         message="Привет, {name}! Кто хочет стать частью захватывающей игры в Мафию? Записываемся: "
                                 "{week_day}, {day} {month}, в {place},  {address}, начало в {time}. Стоимость участия "
                                 "- {price}₽."
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_06",
                         message="Приветствуем, {name}! В {week_day}, {day} {month}, собираемся в {place}, {address} на"
                                 " увлекательную игру. Сбор в {time}, стоимость участия - {price}₽. Отличное "
                                 "время провождение гарантировано!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_07",
                         message="Доброго времени суток! В {week_day}, {day} {month}, приглашаем на игру в Мафию с "
                                 "началом в {time} в {place}, {address}. Стоимость участия {price}₽. Не "
                                 "пропустите, {name}!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_08",
                         message="Здравствуйте, {name}! В {week_day}, {day} {month}, состоится открытая игра в {time} "
                                 "по адресу {address}, {place}. Стоимость участия для одного игрока - {price}₽."
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_09",
                         message="В {week_day}, {day} {month}, играем в Мафию! Сбор в {time}, место проведения - "
                                 "{place}, {address}. Стоимость участия за одного игрока - {price}₽. Ждём, "
                                 "вас, {name}!"
                     ),
                     CTelegramBotMessage(
                         message_group=AnnouncesMessageGroup,
                         message_code="ANNOUNCE_10",
                         message="Приветствую вас, {name}! В {week_day}, {day} {month}, собираемся на игру в Мафию. "
                                 "Начало в {time}, место - {place}, {address}. Стоимость участия одного игрока - "
                                 "{price}₽. Будет интересно!"
                     ),

                     ])


# async def init_pay_details_messages(session: AsyncSession) -> None:
#     PayDetailsMessageGroup = CTelegramBotMessageGroup(code="_PAY_DETAIL_",
#                                                      title="Шаблоны сообщений для реквизитов оплаты")
#     session.add_all([PayDetailsMessageGroup,
#                      CTelegramBotMessage(
#                          message_group=PayDetailsMessageGroup,
#                          message_code="PAY_DETAIL_01",
#                          message="Предоплата на карту Тинькофф по номеру 8 961 729 2115 Евгений Н. *В СООБЩЕНИИ УКАЖИТЕ НИК ИГРОКА!"
#                      )
#                      ])


async def init_first_data():
    async with async_session_factory() as session:
        async with session.begin():
            god_right = CRight(code="__DEVELOPER__",
                               title="Разработчик", notes="Право Бога в системе. "
                                                          "Он видит даже отладочную информацию.")
            await init_rights(session)
            await init_cities(session)
            await init_statuses(session)
            await init_game_types(session)

            session.add_all([god_right])

            AboutMessageGroup = CTelegramBotMessageGroup(code="_ABOUT_BOT_",
                                                         title="Группа сообщений об этом боте.")
            RulesMessageGroup = CTelegramBotMessageGroup(code="_RULES_",
                                                         title="Группа сообщений о правилах игры.")

            session.add_all([AboutMessageGroup, RulesMessageGroup])

            session.add_all([
                CTelegramBotMessage(
                    message_group=AboutMessageGroup,
                    message_code="AUTHORS",
                    message="Этот бот \U0001F916 для вас разработали игрок Портос (Андрей Кушнаренко @avkushnarenko) "
                            "и его студент-выпускник Илья Шипачёв "
                            "(@Shipachevv). Так что если я плохо работаю, "
                            "то это на их совести😀. Ну а если у вас есть какие-либо вопросы или предложения, "
                            "пожалуйста, обращайтесь по выше указанным контактам. Мы будем рады любой обратной "
                            "связи, ведь хотим сделать бот лучше и исправить ошибки."),
                CTelegramBotMessage(
                    message_group=AboutMessageGroup,
                    message_code="AUTHORS",
                    message="ВАЖНОЕ ПРЕДУВЕДОМЛЕНИЕ! БОТ НАХОДИТСЯ В СТАДИИ РАЗРАБОТКИ И ЭТО ЕГО ПЕРВОЕ МАССОВОЕ "
                            "ТЕСТИРОВАНИЕ. ПРОЦЕСС РАЗРАБОТКИ ПРЕДУСМАТРИВАЕТ ВОЗМОЖНОЕ ОБНУЛЕНИЕ БАЗЫ ДАННЫХ. "
                            "ПОЭТОМУ МЫ ПРОСИМ С ПОНИМАЕМ ОТНЕСТИСЬ К ТОМУ, ЧТО ВЕРОЯТНО ВАМ БУДЕТ ПРЕДЛОЖНО ПРОЙТИ "
                            "ПРОЦЕДУРУ РЕГИСТРАЦИИ НЕ ОДИН РАЗ.")
            ])

            await init_note_messages(session=session)
            await init_start_messages(session=session)
            await init_anecdote_messages(session=session)
            await init_joke_messages(session=session)
            await init_announce_messages(session=session)
            await init_actions(session=session)
            # await init_pay_details_messages(session=session)


def validate_mobile_number(phone_number: str) -> bool:
    if len(phone_number) > 15:
        return False
    rule = re.compile(r'(^[+0-9]{1,3})*([0-9]{10,11}$)')

    if rule.search(string=phone_number):
        return True
    else:
        return False


def validate_email_address(email_address: str) -> bool:
    rule = re.compile(r'[^@]+@[^@]+\.[^@]+')
    if rule.match(email_address):
        return True
    else:
        return False


async def DB_IsRegistered(session: AsyncSession, telegram_id: int) -> bool:
    RESULT: bool = False
    query = select(CTelegram).where(CTelegram.telegram_id == telegram_id)
    result = await session.execute(query)
    Telegram: CTelegram | None = result.scalar_one_or_none()
    if Telegram is not None:
        Person: CPerson = await Telegram.Person
        if Person is not None:
            RESULT = Person.family is not None and Person.name is not None
            if RESULT:
                Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
                RESULT = len(Nicknames) > 0
            else:
                return RESULT
        else:
            return False
    else:
        return False
    return RESULT


async def DB_GetAllPersons(session: AsyncSession) -> list[CPerson]:
    query = select(CPerson).order_by(CPerson.family.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetAllModerators(session: AsyncSession) -> list[tuple[CModerator, CPerson, CTelegram]]:
    query = (select(CModerator, CPerson, CTelegram).
             where(CModerator.id_person == CPerson.id).
             where(CTelegram.id_person == CPerson.id).
             where(CModerator.deleted == sql.expression.false()))
    result = await session.execute(query)
    return [(row.CModerator, row.CPerson, row.CTelegram) for row in result]


async def DB_GetAllPersonsModeratorsDistinct(session: AsyncSession) -> list[CPerson]:
    query = (select(CPerson).
             where(CModerator.id_person == CPerson.id).
             where(CModerator.deleted == sql.expression.false()).distinct(CModerator.id_person))
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetModeratorsByIdList(session: AsyncSession, list_of_ids: list[int]) -> list[CModerator]:
    query = select(CModerator).filter(CModerator.id.in_(list_of_ids))
    results = await session.execute(query)
    return list(results.scalars().all())


async def DB_GetTelegramByTelegramUsername(session: AsyncSession, UserNameInTelegram: str) -> CTelegram | None:
    query = select(CTelegram).filter_by(telegram_name=UserNameInTelegram)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def DB_GetTelegramByTelegramID(session: AsyncSession, TelegramID: int) -> CTelegram | None:
    query = select(CTelegram).filter_by(telegram_id=TelegramID)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def DB_GetCityByCode(session: AsyncSession, Code: str) -> CCity | None:
    query = select(CCity).filter_by(code=Code)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def DB_SetEmailForPerson(session: AsyncSession, person_id: int, email: str) -> tuple[str, bool]:
    Person: CPerson | None = await session.get(CPerson, person_id)
    if Person is not None:
        Email: CEmail = CEmail(email_address=email)
        Email.person = Person
        session.add(Email)
        try:
            await session.commit()
            return "Ok", True
        except IntegrityError:
            await session.rollback()
            return "NOT_UNIQUE", False
    else:
        return "PERSON_NULL", False


async def DB_SetPhoneForPerson(session: AsyncSession, id_person: int, phone: str) -> tuple[str, bool]:
    Person: CPerson | None = await session.get(CPerson, id_person)
    if Person is not None:
        Phone: CPhone = CPhone(phone_number=phone)
        Phone.person = Person
        session.add(Phone)
        try:
            await session.commit()
            return "Ok", True
        except IntegrityError:
            await session.rollback()
            return "NOT_UNIQUE", False
    else:
        return "PERSON_NULL", False


async def DB_UpdatePhoneForPerson(session: AsyncSession, id_phone: int, Number: str) -> tuple[str, bool]:
    Phone: CPhone | None = await session.get(CPhone, id_phone)
    Phone.phone_number = Number
    try:
        await session.commit()
        return "Ok", True
    except IntegrityError:
        await session.rollback()
        return "NOT_UNIQUE", False


async def DB_UpdateEmailForPerson(session: AsyncSession, id_email: int, email_address: str) -> tuple[str, bool]:
    Email: CEmail | None = await session.get(CEmail, id_email)
    Email.email_address = email_address
    try:
        await session.commit()
        return "Ok", True
    except IntegrityError:
        await session.rollback()
        return "NOT_UNIQUE", False


async def DB_UpdateNicknameForPerson(session: AsyncSession, id_nickname: int, Name: str) -> tuple[str, bool]:
    Nickname: CNickname | None = await session.get(CNickname, id_nickname)
    Person: CPerson = await Nickname.awaitable_attrs.person
    query = (select(CNickname, CPerson).where(CNickname.id_person == CPerson.id).
             where(CPerson.id_city == Person.id_city))
    result = await session.execute(query)
    CityNicknames: list[str] = [str(Nick.name) for Nick in list(result.scalars().all())]

    if Name in CityNicknames:
        return "NOT_UNIQUE", False

    Nickname.name = Name
    try:
        await session.commit()
        return "Ok", True
    except SQLAlchemyError as E:
        return str(E), False


async def DB_DeletePhone(session: AsyncSession, id_phone: int) -> tuple[str, bool]:
    Phone: CPhone | None = await session.get(CPhone, id_phone)
    await session.delete(Phone)
    try:
        await session.commit()
        return "Ok", True
    except SQLAlchemyError as E:
        return str(E), False


async def DB_DeleteEmail(session: AsyncSession, id_email: int) -> tuple[str, bool]:
    Email: CEmail | None = await session.get(CEmail, id_email)
    await session.delete(Email)
    try:
        await session.commit()
        return "Ok", True
    except SQLAlchemyError as E:
        return str(E), False


async def DB_DeleteNickname(session: AsyncSession, id_nickname: int) -> tuple[str, bool]:
    Nickname: CNickname | None = await session.get(CNickname, id_nickname)
    # Проверка на использование псевдонима для записи на игру
    query = select(func.count(CPlayer.id)).where(CPlayer.id_nickname == id_nickname)
    result = await session.execute(query)
    count = result.scalar()

    if count == 0:
        await session.delete(Nickname)  # Если псевдоним не использовался никогда, его можно просто удалить
    else:
        Nickname.deleted = True  # Для ранее использованных псевдонимов выставляется флаг "удалён"

    try:
        await session.commit()
        return "Ok", True
    except SQLAlchemyError as E:
        return str(E), False


async def DB_GetPersonByPhone(session: AsyncSession, phone: str) -> CPerson:
    query = (select(CPerson, CPhone).
             where(CPhone.id_person == CPerson.id).
             where(CPhone.phone_number == phone))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def DB_GetCityById(session: AsyncSession, ID: int) -> CCity | None:
    return await session.get(CCity, ID)


async def DB_GetTelegramBotMessage(session: AsyncSession, group: str, code: str) -> list[CTelegramBotMessage]:
    query = (select(CTelegramBotMessage, CTelegramBotMessageGroup).
             join(CTelegramBotMessageGroup, CTelegramBotMessage.id_message_group == CTelegramBotMessageGroup.id).
             where(CTelegramBotMessageGroup.code == group and
                   CTelegramBotMessage.message_code == code))
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetTelegramBotMessagesLikeCode(session: AsyncSession, group: str,
                                            like_code: str, order: bool = False) \
        -> list[CTelegramBotMessage]:
    query = (select(CTelegramBotMessage, CTelegramBotMessageGroup).
             join(CTelegramBotMessageGroup, CTelegramBotMessage.id_message_group == CTelegramBotMessageGroup.id).
             where(CTelegramBotMessageGroup.code == group and CTelegramBotMessage.message_code.like(like_code)))
    if order:
        query = query.order_by(CTelegramBotMessage.order_)
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetRandomTelegramBotMessageFromGroup(session: AsyncSession,
                                                  group: str,
                                                  code: str = None,
                                                  sex: str = None) -> CTelegramBotMessage:
    query = (select(CTelegramBotMessage, CTelegramBotMessageGroup).
             join(CTelegramBotMessageGroup, CTelegramBotMessage.id_message_group == CTelegramBotMessageGroup.id).
             where(CTelegramBotMessageGroup.code == group))
    if code is not None:
        query = query.where(CTelegramBotMessage.message_code == code)
    if sex is not None:
        query = query.where(CTelegramBotMessage.sex == sex)
    result = await session.execute(query)
    return random.choice(list(result.scalars().all()))


async def DB_AddNickToPerson(session: AsyncSession, id_person: int, NickName: str) -> tuple[str, bool]:
    Person: CPerson | None = await session.get(CPerson, id_person)
    if Person is not None:
        query = (select(func.count(CNickname.id)).
                 where(CNickname.id_person == CPerson.id).
                 where(CPerson.id_city == Person.id_city).
                 where(CNickname.name == NickName)
                 )
        result = await session.execute(query)
        count = result.scalar()

        if count > 0:
            return "NOT_UNIQUE", False
        Nicknames: list[CNickname] = await Person.awaitable_attrs.nicknames
        Count: int = len(Nicknames)
        if Count >= 3:
            return "MAX_LIMIT", False

        # Если пользователь вводит псевдоним такой же как один из ранее удалённых
        DeletedNicknames: list[CNickname] = await Person.awaitable_attrs.deleted_nicknames

        NewNickname: CNickname | None = None
        for nn in DeletedNicknames:
            if nn.name == NickName:
                NewNickname = nn
                break

        if NewNickname is not None:
            NewNickname.deleted = False  # то просто восстанавливаем его
        else:
            NewNickname: CNickname = CNickname()  # иначе создаём новый
            NewNickname.name = NickName
            NewNickname.person = Person
            session.add(NewNickname)

        await session.commit()
        Nicknames = await Person.awaitable_attrs.nicknames
        Count: int = len(Nicknames)
        if Count >= 3:
            return "MAX_LIMIT", True
        else:
            return "Ok", True
    else:
        return "ERROR", False


async def DB_GetModerators(session: AsyncSession, telegram_id: int) -> list[CModerator]:
    query = (
        select(CModerator, CTelegram).
        where(CModerator.id_person == CTelegram.id_person).
        where(CTelegram.telegram_id == telegram_id)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_NewModerator(session: AsyncSession, id_person: int, city_list: list[int]) -> tuple[bool, str]:
    Person: CPerson | None = await session.get(CPerson, id_person)
    moderators: list[CModerator] = await Person.awaitable_attrs.moderators
    cities: list[int] = []
    for moderator in moderators:
        City = await moderator.City
        cities.append(City.id)

    for id_city in city_list:
        if id_city not in cities:
            session.add(CModerator(id_person=id_person, id_city=id_city))
    try:
        await session.commit()
        return True, "Ок"
    except SQLAlchemyError as E:
        answer_str = f"Ошибка при выполнении записи. {E.args}"
        return False, answer_str


async def DB_DeleteModerator(session: AsyncSession, id_moderator: int) -> tuple[bool, str]:
    Moderator = await session.get(CModerator, id_moderator)
    Moderator.deleted = True
    try:
        await session.commit()
        return True, "Ок"
    except SQLAlchemyError as E:
        answer_str = f"Ошибка при выполнении записи. {E.args}"
        return False, answer_str


async def DB_GetPlacesByCityID(session: AsyncSession, id_city: int) -> list[CPlace]:
    query = select(CPlace).where(CPlace.id_city == id_city).order_by(CPlace.title)
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetPlacesByModeratorID(session: AsyncSession, id_moderator: int) -> list[CPlace]:
    Moderator = await session.get(CModerator, id_moderator)
    City: CCity = Moderator.city
    return list(City.places)


async def DB_GetAllGameTypes(session: AsyncSession) -> list[CGameType]:
    result = await session.execute(select(CGameType))
    return list(result.scalars().all())


async def DB_GetAllGameTypesAsDict(session: AsyncSession) -> dict[int, str]:
    result = await session.execute(select(CGameType))
    return {game_type.id: game_type.title for game_type in result.scalars().all()}


async def DB_CreateNewGame(session: AsyncSession, id_game_type: int) -> CGame:
    game = CGame(id_game_type=id_game_type)
    session.add(game)
    return game


async def DB_GetStatusByCode(session: AsyncSession, Code: str) -> CStatus:
    result = await session.execute(select(CStatus).where(CStatus.code == Code))
    return result.scalar_one_or_none()


async def DB_GetStatusesByCodeLike(session: AsyncSession, CodeStartsWith: str) -> list[CStatus]:
    result = await session.execute(select(CStatus).where(CStatus.code.startswith(CodeStartsWith)))
    return list(result.scalars().all())


async def DB_GetStatusesForGame(session: AsyncSession) -> list[CStatus]:
    return await DB_GetStatusesByCodeLike(session=session, CodeStartsWith="GAME_")


async def DB_GetStatusesForPayment(session: AsyncSession) -> list[CStatus]:
    return await DB_GetStatusesByCodeLike(session=session, CodeStartsWith="PAY_")


async def DB_GetPersonListOfCity(session: AsyncSession, City: CCity) -> list[CPerson]:
    query = select(CPerson).where(CPerson.id_city == City.id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetPersonListOfCityId(session: AsyncSession, id_city: int) -> list[CPerson]:
    query = select(CPerson).where(CPerson.id_city == id_city)
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetAllCities(session: AsyncSession) -> list[CCity]:
    query = select(CCity).order_by(CCity.id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetAllCities_as_dict(session: AsyncSession) -> dict[int, str]:
    query = select(CCity).order_by(CCity.id)
    result = await session.execute(query)
    cities: list[CCity] = list(result.scalars().all())
    return {city.id: city.name for city in cities}


async def DB_GetAllActions(session: AsyncSession) -> list[CAction]:
    query = select(CAction).order_by(CAction.id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_GetAllActions_as_dict(session: AsyncSession) -> dict[int, str]:
    query = select(CAction).order_by(CAction.id)
    result = await session.execute(query)
    actions: list[CAction] = list(result.scalars().all())
    return {action.id: action.title for action in actions}


async def DB_GetGamesAfterDate(session: AsyncSession, City: CCity, after_date: datetime) -> list[CGame]:
    query = ((select(CGame).where(CGame.start_date > after_date).
              where(CGame.id_place == CPlace.id).where(CPlace.id_city == City.id)).
             order_by(CGame.start_date))
    result = await session.execute(query)
    game_list: list[CGame] = []
    for Game in result.scalars().all():
        Status: CStatus = await Game.ActualStatus()
        if Status.code == "GAME_ANNOUNCED":
            game_list.append(Game)
    return game_list


async def DB_GetGamesAfterDateByCityID(session: AsyncSession, id_city: int, after_date: datetime) -> list[CGame]:
    query = (select(CGame, CPlace).where(CGame.start_date > after_date).
             where(CGame.id_place == CPlace.id).where(CPlace.id_city == id_city))
    result = await session.execute(query)
    game_list: list[CGame] = []
    for Game in result.scalars().all():
        Status: CStatus = await Game.ActualStatus()
        if Status.code == "GAME_ANNOUNCED":
            game_list.append(Game)
    return game_list


async def DB_GetGamesOfModeratorAfterDate(session: AsyncSession, id_moderator: int, id_city: int,
                                          after_date: datetime) -> list[CGame]:
    query = (select(CGame, CPlace, CModerator).
             where(CGame.id_moderator == CModerator.id).
             where(CGame.id_place == CPlace.id).
             where(CPlace.id_city == id_city).
             where(CGame.id_moderator == id_moderator).
             where(CGame.start_date > after_date))
    result = await session.execute(query)
    game_list: list[CGame] = []
    for Game in result.scalars().all():
        Status: CStatus = await Game.ActualStatus()
        if Status.code == "GAME_ANNOUNCED":
            game_list.append(Game)
    return game_list


async def DB_CheckSigned(session: AsyncSession, id_game: int, id_person: int) -> CNickname | None:
    query = (select(CNickname, CGame, CPerson, CPlayer).
             where(CPlayer.id_nickname == CNickname.id).
             where(CPlayer.id_game == CGame.id).
             where(CPlayer.deleted == sql.expression.false()).
             where(CNickname.id_person == CPerson.id).
             where(CGame.id == id_game).where(CPerson.id == id_person))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def DB_CheckSigned2(session: AsyncSession, id_game: int, id_person: int) -> list[CNickname]:
    query = (select(CNickname, CGame, CPerson, CPlayer).
             where(CPlayer.id_nickname == CNickname.id).
             where(CPlayer.id_game == CGame.id).
             where(CPlayer.deleted == sql.expression.false()).
             where(CNickname.id_person == CPerson.id).
             where(CGame.id == id_game).where(CPerson.id == id_person))
    result = await session.execute(query)
    return list(result.scalars().all())

async def DB_CheckSignedByNickNameID(session: AsyncSession, id_game: int, id_nickname: int) -> CNickname:
    query = (select(CNickname, CGame, CPerson, CPlayer).
             where(CPlayer.id_nickname == CNickname.id).
             where(CPlayer.id_game == CGame.id).
             where(CPlayer.deleted == sql.expression.false()).
             where(CNickname.id_person == CPerson.id).
             where(CGame.id == id_game).where(CNickname.id == id_nickname))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def DB_CheckBills(session: AsyncSession, id_telegram: int) -> list[tuple[CPayment, CPerson, CGame, CNickname]]:
    query = (select(CPayment, CPerson, CGame, CStatus, CPlayer, CNickname, CTelegram).
             where(CPayment.id_status == CStatus.id).
             where(CPayment.id_player == CPlayer.id).
             where(CPlayer.id_nickname == CNickname.id).
             where(CPlayer.id_game == CGame.id).
             where(CNickname.id_person == CPerson.id).
             where(CTelegram.id_person == CPerson.id).
             where(CStatus.code == "PAY_RESERVED").
             where(CTelegram.telegram_id == id_telegram)
             )
    result = await session.execute(query)
    return [(row.CPayment, row.CPerson, row.CGame, row.CNickname) for row in result]


async def DB_Get_RESERVED_Payment(session: AsyncSession, id_telegram: int, id_payment) -> CPayment | None:
    query = (select(CPayment, CPerson, CGame, CStatus, CPlayer, CNickname, CTelegram).
             where(CPayment.id_status == CStatus.id).
             where(CPayment.id_player == CPlayer.id).
             where(CPlayer.id_nickname == CNickname.id).
             where(CPlayer.id_game == CGame.id).
             where(CNickname.id_person == CPerson.id).
             where(CTelegram.id_person == CPerson.id).
             where(CStatus.code == "PAY_RESERVED").
             where(CTelegram.telegram_id == id_telegram).
             where(CPayment.id == id_payment)
             )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if row is not None:
        return row.CPayment
    else:
        return None


async def DB_SignUpPlayer(session: AsyncSession, id_game: int, id_nickname: int,
                          Amount: int = 1) -> tuple[bool, str, int]:
    Game: CGame | None = await session.get(CGame, id_game)
    Nickname: CNickname | None = await session.get(CNickname, id_nickname)
    Place: CPlace = await Game.awaitable_attrs.place
    City: CCity = await Place.awaitable_attrs.city
    Gametype: CGameType | None = await Game.awaitable_attrs.game_type

    Player = CPlayer()
    Player.game = Game
    Player.nickname = Nickname
    session.add(Player)

    Status = await DB_GetStatusByCode(session=session, Code="PAY_RESERVED")

    for index in range(Amount):
        Payment = CPayment()
        Payment.player = Player
        Payment.status = Status
        Payment.game = Game
        NOW: datetime = NowConvertFromServerDateTime(tz=City.tz)
        Payment.assign_date = NOW
        session.add(Payment)

    ################################################################################
    Lead_Add = BitrixLeadAdd(WebHookUrl=GlobalSettings.BITRIX_LEAD_ADD)

    Person: CPerson = await Nickname.awaitable_attrs.person
    Phone: CPhone | None = await Nickname.Phone
    Telegram: CTelegram = await Person.MainTelegram

    """Работает"""
    Last_name = await  Person.awaitable_attrs.family
    Name = await Person.awaitable_attrs.name
    City_name = await City.awaitable_attrs.name

    Phone_number : str = ""
    if Phone is not None:
        Phone_number = await Phone.awaitable_attrs.phone_number

    Telegram_name = Telegram.telegram_name if Telegram.telegram_name else None


    Player_counts: str = f" + {Amount - 1}" if Amount > 1 else ""
    lead_fields = {
        "TITLE": "Лид из Mafia_inc_bot",
        "LAST_NAME": Last_name,
        "NAME": Name,
        "BIRTHDATE": Person.birthdate.strftime('%d.%m.%Y'),
        "ADDRESS_CITY": City_name,
        "PHONE": [{"VALUE": Phone_number, "VALUE_TYPE": "MOBILE"}],
        "COMMENTS": f"{Nickname.name}{Player_counts} - {City_name}\n"
                    f"{Game.start_date.strftime('%A, %d.%m.%Y, %H:%M')}\n"
                    f"{Gametype.title}\n"
                    f"Telegram: https://t.me/{Telegram_name}\n",
        "UTM_SOURCE": f"Бот телеграм"
    }

    ##############################################################################

    try:
        await session.flush()
        await session.refresh(Player) #Обновление записи об игроке
        await session.commit()

        ##########################################################################
        try:
            # Создание data лида
            response = await Lead_Add.create_lead(lead_fields=lead_fields)  # (session=session, lead_fields=lead_fields)
            if "result" in response:
                logging.getLogger().info(f"Лид успешно создан! ID: {response['result']}")
            elif "error" in response:
                logging.getLogger().error(f"Ошибка при создании лида: {response['error_description']} lead_fields = {lead_fields}")
            else:
                logging.getLogger().error(f"Неизвестный ответ от Bitrix24 lead_fields = {lead_fields}")
        except Exception as expt:
            logging.getLogger().error(f'Проблемы с лидом type: {type(expt)} args: {expt.args} exception: {expt} lead_fields = {lead_fields}')
        ##########################################################################

        return True, "Ок", Player.id
    except SQLAlchemyError:
        answer_str = "Ошибка при выполнении записи"
        return False, answer_str, 0

async def DB_GetEditableBillBoards(session: AsyncSession, id_moderator: int, id_city: int) -> list[CGame]:
    query = (select(CGame, CModerator, CCity, CPlace).
             where(CGame.id_moderator == CModerator.id).
             where(CGame.id_place == CPlace.id).
             where(CPlace.id_city == CCity.id).
             where(CCity.id == id_city).
             where(CModerator.id == id_moderator).
             where(CGame.start_date > datetime.now())
             )
    result = await session.execute(query)
    all_games: list[CGame] = list(result.scalars().all())
    return_list: list[CGame] = []

    for game in all_games:
        status: CStatus = await game.ActualStatus()
        if status.code in ["GAME_PLANNED", "GAME_PREPARED", "GAME_ANNOUNCED"]:
            return_list.append(game)
    return return_list

async def DB_CheckPlaceTitleInCity(session: AsyncSession, title: str, id_city: int) -> bool:
    query = func.count(select(CPlace.id).where(CPlace.id_city == id_city).
                       where(CPlace.title == title).scalar_subquery())
    result = await session.execute(query)
    value = result.first()[0]
    return value == 0


async def DB_AddNewPlace(session: AsyncSession, title: str,
                         address: str, seats: int, id_city: int,
                         game_types: dict[int, str] | None) -> tuple[bool, str]:
    try:
        Place: CPlace = CPlace(title=title, address=address, seats=seats)
        Place.id_city = id_city
        session.add(Place)
        for id_game_type, name in game_types.items():
            association: CPlaceGameTypeAssociation = CPlaceGameTypeAssociation()
            association.place = Place
            association.id_game_type = id_game_type
            Place.game_types_acc.append(association)
            session.add_all([association])
        await session.commit()
        return True, "Ok"
    except SQLAlchemyError:
        return False, f"Ошибка БД"


async def DB_UpdatePlace(session: AsyncSession, title: str,
                         address: str, seats: int, id_place: int, id_city: int,
                         game_types: dict[int, str] | None) -> tuple[bool, str]:
    try:
        Place: CPlace | None = await session.get(CPlace, id_place)
        Place.title = title
        Place.address = address
        Place.seats = seats
        # типы игр в ассоциации, которые есть сейчас
        associations: list[CPlaceGameTypeAssociation] = Place.game_types_acc
        # удаляем их все
        for index, association in enumerate(associations):
            if len(game_types) > 0:
                key, value = game_types.popitem()
                association.id_game_type = key
            else:
                await session.delete(association)

        if len(game_types) > 0:
            for key, value in game_types.items():
                association: CPlaceGameTypeAssociation = CPlaceGameTypeAssociation()
                association.place = Place
                association.id_game_type = key
                Place.game_types_acc.append(association)
                session.add(association)

        await session.commit()
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"


async def DB_SetGameStatus(session: AsyncSession, id_game: int, GameStatusCode: str, expiry_date: datetime | None = None) -> tuple[bool, str]:
    Game: CGame | None = await session.get(CGame, id_game)
    ActualStatus: CStatus = await Game.ActualStatus()

    if Game is None:
        return False, f"Нет объекта Game с id = {id_game}"

    statuses: list[CStatus] = await DB_GetStatusesForGame(session=session)
    _list = list(filter(lambda status: status.code == GameStatusCode, statuses))
    if len(_list) == 0:
        return False, f"Нет объекта Status с code = {GameStatusCode}"
    NOW: datetime = datetime.now()
    if expiry_date is not None and expiry_date <= NOW:
        return False, f"Нельзя присвоить новый статус с датой и временем окончания ранее даты и времени назначения, кроме None"

    if ActualStatus.code == _list[0].code:
        return False, f"Статус {_list[0].title} уже присвоен этой игре"

    status_association = CGameStatusAssociation()
    status_association.game = Game
    status_association.status = _list[0]
    status_association.assign_date = NOW
    status_association.expiry_date = expiry_date
    Game.statuses_acc.append(status_association)

    try:
        await session.commit()
        await session.refresh(Game)
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"




async def DB_AddNewGame(session: AsyncSession, id_place: int, id_game_type: int, id_moderator: int,
                        start_date: datetime, price: int, actions: dict[int, str],
                        poster_id: str) -> tuple[bool, str, int]:
    # Сначала надо проверить, попытку многократно создать игру с одними и теми жу параметрами
    # Делается на случай плохой связи и длительных задержек получения обновлений
    query = select(CGame).where(CGame.id_place == id_place).where(CGame.start_date == start_date)
    result = await session.execute(query)

    GameList: list[CGame] = list(result.scalars().all())

    count: int = 0
    for game in GameList:
        status: CStatus = await game.ActualStatus()
        if status.code == "GAME_ANNOUNCED" or status.code == "GAME_IN_PROVIDE":
            count += 1

    if count == 0:
        Game = CGame()
        Game.id_place = id_place
        Game.id_game_type = id_game_type
        Game.id_moderator = id_moderator
        Game.start_date = start_date
        Game.price = price

        Moderator: CModerator | None = await session.get(CModerator, id_moderator)
        games: list[CGame] = await Moderator.awaitable_attrs.games

        status = await DB_GetStatusByCode(session=session, Code="GAME_ANNOUNCED")
        status_association = CGameStatusAssociation()
        status_association.game = Game
        status_association.status = status
        status_association.assign_date = datetime.now()
        status_association.expiry_date = Game.start_date
        Game.statuses_acc.append(status_association)

        Moderator.games.append(Game)

        session.add_all([Game, status_association])

        for key, value in actions.items():
            GameAction = CGameActionAssociation()
            GameAction.game = Game
            GameAction.id_action = key
            session.add(GameAction)

        GameProperties: CGameProperties = CGameProperties()
        GameProperties.game = Game
        GameProperties.telegram_file_id = poster_id
        session.add(GameProperties)

        try:
            await session.commit()
            await session.refresh(Game)
            return True, "Ok", Game.id
        except SQLAlchemyError as E:
            return False, f"Ошибка БД: {E.args}", 0
    else:
        return False, f"Игра в выбранном месте и в заданное время уже объявлена ", 0


async def DB_UpdateGame(session: AsyncSession, id_game: int, id_place: int,
                        id_game_type: int, start_date: datetime, price: int,
                        actions: dict[int, str]) -> tuple[bool, str]:
    Game: CGame | None = await session.get(CGame, id_game)
    Game.price = price
    Game.start_date = start_date
    Game.id_place = id_place
    Game.id_game_type = id_game_type

    GameActions: list[CGameActionAssociation] = Game.actions_acc
    for index, association in enumerate(GameActions):
        if association.action.id in actions:
            del actions[association.action.id]
        else:
            del Game.actions_acc[index]
            await session.delete(association)

    if len(actions) > 0:
        for key, value in actions.items():
            association = CGameActionAssociation()
            association.game = Game
            association.id_action = key
            Game.actions_acc.append(association)
            session.add(association)
    try:
        await session.commit()
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"


async def DB_CancelGame(session: AsyncSession, id_game: int, apscheduler: AsyncIOScheduler):
    Game: CGame | None = await session.get(CGame, id_game)

    schedules: list[CScheduler] = await Game.awaitable_attrs.schedules

    Status = await DB_GetStatusByCode(session=session, Code="GAME_ABORTED")

    GameStatusAssociation: CGameStatusAssociation = CGameStatusAssociation()
    GameStatusAssociation.game = Game
    GameStatusAssociation.status = Status

    GameStatusAssociation.assign_date = datetime.now()
    Game.statuses_acc.append(GameStatusAssociation)

    session.add(GameStatusAssociation)

    for schedule in schedules:
        apscheduler.remove_job(job_id=str(schedule.id))
        await session.delete(schedule)
    await session.commit()


async def DB_ProvidePayment(session: AsyncSession, id_payment: int) -> tuple[bool, str]:
    """

    :param session: Сессия работы с БД
    :param id_payment: Значение первичного ключа сущности "Платёж"
    :return: кортеж, где первое значение булевского типа означает успех операции, второе, строковое значение,
    содержит описание ошибки SQLAlchemyError в случае неуспеха. "Ок", в случае успеха.
    """
    Payment: CPayment | None = await session.get(CPayment, id_payment)
    Status = await DB_GetStatusByCode(session=session, Code="PAY_PROVIDED")

    Payment.status = Status

    try:
        await session.commit()
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"


async def DB_ProvidePaymentsOfPlayer(session: AsyncSession, id_player: int) -> tuple[bool, str]:
    Player: CPlayer | None = await session.get(CPlayer, id_player)
    Game: CGame = await Player.awaitable_attrs.game
    Place: CPlace = await Game.awaitable_attrs.place
    City: CCity = await Place.awaitable_attrs.city

    Payments: list[CPayment] = await Player.awaitable_attrs.payments
    Status = await DB_GetStatusByCode(session=session, Code="PAY_PROVIDED")

    for Payment in Payments:
        Payment.status = Status
        NOW: datetime = NowConvertFromServerDateTime(tz=City.tz)
        Payment.assign_date = NOW

    try:
        await session.commit()
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"


async def DB_GetSchedulerJobs(session: AsyncSession) -> list[CScheduler]:
    query = select(CScheduler).where(CScheduler.deleted == sql.expression.false())
    result = await session.execute(query)
    return list(result.scalars().all())


async def DB_SetupReminderScheduler(session: AsyncSession,
                                    id_game: int, id_telegram: int, id_person: int,
                                    id_payment: int, job_type: str, trigger_type: str, interval_hours: int | None,
                                    next_run_time: datetime | None, tz: str, apscheduler: AsyncIOScheduler):
    Scheduler = CScheduler()
    Scheduler.id_telegram = id_telegram
    Scheduler.id_game = id_game
    Scheduler.id_person = id_person
    Scheduler.id_payment = id_payment
    Scheduler.job_type = job_type
    Scheduler.trigger_type = trigger_type
    Scheduler.interval_hours = interval_hours
    Scheduler.next_run_time = next_run_time
    session.add(Scheduler)
    await session.flush()
    await session.refresh(Scheduler)

    if trigger_type == "interval":
        apscheduler.add_job(func=PayReminder, trigger=Scheduler.trigger_type, hours=interval_hours,
                            next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time, tz=tz),
                            id=str(Scheduler.id), kwargs={"shed_id": str(Scheduler.id)})
    else:
        apscheduler.add_job(func=PayReminder, trigger=Scheduler.trigger_type,
                            next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time, tz=tz),
                            id=str(Scheduler.id), kwargs={"shed_id": str(Scheduler.id)})

    if apscheduler.state == 0:
        apscheduler.start()

    await session.commit()


async def DB_SchedulePayReminder(session: AsyncSession, id_game: int,
                                 id_payment: int, apscheduler: AsyncIOScheduler):
    Game: CGame | None = await session.get(CGame, id_game)
    Place: CPlace = await Game.awaitable_attrs.place
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    City: CCity = await Game.City
    Payment: CPayment | None = await session.get(CPayment, id_payment)
    Player: CPlayer = await Payment.awaitable_attrs.player
    Nickname: CNickname = await Player.awaitable_attrs.nickname
    Person: CPerson = await Nickname.Person
    Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams

    Telegram: CTelegram = Telegrams[0]
    message_text: str = f"{Person.FormatName}, напоминаем Вам об оплате игры. " \
                        f"{Game.start_date.strftime('%A, %d.%m %H:%M')} " \
                        f"{Place.title}, {Place.address}. "

    if Moderator is not None and Moderator.pay_detail is not None:
        message_text += Moderator.pay_detail

    NOW = NowConvertFromServerDateTime(tz=City.tz)
    delta = Game.start_date - NOW

    # 1. Если больше 24 часов:
    #    1) отправлять сразу инфу об оплате
    #    2) через 4 часа после записи
    #    3) за 24 часа до игры
    if delta >= timedelta(hours=24):
        await PayReminderSendMessage(Telegram.telegram_id, message_text=message_text)
        await DB_SetupReminderScheduler(session=session, id_game=Game.id, id_telegram=Telegram.id,
                                        id_payment=Payment.id, id_person=Person.id, tz=City.tz,
                                        job_type="PAY_REMINDER", trigger_type="date", interval_hours=None,
                                        next_run_time=NOW + timedelta(hours=4), apscheduler=apscheduler)
        await DB_SetupReminderScheduler(session=session, id_game=Game.id, id_telegram=Telegram.id,
                                        id_payment=Payment.id, id_person=Person.id, tz=City.tz,
                                        job_type="PAY_REMINDER", trigger_type="date", interval_hours=None,
                                        next_run_time=Game.start_date - timedelta(hours=24), apscheduler=apscheduler)
    # 2. 24-8 часов
    #    1) сразу об оплате
    #    2) через 2 часа напомнить об оплате
    if timedelta(hours=8) <= delta < timedelta(hours=24):
        await PayReminderSendMessage(Telegram.telegram_id, message_text=message_text)
        await DB_SetupReminderScheduler(session=session, id_game=Game.id, id_telegram=Telegram.id,
                                        id_payment=Payment.id, id_person=Person.id, tz=City.tz,
                                        job_type="PAY_REMINDER", trigger_type="date",
                                        next_run_time=NOW + timedelta(hours=2), interval_hours=None,
                                        apscheduler=apscheduler)

    # 3. Меньше 8 часов
    #    1) каждые 2 часа, пока ведущий не подтвердит оплату
    if timedelta(hours=4) <= delta < timedelta(hours=8):
        await DB_SetupReminderScheduler(session=session, id_game=Game.id, id_telegram=Telegram.id,
                                        id_payment=Payment.id, id_person=Person.id, tz=City.tz,
                                        job_type="PAY_REMINDER", trigger_type="interval", interval_hours=2,
                                        next_run_time=NOW + timedelta(seconds=3), apscheduler=apscheduler)

    # 4. За 4 часа до игры
    #    1) приходит сразу
    if delta < timedelta(hours=4):
        await PayReminderSendMessage(Telegram.telegram_id, message_text=message_text)


async def DB_ScheduleSwitchGameStatus(session: AsyncSession, id_game: int, apscheduler: AsyncIOScheduler):
    Game: CGame | None = await session.get(CGame, id_game)
    City: CCity = await Game.City
    Moderator: CModerator = await Game.awaitable_attrs.moderator
    Person = await Moderator.Person
    Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
    Telegram: CTelegram = Telegrams[0]

    Scheduler = CScheduler()
    Scheduler.id_telegram = Telegram.id
    Scheduler.id_game = Game.id
    Scheduler.id_person = Person.id
    Scheduler.job_type = "GAME_STATUS_SWITCH"
    Scheduler.trigger_type = "date"
    Scheduler.next_run_time = Game.start_date
    session.add(Scheduler)
    await session.flush()
    await session.refresh(Scheduler)

    apscheduler.add_job(func=GameStatusSwitcher,
                        trigger=Scheduler.trigger_type,
                        next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time, tz=City.tz),
                        id=str(Scheduler.id),
                        kwargs={"shed_id": str(Scheduler.id), "apscheduler": apscheduler}
                        )

    if apscheduler.state == 0:
        apscheduler.start()

    await session.commit()


async def PayReminderSendMessage(chat_id: int | str, message_text: str):
    await bot.bot.MafiaBot.send_message(chat_id=chat_id, text=message_text)


async def PayReminder(shed_id: str):
    async with (async_session_factory() as session):
        scheduler_id: int = int(shed_id)
        Scheduler: CScheduler | None = await session.get(CScheduler, scheduler_id)
        if Scheduler is not None:
            Payment: CPayment = await Scheduler.awaitable_attrs.payment
            Status: CStatus = await Payment.awaitable_attrs.status
            if Status.code == "PAY_PROVIDED":
                await session.delete(Scheduler)
                await session.commit()
                return
            Telegram: CTelegram = await Scheduler.awaitable_attrs.telegram
            Person: CPerson = await Scheduler.awaitable_attrs.person
            Game: CGame = await Scheduler.awaitable_attrs.game
            Moderator: CModerator = await Game.awaitable_attrs.moderator
            Place: CPlace = await Game.awaitable_attrs.place
            if Status.code == "PAY_RESERVED":
                message_text: str = (f"{Person.FormatName}, напоминаем Вам об оплате игры. "
                                     f"{Game.start_date.strftime('%A, %d.%m %H:%M')} {Place.title}, {Place.address}.")

                if Moderator is not None and Moderator.pay_detail is not None:
                    message_text += Moderator.pay_detail

                await PayReminderSendMessage(chat_id=Telegram.telegram_id, message_text=message_text)
                await session.delete(Scheduler)
                await session.commit()


async def GameStatusSwitcher(shed_id: str, apscheduler: AsyncIOScheduler):
    async with async_session_factory() as session:
        scheduler_id = int(shed_id)
        Scheduler: CScheduler | None = await session.get(CScheduler, scheduler_id)
        if Scheduler is not None:
            Telegram: CTelegram = await Scheduler.awaitable_attrs.telegram
            Person: CPerson = await Scheduler.awaitable_attrs.person
            Game: CGame = await Scheduler.awaitable_attrs.game
            City: CCity = await Game.City

            _statuses: list[CGameStatusAssociation] = await Game.awaitable_attrs.statuses_acc
            Status: CStatus = _statuses[0].status
            if Status.code == "GAME_ABORTED":
                await session.delete(Scheduler)
                return

            Place: CPlace = await Game.awaitable_attrs.place

            if Status.code == "GAME_ANNOUNCED":
                NewStatus: CStatus = await DB_GetStatusByCode(session=session, Code="GAME_IN_PROVIDE")

                GameStatusAssociation: CGameStatusAssociation = CGameStatusAssociation()
                GameStatusAssociation.game = Game
                GameStatusAssociation.status = NewStatus

                NOW = NowConvertFromServerDateTime(tz=City.tz)
                GameStatusAssociation.assign_date = NOW
                GameStatusAssociation.expiry_date = NOW + timedelta(hours=5)
                session.add(GameStatusAssociation)

                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id,
                                                    text=f"{Person.FormatName}, статус игры "
                                                         f"{Game.start_date.strftime('%A, %d.%m %H:%M')}, "
                                                         f"{Place.title}, {Place.address} автоматически изменён на "
                                                         f"\"{NewStatus.title}\"")
                await session.delete(Scheduler)

                Scheduler = CScheduler()
                Scheduler.id_telegram = Telegram.id
                Scheduler.id_game = Game.id
                Scheduler.id_person = Person.id
                Scheduler.job_type = "GAME_STATUS_SWITCH"
                Scheduler.trigger_type = "date"
                Scheduler.next_run_time = GameStatusAssociation.expiry_date
                session.add(Scheduler)
                await session.flush()
                await session.refresh(Scheduler)

                apscheduler.add_job(func=GameStatusSwitcher,
                                    trigger=Scheduler.trigger_type,
                                    next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time, tz=City.tz),
                                    id=str(Scheduler.id),
                                    kwargs={"shed_id": str(Scheduler.id), "apscheduler": apscheduler}
                                    )

                await session.commit()
                return

            if Status.code == "GAME_IN_PROVIDE":
                NewStatus: CStatus = await DB_GetStatusByCode(session=session, Code="GAME_OVER")

                GameStatusAssociation: CGameStatusAssociation = CGameStatusAssociation()
                GameStatusAssociation.game = Game
                GameStatusAssociation.status = NewStatus
                NOW = NowConvertFromServerDateTime(tz=City.tz)
                GameStatusAssociation.assign_date = NOW
                session.add(GameStatusAssociation)

                await bot.bot.MafiaBot.send_message(chat_id=Telegram.telegram_id,
                                                    text=f"{Person.FormatName}, статус игры "
                                                         f"{Game.start_date.strftime('%A, %d.%m %H:%M')}, "
                                                         f"{Place.title}, {Place.address} автоматически изменён на "
                                                         f"\"{NewStatus.title}\"")
                await session.delete(Scheduler)
                await session.commit()
                return


async def DB_RestorePayReminder(session: AsyncSession, apscheduler: AsyncIOScheduler):
    query = (select(CScheduler).
             where(CScheduler.deleted == sql.expression.false()).
             where(CScheduler.job_type == "PAY_REMINDER")
             )
    result = await session.execute(query)

    Schedulers: list[CScheduler] = list(result.scalars().all())
    if len(Schedulers) > 0:
        for Scheduler in Schedulers:
            Game: CGame = await Scheduler.awaitable_attrs.game
            City: CCity = await Game.City
            if Scheduler.next_run_time > datetime.now():
                if Scheduler.trigger_type == "date":
                    apscheduler.add_job(func=PayReminder,
                                        trigger=Scheduler.trigger_type,
                                        next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time,
                                                                              tz=City.tz),
                                        id=str(Scheduler.id),
                                        kwargs={"shed_id": str(Scheduler.id)})
                if Scheduler.trigger_type == "interval":
                    apscheduler.add_job(func=PayReminder,
                                        trigger=Scheduler.trigger_type,
                                        hours=Scheduler.interval_hours,
                                        next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time,
                                                                              tz=City.tz),
                                        id=str(Scheduler.id),
                                        kwargs={"shed_id": str(Scheduler.id)})
            else:
                await session.delete(Scheduler)
        await session.commit()
        if apscheduler.state == 0:
            apscheduler.start()


async def DB_RestoreGameStatusSwitcher(session: AsyncSession, apscheduler: AsyncIOScheduler):
    query = (select(CScheduler).
             where(CScheduler.deleted == sql.expression.false()).
             where(CScheduler.job_type == "GAME_STATUS_SWITCH")
             )
    result = await session.execute(query)

    Schedulers: list[CScheduler] = list(result.scalars().all())
    if len(Schedulers) > 0:
        for Scheduler in Schedulers:
            Game: CGame = await Scheduler.awaitable_attrs.game
            City: CCity = await Game.City
            NOW = NowConvertFromServerDateTime(tz=City.tz)
            if Scheduler.next_run_time > NOW:
                apscheduler.add_job(func=GameStatusSwitcher,
                                    trigger=Scheduler.trigger_type,
                                    next_run_time=ConvertToServerDateTime(Value=Scheduler.next_run_time, tz=City.tz),
                                    id=str(Scheduler.id),
                                    kwargs={"shed_id": str(Scheduler.id), "apscheduler": apscheduler}
                                    )
            else:
                await session.delete(Scheduler)
        await session.commit()
        if apscheduler.state == 0:
            apscheduler.start()


async def DB_DeletePlayer(session: AsyncSession, apscheduler: AsyncIOScheduler, id_player: int) -> tuple[bool, str]:
    ReturnStatus: CStatus = await DB_GetStatusByCode(session=session, Code="PAY_RETURN")
    Player: CPlayer | None = await session.get(CPlayer, id_player)
    Player.deleted = True

    Game: CGame = await Player.awaitable_attrs.game

    Payments: list[CPayment] = await Player.awaitable_attrs.payments
    for Payment in Payments:
        Payment.status = ReturnStatus

    try:
        await session.commit()
        await session.refresh(Game)
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"


async def DB_ChangeModerator(session: AsyncSession, id_game: int, id_moderator: int) -> tuple[bool, str]:
    Game: CGame | None = await session.get(CGame, id_game)
    GameCity: CCity = await Game.City
    GameModerator: CModerator = await Game.Moderator

    Moderator: CModerator | None = await session.get(CModerator, id_moderator)
    ModeratorCity: CCity = await Moderator.City

    ModeratorPerson: CPerson = await Moderator.Person

    if ModeratorCity.id != GameCity.id:
        return False, (f"Босс, назначаемый ведущий и игра в разных городах. Добавьте {ModeratorPerson.FormatName} "
                       f"ведущим в городе {GameCity.name} или выберите другого ведущего.")

    if Game.id_moderator == id_moderator:
        return False, "Босс, назначаемый ведущий и ведущий в игры один и тот же"

    try:
        Game.moderator = Moderator
        await session.commit()

        await session.refresh(Game)
        await session.refresh(GameModerator)
        await session.refresh(Moderator)
        return True, "Ok"
    except SQLAlchemyError as E:
        return False, f"Ошибка БД: {E.args}"


async def DB_BlackFilter(session: AsyncSession, AnyText: str | None) -> bool:
    if AnyText is not None:
        s = set('[~!?@#$%^&*()_+{}":;]$<>\\|/.,№«»`').intersection(AnyText)
        if len(s) > 0:
            return False
        else:
            return True
    else:
        return True


# Требуется глубокий рефакторинг. Мудрёная и не до конца исследованная бизнес-операция
# исключения игроков в связи с просрочкой оплаты
async def DB_PaymentStatusUpdater():
    async with (async_session_factory() as session):
        query = (select(CPayment).
                 where(CPayment.id_status == CStatus.id).
                 where(CPayment.id_game == CGame.id).
                 where(CStatus.code == "PAY_RESERVED"))
        result = await session.execute(query)
        Payments: list[CPayment] = list(result.scalars().all())

        if len(Payments) == 0:
            return

        StatusOverdue: CStatus = await DB_GetStatusByCode(session=session, Code="PAY_OVERDUE")

        for Payment in Payments:
            Game: CGame = await Payment.Game
            GameStr: str = await Game.FormatGameStr
            Moderator: CModerator = await Game.awaitable_attrs.moderator
            Person: CPerson = await Moderator.Person
            Telegrams: list[CTelegram] = await Person.awaitable_attrs.telegrams
            ModeratorTelegram: CTelegram = Telegrams[0]

            Player: CPlayer = await Payment.awaitable_attrs.player
            Nickname: CNickname = await Player.awaitable_attrs.nickname

            GameStatus: CStatus = await Game.ActualStatus()
            # Если игра анонсирована, но не начата
            if GameStatus.code == "GAME_ANNOUNCED":
                City: CCity = await Game.City
                NOW = NowConvertFromServerDateTime(tz=City.tz)
                payment_date: datetime | None = Payment.assign_date
                # Если игрок бронировал место за сутки и более до начала игры
                if (payment_date is None) or ((Game.start_date - payment_date) >= timedelta(hours=24)):
                    # отменяем бронь за 6 часов до начала игры
                    if (NOW < Game.start_date) and ((Game.start_date - NOW) < timedelta(hours=6)):
                        Payment.status = StatusOverdue
                        if not Player.deleted:
                            Player.deleted = True
                            await bot.bot.MafiaBot.send_message(chat_id=ModeratorTelegram.telegram_id,
                                                                text=f"Игрок {Nickname.name} удалён из игры {GameStr}, "
                                                                     f"поскольку просрочена оплата.")
                # иначе, если игрок бронировал место менее, чем за 6 часов, но более чем за 4 часа до игры,
                # то аннулируем бронь за 3 часа до игры
                elif ((timedelta(hours=4) <= (Game.start_date - payment_date) <= timedelta(hours=6)) and
                      ((NOW - payment_date) > timedelta(hours=3))):
                    Payment.status = StatusOverdue
                    if not Player.deleted:
                        Player.deleted = True
                        await bot.bot.MafiaBot.send_message(chat_id=ModeratorTelegram.telegram_id,
                                                            text=f"Игрок {Nickname.name} удалён из игры {GameStr}, "
                                                                 f"поскольку просрочена оплата.")
            # Если игра начата
            if GameStatus.code == "GAME_IN_PROVIDE":
                Payment.status = StatusOverdue
                if not Player.deleted:
                    Player.deleted = True
                    await bot.bot.MafiaBot.send_message(chat_id=ModeratorTelegram.telegram_id,
                                                        text=f"Игрок {Nickname.name} удалён из игры {GameStr}, "
                                                             f"поскольку просрочена оплата.")
            await session.commit()
