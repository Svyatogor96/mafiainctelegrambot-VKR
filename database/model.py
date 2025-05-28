from __future__ import annotations
import platform
import locale

from typing import Annotated
from datetime import *
from sqlalchemy import (Table, Column, ForeignKey, Date, Time, DateTime, String, Text, DECIMAL, Integer, BigInteger,
                        Boolean)
from sqlalchemy import desc, asc, text, sql, and_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs

int_pk = Annotated[int, mapped_column(primary_key=True, autoincrement=True)]
str_code = Annotated[str, 20, mapped_column(nullable=False, unique=True)]
str_100 = Annotated[str, 100]
str_50 = Annotated[str, 50]
str_45 = Annotated[str, 45]
str_25 = Annotated[str, 25]
str_15 = Annotated[str, 15]
str_1 = Annotated[str, 1]
str_long = Annotated[str, 255]
str_super_long = Annotated[str, 1024]

if platform.system() == "Linux":
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

if platform.system() == "Windows":
    locale.setlocale(locale.LC_TIME, 'ru_RU')


class CBase(AsyncAttrs, DeclarativeBase):
    type_annotation_map = {
        str_1: String(1),
        str_15: String(15),
        str_25: String(25),
        str_45: String(45),
        str_50: String(50),
        str_100: String(100),
        str_long: String(255),
        str_super_long: String(1024),
        str_code: String(20)
    }
    id: Mapped[int_pk]


class CStatus(CBase):
    __tablename__ = "status"
    code: Mapped[str_code]
    title: Mapped[str_100] = mapped_column(nullable=False)


class CUser(CBase):
    """
    Сущность Пользователь
    Пользователь - это тот, кто использует систему и, в конечном итоге, это приводит к CRUD операциям.
    Сушность Пользователь имеет внешний ключ на сущность Персона. Потому что пользователями в системе
    могут люди (персонифицированные пользователи). А могут быть внешние системы: телеграм-боты, админ-панели,
    прочие информационные системы, которые также могут быть источником CRUD операций. Нужно
    различать таких пользователей.
    """
    __tablename__ = "user"
    id_person: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    person: Mapped["CPerson"] = relationship(lazy="selectin")
    user_hash: Mapped[str_50 | None]
    user_salt: Mapped[str_50 | None]
    user_token: Mapped[str_50 | None]
    right_acc: Mapped[list["CUserRightAssociation"]] = (
        relationship("CUserRightAssociation",
                     lazy="select",
                     order_by=desc(text("user_right.assign_date")),
                     back_populates="user"))

    @property
    async def Person(self) -> CPerson:
        return self.person


class CRight(CBase):
    __tablename__ = "right"
    code: Mapped[str_code]
    title: Mapped[str_long] = mapped_column(nullable=False)
    notes: Mapped[str | None] = mapped_column(type_=Text)


class CUserRightAssociation(CBase):
    __tablename__ = "user_right"
    id_user: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    id_right: Mapped[int] = mapped_column(ForeignKey("right.id"), primary_key=True)
    user: Mapped[CUser] = relationship(CUser, lazy="selectin")
    right: Mapped[CRight] = relationship(CRight, lazy="selectin")
    assign_date: Mapped[date] = mapped_column(type_=Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(type_=Date, nullable=True)


class CTelegram(CBase):
    __tablename__ = "telegram"
    id_person: Mapped[int | None] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=True)
    telegram_name: Mapped[str_50 | None] = mapped_column()
    telegram_url: Mapped[str_50 | None] = mapped_column()
    telegram_id: Mapped[int] = mapped_column(nullable=False, type_=BigInteger, unique=True)
    person: Mapped["CPerson"] = relationship("CPerson", lazy="selectin", back_populates="telegrams")
    last_activity: Mapped[datetime | None] = mapped_column(type_=DateTime)

    @property
    async def is_registered(self) -> bool:
        return await self.awaitable_attrs.person is not None

    @property
    async def Person(self) -> CPerson:
        return await self.awaitable_attrs.person

    def __repr__(self) -> str:
        return f"CTelegram [id={self.id},  id_person={self.id_person}]"


