"""Система уведомлений для пользователей"""
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from loguru import logger
from typing import Optional, Dict, Any

from database.models import Measurement, User
from bot_handlers.keyboards.inline import get_measurers_keyboard, get_measurement_actions_keyboard
from bot_handlers.utils.notification_logging import log_notification


def get_altawin_display_values(altawin_data, contact_phone: Optional[str] = None) -> Dict[str, str]:
    """Подготовить значения Altawin для отображения с фолбэками."""
    missing_text = "Данные не найдены в Altawin"
    amo_missing_text = "Данные не найдены в AmoCRM"

    def value_or_unknown(value):
        if value is None or value == "":
            return "Не указано"
        return str(value)

    if not altawin_data:
        order_number = missing_text
        address = missing_text
        zone = missing_text
        qty_izd = missing_text
        area_izd = missing_text
    else:
        order_number = value_or_unknown(altawin_data.order_number)
        address = value_or_unknown(altawin_data.address)
        zone = value_or_unknown(altawin_data.zone)
        qty_izd = value_or_unknown(altawin_data.qty_izd)
        area_izd = value_or_unknown(altawin_data.area_izd)

    if area_izd not in ["Не указано", missing_text]:
        area_izd = f"{area_izd} м²"

    phone_source = contact_phone
    if not phone_source and altawin_data and getattr(altawin_data, "phone", None):
        phone_source = altawin_data.phone

    if phone_source:
        from utils.phone_formatter import format_phone_for_telegram
        phone = format_phone_for_telegram(phone_source)
    else:
        phone = amo_missing_text

    return {
        "order_number": order_number,
        "address": address,
        "zone": zone,
        "phone": phone,
        "qty_izd": qty_izd,
        "area_izd": area_izd,
    }


def format_lead_info_for_notification(full_info: Dict[str, Any]) -> str:
    """
    Унифицированное форматирование информации о сделке из AmoCRM для уведомлений

    Порядок вывода (унифицированный со всеми другими сообщениями):
    1. Заголовок
    2. Основная информация о заказе
    3. Контактные данные
    4. Дополнительные параметры из AmoCRM
    5. Ответственный и дата создания

    Args:
        full_info: Полная информация о сделке из AmoCRM API

    Returns:
        Отформатированный текст уведомления
    """
    from services.amocrm import amocrm_client

    lead = full_info.get("lead", {})
    contacts = full_info.get("contacts", [])
    responsible_user = full_info.get("responsible_user")

    # === ЗАГОЛОВОК ===
    text = "🆕 <b>Новая заявка из AmoCRM!</b>\n\n"

    # === БЛОК 1: Основная информация о заказе ===
    lead_name = lead.get("name", "Без названия")
    lead_id = lead.get("id")
    text += f"📄 <b>Сделка:</b> {lead_name}\n"

    # Получаем кастомные поля сделки
    lead_custom_fields = lead.get("custom_fields_values", [])

    # Номер заказа (ID: 667253)
    order_number = amocrm_client.extract_custom_field_value(lead_custom_fields, 667253)
    if order_number:
        text += f"🔢 <b>Номер заказа:</b> {order_number}\n"

    # Адрес из кастомных полей сделки
    address_found = False
    for field in lead_custom_fields:
        field_code = field.get("field_code")
        values = field.get("values", [])

        if field_code in ["ADDRESS", "ADRES", "address"] and values:
            address = values[0].get("value")
            text += f"📍 <b>Адрес:</b> {address}\n"
            address_found = True
            break

    if not address_found:
        text += f"📍 <b>Адрес:</b> Данные не найдены в AmoCRM\n"

    text += "\n"

    # === БЛОК 2: Контактные данные ===
    if contacts:
        contact = contacts[0]  # Берем первый контакт
        contact_name = contact.get("name", "Данные не найдены в AmoCRM")
        text += f"👤 <b>Контакт:</b> {contact_name}\n"

        # Ищем телефон в кастомных полях контакта
        custom_fields = contact.get("custom_fields_values", [])
        for field in custom_fields:
            field_code = field.get("field_code")
            values = field.get("values", [])

            if values and field_code == "PHONE":
                from utils.phone_formatter import format_phone_for_telegram
                value = values[0].get("value")
                text += f"📞 <b>Телефон:</b> {format_phone_for_telegram(value)}\n"
                break
    else:
        text += "👤 <b>Контакт:</b> Данные не найдены в AmoCRM\n"

    # Ответственный менеджер
    if responsible_user:
        manager_name = responsible_user.get("name", "Данные не найдены в AmoCRM")
        text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {manager_name}\n"

    text += "\n"

    # === БЛОК 3: Параметры окон из AmoCRM ===
    has_window_info = False

    # Количество окон (ID: 676403)
    windows_count = amocrm_client.extract_custom_field_value(lead_custom_fields, 676403)
    if windows_count:
        text += f"🪟 <b>Количество окон:</b> {windows_count}\n"
        has_window_info = True

    # Площадь окон (ID: 808751)
    windows_area = amocrm_client.extract_custom_field_value(lead_custom_fields, 808751)
    if windows_area:
        text += f"📐 <b>Площадь окон:</b> {windows_area} м²\n"
        has_window_info = True

    if has_window_info:
        text += "\n"

    # === БЛОК 4: Дополнительная информация ===
    text += f"🆔 <b>ID сделки в AmoCRM:</b> {lead_id}\n"

    # Дата создания (конвертируем в московское время)
    created_at = lead.get("created_at")
    if created_at:
        from utils.timezone_utils import timestamp_to_moscow_time
        created_date = timestamp_to_moscow_time(created_at)
        if created_date:
            text += f"📅 <b>Создано:</b> {created_date.strftime('%d.%m.%Y %H:%M')}\n"

    return text


