"""Middleware для автоматического логирования всех действий пользователей"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования всех входящих сообщений и callback запросов

    Логирует:
    - Все команды от пользователей
    - Все callback запросы
    - Все обычные сообщения
    - Ошибки при обработке
    - Время выполнения обработчика
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обрабатывает событие и логирует информацию

        Args:
            handler: Обработчик события
            event: Событие (Message или CallbackQuery)
            data: Дополнительные данные
        """
        import time
        start_time = time.time()

        # Определяем тип события и извлекаем информацию о пользователе
        if isinstance(event, Message):
            await self._log_message(event, data)
        elif isinstance(event, CallbackQuery):
            await self._log_callback(event, data)

        # Выполняем обработчик
        try:
            result = await handler(event, data)

            # Логируем успешное выполнение
            elapsed_time = (time.time() - start_time) * 1000  # в миллисекундах
            self._log_success(event, elapsed_time)

            return result

        except Exception as e:
            # Логируем ошибку
            elapsed_time = (time.time() - start_time) * 1000
            self._log_error(event, e, elapsed_time)
            raise

    async def _log_message(self, message: Message, data: Dict[str, Any]):
        """Логирует входящее сообщение"""
        user = message.from_user
        user_id = user.id
        username = user.username or "NO_USERNAME"
        full_name = user.full_name
        user_role_obj = data.get('user_role')
        user_role = user_role_obj.value if user_role_obj else 'UNKNOWN'

        # Определяем тип сообщения
        if message.text and message.text.startswith('/'):
            # Команда
            command = message.text.split()[0]
            msg_type = "COMMAND"
            content = message.text

            user_logger = logger.bind(
                user_id=f"USER_{user_id}",
                username=username,
                action="COMMAND"
            )

            user_logger.info(
                f"📝 {full_name} (@{username}, ID:{user_id}) | "
                f"Роль: {user_role} | "
                f"Команда: '{command}'"
            )
        else:
            # Обычное сообщение
            if message.text:
                msg_type = "TEXT"
                content = message.text[:100] + ("..." if len(message.text) > 100 else "")
            elif message.photo:
                msg_type = "PHOTO"
                content = f"Photo {len(message.photo)} variants"
            elif message.document:
                msg_type = "DOCUMENT"
                content = f"Doc: {message.document.file_name}"
            elif message.voice:
                msg_type = "VOICE"
                content = "Voice message"
            elif message.video:
                msg_type = "VIDEO"
                content = "Video"
            elif message.sticker:
                msg_type = "STICKER"
                content = f"Sticker: {message.sticker.emoji}"
            else:
                msg_type = "OTHER"
                content = "Unknown type"

            user_logger = logger.bind(
                user_id=f"USER_{user_id}",
                username=username,
                action="MESSAGE"
            )

            user_logger.info(
                f"💬 {full_name} (@{username}, ID:{user_id}) | "
                f"Роль: {user_role} | "
                f"Тип: {msg_type} | "
                f"Содержание: '{content}'"
            )

    async def _log_callback(self, callback: CallbackQuery, data: Dict[str, Any]):
        """Логирует входящий callback запрос"""
        user = callback.from_user
        user_id = user.id
        username = user.username or "NO_USERNAME"
        full_name = user.full_name
        user_role_obj = data.get('user_role')
        user_role = user_role_obj.value if user_role_obj else 'UNKNOWN'
        callback_data = callback.data or "NO_DATA"

        user_logger = logger.bind(
            user_id=f"USER_{user_id}",
            username=username,
            action="CALLBACK"
        )

        user_logger.info(
            f"🔘 {full_name} (@{username}, ID:{user_id}) | "
            f"Роль: {user_role} | "
            f"Callback: '{callback_data}'"
        )

    def _log_success(self, event: TelegramObject, elapsed_time: float):
        """Логирует успешное выполнение обработчика"""
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            logger.debug(
                f"✅ Обработчик выполнен успешно | "
                f"Пользователь: {user_id} | "
                f"Время: {elapsed_time:.2f}ms"
            )

    def _log_error(self, event: TelegramObject, error: Exception, elapsed_time: float):
        """Логирует ошибку при выполнении обработчика"""
        user_id = None
        username = "UNKNOWN"
        action_info = ""

        if isinstance(event, Message):
            user_id = event.from_user.id
            username = event.from_user.username or "NO_USERNAME"
            if event.text:
                action_info = f"Текст: '{event.text[:50]}'"
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username or "NO_USERNAME"
            action_info = f"Callback: '{event.data}'"

        user_logger = logger.bind(
            user_id=f"USER_{user_id}" if user_id else "UNKNOWN",
            username=username,
            action="ERROR"
        )

        user_logger.error(
            f"❌ ОШИБКА при обработке | "
            f"Пользователь: {user_id} | "
            f"{action_info} | "
            f"Время: {elapsed_time:.2f}ms | "
            f"Ошибка: {type(error).__name__}: {str(error)}",
            exc_info=True
        )
