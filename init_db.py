"""Скрипт для инициализации базы данных"""
import asyncio
import sys
from pathlib import Path

from loguru import logger

from config import settings
from database.database import Database
from database.models import Base


async def init_database():
    """Инициализация базы данных"""
    logger.info("=" * 60)
    logger.info("Инициализация базы данных")
    logger.info("=" * 60)

    # Создаем экземпляр базы данных
    db = Database(settings.database_url, echo=True)

    try:
        # Создаем все таблицы
        logger.info("Создание таблиц...")
        await db.create_tables()
        logger.success("✅ Таблицы успешно созданы")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await db.close()

    logger.info("=" * 60)
    logger.success("Инициализация завершена успешно")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    # Запускаем инициализацию
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(init_database())