# cascade="all, delete-orphan",
class CPerson(CBase):
    __tablename__ = "person"
    id_city: Mapped[int | None] = mapped_column(ForeignKey("city.id"), nullable=True)
    family: Mapped[str_50 | None]
    name: Mapped[str_50 | None]
    father_name: Mapped[str_50 | None]
    birthdate: Mapped[date | None]
    sex: Mapped[str_1 | None]
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
    city: Mapped["CCity"] = relationship(lazy="selectin")
    nicknames: Mapped[list["CNickname"]] = relationship("CNickname", lazy="selectin", back_populates="person",
                                                        cascade="all, delete-orphan",
                                                        primaryjoin="and_(CNickname.id_person == CPerson.id, "
                                                                    "CNickname.deleted == False)")
    deleted_nicknames: Mapped[list["CNickname"]] = relationship(lazy="selectin", viewonly=True,
                                                                primaryjoin="and_(CNickname.id_person == CPerson.id, "
                                                                            "CNickname.deleted == True)")
    emails: Mapped[list["CEmail"]] = relationship(lazy="selectin", back_populates="person",
                                                  cascade="all, delete-orphan")
    phones: Mapped[list["CPhone"]] = relationship(lazy="selectin", back_populates="person",
                                                  cascade="all, delete-orphan")
    telegrams: Mapped[list[CTelegram]] = relationship(lazy="selectin", back_populates="person",
                                                      cascade="all, delete-orphan")
    moderators: Mapped[list["CModerator"]] = relationship("CModerator", lazy="selectin", viewonly=True,
                                                          primaryjoin="and_(CModerator.id_person == CPerson.id, "
                                                                      "CModerator.deleted == False)")
    statuses_acc: Mapped[list["CPersonStatusAssociation"]] = (
        relationship("CPersonStatusAssociation",
                     lazy="select",
                     order_by=desc(text("person_status.assign_date")),
                     back_populates="person"))

    @property
    def FormatName(self) -> str:
        if self.family is None and self.name is None and self.father_name is None:
            return "Инкогнито"
        if self.father_name is not None:
            return f"{self.name} {self.father_name}"
        else:
            return f"{self.name}"

    @property
    def FormatNameFamily(self) -> str:
        result = ""
        if self.name is not None:
            result += f"{self.name} "

        if self.family is not None:
            result += f"{self.family} "

        return result

    @property
    def FormatFullName(self) -> str:
        if self.family is None and self.name is None and self.father_name is None:
            return "Нет данных"
        result: str = ""

        if self.family is not None:
            result += f"{self.family} "

        if self.name is not None:
            result += f"{self.name} "

        if self.father_name is not None:
            result += f"{self.father_name}"

        return result

    @property
    async def PersonInfo(self) -> str:
        Family: str | None = self.family
        if Family is None:
            Family = "-"
        Name: str | None = self.name
        if Name is None:
            Name = "-"
        FatherName: str | None = self.father_name
        if FatherName is None:
            FatherName = "-"
        result = "<b>Персональные данные.</b>\n"
        result += f"<b>ФИО:</b> {Family} {Name} {FatherName}\n"

        SexLiteral = await self.awaitable_attrs.sex
        result += f"<b>Пол:</b> "
        if SexLiteral == "M":
            result += f"Мужской\n"
        elif SexLiteral == "F":
            result += f"Женский\n"
        else:
            result += f"не указан\n"

        result += f"<b>Домашний город:</b> {self.city.name}\n"
        result += f"<b>День рождения:</b> "
        if self.birthdate is not None:
            result += f"{self.birthdate.strftime('%d %B %Y')}\n"
        else:
            result += "не указан\n"

        result += f"<b>Номера тел.:</b>"
        phones: list[CPhone] = await self.awaitable_attrs.phones
        for index, phone in enumerate(phones):
            if index > 0:
                result += ", "
            else:
                result += " "
            result += f"{phone.phone_number}"
        if len(phones) == 0:
            result += " нет"

        result += "\n"
        result += f"<b>Emails:</b>"
        emails: list[CEmail] = await self.awaitable_attrs.emails
        for index, email in enumerate(emails):
            if index > 0:
                result += ", "
            else:
                result += " "
            result += f"{email.email_address}"

        if len(emails) == 0:
            result += " нет"

        result += "\n"
        result += f"<b>Псевдонимы:</b>"
        Nicknames: list[CNickname] = await self.awaitable_attrs.nicknames
        for index, nickname in enumerate(Nicknames):
            if index > 0:
                result += ", "
            else:
                result += " "
            result += f"{nickname.name}"
        result += "\n"
        return result

    @property
    async def MainTelegram(self) -> CTelegram | None:
        Telegrams: list[CTelegram] = await self.awaitable_attrs.telegrams
        if len(Telegrams) > 0:
            return Telegrams[0]
        else:
            return None


