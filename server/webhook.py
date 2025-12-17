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
        from services.amocrm import amocrm_client

        try:
            # Получаем полную информацию о сделке через AmoCRM API
            logger.info(f"Запрашиваем полную информацию о сделке #{lead_id} через API")
            full_info = await amocrm_client.get_lead_full_info(lead_id)

            if not full_info:
                logger.error(f"Не удалось получить информацию о сделке #{lead_id} из AmoCRM API")
                # Fallback на данные из вебхука
                full_info = {
                    "lead": lead_data,
                    "contacts": [],
                    "responsible_user": None
                }

            lead = full_info.get("lead") or {}
            contacts = full_info.get("contacts") or []
            responsible_user = full_info.get("responsible_user")
            company = full_info.get("company")
            company_measurer_field = full_info.get("company_measurer_field")

            # Извлекаем данные из сделки
            lead_name = lead.get("name", "Неизвестная сделка")

            # Получаем название компании, если есть
            company_name = company.get("name") if company else None

            # Логируем информацию о компании для отладки
            if company:
                logger.info(f"Компания найдена: {company_name}")
                logger.info(f"Поле 'Замерщик' компании: {company_measurer_field}")
            else:
                logger.info("Компания не привязана к сделке")

            # Получаем имя и ID ответственного пользователя из AmoCRM
            responsible_user_name = None
            responsible_user_id = None
            if responsible_user:
                responsible_user_name = responsible_user.get("name")
                responsible_user_id = responsible_user.get("id")

            # Извлекаем данные контакта
            contact_name = None
            contact_phone = None

            if contacts:
                first_contact = contacts[0]
                contact_name = first_contact.get("name")

                custom_fields = first_contact.get("custom_fields_values") or []
                for field in custom_fields:
                    field_code = field.get("field_code")
                    field_id = field.get("field_id")
                    values = field.get("values", [])

                    if field_code == "PHONE" and values:
                        from utils.phone_formatter import normalize_phone
                        contact_phone = normalize_phone(values[0].get("value"))
                        break

            # Получаем кастомные поля сделки по ID
            lead_custom_fields = lead.get("custom_fields_values") or []

            address = None  # Поле с ID 809475
            delivery_zone = None  # Поле с ID 808753
            order_number = None  # Номер заказа (ID: 667253)
            windows_count = None  # Количество окон (ID: 676403)
            windows_area = None  # Площадь окон (ID: 808751)

            for field in lead_custom_fields:
                field_id = field.get("field_id")
                values = field.get("values", [])

                if field_id == 809475 and values:  # Адрес
                    address = values[0].get("value")
                elif field_id == 808753 and values:  # Зона доставки
                    delivery_zone = values[0].get("value")
                elif field_id == 667253 and values:  # Номер заказа
                    order_number = str(values[0].get("value"))
                elif field_id == 676403 and values:  # Количество окон
                    windows_count = str(values[0].get("value"))
                elif field_id == 808751 and values:  # Площадь окон
                    windows_area = str(values[0].get("value"))

            # Создаем замер в БД
            async for session in get_db():
                # Проверяем, нет ли уже замера для этой сделки
                existing = await get_measurement_by_amocrm_id(session, lead_id)
                if existing:
                    logger.info(f"Замер для сделки {lead_id} уже существует")
                    return

                # Ищем менеджера по amocrm_user_id
                from database import get_user_by_amocrm_id
                manager = None
                manager_id = None
                if responsible_user_id:
                    manager = await get_user_by_amocrm_id(session, responsible_user_id)
                    if manager:
                        manager_id = manager.id
                        logger.info(f"Найден менеджер {manager.full_name} (AmoCRM ID: {responsible_user_id})")
                    else:
                        logger.warning(f"Менеджер с AmoCRM ID {responsible_user_id} не найден в базе")

                # Создаем новый замер с автоматическим распределением
                measurement = await create_measurement(
                    session=session,
                    amocrm_lead_id=lead_id,
                    lead_name=lead_name,
                    responsible_user_name=responsible_user_name,
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                    address=address,
                    delivery_zone=delivery_zone,
                    order_number=order_number,
                    windows_count=windows_count,
                    windows_area=windows_area,
                    manager_id=manager_id,
                    # Новые параметры для dealer assignment
                    dealer_company_name=company_name,
                    dealer_field_value=company_measurer_field
                )

                logger.info(
                    f"Создан замер #{measurement.id} для сделки {lead_id}. "
                    f"Автораспределение: {measurement.assignment_reason or 'none'}, "
                    f"Предложенный замерщик: {measurement.auto_assigned_measurer.full_name if measurement.auto_assigned_measurer else 'Не назначен'}"
                )

                # Отправляем уведомления только администраторам и руководителям для подтверждения
                if self.bot:
                    # Уведомление администраторам и руководителям с запросом подтверждения
                    await self._notify_admins_new_measurement(measurement)

                    # Уведомления замерщику и менеджеру НЕ отправляются
                    # Они будут отправлены после подтверждения руководителем

        except Exception as e:
            logger.error(f"Ошибка создания замера из сделки {lead_id}: {e}", exc_info=True)

    async def _notify_admins_new_measurement(self, measurement):
        """Отправка уведомления администраторам и руководителям о новом замере"""
        if not self.bot:
            logger.warning("Bot instance не установлен, уведомление не отправлено")
            return

        from config import settings
        from bot.utils.notifications import send_new_measurement_to_admin
        from database import get_db, get_all_supervisors

        # Отправляем уведомления администраторам из конфига
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

        # Отправляем уведомления всем руководителям из БД
        async for session in get_db():
            supervisors = await get_all_supervisors(session)
            for supervisor in supervisors:
                try:
                    await send_new_measurement_to_admin(
                        bot=self.bot,
                        admin_telegram_id=supervisor.telegram_id,
                        measurement=measurement
                    )
                    logger.info(f"Отправлено уведомление руководителю {supervisor.full_name} ({supervisor.telegram_id})")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления руководителю {supervisor.telegram_id}: {e}")

    async def _notify_measurer_new_assignment(self, measurement):
        """Отправка уведомления замерщику о назначении замера"""
        if not self.bot:
            logger.warning("Bot instance не установлен, уведомление не отправлено")
            return

        from bot.utils.notifications import send_assignment_notification_to_measurer

        try:
            await send_assignment_notification_to_measurer(
                bot=self.bot,
                measurer=measurement.measurer,
                measurement=measurement,
                measurer_name=measurement.measurer.full_name
            )
            logger.info(f"Отправлено уведомление о назначении замерщику {measurement.measurer.full_name}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления замерщику: {e}")

    async def _notify_manager_new_assignment(self, measurement, manager):
        """Отправка уведомления менеджеру о назначении замерщика"""
        if not self.bot:
            logger.warning("Bot instance не установлен, уведомление не отправлено")
            return

        from bot.utils.notifications import send_assignment_notification_to_manager

        try:
            await send_assignment_notification_to_manager(
                bot=self.bot,
                manager=manager,
                measurement=measurement,
                measurer=measurement.measurer
            )
            logger.info(f"Отправлено уведомление о назначении замерщика менеджеру {manager.full_name}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления менеджеру: {e}")
