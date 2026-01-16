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

        # Логируем для отладки
        logger.info(f"Получен webhook запрос:")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Body length: {len(body)}")
        logger.info(f"Body (raw): {body[:500]}")  # Первые 500 байт

        # Если тело пустое - это может быть проверочный запрос от AmoCRM
        if not body or len(body) == 0:
            logger.warning("Получен пустой webhook (возможно, проверочный запрос от AmoCRM)")
            return JSONResponse(content={"status": "ok", "message": "Empty webhook accepted"})

        # Проверяем подпись (опционально, если настроена в AmoCRM)
        # if settings.webhook_secret:
        #     if not verify_webhook_signature(body, x_signature):
        #         raise HTTPException(status_code=403, detail="Invalid signature")

        # Парсим данные
        try:
            # AmoCRM может отправлять данные как JSON или как form-data
            content_type = request.headers.get("content-type", "")

            if "application/json" in content_type:
                data = await request.json()
            elif "application/x-www-form-urlencoded" in content_type:
                # AmoCRM отправляет данные в URL-encoded формате
                from urllib.parse import parse_qs

                # Парсим URL-encoded данные
                parsed = parse_qs(body.decode('utf-8'))

                # Преобразуем в удобный формат
                # parse_qs возвращает списки, берём первое значение
                data = {}

                # Обрабатываем leads[status][0][...]
                if any(key.startswith('leads[') for key in parsed.keys()):
                    data['leads'] = {'status': []}

                    lead_item = {}
                    for key, value in parsed.items():
                        if key.startswith('leads[status][0]'):
                            # Извлекаем имя поля из ключа
                            # leads[status][0][id] -> id
                            field_name = key.split('[')[-1].rstrip(']')
                            lead_item[field_name] = int(value[0]) if value[0].isdigit() else value[0]

                    if lead_item:
                        data['leads']['status'].append(lead_item)

                # Добавляем информацию об аккаунте
                if 'account[id]' in parsed:
                    data['account'] = {
                        'id': int(parsed['account[id]'][0]),
                        'subdomain': parsed.get('account[subdomain]', [''])[0]
                    }

            else:
                # Пробуем распарсить как JSON
                import json
                data = json.loads(body.decode('utf-8'))

            logger.info(f"Распарсенные данные: {data}")

        except Exception as e:
            logger.error(f"Ошибка парсинга данных: {e}")
            logger.error(f"Content-Type: {request.headers.get('content-type')}")
            logger.error(f"Body: {body.decode('utf-8', errors='ignore')}")

            # Возвращаем OK, чтобы AmoCRM не ретраил
            return JSONResponse(
                content={"status": "error", "message": f"Parse error: {str(e)}"},
                status_code=200  # Намеренно 200, чтобы AmoCRM не повторял запрос
            )

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
        # Возвращаем 200 даже при ошибке, чтобы AmoCRM не ретраил
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=200
        )