class CPersonStatusAssociation(CBase):
    __tablename__ = "person_status"
    id_person: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), primary_key=True)
    id_status: Mapped[int] = mapped_column(ForeignKey("status.id"), primary_key=True)
    person: Mapped[CPerson] = relationship(CPerson, lazy="selectin")
    status: Mapped[CStatus] = relationship(CStatus, lazy="selectin")
    assign_date: Mapped[date] = mapped_column(type_=Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(type_=Date, nullable=True)


class CNickname(CBase):
    __tablename__ = "nickname"
    id_person: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)  # ondelete="cascade"
    person: Mapped[CPerson] = relationship(back_populates="nicknames", lazy="selectin")
    name: Mapped[str_100] = mapped_column(nullable=False)
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)

    @property
    async def Person(self) -> CPerson:
        return await self.awaitable_attrs.person

    @property
    async def Phone(self) -> CPhone | None:
        _person: CPerson =  await self.Person
        Phones: list[CPhone] = await _person.awaitable_attrs.phones
        if len(Phones) > 0:
            return Phones[0]
        else:
            return None



class CEmail(CBase):
    __tablename__ = "email"
    id_person: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    person: Mapped[CPerson] = relationship(back_populates="emails", lazy="selectin")
    email_address: Mapped[str_100] = mapped_column(nullable=False, unique=True)

    @property
    def Person(self) -> CPerson:
        return self.person


class CPhone(CBase):
    __tablename__ = "phone"
    id_person: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    person: Mapped[CPerson] = relationship(back_populates="phones", lazy="selectin")
    phone_number: Mapped[str_15] = mapped_column(nullable=False, unique=True)

    @property
    def Person(self) -> CPerson:
        return self.person


class CCity(CBase):
    __tablename__ = "city"
    name: Mapped[str_25] = mapped_column(nullable=False)
    code: Mapped[str_code]
    tz: Mapped[str_45] = mapped_column(nullable=False)
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
    places: Mapped[list["CPlace"]] = relationship(lazy="selectin", back_populates="city")
    moderators: Mapped[list["CModerator"]] = relationship(lazy="selectin")


class CPlace(CBase):
    __tablename__ = "place"
    id_city: Mapped[int] = mapped_column(ForeignKey("city.id"), nullable=False)
    city: Mapped[CCity] = relationship(back_populates="places", lazy="selectin")
    title: Mapped[str_100] = mapped_column(nullable=False)
    address: Mapped[str_100] = mapped_column(nullable=False)
    seats: Mapped[int] = mapped_column(server_default='20', default=20)
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
    game_types_acc: Mapped[list["CPlaceGameTypeAssociation"]] = relationship("CPlaceGameTypeAssociation",
                                                                             lazy="selectin", back_populates="place")

    @property
    async def City(self) -> CCity:
        return self.city

    @property
    async def PlaceGameTypes(self) -> list["CPlaceGameTypeAssociation"]:
        return self.game_types_acc


