"""Middleware для проверки прав доступа на основе ролей"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from loguru import logger

from database.database import get_session, get_user_by_telegram_id
from database.models import UserRole
from config import settings


async def get_user_role(telegram_id: int) -> UserRole | None:
    """
    Получить роль пользователя из БД

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        Роль пользователя или None
    """
    # Проверяем, является ли пользователь администратором из конфига
    if telegram_id in settings.admin_ids_list:
        return UserRole.ADMIN

    # Получаем роль из БД
    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if user:
            return user.role

    return None


def has_access(required_roles: list[UserRole], user_role: UserRole | None) -> bool:
    """
    Проверка, имеет ли пользователь необходимые права

    Args:
        required_roles: Список разрешенных ролей
        user_role: Роль пользователя

    Returns:
        True если доступ разрешен
    """
    if not user_role:
        return False

    return user_role in required_roles


class RoleCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки ролей пользователей
    Добавляет информацию о роли в данные обработчика
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события с добавлением информации о роли

        Args:
            handler: Обработчик события
            event: Событие (Message или CallbackQuery)
            data: Данные для передачи обработчику
        """
        # Получаем telegram_id пользователя
        if isinstance(event, Message):
            telegram_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            telegram_id = event.from_user.id
        else:
            telegram_id = None

        if telegram_id:
            # Получаем роль пользователя
            user_role = await get_user_role(telegram_id)

            # Добавляем роль в данные
            data["user_role"] = user_role

            # Проверяем, является ли пользователь админом или супервизором
            data["is_admin"] = user_role == UserRole.ADMIN
            data["is_supervisor"] = user_role == UserRole.SUPERVISOR
            data["is_manager"] = user_role == UserRole.MANAGER
            data["is_measurer"] = user_role == UserRole.MEASURER
            data["is_observer"] = user_role == UserRole.OBSERVER

            # Руководитель (Supervisor) имеет ПОЛНЫЕ права администратора (один в один!)
            # Единственное отличие - администратор зафиксирован в конфиге, а руководители управляются в БД
            data["has_admin_access"] = user_role in [UserRole.ADMIN, UserRole.SUPERVISOR]

            logger.debug(f"User {telegram_id} has role: {user_role}")
        else:
            data["user_role"] = None
            data["is_admin"] = False
            data["is_supervisor"] = False
            data["is_manager"] = False
            data["is_measurer"] = False
            data["is_observer"] = False
            data["has_admin_access"] = False

        # Вызываем обработчик
        return await handler(event, data)
