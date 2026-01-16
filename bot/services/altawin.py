"""Интеграция с базой данных Altawin через HTTP API"""
import httpx
from typing import Optional, Dict, Any
from loguru import logger
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from config import settings


@dataclass
class AltawinOrderData:
    """Данные заказа из Altawin"""
    order_id: int
    order_number: str  # Номер заказа
    total_price: Optional[Decimal] = None  # Общая стоимость
    qty_izd: Optional[Decimal] = None  # Количество изделий
    area_izd: Optional[Decimal] = None  # Площадь изделий
    zone: Optional[str] = None  # Зона доставки
    measurer: Optional[str] = None  # Замерщик
    address: Optional[str] = None  # Адрес объекта
    agreement_date: Optional[datetime] = None  # Дата договора
    agreement_no: Optional[str] = None  # Номер договора
    phone: Optional[str] = None  # Телефон

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            "order_id": self.order_id,
            "order_number": self.order_number,
            "total_price": float(self.total_price) if self.total_price else None,
            "qty_izd": float(self.qty_izd) if self.qty_izd else None,
            "area_izd": float(self.area_izd) if self.area_izd else None,
            "zone": self.zone,
            "measurer": self.measurer,
            "address": self.address,
            "agreement_date": self.agreement_date,
            "agreement_no": self.agreement_no,
            "phone": self.phone
        }


class AltawinClient:
    """HTTP клиент для работы с API БД Altawin"""

    def __init__(self):
        # URL API сервиса для работы с БД Altawin
        self.api_url = getattr(settings, 'altawin_api_url', "http://127.0.0.1:8001")
        self.timeout = 30.0  # Таймаут запросов в секундах

    def get_order_data(self, order_code: str) -> Optional[AltawinOrderData]:
        """
        Получить данные заказа из БД Altawin по уникальному коду через HTTP API

        Args:
            order_code: Уникальный код заказа (поле Unique_code)

        Returns:
            AltawinOrderData или None если заказ не найден
        """
        try:
            url = f"{self.api_url}/api/orders/{order_code}"
            logger.info(f"Запрос данных заказа через API: {url}")

            # Используем httpx для синхронного HTTP запроса
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)

                if response.status_code == 404:
                    logger.warning(f"Заказ с кодом {order_code} не найден в Altawin")
                    return None

                response.raise_for_status()  # Проверка на ошибки HTTP

                # Парсим JSON ответ
                data = response.json()

                # Преобразуем в объект AltawinOrderData
                result = AltawinOrderData(
                    order_id=data["order_id"],
                    order_number=data.get("order_number", ""),
                    total_price=Decimal(str(data["total_price"])) if data.get("total_price") else None,
                    qty_izd=Decimal(str(data["qty_izd"])) if data.get("qty_izd") else None,
                    area_izd=Decimal(str(data["area_izd"])) if data.get("area_izd") else None,
                    zone=data.get("zone"),
                    measurer=data.get("measurer"),
                    address=data.get("address"),
                    agreement_date=datetime.fromisoformat(data["agreement_date"]) if data.get("agreement_date") else None,
                    agreement_no=data.get("agreement_no"),
                    phone=data.get("phone")
                )

                logger.info(f"✅ Получены данные для заказа {order_code}: {result.order_number}")
                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка при запросе данных заказа {order_code}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"❌ Ошибка подключения к API Altawin для заказа {order_code}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных из API Altawin для кода {order_code}: {e}", exc_info=True)
            return None


# Глобальный экземпляр клиента
altawin_client = AltawinClient()
