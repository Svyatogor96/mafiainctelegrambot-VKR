from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from bot.callbacks import AdminCallback
from backendapi.database import *


def InlineKeyboard_Admin_Yes_No() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data=AdminCallback(action="YES"))
    builder.button(text="Нет", callback_data=AdminCallback(action="NO"))
    return builder.as_markup()


def InlineKeyboard_Admin_Keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Открыть запись на игру", callback_data=AdminCallback(action="BB_NEW"))
    builder.button(text="ЗАКРЫТЬ запись на игру", callback_data=AdminCallback(action="BB_CLOSE"))
    builder.button(text="Редактировать афишу", callback_data=AdminCallback(action="BB_EDIT"))
    builder.button(text="Новое место для игр", callback_data=AdminCallback(action="PE_NEW"))
    builder.button(text="Редактировать место для игр", callback_data=AdminCallback(action="PE_EDIT_PLACE"))
    builder.button(text="Подтвердить оплату", callback_data=AdminCallback(action="ADMIN_GAME_LIST"))
    builder.button(text="Общее сообщение", callback_data=AdminCallback(action="ADMIN_BROADCAST_MESSAGE_PREPARE"))
    builder.button(text="Исключить игроков", callback_data=AdminCallback(action="ADMIN_PLAYER_EDITOR"))
    builder.button(text="Добавить игроков", callback_data=AdminCallback(action="ADMIN_PLAYER_ADD"))
    builder.button(text="Отчёт", callback_data=AdminCallback(action="ADM_REPORT_MAIN"))
    builder.button(text="Выход", callback_data=AdminCallback(action="ADMIN_LOGOUT"))
    builder.adjust(2, 1, 2, 2, 1, 1, 1)
    return builder.as_markup()


def InlineKeyboard_Admin_Report_Keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Игры", callback_data=AdminCallback(action="ADM_REPORT_GAMES"))
    builder.button(text="Игроки", callback_data=AdminCallback(action="ADM_REPORT_PLAYERS"))
    builder.button(text="Места", callback_data=AdminCallback(action="ADM_REPORT_PLACES"))
    builder.button(text="Назад", callback_data=AdminCallback(action="ADM_REPORT_EXIT"))
    builder.adjust(2)
    return builder.as_markup()


def InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict: dict[str, AdminCallback],
                                             size: int = 2) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, cb_data in cb_data_dict.items():
        builder.button(text=key, callback_data=cb_data)
    builder.adjust(size)
    return builder.as_markup()


def InlineKeyboard_Admin_ByDict_IdGameTypeKeyValue(data: dict[int, str], action: str,
                                                   size: int = 2,
                                                   AllButton: bool = False,
                                                   CancelButton: bool = False,
                                                   CancelButtonCaption: str = "Отмена") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value in data.items():
        builder.button(text=value, callback_data=AdminCallback(action=action, id_game_type=key))

    if AllButton:
        builder.button(text="Все", callback_data=AdminCallback(action=action, id_game_type=-1))
    if CancelButton:
        builder.button(text=CancelButtonCaption, callback_data=AdminCallback(action=action, id_game_type=0))

    builder.adjust(size)
    return builder.as_markup()


async def AskSelect(message: Message, message_text: str, state: FSMContext,
                    next_state: State | None, cb_data_dict: dict[str, AdminCallback], edit: bool = False) -> None:
    kbm = InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=cb_data_dict)
    if edit:
        await message.edit_text(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    if next_state is not None:
        await state.set_state(next_state)


async def AskSelectKBM(message: Message, message_text: str, state: FSMContext,
                       next_state: State | None, kbm: InlineKeyboardMarkup, edit: bool = False) -> None:
    if edit and message.from_user.id == bot.bot.MafiaBot.id:
        await message.edit_text(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    if next_state is not None:
        await state.set_state(next_state)


async def Ask(message: Message, message_text: str, state: FSMContext,
              next_state: State, edit: bool = False, action_code: str = "CANCEL") -> None:
    data = {"Отмена": AdminCallback(action=action_code)}
    kbm = InlineKeyboard_Admin_ByDict_CallbackData(cb_data_dict=data)
    if edit and message.from_user.id == bot.bot.MafiaBot.id:
        await message.edit_text(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    await state.set_state(next_state)
