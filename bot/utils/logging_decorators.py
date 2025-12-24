"""Декораторы для автоматического логирования действий пользователей"""
import functools
from typing import Callable, Any
from loguru import logger
from aiogram.types import Message, CallbackQuery


def log_command(func: Callable) -> Callable:
    """
    Декоратор для логирования команд бота

    Логирует:
    - Кто отправил команду (user_id, username, full_name)
    - Какую команду (текст команды)
    - Роль пользователя
    - Результат выполнения (успех/ошибка)
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Находим объект Message в аргументах
        message = None
        for arg in args:
            if isinstance(arg, Message):
                message = arg
                break

        if not message:
            # Пытаемся найти в kwargs
            message = kwargs.get('message')

        if message:
            user = message.from_user
            user_id = user.id
            username = user.username or "NO_USERNAME"
            full_name = user.full_name
            command_text = message.text or "NO_TEXT"

            # Получаем роль из kwargs (добавляется middleware)
            user_role_obj = kwargs.get('user_role')
            user_role = user_role_obj.value if user_role_obj else 'UNKNOWN'

            # Создаем логгер с контекстом пользователя
            user_logger = logger.bind(
                user_id=f"USER_{user_id}",
                username=username,
                action="COMMAND"
            )

            user_logger.info(
                f"📝 Команда получена: '{command_text}' | "
                f"От: {full_name} (@{username}, ID: {user_id}) | "
                f"Роль: {user_role}"
            )

            try:
                # Выполняем команду
                result = await func(*args, **kwargs)

                user_logger.info(
                    f"✅ Команда выполнена успешно: '{command_text}' | "
                    f"Пользователь: {user_id}"
                )

                return result

            except Exception as e:
                user_logger.error(
                    f"❌ Ошибка при выполнении команды: '{command_text}' | "
                    f"Пользователь: {user_id} | "
                    f"Ошибка: {str(e)}",
                    exc_info=True
                )
                raise
        else:
            # Если не нашли Message, просто выполняем функцию
            return await func(*args, **kwargs)

    return wrapper


def log_callback(func: Callable) -> Callable:
    """
    Декоратор для логирования callback запросов

    Логирует:
    - Кто нажал кнопку (user_id, username, full_name)
    - Какие данные callback (callback_data)
    - Роль пользователя
    - Результат выполнения
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Находим объект CallbackQuery в аргументах
        callback = None
        for arg in args:
            if isinstance(arg, CallbackQuery):
                callback = arg
                break

        if not callback:
            callback = kwargs.get('callback_query') or kwargs.get('callback')

        if callback:
            user = callback.from_user
            user_id = user.id
            username = user.username or "NO_USERNAME"
            full_name = user.full_name
            callback_data = callback.data or "NO_DATA"

            # Получаем роль из kwargs
            user_role_obj = kwargs.get('user_role')
            user_role = user_role_obj.value if user_role_obj else 'UNKNOWN'

            # Создаем логгер с контекстом пользователя
            user_logger = logger.bind(
                user_id=f"USER_{user_id}",
                username=username,
                action="CALLBACK"
            )

            user_logger.info(
                f"🔘 Callback получен: '{callback_data}' | "
                f"От: {full_name} (@{username}, ID: {user_id}) | "
                f"Роль: {user_role}"
            )

            try:
                # Выполняем обработчик
                result = await func(*args, **kwargs)

                user_logger.info(
                    f"✅ Callback обработан: '{callback_data}' | "
                    f"Пользователь: {user_id}"
                )

                return result

            except Exception as e:
                user_logger.error(
                    f"❌ Ошибка при обработке callback: '{callback_data}' | "
                    f"Пользователь: {user_id} | "
                    f"Ошибка: {str(e)}",
                    exc_info=True
                )
                raise
        else:
            return await func(*args, **kwargs)

    return wrapper


def log_message(func: Callable) -> Callable:
    """
    Декоратор для логирования обычных сообщений (не команд)

    Логирует:
    - Кто отправил сообщение
    - Тип сообщения (текст, фото и т.д.)
    - Содержимое (первые 100 символов текста)
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Находим объект Message
        message = None
        for arg in args:
            if isinstance(arg, Message):
                message = arg
                break

        if not message:
            message = kwargs.get('message')

        if message:
            user = message.from_user
            user_id = user.id
            username = user.username or "NO_USERNAME"
            full_name = user.full_name

            # Определяем тип сообщения
            if message.text:
                msg_type = "TEXT"
                content = message.text[:100]
            elif message.photo:
                msg_type = "PHOTO"
                content = f"Photo ID: {message.photo[-1].file_id}"
            elif message.document:
                msg_type = "DOCUMENT"
                content = f"Document: {message.document.file_name}"
            elif message.voice:
                msg_type = "VOICE"
                content = "Voice message"
            else:
                msg_type = "OTHER"
                content = "Unknown content type"

            # Получаем роль
            user_role_obj = kwargs.get('user_role')
            user_role = user_role_obj.value if user_role_obj else 'UNKNOWN'

            user_logger = logger.bind(
                user_id=f"USER_{user_id}",
                username=username,
                action="MESSAGE"
            )

            user_logger.info(
                f"💬 Сообщение получено [{msg_type}]: '{content}' | "
                f"От: {full_name} (@{username}, ID: {user_id}) | "
                f"Роль: {user_role}"
            )

            try:
                result = await func(*args, **kwargs)

                user_logger.debug(
                    f"✅ Сообщение обработано | Пользователь: {user_id}"
                )

                return result

            except Exception as e:
                user_logger.error(
                    f"❌ Ошибка при обработке сообщения | "
                    f"Пользователь: {user_id} | "
                    f"Ошибка: {str(e)}",
                    exc_info=True
                )
                raise
        else:
            return await func(*args, **kwargs)

    return wrapper


def log_fsm_state(func: Callable) -> Callable:
    """
    Декоратор для логирования переходов между состояниями FSM

    Логирует:
    - Пользователь
    - Переход состояния
    - Данные состояния
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Получаем state из kwargs
        state = kwargs.get('state')

        # Получаем message или callback
        message = kwargs.get('message')
        callback = kwargs.get('callback_query') or kwargs.get('callback')

        user_obj = None
        if message:
            user_obj = message.from_user
        elif callback:
            user_obj = callback.from_user

        if user_obj and state:
            user_id = user_obj.id
            username = user_obj.username or "NO_USERNAME"

            # Получаем текущее состояние
            current_state = await state.get_state()

            user_logger = logger.bind(
                user_id=f"USER_{user_id}",
                username=username,
                action="FSM_STATE"
            )

            user_logger.info(
                f"🔄 FSM состояние: {current_state} | "
                f"Пользователь: {user_id}"
            )

            try:
                result = await func(*args, **kwargs)

                # Логируем новое состояние после выполнения
                new_state = await state.get_state()
                if new_state != current_state:
                    user_logger.info(
                        f"🔄 FSM переход: {current_state} → {new_state} | "
                        f"Пользователь: {user_id}"
                    )

                return result

            except Exception as e:
                user_logger.error(
                    f"❌ Ошибка в FSM состоянии: {current_state} | "
                    f"Пользователь: {user_id} | "
                    f"Ошибка: {str(e)}",
                    exc_info=True
                )
                raise
        else:
            return await func(*args, **kwargs)

    return wrapper