async def notify_measurers_about_new_lead(full_info: Dict[str, Any]) -> None:
    """
    Отправить уведомления замерщикам о новой сделке из AmoCRM

    Args:
        full_info: Полная информация о сделке из AmoCRM API
    """
    from database import get_db, get_all_measurers
    from config import settings

    try:
        # Форматируем красивое уведомление
        notification_text = format_lead_info_for_notification(full_info)
        notification_text += "\n\n⏳ <i>Ожидаем назначения замерщика...</i>"

        # Получаем список замерщиков
        async for session in get_db():
            measurers = await get_all_measurers(session)

            if not measurers:
                logger.warning("Нет доступных замерщиков для уведомления")
                return

            # Получаем экземпляр бота
            from bot_handlers import get_bot
            bot = get_bot()

            if not bot:
                logger.error("Не удалось получить экземпляр бота")
                return

            # Отправляем уведомления всем замерщикам
            for measurer in measurers:
                try:
                    await bot.send_message(
                        chat_id=measurer.telegram_id,
                        text=notification_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"Отправлено уведомление замерщику {measurer.full_name} ({measurer.telegram_id})")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления замерщику {measurer.telegram_id}: {e}")

            # Также уведомляем администраторов
            for admin_id in settings.admin_ids_list:
                try:
                    admin_text = notification_text.replace(
                        "⏳ <i>Ожидаем назначения замерщика...</i>",
                        "👇 <b>Назначьте замерщика через команду или интерфейс бота</b>"
                    )

                    await bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"Отправлено уведомление администратору {admin_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления администратору {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о новой сделке: {e}", exc_info=True)


