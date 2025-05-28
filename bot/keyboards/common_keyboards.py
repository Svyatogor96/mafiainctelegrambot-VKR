from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from bot.callbacks import RegistrationCallback, UserCallback


def InlineKeyboard_ByDict(data_dict: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value in data_dict.items():
        builder.row(InlineKeyboardButton(text=key, callback_data=value))
    return builder.as_markup()


def InlineKeyboard_ByDict_CallbackData(cb_data_dict: dict[str, CallbackData]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, cb_data in cb_data_dict.items():
        builder.button(text=key, callback_data=cb_data)
    builder.adjust(2)
    return builder.as_markup()


def ReplyKeyboard_ByDict(data_dict: dict[str, str]) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for key, value in data_dict:
        kb.button(text=value)
    return kb.as_markup()


def ReplyKeyboard_ByList(ButtonCaptions: list[str]) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for caption in ButtonCaptions:
        kb.button(text=caption)
    return kb.as_markup(resize_keyboard=True)


def ReplyKeyboard_Two_Button(Button1Caption: str, Button2Caption: str) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=Button1Caption)
    kb.button(text=Button2Caption)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def ReplyKeyboard_Yes_No() -> ReplyKeyboardMarkup:
    return ReplyKeyboard_Two_Button(Button1Caption="Да", Button2Caption="Нет")


def InlineKeyboard_Yes_No() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Да", callback_data="_YES_"))
    builder.row(InlineKeyboardButton(text="Нет", callback_data="_NO_"))
    return builder.as_markup()


def InlineKeyboard_Yes_No_For_Registration() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data=RegistrationCallback(action="YES"))
    builder.button(text="Нет", callback_data=RegistrationCallback(action="NO"))
    return builder.as_markup()


def IKBM_User_ByDict_KeyValue(data: dict[int, str], action: str,
                              size: int = 2,
                              CancelButton: bool = False,
                              CancelButtonCaption: str = "Отмена") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value in data.items():
        builder.button(text=value, callback_data=UserCallback(action=action, key=key))
    if CancelButton:
        builder.button(text=CancelButtonCaption, callback_data=UserCallback(action=action, id_game_type=0))
    builder.adjust(size)
    return builder.as_markup()


def IKBM_User_ByDict_UserCallbackData(callback_data_dict: dict[str, UserCallback],
                                      size: int = 2,
                                      CancelButton: bool = False,
                                      CancelButtonCaption: str = "Отмена",
                                      CancelButtonCallbackData: UserCallback = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value in callback_data_dict.items():
        builder.button(text=key, callback_data=value)
    if CancelButton:
        builder.button(text=CancelButtonCaption, callback_data=CancelButtonCallbackData)
    builder.adjust(size)
    return builder.as_markup()
