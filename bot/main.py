"""Главный файл запуска Telegram бота"""
import asyncio
import sys
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import db
from bot.handlers import admin_router, measurer_router, manager_router


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Бот запускается...")

    # Создаем таблицы БД
    try:
        await db.create_tables()
        logger.info("Таблицы базы данных готовы")
    except Exception as e:
        logger.error(f"Ошибка создания таблиц БД: {e}")
        sys.exit(1)

    # Отправляем уведомление администраторам о запуске
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="✅ <b>Бот запущен и готов к работе!</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    logger.info("Бот успешно запущен")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Бот останавливается...")

    # Отправляем уведомление администраторам об остановке
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="⚠️ <b>Бот остановлен</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    # Закрываем подключение к БД
    await db.close()

    logger.info("Бот остановлен")


async def main():
    """Главная функция запуска бота"""
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=settings.log_level,
        encoding="utf-8"
    )

    logger.info("=" * 50)
    logger.info("Запуск Telegram бота для управления замерами")
    logger.info("=" * 50)

    # Создаем бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Создаем диспетчер
    dp = Dispatcher()

    # Регистрируем роутеры
    dp.include_router(admin_router)
    dp.include_router(measurer_router)
    dp.include_router(manager_router)

    # Регистрируем startup и shutdown хэндлеры
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем бота
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