@log_notification("NEW_MEASUREMENT_TO_ADMIN")
async def send_new_measurement_to_admin(
    bot: Bot,
    admin_telegram_id: int,
    measurement: Measurement
):
    """
    Отправить уведомление администратору/руководителю о новом замере с запросом подтверждения

    Args:
        bot: Экземпляр бота
        admin_telegram_id: Telegram ID администратора/руководителя
        measurement: Объект замера
    """
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        # Формируем текст уведомления с информацией о распределении
        text = "🆕 <b>Новый замер - требуется подтверждение!</b>\n\n"
        text += measurement.get_info_text(detailed=True, show_admin_info=True)

        # Проверяем auto_assigned_measurer (предложенный системой)
        if measurement.auto_assigned_measurer:
            text += f"\n⚡️ <b>Система предлагает:</b> {measurement.auto_assigned_measurer.full_name}\n"
            text += "\n❓ <b>Подтвердите распределение или выберите другого замерщика:</b>"
        else:
            text += "\n⚠️ <b>Замерщик не был назначен автоматически</b>\n"
            text += "\n❓ <b>Выберите замерщика для этого замера:</b>"

        # Создаем клавиатуру с кнопками подтверждения и изменения
        builder = InlineKeyboardBuilder()

        if measurement.auto_assigned_measurer:
            # Замерщик был предложен - даем кнопки подтверждения и изменения
            builder.button(
                text="✅ Подтвердить предложенного",
                callback_data=f"confirm_assignment:{measurement.id}"
            )
            builder.button(
                text="🔄 Выбрать другого",
                callback_data=f"change_measurer:{measurement.id}"
            )
        else:
            # Замерщик не был предложен - только кнопка выбора
            builder.button(
                text="👷 Назначить замерщика",
                callback_data=f"change_measurer:{measurement.id}"
            )

        builder.adjust(1)
        keyboard = builder.as_markup()

        sent_message = await bot.send_message(
            chat_id=admin_telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        # Сохраняем message_id в БД для возможности удаления/редактирования
        from database import get_db, create_notification
        async for session in get_db():
            await create_notification(
                session=session,
                recipient_telegram_id=admin_telegram_id,
                message_text=text,
                notification_type="new_measurement_confirmation",
                measurement_id=measurement.id,
                is_sent=True,
                telegram_message_id=sent_message.message_id,
                telegram_chat_id=sent_message.chat.id
            )

        logger.info(f"Отправлено уведомление о замере #{measurement.id} администратору/руководителю {admin_telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления администратору {admin_telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке уведомления: {e}", exc_info=True)


@log_notification("ASSIGNMENT_TO_MEASURER")
async def send_assignment_notification_to_measurer(
    bot: Bot,
    measurer: User,
    measurement: Measurement,
    measurer_name: str = None
):
    """
    Отправить уведомление замерщику о назначении замера

    Args:
        bot: Экземпляр бота
        measurer: Объект замерщика
        measurement: Объект замера
        measurer_name: Имя замерщика (опционально, для корректного отображения)
    """
    from database import get_db, create_notification

    try:
        # Получаем актуальные данные из Altawin
        altawin_data = measurement.get_altawin_data()
        altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

        text = "📋 <b>Вам назначен новый замер!</b>\n\n"
        # Формируем текст вручную, чтобы избежать проблем с detached объектами
        text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

        # Основная информация
        text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
        text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
        text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
        text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

        text += "\n"

        # Контактные данные
        text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
        text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"
        text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {measurement.responsible_user_name or 'Данные не найдены в AmoCRM'}\n"

        text += "\n"

        # Параметры окон из Altawin
        text += f"🪟 <b>Количество окон:</b> {altawin_values['qty_izd']}\n"
        text += f"📐 <b>Площадь окон:</b> {altawin_values['area_izd']}\n\n"

        # Статус и замерщик
        text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

        # ВАЖНО: Используем переданное имя замерщика, а не из measurement.measurer
        # чтобы избежать проблем с detached объектами
        if measurer_name:
            text += f"👷 <b>Замерщик:</b> {measurer_name}\n"

        # Дополнительная информация
        from utils.timezone_utils import format_moscow_time
        text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

        if measurement.created_at:
            text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

        if measurement.assigned_at:
            text += f"📅 <b>Назначено:</b> {format_moscow_time(measurement.assigned_at)}\n"

        # Уведомление БЕЗ кнопок
        await bot.send_message(
            chat_id=measurer.telegram_id,
            text=text,
            parse_mode="HTML"
        )

        # Сохраняем уведомление в БД
        async for session in get_db():
            await create_notification(
                session=session,
                recipient_id=measurer.id,
                message_text=text,
                notification_type="assignment",
                measurement_id=measurement.id,
                is_sent=True
            )

        logger.info(f"Отправлено уведомление о назначении замера #{measurement.id} замерщику {measurer.telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления замерщику {measurer.telegram_id}: {e}")
        # Сохраняем неудачную попытку в БД
        try:
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=measurer.id,
                    message_text=text if 'text' in locals() else "Ошибка формирования текста",
                    notification_type="assignment",
                    measurement_id=measurement.id,
                    is_sent=False
                )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке уведомления: {e}", exc_info=True)


