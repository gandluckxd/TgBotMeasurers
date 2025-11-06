"""Скрипт для запуска только FastAPI сервера (без бота)"""
import uvicorn
from config import settings
from server import app

if __name__ == "__main__":
    print(f"Запуск FastAPI сервера на {settings.server_host}:{settings.server_port}")
    print(f"Webhook URL: {settings.webhook_url}")

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower()
    )
