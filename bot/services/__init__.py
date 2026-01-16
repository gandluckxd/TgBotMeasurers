"""Сервисы для интеграции с внешними API"""
from services.amocrm import AmoCRMClient, amocrm_client

__all__ = [
    "AmoCRMClient",
    "amocrm_client",
]
