"""Скрипт для периодической выгрузки данных в Google Sheets"""
import asyncio
import sys
from datetime import datetime
from loguru import logger

from config_exporter import settings
from services.sheets_export import export_to_google_sheets
from utils.timezone_utils import format_moscow_time, moscow_now


async def periodic_export():
    """Периодический экспорт данных в Google Sheets"""
    logger.info("Запуск периодического экспорта данных в Google Sheets")
    logger.info(f"Интервал обновления: {settings.google_export_interval} секунд")

    while True:
        try:
            logger.info(f"Начало экспорта данных: {format_moscow_time(moscow_now(), '%d.%m.%Y %H:%M:%S')}")

            # Выполняем экспорт
            await export_to_google_sheets()

            logger.info(f"Экспорт завершен. Следующее обновление через {settings.google_export_interval} секунд")

        except Exception as e:
            logger.error(f"Ошибка при экспорте данных: {e}")
            logger.exception(e)

        # Ждем указанный интервал перед следующим обновлением
        await asyncio.sleep(settings.google_export_interval)


async def main():
    """Главная функция"""
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
    logger.add(
        "logs/sheets_export_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="00:00",
        retention="30 days",
        compression="zip"
    )

    logger.info("=" * 60)
    logger.info("Запуск приложения экспорта данных в Google Sheets")
    logger.info("=" * 60)

    try:
        # Запускаем периодический экспорт
        await periodic_export()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки. Завершение работы...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        logger.exception(e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