class CPlaceGameTypeAssociation(CBase):
    __tablename__ = "place_game_type"
    id_place: Mapped[int] = mapped_column(ForeignKey("place.id"))
    id_game_type: Mapped[int] = mapped_column(ForeignKey("game_type.id"))
    place: Mapped[CPlace] = relationship(CPlace, lazy="selectin")
    game_type: Mapped["CGameType"] = relationship("CGameType", lazy="selectin")


class CModerator(CBase):
    __tablename__ = "moderator"
    id_person: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    id_city: Mapped[int] = mapped_column(ForeignKey("city.id"), nullable=False)
    pay_detail: Mapped[str | None] = mapped_column(type_=Text)
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
    person: Mapped[CPerson] = relationship(lazy="selectin", back_populates="moderators")
    city: Mapped[CCity] = relationship(back_populates="moderators", lazy="selectin")
    games: Mapped[list[CGame]] = relationship("CGame", lazy="selectin", order_by=asc(text("game.start_date")))

    @property
    async def Person(self) -> CPerson:
        return await self.awaitable_attrs.person

    @property
    async def City(self) -> CCity:
        return await self.awaitable_attrs.city

    @property
    async def Telegram(self) -> CTelegram | None:
        _p: CPerson = await self.Person
        return await _p.MainTelegram


class CGameType(CBase):
    __tablename__ = "game_type"
    title: Mapped[str_long] = mapped_column(nullable=False)
    code: Mapped[str_code]
    notes: Mapped[str | None] = mapped_column(type_=Text)


class CGame(CBase):
    __tablename__ = "game"
    id_place: Mapped[int] = mapped_column(ForeignKey("place.id"), nullable=False)
    id_game_type: Mapped[int] = mapped_column(ForeignKey("game_type.id"), nullable=False)
    id_moderator: Mapped[int] = mapped_column(ForeignKey("moderator.id"), nullable=False)
    place: Mapped[CPlace] = relationship(CPlace, lazy="selectin")
    moderator: Mapped[CModerator] = relationship(CModerator, lazy="selectin", back_populates="games")
    game_type: Mapped[CGameType] = relationship(CGameType, lazy="selectin")
    start_date: Mapped[datetime] = mapped_column(nullable=False, type_=DateTime)
    price: Mapped[int] = mapped_column(nullable=False, type_=Integer)
    statuses_acc: Mapped[list["CGameStatusAssociation"]] = (relationship("CGameStatusAssociation",
                                                                         lazy="selectin",
                                                                         order_by=desc(text("game_status.assign_date")),
                                                                         back_populates="game"))
    actions_acc: Mapped[list["CGameActionAssociation"]] = (relationship("CGameActionAssociation",
                                                                        lazy="selectin",
                                                                        back_populates="game"))
    properties: Mapped["CGameProperties"] = relationship("CGameProperties",
                                                         lazy="selectin", back_populates="game")
    players: Mapped[list["CPlayer"]] = relationship("CPlayer", lazy="selectin", back_populates="game")

    actual_players: Mapped[list["CPlayer"]] = relationship("CPlayer",
                                                           primaryjoin="and_(CPlayer.id_game == CGame.id,"
                                                                       "CPlayer.deleted == False)",
                                                           viewonly=True)
    payments: Mapped[list["CPayment"]] = relationship("CPayment", lazy="selectin", back_populates="game")
    schedules: Mapped[list["CScheduler"]] = relationship("CScheduler",
                                                         primaryjoin="and_(CScheduler.id_game == CGame.id)",
                                                         viewonly=True)

    def __str__(self):
        return f"{self.place.title}, {self.start_date.strftime('%d.%m %H:%M')}"

    def __repr__(self) -> str:
        return f"{self.id}"

    @property
    async def Place(self) -> CPlace:
        return self.place

    @property
    async def City(self) -> CCity:
        _place: CPlace = await self.awaitable_attrs.place
        return await _place.awaitable_attrs.city

    @property
    async def Moderator(self) -> CModerator:
        return await self.awaitable_attrs.moderator

    @property
    async def FormatGameStr(self) -> str:
        city = await self.City
        return (f"{city.name}, "
                f"{self.start_date.strftime('%A, %d.%m.%Y, %H:%M')}, "
                f"{self.place.title}, {self.place.address}")

    async def HasStatus(self, StatusCode: str) -> bool:
        status_list: list[CGameStatusAssociation] = self.statuses_acc
        for elem in status_list:
            if elem.status.code == StatusCode:
                return True
        return False

    async def ActualStatus(self) -> CStatus:
        status_list: list[CGameStatusAssociation] = await self.awaitable_attrs.statuses_acc
        return await status_list[0].awaitable_attrs.status

    async def PaymentsWithStatus(self, StatusCodes: list[str]) -> list[CPayment]:
        result: list[CPayment] = []
        for _payment in await self.awaitable_attrs.payments:
            Status: CStatus = await _payment.awaitable_attrs.status
            if Status.code in StatusCodes:
                result.append(_payment)
        return result


