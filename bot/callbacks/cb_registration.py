from typing import Any
from aiogram.filters.callback_data import CallbackData


class RegistrationCallback(CallbackData, prefix="registration"):
    action: str = "0"
    city_id: int = 0
    telegram_id: int = 0
    telegram_user: str = "0"
    person_family: str = "0"
    person_name: str = "0"
    person_father_name: str = "0"
    person_phone_number: str = "0"
    person_sex: str = "0"


class AdminCallback(CallbackData, prefix="admin"):
    action: str = "0"
    id_admin: int = 0
    id_game: int = 0
    id_game_type: int = 0
    id_city: int = 0
    id_moderator: int = 0
    id_place: int = 0
    id_action: int = 0
    id_player: int = 0
    id_payment: int = 0
    price: int = 0

    def __init__(self, action: str = "0", id_admin: int = 0, id_game: int = 0,
                 id_game_type: int = 0, id_city: int = 0, id_moderator: int = 0,
                 id_place: int = 0, id_action: int = 0, id_player: int = 0,
                 id_payment: int = 0, price: int = 0,
                 **data: Any):
        super().__init__(**data)
        self.action = action
        self.id_admin = id_admin
        self.id_game = id_game
        self.id_game_type = id_game_type
        self.id_city = id_city
        self.id_moderator = id_moderator
        self.id_place = id_place
        self.id_action = id_action
        self.id_player = id_player
        self.id_payment = id_payment
        self.price = price


class UserCallback(CallbackData, prefix="user"):
    action: str = "0"
    key: int = 0
    id_person: int = 0
    id_game: int = 0
    id_city: int = 0
    id_place: int = 0
    id_player: int = 0
    id_payment: int = 0
    id_nickname: int = 0
    id_phone: int = 0
    id_email: int = 0


class CSUCallBack(CallbackData, prefix="su"):
    action: str = "0"
    id_person: int = 0
    id_city: int = 0
    id_moderator: int = 0
    id_game: int = 0
