from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class CMenuCallBack(CallbackData, prefix="menu"):
    level: int
    code: str
    category: int | None = None
    page: int = 1
    key: int | None = None


async def TL_Menu(level: int, Buttons: dict[str, str], BackButton: bool,
                  BackButtonCaption: str,
                  Sizes: tuple[int] = (2,)) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for Caption, code in Buttons.items():
        keyboard.add(InlineKeyboardButton(text=Caption,
                                          callback_data=CMenuCallBack(level=level + 1, code=code).pack()))
    if BackButton:
        keyboard.add(InlineKeyboardButton(text=BackButtonCaption,
                                          callback_data=CMenuCallBack(level=level - 1, code="BACK").pack()))

    return keyboard.adjust(*Sizes).as_markup()
