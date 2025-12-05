"""Главный файл запуска Telegram бота"""
import asyncio
import sys
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import db
from bot.handlers import (
    registration_router,
    invite_links_router,
    admin_router,
    measurer_router,
    manager_router,
    zones_router,
    measurer_names_router
)
from bot.middlewares import RoleCheckMiddleware


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

    # Регистрируем администраторов из конфига в БД
    from database import get_db, get_user_by_telegram_id, create_user, UserRole

    for admin_id in settings.admin_ids_list:
        try:
            async for session in get_db():
                # Проверяем, существует ли администратор
                admin = await get_user_by_telegram_id(session, admin_id)

                if not admin:
                    # Получаем информацию о пользователе из Telegram
                    try:
                        chat = await bot.get_chat(admin_id)
                        username = chat.username
                        first_name = chat.first_name
                        last_name = chat.last_name
                    except Exception:
                        username = None
                        first_name = "Admin"
                        last_name = None

                    # Создаем администратора
                    admin = await create_user(
                        session,
                        telegram_id=admin_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        role=UserRole.ADMIN
                    )
                    logger.info(f"Создан администратор: {admin.full_name} (ID: {admin_id})")
                elif admin.role != UserRole.ADMIN:
                    # Если пользователь существует, но не админ - повышаем до админа
                    admin.role = UserRole.ADMIN
                    await session.commit()
                    logger.info(f"Пользователь {admin.full_name} повышен до администратора")

                break  # Выходим из async for после первой итерации
        except Exception as e:
            logger.error(f"Ошибка при регистрации администратора {admin_id}: {e}", exc_info=True)

    # Отправляем уведомление администраторам о запуске
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="✅ <b>Бот запущен и готов к работе!</b>",
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Отправлено уведомление о запуске администратору {admin_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору {admin_id}: {e}. "
                         f"Возможно, администратор еще не начал диалог с ботом.")

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
            logger.info(f"Отправлено уведомление об остановке администратору {admin_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору {admin_id}: {e}. "
                         f"Возможно, администратор еще не начал диалог с ботом.")

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

    # Регистрируем middleware для проверки ролей
    dp.message.middleware(RoleCheckMiddleware())
    dp.callback_query.middleware(RoleCheckMiddleware())

    # Регистрируем роутеры (registration_router должен быть первым для обработки /start)
    dp.include_router(registration_router)
    dp.include_router(invite_links_router)
    dp.include_router(zones_router)
    dp.include_router(measurer_names_router)
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