@log_notification("ASSIGNMENT_TO_MANAGER")
async def send_assignment_notification_to_manager(
    bot: Bot,
    manager: User,
    measurement: Measurement,
    measurer: User | None
):
    """
    Отправить уведомление менеджеру о назначении замерщика

    Args:
        bot: Экземпляр бота
        manager: Объект менеджера
        measurement: Объект замера
        measurer: Объект назначенного замерщика (может быть None)
    """
    from database import get_db, create_notification
    from utils.timezone_utils import format_moscow_time

    try:
        # Проверяем, что замерщик назначен
        if not measurer:
            logger.warning(f"Попытка отправить уведомление менеджеру без замерщика для замера #{measurement.id}")
            return

        # Получаем актуальные данные из Altawin
        altawin_data = measurement.get_altawin_data()
        altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

        text = "✅ <b>Замерщик назначен на ваш заказ</b>\n\n"
        text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

        # === БЛОК 1: Основная информация о заказе ===
        text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
        text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
        text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
        text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

        text += "\n"

        # === БЛОК 2: Контактные данные ===
        text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
        text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"

        text += "\n"

        # === БЛОК 3: Параметры окон (если есть) ===
        text += f"🪟 <b>Количество окон:</b> {altawin_values['qty_izd']}\n"
        text += f"📐 <b>Площадь окон:</b> {altawin_values['area_izd']}\n\n"

        # === БЛОК 4: Назначение и статус ===
        text += f"👷 <b>Замерщик:</b> {measurer.full_name}\n"
        text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

        # === БЛОК 5: Временные метки ===
        text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

        if measurement.created_at:
            text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

        if measurement.assigned_at:
            text += f"📅 <b>Назначено:</b> {format_moscow_time(measurement.assigned_at)}\n"

        await bot.send_message(
            chat_id=manager.telegram_id,
            text=text,
            parse_mode="HTML"
        )

        # Сохраняем уведомление в БД
        async for session in get_db():
            await create_notification(
                session=session,
                recipient_id=manager.id,
                message_text=text,
                notification_type="manager_notification",
                measurement_id=measurement.id,
                is_sent=True
            )

        logger.info(f"Отправлено уведомление о назначении менеджеру {manager.telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления менеджеру {manager.telegram_id}: {e}")
        # Сохраняем неудачную попытку в БД
        try:
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=manager.id,
                    message_text=text if 'text' in locals() else "Ошибка формирования текста",
                    notification_type="manager_notification",
                    measurement_id=measurement.id,
                    is_sent=False
                )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке уведомления: {e}", exc_info=True)


@log_notification("NEW_MEASUREMENT_TO_OBSERVERS")
async def send_new_measurement_notification_to_observers(
    bot: Bot,
    measurement: Measurement
):
    """
    Отправить уведомление наблюдателям о НОВОМ замере (без информации об автоназначении)

    Args:
        bot: Экземпляр бота
        measurement: Объект замера
    """
    from database import get_db, create_notification, get_all_observers
    from utils.timezone_utils import format_moscow_time

    try:
        # Получаем актуальные данные из Altawin
        altawin_data = measurement.get_altawin_data()
        altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

        # Получаем всех активных наблюдателей
        async for session in get_db():
            observers = await get_all_observers(session)

            if not observers:
                logger.info("Нет активных наблюдателей для уведомления")
                return

            # Формируем текст уведомления (БЕЗ информации об автоматическом распределении)
            text = "🆕 <b>Новый замер (Наблюдатель)</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

            # === БЛОК 1: Основная информация о заказе ===
            text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
            text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
            text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
            text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

            text += "\n"

            # === БЛОК 2: Контактные данные ===
            text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
            text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"
            text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {measurement.responsible_user_name or 'Данные не найдены в AmoCRM'}\n"

            text += "\n"

            # === БЛОК 3: Параметры окон (если есть) ===
            text += f"🪟 <b>Количество окон:</b> {altawin_values['qty_izd']}\n"
            text += f"📐 <b>Площадь окон:</b> {altawin_values['area_izd']}\n\n"

            # === БЛОК 4: Статус (БЕЗ информации о замерщике!) ===
            text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

            # Добавляем информацию о менеджере, если есть
            if measurement.manager:
                text += f"💼 <b>Менеджер:</b> {measurement.manager.full_name}\n"

            # === БЛОК 5: Временные метки ===
            text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

            if measurement.created_at:
                text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

            text += "\n⏳ <i>Ожидает подтверждения распределения...</i>"

            # Отправляем уведомление каждому наблюдателю
            for observer in observers:
                try:
                    await bot.send_message(
                        chat_id=observer.telegram_id,
                        text=text,
                        parse_mode="HTML"
                    )

                    # Сохраняем уведомление в БД
                    async for session in get_db():
                        await create_notification(
                            session=session,
                            recipient_id=observer.id,
                            message_text=text,
                            notification_type="observer_new_measurement",
                            measurement_id=measurement.id,
                            is_sent=True
                        )
                        break

                    logger.info(f"Отправлено уведомление о новом замере наблюдателю {observer.telegram_id} ({observer.full_name})")

                except TelegramAPIError as e:
                    logger.error(f"Ошибка отправки уведомления наблюдателю {observer.telegram_id}: {e}")
                    # Сохраняем неудачную попытку в БД
                    try:
                        async for session in get_db():
                            await create_notification(
                                session=session,
                                recipient_id=observer.id,
                                message_text=text,
                                notification_type="observer_new_measurement",
                                measurement_id=measurement.id,
                                is_sent=False
                            )
                            break
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Неожиданная ошибка при отправке уведомления наблюдателю {observer.telegram_id}: {e}", exc_info=True)

            break  # Выходим из цикла get_db()

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений наблюдателям: {e}", exc_info=True)