# используется шаблон ассоциативного объекта (согласно документации) для реализации отношения многие-ко-многим для
# статусов игр


class CGameStatusAssociation(CBase):
    __tablename__ = "game_status"
    id_game: Mapped[int] = mapped_column(ForeignKey("game.id"), primary_key=True)
    id_status: Mapped[int] = mapped_column(ForeignKey("status.id"), primary_key=True)
    status: Mapped[CStatus] = relationship(CStatus, lazy="selectin")
    game: Mapped[CGame] = relationship(CGame, lazy="selectin")
    assign_date: Mapped[datetime] = mapped_column(type_=DateTime, nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(type_=DateTime, nullable=True)


class CGameProperties(CBase):
    __tablename__ = "game_properties"
    id_game: Mapped[int] = mapped_column(ForeignKey("game.id"), primary_key=True)
    game: Mapped[CGame] = relationship(CGame, lazy="selectin", back_populates="properties")
    telegram_file_id: Mapped[str_super_long | None]
    image_url: Mapped[str_super_long | None]
    post: Mapped[str | None] = mapped_column(type_=Text)

    @property
    async def HasFileID(self) -> bool:
        return await self.telegram_file_id is not None

    @property
    async def HasURL(self) -> bool:
        return await self.image_url is not None

    @property
    async def HasPost(self) -> bool:
        return await self.post is not None


class CAction(CBase):
    __tablename__ = "action"
    code: Mapped[str_code]
    title: Mapped[str_100] = mapped_column(nullable=False)
    comment: Mapped[str_100] = mapped_column(nullable=False)
    notes: Mapped[str | None] = mapped_column(type_=Text)
    games_acc: Mapped[list["CGameActionAssociation"]] = (relationship("CGameActionAssociation",
                                                                      lazy="select",
                                                                      back_populates="action"))


class CGameActionAssociation(CBase):
    __tablename__ = "game_action"
    id_game: Mapped[int] = mapped_column(ForeignKey("game.id"), primary_key=True)
    id_action: Mapped[int] = mapped_column(ForeignKey("action.id"), primary_key=True)
    action: Mapped[CAction] = relationship(CAction, lazy="selectin")
    game: Mapped[CGame] = relationship(CGame, lazy="selectin")


class CPlayer(CBase):
    __tablename__ = "player"
    id_game: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False)
    id_nickname: Mapped[int] = mapped_column(ForeignKey("nickname.id"), nullable=False)
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
    nickname: Mapped[CNickname] = relationship(CNickname, lazy="selectin")
    game: Mapped[CGame] = relationship(CGame, lazy="selectin", back_populates="players")
    payments: Mapped[list["CPayment"]] = relationship("CPayment", lazy="selectin", back_populates="player")
    statuses_acc: Mapped[list["CPlayerStatusAssociation"]] = (
        relationship("CPlayerStatusAssociation",
                     lazy="select",
                     order_by=desc(text("player_status.assign_date")),
                     back_populates="player"))

    @property
    async def ProvidedPaymentsCount(self) -> int:
        result: int = 0
        _pays: list[CPayment] = await self.awaitable_attrs.payments

        for _pay in _pays:
            Status: CStatus = await _pay.awaitable_attrs.status
            if Status.code == "PAY_PROVIDED":
                result += 1
        return result


