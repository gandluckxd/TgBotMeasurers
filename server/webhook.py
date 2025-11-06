"""Обработчик webhook от AmoCRM"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from loguru import logger


class AmoCRMContact(BaseModel):
    """Модель контакта из AmoCRM"""
    id: int
    name: Optional[str] = None


class AmoCRMCustomField(BaseModel):
    """Модель кастомного поля"""
    field_id: int
    field_name: Optional[str] = None
    field_code: Optional[str] = None
    field_type: Optional[str] = None
    values: list[Dict[str, Any]] = []


class AmoCRMLead(BaseModel):
    """Модель сделки (лида) из AmoCRM"""
    id: int
    name: str
    price: Optional[int] = 0
    responsible_user_id: Optional[int] = None
    status_id: Optional[int] = None
    pipeline_id: Optional[int] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    contacts: Optional[Dict[str, Any]] = None
    custom_fields_values: Optional[list[Dict[str, Any]]] = None

    def get_custom_field_value(self, field_code: str) -> Optional[str]:
        """Получить значение кастомного поля по коду"""
        if not self.custom_fields_values:
            return None

        for field in self.custom_fields_values:
            if field.get("field_code") == field_code and field.get("values"):
                values = field.get("values", [])
                if values and len(values) > 0:
                    return values[0].get("value")
        return None

    def get_phone(self) -> Optional[str]:
        """Получить телефон из кастомных полей"""
        return self.get_custom_field_value("PHONE")

    def get_address(self) -> Optional[str]:
        """Получить адрес из кастомных полей"""
        # Попробуйте разные варианты кода поля для адреса
        address = self.get_custom_field_value("ADDRESS")
        if not address:
            address = self.get_custom_field_value("ADRES")
        return address


class AmoCRMWebhookData(BaseModel):
    """Модель данных webhook от AmoCRM"""
    leads: Optional[Dict[str, Any]] = Field(default=None, alias="leads")

    class Config:
        populate_by_name = True


class WebhookProcessor:
    """Обработчик webhook событий от AmoCRM"""

    def __init__(self, bot_instance=None):
        """
        Args:
            bot_instance: Экземпляр Telegram бота для отправки уведомлений
        """
        self.bot = bot_instance

    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка входящего webhook

        Args:
            data: Данные webhook от AmoCRM

        Returns:
            Результат обработки
        """
        logger.info(f"Получен webhook от AmoCRM: {data}")

        try:
            # AmoCRM отправляет данные в формате:
            # {
            #   "leads": {
            #     "status": [
            #       {"id": 123, "status_id": 456, ...}
            #     ]
            #   }
            # }

            if "leads" not in data:
                logger.warning("Webhook не содержит данных о сделках")
                return {"status": "error", "message": "No leads data"}

            leads_data = data["leads"]

            # Проверяем, есть ли изменения статуса
            if "status" in leads_data:
                status_changes = leads_data["status"]
                for lead_data in status_changes:
                    await self._process_lead_status_change(lead_data)

            # Можно также обработать другие события
            if "add" in leads_data:
                new_leads = leads_data["add"]
                for lead_data in new_leads:
                    await self._process_new_lead(lead_data)

            return {"status": "success", "message": "Webhook processed"}

        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def _process_lead_status_change(self, lead_data: Dict[str, Any]):
        """Обработка изменения статуса сделки"""
        logger.info(f"Обработка изменения статуса сделки: {lead_data}")

        lead_id = lead_data.get("id")
        new_status_id = lead_data.get("status_id")

        # Здесь нужно проверить, является ли новый статус триггером для создания замера
        # Это зависит от настроек вашего AmoCRM
        # Например, если статус = "Нужен замер" (ID может быть 142, 143 и т.д.)

        # TODO: Добавить проверку на нужный статус
        # Пока для примера создаем замер для любого изменения статуса
        await self._create_measurement_from_lead(lead_id, lead_data)

    async def _process_new_lead(self, lead_data: Dict[str, Any]):
        """Обработка новой сделки"""
        logger.info(f"Обработка новой сделки: {lead_data}")
        # Можно добавить логику обработки новых сделок, если нужно

    async def _create_measurement_from_lead(self, lead_id: int, lead_data: Dict[str, Any]):
        """
        Создание замера из данных сделки

        Args:
            lead_id: ID сделки в AmoCRM
            lead_data: Данные сделки
        """
        from database import (
            get_db,
            create_measurement,
            get_measurement_by_amocrm_id
        )

        try:
            # Получаем данные из AmoCRM API (детальную информацию)
            # TODO: Реализовать получение полных данных через AmoCRM API
            # Пока используем данные из webhook

            client_name = lead_data.get("name", "Неизвестный клиент")

            # Извлекаем телефон и адрес из кастомных полей
            custom_fields = lead_data.get("custom_fields_values", [])
            phone = None
            address = None

            for field in custom_fields:
                field_code = field.get("field_code")
                values = field.get("values", [])

                if field_code == "PHONE" and values:
                    phone = values[0].get("value")
                elif field_code in ["ADDRESS", "ADRES"] and values:
                    address = values[0].get("value")

            if not address:
                address = "Адрес не указан"

            responsible_user_id = lead_data.get("responsible_user_id")

            # Создаем замер в БД
            async for session in get_db():
                # Проверяем, нет ли уже замера для этой сделки
                existing = await get_measurement_by_amocrm_id(session, lead_id)
                if existing:
                    logger.info(f"Замер для сделки {lead_id} уже существует")
                    return

                # Создаем новый замер
                measurement = await create_measurement(
                    session=session,
                    amocrm_lead_id=lead_id,
                    client_name=client_name,
                    address=address,
                    client_phone=phone,
                    description=f"Сделка: {client_name}",
                    manager_id=None  # TODO: связать с менеджером из AmoCRM
                )

                logger.info(f"Создан замер #{measurement.id} для сделки {lead_id}")

                # Отправляем уведомление администраторам
                if self.bot:
                    await self._notify_admins_new_measurement(measurement)

        except Exception as e:
            logger.error(f"Ошибка создания замера из сделки {lead_id}: {e}", exc_info=True)

    async def _notify_admins_new_measurement(self, measurement):
        """Отправка уведомления администраторам о новом замере"""
        if not self.bot:
            logger.warning("Bot instance не установлен, уведомление не отправлено")
            return

        from config import settings
        from bot.utils.notifications import send_new_measurement_to_admin

        for admin_id in settings.admin_ids_list:
            try:
                await send_new_measurement_to_admin(
                    bot=self.bot,
                    admin_telegram_id=admin_id,
                    measurement=measurement
                )
                logger.info(f"Отправлено уведомление администратору {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору {admin_id}: {e}")
