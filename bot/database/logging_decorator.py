"""Декоратор для логирования операций с базой данных"""
import functools
import inspect
import time
from typing import Callable, Any
from loguru import logger


def log_db_operation(operation_name: str = None):
    """
    Декоратор для логирования операций с базой данных

    Args:
        operation_name: Название операции (если не указано, используется имя функции)

    Логирует:
    - Начало операции
    - Успешное завершение с временем выполнения
    - Ошибки при выполнении
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            op_name = operation_name or func.__name__.upper().replace('_', ' ')

            # Создаем логгер с контекстом БД
            db_logger = logger.bind(operation=op_name)

            # Извлекаем ключевые параметры для логирования
            params_info = _extract_params_info(func.__name__, args, kwargs)

            start_time = time.time()

            db_logger.debug(
                f"🔵 БД операция начата: {op_name} | {params_info}"
            )

            try:
                result = await func(*args, **kwargs)

                elapsed_time = (time.time() - start_time) * 1000  # в миллисекундах

                # Информация о результате
                result_info = _extract_result_info(func.__name__, result)

                db_logger.info(
                    f"✅ БД операция успешна: {op_name} | "
                    f"{params_info} | "
                    f"{result_info} | "
                    f"Время: {elapsed_time:.2f}ms"
                )

                return result

            except Exception as e:
                elapsed_time = (time.time() - start_time) * 1000

                db_logger.error(
                    f"❌ БД операция провалилась: {op_name} | "
                    f"{params_info} | "
                    f"Время: {elapsed_time:.2f}ms | "
                    f"Ошибка: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            op_name = operation_name or func.__name__.upper().replace('_', ' ')
            db_logger = logger.bind(operation=op_name)
            params_info = _extract_params_info(func.__name__, args, kwargs)

            start_time = time.time()

            db_logger.debug(f"🔵 БД операция начата: {op_name} | {params_info}")

            try:
                result = func(*args, **kwargs)
                elapsed_time = (time.time() - start_time) * 1000
                result_info = _extract_result_info(func.__name__, result)

                db_logger.info(
                    f"✅ БД операция успешна: {op_name} | "
                    f"{params_info} | "
                    f"{result_info} | "
                    f"Время: {elapsed_time:.2f}ms"
                )

                return result

            except Exception as e:
                elapsed_time = (time.time() - start_time) * 1000

                db_logger.error(
                    f"❌ БД операция провалилась: {op_name} | "
                    f"{params_info} | "
                    f"Время: {elapsed_time:.2f}ms | "
                    f"Ошибка: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                raise

        # Проверяем, является ли функция асинхронной
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _extract_params_info(func_name: str, args: tuple, kwargs: dict) -> str:
    """Извлекает ключевую информацию из параметров функции"""
    params = []

    # Для функций с пользователями
    if 'telegram_id' in kwargs:
        params.append(f"TelegramID:{kwargs['telegram_id']}")
    if 'user_id' in kwargs:
        params.append(f"UserID:{kwargs['user_id']}")

    # Для функций с замерами
    if 'measurement_id' in kwargs:
        params.append(f"MeasurementID:{kwargs['measurement_id']}")
    if 'lead_id' in kwargs:
        params.append(f"LeadID:{kwargs['lead_id']}")

    # Для функций с ролями
    if 'role' in kwargs:
        params.append(f"Role:{kwargs['role']}")

    # Для функций со статусами
    if 'status' in kwargs:
        params.append(f"Status:{kwargs['status']}")

    # Для функций с токенами
    if 'token' in kwargs:
        token = kwargs['token']
        params.append(f"Token:{token[:8]}..." if len(token) > 8 else f"Token:{token}")

    # Если ничего не нашли, просто считаем количество аргументов
    if not params:
        if args:
            # Пропускаем первый аргумент (обычно session)
            params.append(f"Args:{len(args) - 1}")
        if kwargs:
            params.append(f"Kwargs:{len(kwargs)}")

    return " | ".join(params) if params else "No params"


def _extract_result_info(func_name: str, result: Any) -> str:
    """Извлекает информацию о результате операции"""
    if result is None:
        return "Result: None"

    # Для списков
    if isinstance(result, list):
        return f"Result: List[{len(result)} items]"

    # Для моделей БД
    if hasattr(result, '__tablename__'):
        table_name = result.__tablename__
        if hasattr(result, 'id'):
            return f"Result: {table_name} ID:{result.id}"
        return f"Result: {table_name}"

    # Для булевых значений
    if isinstance(result, bool):
        return f"Result: {result}"

    # Для чисел
    if isinstance(result, (int, float)):
        return f"Result: {result}"

    return "Result: Object"
