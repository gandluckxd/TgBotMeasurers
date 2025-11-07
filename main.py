"""Главный файл запуска всего приложения (бот + веб-сервер)"""
import asyncio
import sys
from pathlib import Path

from loguru import logger
import uvicorn
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from server import app, set_webhook_processor, WebhookProcessor


async def run_bot():
    """Запуск Telegram бота"""
    # Импортируем здесь, чтобы избежать циклических импортов
    from bot.main import main as bot_main

    await bot_main()


async def run_server():
    """Запуск FastAPI сервера"""
    config = uvicorn.Config(
        app=app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower()
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Главная функция запуска всего приложения"""
    # Создаем директорию для логов
    Path("logs").mkdir(exist_ok=True)

    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=settings.log_level,
        encoding="utf-8"
    )

    logger.info("=" * 60)
    logger.info("Запуск системы управления замерами")
    logger.info("=" * 60)

    # Создаем экземпляр бота для webhook процессора
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Регистрируем глобальный экземпляр бота
    from bot import set_bot
    set_bot(bot)

    # Создаем и устанавливаем webhook процессор
    webhook_processor = WebhookProcessor(bot_instance=bot)
    set_webhook_processor(webhook_processor)

    logger.info(f"FastAPI сервер будет запущен на {settings.server_host}:{settings.server_port}")
    logger.info(f"Webhook URL: {settings.webhook_url}")
    logger.info(f"Telegram бот токен: {settings.bot_token[:10]}...")

    # Запускаем бота и сервер параллельно
    try:
        # Создаем задачи
        bot_task = asyncio.create_task(run_bot())
        server_task = asyncio.create_task(run_server())

        # Ждем завершения любой из задач
        done, pending = await asyncio.wait(
            [bot_task, server_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Если одна из задач завершилась, отменяем остальные
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Проверяем, есть ли ошибки в завершенных задачах
        for task in done:
            if task.exception():
                logger.error(f"Задача завершилась с ошибкой: {task.exception()}")

    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("Приложение остановлено")


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            # Для Windows используем ProactorEventLoop
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)
