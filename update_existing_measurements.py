"""Скрипт обновления существующих замеров данными из AmoCRM"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database import get_db
from database.models import Measurement
from services.amocrm import amocrm_client
from sqlalchemy import select
from loguru import logger


async def update_measurements():
    """Обновить все существующие замеры данными из AmoCRM"""
    logger.info("Starting measurements update...")

    updated_count = 0
    error_count = 0

    async for session in get_db():
        # Получаем все замеры
        result = await session.execute(select(Measurement))
        measurements = result.scalars().all()

        logger.info(f"Found {len(measurements)} measurements to update")

        for measurement in measurements:
            try:
                logger.info(f"Updating measurement #{measurement.id} (AmoCRM Lead ID: {measurement.amocrm_lead_id})")

                # Получаем полную информацию о сделке из AmoCRM
                full_info = await amocrm_client.get_lead_full_info(measurement.amocrm_lead_id)

                if not full_info:
                    logger.warning(f"Could not fetch data for lead {measurement.amocrm_lead_id}")
                    error_count += 1
                    continue

                lead = full_info.get("lead", {})
                contacts = full_info.get("contacts", [])
                responsible_user = full_info.get("responsible_user")

                # Обновляем название сделки
                measurement.lead_name = lead.get("name", measurement.lead_name)

                # Получаем имя ответственного пользователя
                if responsible_user:
                    measurement.responsible_user_name = responsible_user.get("name")

                # Извлекаем данные контакта
                if contacts:
                    first_contact = contacts[0]
                    measurement.contact_name = first_contact.get("name")

                    custom_fields = first_contact.get("custom_fields_values", [])
                    for field in custom_fields:
                        field_code = field.get("field_code")
                        values = field.get("values", [])

                        if field_code == "PHONE" and values:
                            measurement.contact_phone = values[0].get("value")
                            break

                # Получаем кастомные поля сделки по ID
                lead_custom_fields = lead.get("custom_fields_values", [])

                for field in lead_custom_fields:
                    field_id = field.get("field_id")
                    values = field.get("values", [])

                    if field_id == 809475 and values:  # Адрес
                        measurement.address = values[0].get("value")
                    elif field_id == 808753 and values:  # Зона доставки
                        measurement.delivery_zone = values[0].get("value")

                await session.commit()
                updated_count += 1
                logger.info(f"Successfully updated measurement #{measurement.id}")

            except Exception as e:
                logger.error(f"Error updating measurement #{measurement.id}: {e}", exc_info=True)
                error_count += 1
                continue

    logger.info(f"Update complete! Updated: {updated_count}, Errors: {error_count}")
    print(f"\n[SUMMARY]")
    print(f"  Updated: {updated_count}")
    print(f"  Errors: {error_count}")


if __name__ == "__main__":
    asyncio.run(update_measurements())
