"""Интеграция с AmoCRM API"""
import time
from typing import Dict, Any, Optional
import aiohttp
from loguru import logger

from config import settings


class AmoCRMClient:
    """Клиент для работы с AmoCRM API"""

    def __init__(self):
        # Используем поддомен из настроек
        self.base_url = f"https://{settings.amocrm_subdomain}.amocrm.ru/api/v4"
        self.access_token = settings.amocrm_access_token
        self.refresh_token = settings.amocrm_refresh_token
        self.client_id = settings.amocrm_client_id
        self.client_secret = settings.amocrm_client_secret
        self.redirect_uri = settings.amocrm_redirect_uri
        # Долгосрочный токен действует до 2030 года
        self.token_expires_at = 1919548800  # 2030-10-20

    async def refresh_access_token(self) -> bool:
        """
        Обновление access токена

        Returns:
            True если обновление успешно
        """
        try:
            url = f"https://{settings.amocrm_subdomain}.amocrm.ru/oauth2/access_token"

            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "redirect_uri": self.redirect_uri
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()

                        self.access_token = result["access_token"]
                        self.refresh_token = result["refresh_token"]
                        self.token_expires_at = time.time() + result["expires_in"]

                        logger.info("Access токен AmoCRM успешно обновлен")

                        # TODO: Сохранить новые токены в конфигурацию или БД
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка обновления токена AmoCRM: {response.status} - {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Ошибка при обновлении токена AmoCRM: {e}", exc_info=True)
            return False

    async def _ensure_token_valid(self):
        """Проверка и обновление токена при необходимости"""
        if time.time() >= self.token_expires_at - 300:  # За 5 минут до истечения
            await self.refresh_access_token()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Выполнение запроса к AmoCRM API

        Args:
            method: HTTP метод (GET, POST, PATCH и т.д.)
            endpoint: Endpoint API (без базового URL)
            data: Данные для отправки (для POST/PATCH)
            params: Query параметры

        Returns:
            Ответ от API или None в случае ошибки
        """
        await self._ensure_token_valid()

        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params
                ) as response:
                    if response.status in [200, 201, 204]:
                        if response.status == 204:
                            return {}
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка запроса к AmoCRM: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Ошибка при выполнении запроса к AmoCRM: {e}", exc_info=True)
            return None

    async def get_lead(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о сделке

        Args:
            lead_id: ID сделки

        Returns:
            Данные сделки или None
        """
        result = await self._make_request(
            method="GET",
            endpoint=f"leads/{lead_id}",
            params={"with": "contacts"}
        )

        if result and "_embedded" in result:
            leads = result["_embedded"].get("leads", [])
            if leads:
                return leads[0]

        return result

    def extract_custom_field_value(self, custom_fields: list, field_id: int) -> Optional[str]:
        """
        Извлечь значение кастомного поля по ID

        Args:
            custom_fields: Список кастомных полей из AmoCRM
            field_id: ID поля

        Returns:
            Значение поля или None
        """
        if not custom_fields:
            return None

        for field in (custom_fields or []):
            if field.get("field_id") == field_id:
                values = field.get("values", [])
                if values and len(values) > 0:
                    return str(values[0].get("value", ""))

        return None

    async def get_lead_contacts(self, lead_id: int) -> list[Dict[str, Any]]:
        """
        Получить контакты сделки

        Args:
            lead_id: ID сделки

        Returns:
            Список контактов
        """
        result = await self._make_request(
            method="GET",
            endpoint=f"leads/{lead_id}/links"
        )

        if not result or "_embedded" not in result:
            return []

        links = result["_embedded"].get("links", [])
        contact_ids = [link["to_entity_id"] for link in links if link["to_entity_type"] == "contacts"]

        if not contact_ids:
            return []

        # Получаем информацию о контактах
        contacts_result = await self._make_request(
            method="GET",
            endpoint="contacts",
            params={"id": contact_ids}
        )

        if contacts_result and "_embedded" in contacts_result:
            return contacts_result["_embedded"].get("contacts", [])

        return []

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пользователе AmoCRM

        Args:
            user_id: ID пользователя

        Returns:
            Данные пользователя или None
        """
        result = await self._make_request(
            method="GET",
            endpoint=f"users/{user_id}"
        )

        return result

    async def get_company(self, company_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о компании

        Args:
            company_id: ID компании

        Returns:
            Данные компании или None
        """
        result = await self._make_request(
            method="GET",
            endpoint=f"companies/{company_id}"
        )

        return result

    async def get_lead_with_company(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о сделке вместе с компанией

        Args:
            lead_id: ID сделки

        Returns:
            Данные сделки со встроенной информацией о компании или None
        """
        result = await self._make_request(
            method="GET",
            endpoint=f"leads/{lead_id}",
            params={"with": "contacts,companies"}
        )

        if result and "_embedded" in result:
            leads = result["_embedded"].get("leads", [])
            if leads:
                return leads[0]

        return result

    def extract_company_measurer_field(self, company: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Извлечь значение поля "Замерщик" из компании (field_id: 809619)

        Args:
            company: Данные компании из AmoCRM

        Returns:
            Значение поля "Замерщик" или None
        """
        if not company:
            return None

        custom_fields = company.get("custom_fields_values", [])
        return self.extract_custom_field_value(custom_fields, field_id=809619)

    async def get_lead_full_info(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить полную информацию о сделке включая контакты и компанию

        Args:
            lead_id: ID сделки

        Returns:
            Полная информация о сделке
        """
        # Используем новый метод для получения сделки с компанией
        lead = await self.get_lead_with_company(lead_id)

        if not lead:
            return None

        # Получаем контакты
        contacts = await self.get_lead_contacts(lead_id)

        # Получаем ответственного пользователя
        responsible_user_id = lead.get("responsible_user_id")
        responsible_user = None

        if responsible_user_id:
            responsible_user = await self.get_user(responsible_user_id)

        # Извлекаем компанию из _embedded, если есть
        company = None
        company_measurer_field = None

        if "_embedded" in lead and "companies" in lead["_embedded"]:
            companies = lead["_embedded"]["companies"]
            if companies and len(companies) > 0:
                company_basic = companies[0]
                company_id = company_basic.get("id")
                logger.info(f"Найдена компания ID {company_id}: {company_basic.get('name')}")

                # Получаем полную информацию о компании с кастомными полями
                if company_id:
                    company = await self.get_company(company_id)
                    if company:
                        logger.info(f"Получена полная информация о компании: {company.get('name')}")
                        logger.info(f"Custom fields компании: {company.get('custom_fields_values', [])}")
                        # Извлекаем поле "Замерщик" из компании
                        company_measurer_field = self.extract_company_measurer_field(company)
                        logger.info(f"Извлечено значение поля 'Замерщик' (809619): {company_measurer_field}")
                    else:
                        logger.warning(f"Не удалось получить полную информацию о компании {company_id}")
                        company = company_basic

        return {
            "lead": lead,
            "contacts": contacts,
            "responsible_user": responsible_user,
            "company": company,
            "company_measurer_field": company_measurer_field
        }

    async def get_all_users(self) -> list[Dict[str, Any]]:
        """
        Получить список всех пользователей AmoCRM

        Returns:
            Список пользователей
        """
        result = await self._make_request(
            method="GET",
            endpoint="users"
        )

        if result and "_embedded" in result:
            return result["_embedded"].get("users", [])

        return []


# Глобальный экземпляр клиента
amocrm_client = AmoCRMClient()
