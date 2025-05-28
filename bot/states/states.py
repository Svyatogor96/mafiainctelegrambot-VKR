from aiogram.fsm.state import State, StatesGroup


class SMRegistration(StatesGroup):
    # Шаги состояний
    wait_apply_registration = State()
    choosing_city = State()
    choosing_person_sex = State()
    choosing_person_family = State()
    choosing_person_name = State()
    choosing_person_father_name = State()
    choosing_person_phone = State()
    choosing_person_email = State()
    choosing_person_birthdate = State()
    choosing_nickname = State()


class AdminState(StatesGroup):
    start = State()
    new_game = State()
    close_registration = State()
    add_place = State()
    choose_game_type = State()
    choose_game_place = State()
    choose_game_start = State()
    choose_game_price = State()
    choose_game_actions = State()
    edit_game = State()
    save_game = State()

    setting_place_title = State()
    setting_place_address = State()
    setting_place_seats = State()
    setting_place_game_types = State()
    edit_place = State()
    save_place = State()
    make_post = State()
    load_poster = State()
    message_text = State()
    message_pic = State()
    message_confirm = State()


class UserState(StatesGroup):
    start = State(state="start")
    sign_up_to_game = State()
    get_invoice = State()
    unregistered_start = State(state="unregistered_user_starts")
    edit_profile = State(state="user_profile_edit")
    edit_family = State(state="user_profile_edit_family")
    edit_name = State(state="user_profile_edit_name")
    edit_father_name = State(state="user_profile_edit_father_name")
    edit_sex = State(state="user_profile_edit_sex")
    edit_birthdate = State(state="user_profile_edit_birthdate")
    edit_phone = State(state="user_profile_edit_phone")
    edit_phone_add = State(state="user_profile_edit_phone_add")
    edit_phone_del = State(state="user_profile_edit_phone_del")
    edit_phone_edt = State(state="user_profile_edit_phone_edt")
    edit_email = State(state="user_profile_edit_email")
    edit_email_add = State(state="user_profile_edit_email_add")
    edit_email_del = State(state="user_profile_edit_email_del")
    edit_email_edt = State(state="user_profile_edit_email_edt")
    edit_nickname = State(state="user_profile_edit_nickname")
    edit_nickname_add = State(state="user_profile_edit_nickname_add")
    edit_nickname_del = State(state="user_profile_edit_nickname_del")
    edit_nickname_edt = State(state="user_profile_edit_nickname_edt")
    edit_nickname_select = State(state="user_profile_edit_nickname_select")


class SUState(StatesGroup):
    start = State(state="su_start")
    moderators = State(state="moderators")
    moderator_add_input_phone = State(state="moderator_add_input_phone")
    moderator_add_city = State("moderator_add_city")
    moderator_commit = State("moderator_commit")
    moderator_select = State("moderator_select")
    moderator_select_city = State("moderator_select_city")
    moderator_delete = State("moderator_delete")


