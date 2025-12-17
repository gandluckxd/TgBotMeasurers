"""Декоратор для логирования отправки уведомлений"""
import functools
import time
from typing import Callable, Any
from loguru import logger
from aiogram.exceptions import TelegramAPIError


def log_notification(notification_type: str):
    """
    Декоратор для логирования отправки уведомлений

    Args:
        notification_type: Тип уведомления (например, "NEW_MEASUREMENT", "ASSIGNMENT" и т.д.)

    Логирует:
    - Попытку отправки уведомления
    - Получателей
    - Успешную отправку
    - Ошибки Telegram API
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            # Извлекаем информацию о получателе из аргументов
            recipient_info = _extract_recipient_info(args, kwargs)

            # Создаем логгер с контекстом
            notif_logger = logger.bind(
                user_id=f"NOTIFICATION",
                username="SYSTEM",
                action="NOTIFICATION"
            )

            notif_logger.info(
                f"📤 Отправка уведомления: {notification_type} → {recipient_info}"
            )

            try:
                result = await func(*args, **kwargs)

                elapsed_time = (time.time() - start_time) * 1000

                # Проверяем, было ли уведомление успешно отправлено
                if result is False:
                    notif_logger.warning(
                        f"⚠️ Уведомление НЕ отправлено: {notification_type} → {recipient_info} | "
                        f"Время: {elapsed_time:.2f}ms | "
                        f"Причина: Пользователь не найден или бот не запущен"
                    )
                else:
                    notif_logger.info(
                        f"✅ Уведомление отправлено: {notification_type} → {recipient_info} | "
                        f"Время: {elapsed_time:.2f}ms"
                    )

                return result

            except TelegramAPIError as e:
                elapsed_time = (time.time() - start_time) * 1000

                notif_logger.error(
                    f"❌ Ошибка Telegram API при отправке уведомления: {notification_type} → {recipient_info} | "
                    f"Время: {elapsed_time:.2f}ms | "
                    f"Ошибка: {type(e).__name__}: {str(e)}"
                )
                # Не пробрасываем исключение, чтобы не ломать основной процесс
                return False

            except Exception as e:
                elapsed_time = (time.time() - start_time) * 1000

                notif_logger.error(
                    f"❌ Критическая ошибка при отправке уведомления: {notification_type} → {recipient_info} | "
                    f"Время: {elapsed_time:.2f}ms | "
                    f"Ошибка: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                raise

        return wrapper

    return decorator


def _extract_recipient_info(args: tuple, kwargs: dict) -> str:
    """Извлекает информацию о получателе из аргументов функции"""
    recipients = []

    # Ищем telegram_id или user_id в kwargs
    if 'telegram_id' in kwargs:
        recipients.append(f"TelegramID:{kwargs['telegram_id']}")
    if 'user_id' in kwargs:
        recipients.append(f"UserID:{kwargs['user_id']}")

    # Ищем объекты User в kwargs
    if 'user' in kwargs:
        user = kwargs['user']
        if hasattr(user, 'telegram_id'):
            recipients.append(f"User:{user.telegram_id}")

    if 'measurer' in kwargs:
        measurer = kwargs['measurer']
        if hasattr(measurer, 'telegram_id'):
            recipients.append(f"Measurer:{measurer.telegram_id}")

    if 'manager' in kwargs:
        manager = kwargs['manager']
        if hasattr(manager, 'telegram_id'):
            recipients.append(f"Manager:{manager.telegram_id}")

    # Ищем списки пользователей
    if 'measurers' in kwargs:
        measurers = kwargs['measurers']
        if isinstance(measurers, list):
            recipients.append(f"Measurers:{len(measurers)} users")

    if 'observers' in kwargs:
        observers = kwargs['observers']
        if isinstance(observers, list):
            recipients.append(f"Observers:{len(observers)} users")

    # Ищем telegram_id в позиционных аргументах (после bot)
    for i, arg in enumerate(args):
        if i == 0:  # Пропускаем первый аргумент (обычно bot)
            continue
        if isinstance(arg, int) and arg > 0:  # Похоже на telegram_id
            recipients.append(f"TelegramID:{arg}")
            break

    return ", ".join(recipients) if recipients else "Unknown recipient"
