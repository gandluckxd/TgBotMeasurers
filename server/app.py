"""FastAPI приложение для приема webhook"""
import hmac
import hashlib
import asyncio
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from loguru import logger

from config import settings
from server.webhook import WebhookProcessor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("FastAPI сервер запускается...")
    logger.info(f"Webhook URL: {settings.webhook_url}")

    yield

    # Shutdown
    logger.info("FastAPI сервер останавливается...")
    try:
        # Даем время на завершение текущих запросов
        await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    logger.info("FastAPI сервер остановлен")


# Создаем FastAPI приложение с lifespan
app = FastAPI(
    title="Measurers Bot Webhook Server",
    description="Сервер для приема webhook от AmoCRM",
    version="1.0.0",
    lifespan=lifespan
)

# Процессор webhook (будет установлен при запуске бота)
webhook_processor: WebhookProcessor | None = None


def set_webhook_processor(processor: WebhookProcessor):
    """Установка процессора webhook"""
    global webhook_processor
    webhook_processor = processor
    logger.info("Webhook processor установлен")


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """
    Проверка подписи webhook от AmoCRM

    Args:
        payload: Тело запроса
        signature: Подпись из заголовка

    Returns:
        True если подпись валидна
    """
    if not signature:
        logger.warning("Подпись webhook отсутствует")
        return False

    # Вычисляем HMAC подпись
    expected_signature = hmac.new(
        key=settings.webhook_secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    is_valid = hmac.compare_digest(signature, expected_signature)

    if not is_valid:
        logger.warning(f"Неверная подпись webhook. Получено: {signature}, ожидалось: {expected_signature}")

    return is_valid


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "status": "ok",
        "service": "Measurers Bot Webhook Server",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "webhook_processor": webhook_processor is not None
    }


@app.post(settings.webhook_path)
async def handle_amocrm_webhook(
    request: Request,
    x_signature: str | None = Header(None, alias="X-Signature")
):
    """
    Обработка webhook от AmoCRM

    Args:
        request: HTTP запрос
        x_signature: Подпись из заголовка (если используется)

    Returns:
        Результат обработки
    """
    try:
        # Получаем тело запроса
        body = await request.body()

        # Проверяем подпись (опционально, если настроена в AmoCRM)
        # if settings.webhook_secret:
        #     if not verify_webhook_signature(body, x_signature):
        #         raise HTTPException(status_code=403, detail="Invalid signature")

        # Парсим JSON
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Обрабатываем webhook
        if not webhook_processor:
            logger.error("Webhook processor не установлен")
            raise HTTPException(status_code=500, detail="Webhook processor not initialized")

        result = await webhook_processor.process_webhook(data)

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
