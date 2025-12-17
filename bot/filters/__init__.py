"""Фильтры для бота"""
from bot.filters.role_filters import (
    RoleFilter,
    IsAdmin,
    IsSupervisor,
    IsManager,
    IsMeasurer,
    IsObserver,
    HasAdminAccess
)

__all__ = [
    "RoleFilter",
    "IsAdmin",
    "IsSupervisor",
    "IsManager",
    "IsMeasurer",
    "IsObserver",
    "HasAdminAccess"
]
