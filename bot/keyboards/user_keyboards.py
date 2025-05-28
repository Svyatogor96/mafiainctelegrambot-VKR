from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.callbacks import UserCallback


def UserMainMenuKeyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Город", callback_data=UserCallback(action="U_SUGGEST_CITY"))
    builder.button(text="Афиша", callback_data=UserCallback(action="U_BILLBOARDS"))
    builder.button(text="Правила", url="https://vk.com/@mafia_inc_official-pravila-igry")
    builder.button(text="Оплатить", callback_data=UserCallback(action="U_PAY"))
    builder.button(text="Профиль", callback_data=UserCallback(action="U_PROFILE"))

    builder.adjust(2)
    return builder.as_markup()


def UserProfileKeyboard(id_person: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Редактировать", callback_data=UserCallback(action="EDIT_PROFILE_ENTRY", id_person=id_person))
    builder.button(text="Удалить", callback_data=UserCallback(action="U_DEL_PROFILE", id_person=id_person))
    builder.button(text="Рейтинг", callback_data=UserCallback(action="U_RATING", id_person=id_person))
    if is_admin:
        builder.button(text="Админ", callback_data=UserCallback(action="ADMIN_LOG_IN", id_person=id_person))
    builder.button(text="Отмена", callback_data=UserCallback(action="U_CANCEL"))
    builder.adjust(2)
    return builder.as_markup()


def UserEditProfileKeyboard(id_person: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Фамилия", callback_data=UserCallback(action="U_EDIT_PROFILE_FAMILY", id_person=id_person))
    builder.button(text="Имя", callback_data=UserCallback(action="U_EDIT_PROFILE_NAME", id_person=id_person))
    builder.button(text="Отчество", callback_data=UserCallback(action="U_EDIT_PROFILE_FATHER_NAME",
                                                               id_person=id_person))
    builder.button(text="Пол", callback_data=UserCallback(action="U_EDIT_PROFILE_SEX", id_person=id_person))
    builder.button(text="Дата рождения", callback_data=UserCallback(action="U_EDIT_PROFILE_BIRTHDATE",
                                                                    id_person=id_person))
    builder.button(text="Телефон", callback_data=UserCallback(action="U_EDIT_PROFILE_PHONE", id_person=id_person))
    builder.button(text="EMail", callback_data=UserCallback(action="U_EDIT_PROFILE_EMAIL", id_person=id_person))
    builder.button(text="Псевдонимы", callback_data=UserCallback(action="U_EDIT_PROFILE_NICKNAME", id_person=id_person))
    builder.button(text="Выход", callback_data=UserCallback(action="U_EDIT_PROFILE_EXIT", id_person=id_person))
    builder.adjust(3, 2, 2, 2)
    return builder.as_markup()


def UserCBKeyboard(callbacks: dict[str, UserCallback], size: int = 2) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, callback_data in callbacks.items():
        builder.button(text=key, callback_data=callback_data)
    builder.adjust(size)
    return builder.as_markup()
