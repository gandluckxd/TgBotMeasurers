"""Централизованная конфигурация логирования для всего бота"""
import sys
from pathlib import Path
from loguru import logger
from config import settings


def setup_logging():
    """
    Настройка системы логирования с несколькими обработчиками:
    - Консольный вывод (все логи)
    - Общий файл логов (все логи)
    - Файл действий пользователей (info уровень)
    - Файл ошибок (warning+ уровень)
    """
    # Создаем директорию для логов
    Path("logs").mkdir(exist_ok=True)

    # Удаляем стандартный обработчик loguru
    logger.remove()

    # === КОНСОЛЬНЫЙ ВЫВОД (цветной, детальный) ===
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # === ОБЩИЙ ФАЙЛ ЛОГОВ (все логи) ===
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        level=settings.log_level,
        rotation="00:00",  # Новый файл каждый день в полночь
        retention="30 days",  # Хранить 30 дней
        compression="zip",  # Сжимать старые логи
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # === ФАЙЛ ДЕЙСТВИЙ ПОЛЬЗОВАТЕЛЕЙ (только INFO и выше) ===
    logger.add(
        "logs/user_actions_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{extra[user_id]} | {extra[username]} | {extra[action]} | "
            "{message}"
        ),
        level="INFO",
        rotation="00:00",
        retention="60 days",  # Действия пользователей храним дольше
        compression="zip",
        encoding="utf-8",
        filter=lambda record: "user_id" in record["extra"],  # Только логи с пользователем
    )

    # === ФАЙЛ ОШИБОК (только WARNING и выше) ===
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}\n"
            "{exception}"
        ),
        level="WARNING",
        rotation="00:00",
        retention="90 days",  # Ошибки храним еще дольше
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # === ФАЙЛ ДЕЙСТВИЙ С БАЗОЙ ДАННЫХ ===
    logger.add(
        "logs/database_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{extra[operation]} | "
            "{message}"
        ),
        level="DEBUG",
        rotation="00:00",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        filter=lambda record: "operation" in record["extra"],  # Только логи с операциями БД
    )

    logger.info("=" * 80)
    logger.info("Система логирования успешно настроена")
    logger.info(f"Уровень логирования: {settings.log_level}")
    logger.info("Файлы логов:")
    logger.info("  - logs/bot_YYYY-MM-DD.log (все логи)")
    logger.info("  - logs/user_actions_YYYY-MM-DD.log (действия пользователей)")
    logger.info("  - logs/errors_YYYY-MM-DD.log (ошибки и предупреждения)")
    logger.info("  - logs/database_YYYY-MM-DD.log (операции с БД)")
    logger.info("=" * 80)


def get_user_logger(user_id: int, username: str | None = None, action: str = ""):
    """
    Создает логгер с контекстом пользователя

    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя (если есть)
        action: Тип действия (command, callback, message и т.д.)

    Returns:
        logger с привязанным контекстом пользователя
    """
    return logger.bind(
        user_id=f"USER_{user_id}",
        username=username or "NO_USERNAME",
        action=action
    )


def get_db_logger(operation: str):
    """
    Создает логгер для операций с базой данных

    Args:
        operation: Тип операции (SELECT, INSERT, UPDATE, DELETE и т.д.)

    Returns:
        logger с привязанным контекстом операции БД
    """
    return logger.bind(operation=operation)


def log_user_action(
    user_id: int,
    username: str | None,
    action: str,
    details: str,
    level: str = "INFO"
):
    """
    Удобная функция для логирования действий пользователя

    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя
        action: Тип действия
        details: Детали действия
        level: Уровень логирования (INFO, WARNING, ERROR)
    """
    user_logger = get_user_logger(user_id, username, action)

    if level == "INFO":
        user_logger.info(details)
    elif level == "WARNING":
        user_logger.warning(details)
    elif level == "ERROR":
        user_logger.error(details)
    else:
        user_logger.debug(details)


def log_db_operation(operation: str, details: str, level: str = "DEBUG"):
    """
    Удобная функция для логирования операций с БД

    Args:
        operation: Тип операции
        details: Детали операции
        level: Уровень логирования
    """
    db_logger = get_db_logger(operation)

    if level == "INFO":
        db_logger.info(details)
    elif level == "WARNING":
        db_logger.warning(details)
    elif level == "ERROR":
        db_logger.error(details)
    else:
        db_logger.debug(details)