@log_notification("ASSIGNMENT_TO_OBSERVERS")
async def send_assignment_notification_to_observers(
    bot: Bot,
    measurement: Measurement,
    measurer: User | None
):
    """
    Отправить уведомление наблюдателям о назначении замерщика

    Args:
        bot: Экземпляр бота
        measurement: Объект замера
        measurer: Объект назначенного замерщика (может быть None)
    """
    from database import get_db, create_notification, get_all_observers
    from utils.timezone_utils import format_moscow_time

    try:
        # Получаем актуальные данные из Altawin
        altawin_data = measurement.get_altawin_data()
        altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

        # Получаем всех активных наблюдателей
        async for session in get_db():
            observers = await get_all_observers(session)

            if not observers:
                logger.info("Нет активных наблюдателей для уведомления")
                return

            # Проверяем, что замерщик назначен
            if not measurer:
                logger.warning(f"Попытка отправить уведомление наблюдателям без замерщика для замера #{measurement.id}")
                return

            # Формируем текст уведомления
            text = "✅ <b>Замер распределен (Наблюдатель)</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

            # === БЛОК 1: Основная информация о заказе ===
            text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
            text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
            text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
            text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

            text += "\n"

            # === БЛОК 2: Контактные данные ===
            text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
            text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"
            text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {measurement.responsible_user_name or 'Данные не найдены в AmoCRM'}\n"

            text += "\n"

            # === БЛОК 3: Параметры окон (если есть) ===
            text += f"🪟 <b>Количество окон:</b> {altawin_values['qty_izd']}\n"
            text += f"📐 <b>Площадь окон:</b> {altawin_values['area_izd']}\n\n"

            # === БЛОК 4: Назначение и статус ===
            text += f"👷 <b>Замерщик:</b> {measurer.full_name}\n"
            text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

            # Добавляем информацию о менеджере, если есть
            if measurement.manager:
                text += f"💼 <b>Менеджер:</b> {measurement.manager.full_name}\n"

            # === БЛОК 5: Временные метки ===
            text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

            if measurement.created_at:
                text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

            if measurement.assigned_at:
                text += f"📅 <b>Назначено:</b> {format_moscow_time(measurement.assigned_at)}\n"

            # Отправляем уведомление каждому наблюдателю
            for observer in observers:
                try:
                    await bot.send_message(
                        chat_id=observer.telegram_id,
                        text=text,
                        parse_mode="HTML"
                    )

                    # Сохраняем уведомление в БД
                    async for session in get_db():
                        await create_notification(
                            session=session,
                            recipient_id=observer.id,
                            message_text=text,
                            notification_type="observer_notification",
                            measurement_id=measurement.id,
                            is_sent=True
                        )
                        break

                    logger.info(f"Отправлено уведомление о назначении наблюдателю {observer.telegram_id} ({observer.full_name})")

                except TelegramAPIError as e:
                    logger.error(f"Ошибка отправки уведомления наблюдателю {observer.telegram_id}: {e}")
                    # Сохраняем неудачную попытку в БД
                    try:
                        async for session in get_db():
                            await create_notification(
                                session=session,
                                recipient_id=observer.id,
                                message_text=text,
                                notification_type="observer_notification",
                                measurement_id=measurement.id,
                                is_sent=False
                            )
                            break
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Неожиданная ошибка при отправке уведомления наблюдателю {observer.telegram_id}: {e}", exc_info=True)

            break  # Выходим из цикла get_db()

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений наблюдателям: {e}", exc_info=True)


