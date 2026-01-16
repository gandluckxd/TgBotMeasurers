"""FastAPI приложение для работы с БД Altawin"""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import SERVER_HOST, SERVER_PORT
from database import get_order_data, db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Altawin DB API",
    description="API для работы с базой данных Altawin",
    version="1.0.0"
)


class OrderData(BaseModel):
    """Модель данных заказа"""
    order_id: int
    order_number: str
    total_price: float
    qty_izd: float
    area_izd: float
    zone: str
    measurer: str
    address: str
    agreement_date: Optional[str] = None
    agreement_no: str
    phone: str


@app.on_event("startup")
async def startup():
    """Инициализация при запуске"""
    logger.info("Запуск Altawin DB API")
    try:
        db.connect()
        logger.info("Подключение к БД установлено")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Очистка при остановке"""
    logger.info("Остановка Altawin DB API")
    db.disconnect()


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "Altawin DB API",
        "version": "1.0.0",
        "status": "ok"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        connection = db.connect()
        is_connected = connection and not connection.closed
        return {
            "status": "healthy" if is_connected else "unhealthy",
            "database": "connected" if is_connected else "disconnected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/api/orders/{order_code}", response_model=OrderData)
async def get_order(order_code: str):
    """
    Получить данные заказа по уникальному коду

    Args:
        order_code: Уникальный код заказа из Altawin

    Returns:
        OrderData: Данные заказа
    """
    try:
        logger.info(f"Запрос данных для заказа: {order_code}")
        data = get_order_data(order_code)

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Заказ с кодом {order_code} не найден"
            )

        return OrderData(**data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения данных заказа {order_code}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения данных из БД: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info"
    )
