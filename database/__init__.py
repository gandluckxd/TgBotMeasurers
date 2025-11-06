"""Модуль работы с базой данных"""
from database.models import (
    Base,
    User,
    Measurement,
    UserRole,
    MeasurementStatus
)
from database.database import (
    db,
    get_db,
    get_user_by_telegram_id,
    get_or_create_user,
    get_all_measurers,
    get_measurement_by_id,
    get_measurement_by_amocrm_id,
    get_measurements_by_status,
    get_measurements_by_measurer,
    get_measurements_by_manager,
    create_measurement
)

__all__ = [
    # Models
    "Base",
    "User",
    "Measurement",
    "UserRole",
    "MeasurementStatus",
    # Database
    "db",
    "get_db",
    # User functions
    "get_user_by_telegram_id",
    "get_or_create_user",
    "get_all_measurers",
    # Measurement functions
    "get_measurement_by_id",
    "get_measurement_by_amocrm_id",
    "get_measurements_by_status",
    "get_measurements_by_measurer",
    "get_measurements_by_manager",
    "create_measurement",
]