@log_notification("STATUS_CHANGE")
async def send_status_change_notification(
    bot: Bot,
    user: User,
    measurement: Measurement,
    old_status: str,
    new_status: str
):
    """
    Отправить уведомление об изменении статуса замера

    Args:
        bot: Экземпляр бота
        user: Пользователь для уведомления
        measurement: Объект замера
        old_status: Старый статус
        new_status: Новый статус
    """
    try:
        # Получаем актуальные данные из Altawin
        altawin_data = measurement.get_altawin_data()
        altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

        text = "🔄 <b>Изменен статус замера</b>\n\n"
        text += f"📋 <b>Замер #{measurement.id}</b>\n"
        text += f"👤 <b>Клиент:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
        text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n\n"
        text += f"<b>Старый статус:</b> {old_status}\n"
        text += f"<b>Новый статус:</b> {new_status}\n"

        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML"
        )

        logger.info(f"Отправлено уведомление об изменении статуса пользователю {user.telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления пользователю {user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке уведомления: {e}", exc_info=True)


@log_notification("MEASURER_CHANGE")
async def send_measurer_change_notification(
    bot: Bot,
    old_measurer: Optional[User],
    new_measurer: User,
    measurement: Measurement,
    manager: Optional[User] = None
):
    """
    Отправить уведомления при изменении замерщика

    Args:
        bot: Экземпляр бота
        old_measurer: Предыдущий замерщик (если был)
        new_measurer: Новый замерщик
        measurement: Объект замера
        manager: Менеджер (если есть)
    """
    from database import get_db, create_notification

    # Получаем актуальные данные из Altawin
    altawin_data = measurement.get_altawin_data()
    altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

    # Уведомление старому замерщику
    if old_measurer:
        try:
            text = "⚠️ <b>Вы сняты с замера</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n"
            text += f"👤 <b>Клиент:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
            text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n\n"
            text += f"Замер переназначен на: {new_measurer.full_name}"

            await bot.send_message(
                chat_id=old_measurer.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=old_measurer.id,
                    message_text=text,
                    notification_type="change",
                    measurement_id=measurement.id,
                    is_sent=True
                )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления старому замерщику: {e}")

    # Уведомление новому замерщику
    await send_assignment_notification_to_measurer(bot, new_measurer, measurement, new_measurer.full_name)

    # Уведомление менеджеру
    if manager:
        try:
            from utils.timezone_utils import format_moscow_time

            text = "🔄 <b>Изменен замерщик на вашем заказе</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

            # === БЛОК 1: Основная информация о заказе ===
            text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
            text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
            text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
            text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

            text += "\n"

            # === БЛОК 2: Контактные данные ===
            text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
            text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"

            text += "\n"

            # === БЛОК 3: Параметры окон (если есть) ===
            text += f"🪟 <b>Количество окон:</b> {altawin_values['qty_izd']}\n"
            text += f"📐 <b>Площадь окон:</b> {altawin_values['area_izd']}\n\n"

            # === БЛОК 4: Изменение замерщика ===
            text += "⚠️ <b>ИЗМЕНЕНИЕ ЗАМЕРЩИКА:</b>\n"
            if old_measurer:
                text += f"   ❌ Старый: {old_measurer.full_name}\n"

            text += f"   ✅ Новый: {new_measurer.full_name}\n"
            text += f"\n📊 <b>Статус:</b> {measurement.status_text}\n"

            # === БЛОК 5: Дополнительная информация ===
            text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

            if measurement.created_at:
                text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

            await bot.send_message(
                chat_id=manager.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=manager.id,
                    message_text=text,
                    notification_type="change",
                    measurement_id=measurement.id,
                    is_sent=True
                )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления менеджеру: {e}")


