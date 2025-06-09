from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from bot.callbacks import CSUCallBack
from backendapi.model import CModerator, CPerson


async def SU_KB_CB_by_dict(cb_data_dict: dict[str, CSUCallBack], size: int = 2) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, cb_data in cb_data_dict.items():
        builder.button(text=key, callback_data=cb_data)
    builder.adjust(size)
    return builder.as_markup()


async def AskSelect(message: Message, message_text: str, state: FSMContext,
                    next_state: State | None, cb_data_dict: dict[str, CSUCallBack], edit: bool = False) -> None:
    kbm = await SU_KB_CB_by_dict(cb_data_dict=cb_data_dict)
    if edit:
        await message.edit_text(text=message_text, reply_markup=kbm)
    else:
        await message.answer(text=message_text, reply_markup=kbm)
    if next_state is not None:
        await state.set_state(next_state)


def SU_Main_Keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ведущие игр.", callback_data=CSUCallBack(action="SU_MODERATORS"))
    builder.button(text="Сообщения бота.", callback_data=CSUCallBack(action="SU_MESSAGES"))
    builder.button(text="Настройки бота.", callback_data=CSUCallBack(action="SU_OPTIONS"))
    builder.button(text="Выход", callback_data=CSUCallBack(action="SU_EXIT"))
    builder.adjust(2)
    return builder.as_markup()


async def SU_Moderators_Menu_Keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить", callback_data=CSUCallBack(action="MODERATOR_ADD"))
    builder.button(text="Заменить", callback_data=CSUCallBack(action="MODERATOR_REPLACE"))
    builder.button(text="Редактировать", callback_data=CSUCallBack(action="MODERATOR_EDIT"))
    builder.button(text="Назад", callback_data=CSUCallBack(action="MODERATOR_BACK"))
    builder.adjust(2)
    return builder.as_markup()


async def SU_Moderators_List_Keyboard(Persons: list[CPerson] | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if Persons is not None:
        for Person in Persons:
            builder.button(text=Person.FormatNameFamily, callback_data=CSUCallBack(action="MODERATOR_SELECT",
                                                                                   id_person=Person.id))
    builder.button(text="Назад", callback_data=CSUCallBack(action="MODERATOR_BACK"))
    builder.adjust(2)
    return builder.as_markup()



def SU_Back_Keyboard(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data=CSUCallBack(action=action))
    return builder.as_markup()
