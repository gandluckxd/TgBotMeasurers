"""Модуль клавиатур для бота"""
from bot_handlers.keyboards.inline import (
    get_measurers_keyboard,
    get_measurement_actions_keyboard,
    get_measurement_status_keyboard,
    get_main_menu_keyboard,
    get_confirmation_keyboard,
    get_back_button,
    get_users_list_keyboard,
    get_user_detail_keyboard,
    get_role_selection_keyboard,
    get_invite_links_keyboard,
    get_invite_link_detail_keyboard,
    get_invite_role_selection_keyboard,
    get_invite_options_keyboard,
    get_delete_invite_confirmation_keyboard
)
from bot_handlers.keyboards.reply import (
    get_admin_commands_keyboard,
    get_measurer_commands_keyboard,
    get_manager_commands_keyboard,
    get_cancel_keyboard,
    remove_keyboard
)

__all__ = [
    # Inline keyboards
    "get_measurers_keyboard",
    "get_measurement_actions_keyboard",
    "get_measurement_status_keyboard",
    "get_main_menu_keyboard",
    "get_confirmation_keyboard",
    "get_back_button",
    "get_users_list_keyboard",
    "get_user_detail_keyboard",
    "get_role_selection_keyboard",
    "get_invite_links_keyboard",
    "get_invite_link_detail_keyboard",
    "get_invite_role_selection_keyboard",
    "get_invite_options_keyboard",
    "get_delete_invite_confirmation_keyboard",
    # Reply keyboards
    "get_admin_commands_keyboard",
    "get_measurer_commands_keyboard",
    "get_manager_commands_keyboard",
    "get_cancel_keyboard",
    "remove_keyboard",
]