@log_notification("COMPLETION")
async def send_completion_notification(
    bot: Bot,
    measurement: Measurement,
    manager: Optional[User] = None
):
    """
    Отправить уведомление о завершении замера менеджеру, администраторам и руководителям

    Args:
        bot: Экземпляр бота
        measurement: Объект замера
        manager: Менеджер (если есть)
    """
    from database import get_db, create_notification, get_all_admins, get_all_supervisors
    from utils.timezone_utils import format_moscow_time

    # Получаем актуальные данные из Altawin
    altawin_data = measurement.get_altawin_data()
    altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

    # Формируем развернутое текст уведомления
    text = "✅ <b>Замер выполнен!</b>\n\n"
    text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

    # === БЛОК 1: Основная информация о заказе ===
    text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
    text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
    text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
    text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

    text += "\n"

    # === БЛОК 2: Контактные данные ===
    text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
    text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"
    text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {measurement.responsible_user_name or 'Данные не найдены в AmoCRM'}\n"

    text += "\n"

    # === БЛОК 3: Параметры окон (если есть) ===
    text += f"🪟 <b>Количество окон:</b> {altawin_values['qty_izd']}\n"
    text += f"📐 <b>Площадь окон:</b> {altawin_values['area_izd']}\n\n"

    # === БЛОК 4: Результат выполнения ===
    if measurement.measurer:
        text += f"👷 <b>Замерщик:</b> {measurement.measurer.full_name}\n"

    text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

    # === БЛОК 5: Временные метки ===
    text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

    if measurement.created_at:
        text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

    if measurement.assigned_at:
        text += f"📅 <b>Назначено:</b> {format_moscow_time(measurement.assigned_at)}\n"

    if measurement.completed_at:
        text += f"✅ <b>Завершено:</b> {format_moscow_time(measurement.completed_at)}\n"

    logger.info(f"Начало отправки уведомлений о завершении замера #{measurement.id}")

    # Получаем список администраторов и руководителей
    admins = []
    supervisors = []

    try:
        async for session in get_db():
            admins = await get_all_admins(session)
            supervisors = await get_all_supervisors(session)
            logger.info(f"Найдено администраторов: {len(admins)}, руководителей: {len(supervisors)}")
            break
    except Exception as e:
        logger.error(f"Ошибка получения списка администраторов и руководителей: {e}", exc_info=True)

    # Отправляем уведомление менеджеру
    if manager:
        try:
            await bot.send_message(
                chat_id=manager.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=manager.id,
                    message_text=text,
                    notification_type="completion",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление о завершении менеджеру {manager.telegram_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о завершении менеджеру: {e}", exc_info=True)

    # Отправляем уведомления администраторам
    for admin in admins:
        try:
            await bot.send_message(
                chat_id=admin.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=admin.id,
                    message_text=text,
                    notification_type="completion",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление о завершении администратору {admin.telegram_id} ({admin.full_name})")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору {admin.telegram_id}: {e}", exc_info=True)

    # Отправляем уведомления руководителям
    for supervisor in supervisors:
        try:
            await bot.send_message(
                chat_id=supervisor.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=supervisor.id,
                    message_text=text,
                    notification_type="completion",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление о завершении руководителю {supervisor.telegram_id} ({supervisor.full_name})")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления руководителю {supervisor.telegram_id}: {e}", exc_info=True)

    logger.info(f"Завершена отправка уведомлений о завершении замера #{measurement.id}")


async def send_cancellation_notification(
    bot: Bot,
    measurement: Measurement,
    cancelled_by: User,
    manager: Optional[User] = None
):
    """
    Отправить уведомление об отмене замера всем участникам

    Args:
        bot: Экземпляр бота
        measurement: Объект замера
        cancelled_by: Пользователь, который отменил замер
        manager: Менеджер (если есть)
    """
    from database import get_db, create_notification, get_all_admins, get_all_supervisors, get_all_observers
    from utils.timezone_utils import format_moscow_time

    # Получаем актуальные данные из Altawin
    altawin_data = measurement.get_altawin_data()
    altawin_values = get_altawin_display_values(altawin_data, measurement.contact_phone)

    # Формируем текст уведомления
    text = "❌ <b>Замер отменен</b>\n\n"
    text += f"📋 <b>Замер #{measurement.id}</b>\n\n"

    # === БЛОК 1: Основная информация о заказе ===
    text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
    text += f"🔢 <b>Номер заказа:</b> {altawin_values['order_number']}\n"
    text += f"📍 <b>Адрес:</b> {altawin_values['address']}\n"
    text += f"🚚 <b>Зона доставки:</b> {altawin_values['zone']}\n"

    text += "\n"

    # === БЛОК 2: Контактные данные ===
    text += f"👤 <b>Контакт:</b> {measurement.contact_name or 'Данные не найдены в AmoCRM'}\n"
    text += f"📞 <b>Телефон:</b> {altawin_values['phone']}\n"
    text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {measurement.responsible_user_name or 'Данные не найдены в AmoCRM'}\n"

    text += "\n"

    # === БЛОК 3: Информация об отмене ===
    if measurement.measurer:
        text += f"👷 <b>Замерщик был назначен:</b> {measurement.measurer.full_name}\n"

    text += f"🚫 <b>Отменено пользователем:</b> {cancelled_by.full_name}\n"
    text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

    # === БЛОК 4: Временные метки ===
    text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {measurement.amocrm_lead_id}\n"

    if measurement.created_at:
        text += f"📅 <b>Создано:</b> {format_moscow_time(measurement.created_at)}\n"

    if measurement.assigned_at:
        text += f"📅 <b>Назначено:</b> {format_moscow_time(measurement.assigned_at)}\n"

    if measurement.updated_at:
        text += f"❌ <b>Отменено:</b> {format_moscow_time(measurement.updated_at)}\n"

    logger.info(f"Начало отправки уведомлений об отмене замера #{measurement.id}")

    # Получаем список администраторов, руководителей и наблюдателей
    admins = []
    supervisors = []
    observers = []

    try:
        async for session in get_db():
            admins = await get_all_admins(session)
            supervisors = await get_all_supervisors(session)
            observers = await get_all_observers(session)
            logger.info(f"Найдено администраторов: {len(admins)}, руководителей: {len(supervisors)}, наблюдателей: {len(observers)}")
            break
    except Exception as e:
        logger.error(f"Ошибка получения списков пользователей: {e}", exc_info=True)

    # Отправляем уведомление менеджеру
    if manager:
        try:
            await bot.send_message(
                chat_id=manager.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=manager.id,
                    message_text=text,
                    notification_type="cancellation",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление об отмене менеджеру {manager.telegram_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об отмене менеджеру: {e}", exc_info=True)

    # Отправляем уведомление замерщику (если он не тот, кто отменил)
    if measurement.measurer and measurement.measurer.id != cancelled_by.id:
        try:
            await bot.send_message(
                chat_id=measurement.measurer.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=measurement.measurer.id,
                    message_text=text,
                    notification_type="cancellation",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление об отмене замерщику {measurement.measurer.telegram_id} ({measurement.measurer.full_name})")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления замерщику {measurement.measurer.telegram_id}: {e}", exc_info=True)

    # Отправляем уведомления администраторам
    for admin in admins:
        # Не отправляем тому, кто отменил
        if admin.id == cancelled_by.id:
            continue

        try:
            await bot.send_message(
                chat_id=admin.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=admin.id,
                    message_text=text,
                    notification_type="cancellation",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление об отмене администратору {admin.telegram_id} ({admin.full_name})")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору {admin.telegram_id}: {e}", exc_info=True)

    # Отправляем уведомления руководителям
    for supervisor in supervisors:
        # Не отправляем тому, кто отменил
        if supervisor.id == cancelled_by.id:
            continue

        try:
            await bot.send_message(
                chat_id=supervisor.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=supervisor.id,
                    message_text=text,
                    notification_type="cancellation",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление об отмене руководителю {supervisor.telegram_id} ({supervisor.full_name})")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления руководителю {supervisor.telegram_id}: {e}", exc_info=True)

    # Отправляем уведомления наблюдателям
    for observer in observers:
        # Не отправляем тому, кто отменил
        if observer.id == cancelled_by.id:
            continue

        try:
            await bot.send_message(
                chat_id=observer.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            # Сохраняем уведомление в БД
            async for session in get_db():
                await create_notification(
                    session=session,
                    recipient_id=observer.id,
                    message_text=text,
                    notification_type="cancellation",
                    measurement_id=measurement.id,
                    is_sent=True
                )
                break

            logger.info(f"Отправлено уведомление об отмене наблюдателю {observer.telegram_id} ({observer.full_name})")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления наблюдателю {observer.telegram_id}: {e}", exc_info=True)

    logger.info(f"Завершена отправка уведомлений об отмене замера #{measurement.id}")



