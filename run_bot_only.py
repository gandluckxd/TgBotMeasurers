"""Скрипт для запуска только Telegram бота (без веб-сервера)"""
import asyncio
import sys

if __name__ == "__main__":
    # Импортируем main из bot
    from bot.main import main

    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
