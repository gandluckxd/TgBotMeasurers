"""Utilities for Altawin API access"""
import httpx
from typing import Optional, Dict, Any
from urllib.parse import quote
from loguru import logger
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from config import settings


@dataclass
class AltawinOrderData:
    """Р”Р°РЅРЅС‹Рµ Р·Р°РєР°Р·Р° РёР· Altawin"""
    order_id: int
    order_number: str  # РќРѕРјРµСЂ Р·Р°РєР°Р·Р°
    total_price: Optional[Decimal] = None  # РћР±С‰Р°СЏ СЃС‚РѕРёРјРѕСЃС‚СЊ
    qty_izd: Optional[Decimal] = None  # РљРѕР»РёС‡РµСЃС‚РІРѕ РёР·РґРµР»РёР№
    area_izd: Optional[Decimal] = None  # РџР»РѕС‰Р°РґСЊ РёР·РґРµР»РёР№
    zone: Optional[str] = None  # Р—РѕРЅР° РґРѕСЃС‚Р°РІРєРё
    measurer: Optional[str] = None  # Р—Р°РјРµСЂС‰РёРє
    address: Optional[str] = None  # РђРґСЂРµСЃ РѕР±СЉРµРєС‚Р°
    agreement_date: Optional[datetime] = None  # Р”Р°С‚Р° РґРѕРіРѕРІРѕСЂР°
    agreement_no: Optional[str] = None  # РќРѕРјРµСЂ РґРѕРіРѕРІРѕСЂР°
    phone: Optional[str] = None  # РўРµР»РµС„РѕРЅ

    def to_dict(self) -> Dict[str, Any]:
        """РџСЂРµРѕР±СЂР°Р·РѕРІР°С‚СЊ РІ СЃР»РѕРІР°СЂСЊ"""
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
    """HTTP client for Altawin API"""

    def __init__(self):
        self.api_url = getattr(settings, 'altawin_api_url', "http://127.0.0.1:8001")
        self.timeout = 30.0

    def get_order_data(self, order_code: str) -> Optional[AltawinOrderData]:
        """
        Fetch order data from Altawin API by unique order code.

        Args:
            order_code: Unique order code (Unique_code field)

        Returns:
            AltawinOrderData or None if not found
        """
        try:
            encoded_code = quote(order_code, safe="")
            url = f"{self.api_url}/api/orders/{encoded_code}"
            logger.info(f"Requesting order data from Altawin API: {url} (raw code: {order_code})")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)

                if response.status_code == 404:
                    logger.warning(f"Order {order_code} not found in Altawin")
                    return None

                response.raise_for_status()

                data = response.json()

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

                logger.info(f"Order {order_code} loaded: {result.order_number}")
                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching order {order_code}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Altawin API connection error for order {order_code}: {e}")
            return None
        except Exception as e:
            logger.error(f"Altawin API error for order {order_code}: {e}", exc_info=True)
            return None


# Configure Altawin client
altawin_client = AltawinClient()


