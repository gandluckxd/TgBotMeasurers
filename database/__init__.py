"""Модуль работы с базой данных"""
from database.models import (
    Base,
    User,
    Measurement,
    InviteLink,
    UserRole,
    MeasurementStatus
)
from database.database import (
    db,
    get_db,
    get_session,
    get_user_by_telegram_id,
    get_or_create_user,
    create_user,
    get_all_measurers,
    get_all_users,
    get_user_by_id,
    update_user_role,
    toggle_user_active,
    create_user_by_telegram_id,
    get_measurement_by_id,
    get_measurement_by_amocrm_id,
    get_measurements_by_status,
    get_measurements_by_measurer,
    get_measurements_by_manager,
    create_measurement,
    create_invite_link,
    get_invite_link_by_token,
    get_all_invite_links,
    use_invite_link,
    toggle_invite_link_active,
    delete_invite_link
)

__all__ = [
    # Models
    "Base",
    "User",
    "Measurement",
    "InviteLink",
    "UserRole",
    "MeasurementStatus",
    # Database
    "db",
    "get_db",
    "get_session",
    # User functions
    "get_user_by_telegram_id",
    "get_or_create_user",
    "create_user",
    "get_all_measurers",
    "get_all_users",
    "get_user_by_id",
    "update_user_role",
    "toggle_user_active",
    "create_user_by_telegram_id",
    # Measurement functions
    "get_measurement_by_id",
    "get_measurement_by_amocrm_id",
    "get_measurements_by_status",
    "get_measurements_by_measurer",
    "get_measurements_by_manager",
    "create_measurement",
    # Invite link functions
    "create_invite_link",
    "get_invite_link_by_token",
    "get_all_invite_links",
    "use_invite_link",
    "toggle_invite_link_active",
    "delete_invite_link",
]