class CPlayerStatusAssociation(CBase):
    __tablename__ = "player_status"
    id_player: Mapped[int] = mapped_column(ForeignKey("player.id"), primary_key=True)
    id_status: Mapped[int] = mapped_column(ForeignKey("status.id"), primary_key=True)
    player: Mapped[CPerson] = relationship(CPlayer, lazy="selectin")
    status: Mapped[CStatus] = relationship(CStatus, lazy="selectin")
    assign_date: Mapped[date] = mapped_column(type_=Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(type_=Date, nullable=True)


class CPayment(CBase):
    __tablename__ = "payment"
    id_player: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    id_status: Mapped[int] = mapped_column(ForeignKey("status.id"), nullable=False)
    id_game: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False)
    player: Mapped[CPlayer] = relationship(CPlayer, lazy="selectin", back_populates="payments")
    status: Mapped[CStatus] = relationship(CStatus, lazy="selectin")
    game: Mapped[CGame] = relationship(CGame, lazy="selectin", back_populates="payments")
    assign_date: Mapped[datetime | None] = mapped_column(type_=DateTime, nullable=True)

    @property
    async def Game(self) -> CGame:
        return self.player.game


class CTelegramBotMessageGroup(CBase):
    __tablename__ = "telegram_bot_message_group"
    code: Mapped[str_code]
    title: Mapped[str_100] = mapped_column(nullable=False)


class CTelegramBotMessage(CBase):
    __tablename__ = "telegram_bot_message"
    id_message_group: Mapped[int] = mapped_column(ForeignKey("telegram_bot_message_group.id"), nullable=False)
    message_group: Mapped[CTelegramBotMessageGroup] = relationship(CTelegramBotMessageGroup, lazy="selectin")
    message_code: Mapped[str | None] = mapped_column(type_=String(50))
    sex: Mapped[str_1 | None]
    message: Mapped[str | None] = mapped_column(type_=Text)
    order_: Mapped[int | None] = mapped_column(type_=Integer)

    @property
    async def Message(self) -> str:
        return self.message


class CScheduler(CBase):
    __tablename__ = "scheduler"
    job_type: Mapped[str_25]
    trigger_type: Mapped[str_15]  # trigger (e.g. ``date``, ``interval`` or ``cron``)
    next_run_time: Mapped[datetime | None]
    interval_hours: Mapped[int | None]
    id_telegram: Mapped[int | None] = mapped_column(ForeignKey("telegram.id"))
    id_payment: Mapped[int | None] = mapped_column(ForeignKey("payment.id"))
    id_person: Mapped[int | None] = mapped_column(ForeignKey("person.id"))
    id_game: Mapped[int | None] = mapped_column(ForeignKey("game.id"))
    telegram: Mapped[CTelegram | None] = relationship(lazy="selectin")
    payment: Mapped[CPayment | None] = relationship(lazy="selectin")
    person: Mapped[CPerson | None] = relationship(lazy="selectin")
    game: Mapped[CGame | None] = relationship(lazy="selectin")
    pause: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
    deleted: Mapped[bool] = mapped_column(type_=Boolean, server_default=sql.expression.false(), nullable=False)
