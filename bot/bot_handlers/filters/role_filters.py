"""Фильтры для проверки ролей пользователей"""
from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from database.models import UserRole
from bot_handlers.middlewares.role_check import get_user_role


class RoleFilter(BaseFilter):
    """
    Фильтр для проверки роли пользователя

    Использование:
        @router.message(RoleFilter(UserRole.ADMIN))
        async def handler(message: Message):
            ...
    """

    def __init__(self, *roles: UserRole):
        """
        Args:
            roles: Допустимые роли для обработчика
        """
        self.roles = roles

    async def __call__(
        self,
        event: Union[Message, CallbackQuery]
    ) -> bool:
        """
        Проверка роли пользователя

        Args:
            event: Событие (Message или CallbackQuery)

        Returns:
            True если роль пользователя подходит
        """
        # Получаем telegram_id из события
        telegram_id = event.from_user.id

        # Получаем роль пользователя
        user_role = await get_user_role(telegram_id)

        if user_role is None:
            return False

        return user_role in self.roles


class IsAdmin(RoleFilter):
    """Фильтр для проверки роли Администратора"""

    def __init__(self):
        super().__init__(UserRole.ADMIN)


class IsSupervisor(RoleFilter):
    """Фильтр для проверки роли Руководителя"""

    def __init__(self):
        super().__init__(UserRole.SUPERVISOR)


class IsManager(RoleFilter):
    """Фильтр для проверки роли Менеджера"""

    def __init__(self):
        super().__init__(UserRole.MANAGER)


class IsMeasurer(RoleFilter):
    """Фильтр для проверки роли Замерщика"""

    def __init__(self):
        super().__init__(UserRole.MEASURER)


class IsObserver(RoleFilter):
    """Фильтр для проверки роли Наблюдателя"""

    def __init__(self):
        super().__init__(UserRole.OBSERVER)


class HasAdminAccess(RoleFilter):
    """Фильтр для проверки прав администратора (Админ или Руководитель)"""

    def __init__(self):
        super().__init__(UserRole.ADMIN, UserRole.SUPERVISOR)
