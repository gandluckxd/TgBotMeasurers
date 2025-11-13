"""Система уведомлений для пользователей"""
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from loguru import logger
from typing import Optional, Dict, Any

from database.models import Measurement, User
from bot.keyboards.inline import get_measurers_keyboard, get_measurement_actions_keyboard


def format_lead_info_for_notification(full_info: Dict[str, Any]) -> str:
    """
    Форматирование информации о сделке из AmoCRM для красивого уведомления

    Args:
        full_info: Полная информация о сделке из AmoCRM API

    Returns:
        Отформатированный текст уведомления
    """
    lead = full_info.get("lead", {})
    contacts = full_info.get("contacts", [])
    responsible_user = full_info.get("responsible_user")

    # Основная информация
    text = "🆕 <b>Новая заявка из AmoCRM!</b>\n\n"

    # Название сделки
    lead_name = lead.get("name", "Без названия")
    lead_id = lead.get("id")
    text += f"📋 <b>Сделка:</b> {lead_name} (ID: {lead_id})\n"

    # Стоимость
    price = lead.get("price", 0)
    if price:
        text += f"💰 <b>Сумма:</b> {price:,.0f} ₽\n"

    text += "\n"

    # Информация о клиенте
    if contacts:
        contact = contacts[0]  # Берем первый контакт
        contact_name = contact.get("name", "Не указано")
        text += f"👤 <b>Клиент:</b> {contact_name}\n"

        # Ищем телефон и email в кастомных полях контакта
        custom_fields = contact.get("custom_fields_values", [])

        for field in custom_fields:
            field_code = field.get("field_code")
            values = field.get("values", [])

            if values:
                value = values[0].get("value")

                if field_code == "PHONE":
                    text += f"📱 <b>Телефон:</b> {value}\n"
                elif field_code == "EMAIL":
                    text += f"📧 <b>Email:</b> {value}\n"
    else:
        text += "👤 <b>Клиент:</b> Не указан\n"

    # Адрес из кастомных полей сделки
    lead_custom_fields = lead.get("custom_fields_values", [])
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
        text += f"📍 <b>Адрес:</b> Не указан\n"

    # Ответственный менеджер
    if responsible_user:
        manager_name = responsible_user.get("name", "Не указан")
        text += f"\n👨‍💼 <b>Менеджер в AmoCRM:</b> {manager_name}\n"

    # Дата создания
    created_at = lead.get("created_at")
    if created_at:
        from datetime import datetime
        created_date = datetime.fromtimestamp(created_at)
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
            from bot import get_bot
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
        text += measurement.get_info_text(detailed=True)

        if measurement.measurer:
            text += f"\n⚡️ <b>Автоматически распределен на:</b> {measurement.measurer.full_name}\n"
            text += "\n❓ <b>Подтвердите распределение или выберите другого замерщика:</b>"
        else:
            text += "\n⚠️ <b>Замерщик не был назначен автоматически</b>\n"
            text += "\n❓ <b>Выберите замерщика для этого замера:</b>"

        # Создаем клавиатуру с кнопками подтверждения и изменения
        builder = InlineKeyboardBuilder()

        if measurement.measurer:
            # Замерщик был назначен - даем кнопки подтверждения и изменения
            builder.button(
                text="✅ Подтвердить распределение",
                callback_data=f"confirm_assignment:{measurement.id}"
            )
            builder.button(
                text="🔄 Изменить замерщика",
                callback_data=f"change_measurer:{measurement.id}"
            )
        else:
            # Замерщик не был назначен - только кнопка выбора
            builder.button(
                text="👷 Назначить замерщика",
                callback_data=f"change_measurer:{measurement.id}"
            )

        builder.adjust(1)
        keyboard = builder.as_markup()

        await bot.send_message(
            chat_id=admin_telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        logger.info(f"Отправлено уведомление о замере #{measurement.id} администратору/руководителю {admin_telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления администратору {admin_telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке уведомления: {e}", exc_info=True)


async def send_assignment_notification_to_measurer(
    bot: Bot,
    measurer: User,
    measurement: Measurement
):
    """
    Отправить уведомление замерщику о назначении замера

    Args:
        bot: Экземпляр бота
        measurer: Объект замерщика
        measurement: Объект замера
    """
    from database import get_db, create_notification

    try:
        text = "📋 <b>Вам назначен новый замер!</b>\n\n"
        text += measurement.get_info_text(detailed=True)

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


async def send_assignment_notification_to_manager(
    bot: Bot,
    manager: User,
    measurement: Measurement,
    measurer: User
):
    """
    Отправить уведомление менеджеру о назначении замерщика

    Args:
        bot: Экземпляр бота
        manager: Объект менеджера
        measurement: Объект замера
        measurer: Объект назначенного замерщика
    """
    from database import get_db, create_notification

    try:
        text = "✅ <b>Замерщик назначен на ваш заказ</b>\n\n"
        text += f"📋 <b>Замер #{measurement.id}</b>\n"
        text += f"👤 <b>Клиент:</b> {measurement.contact_name or 'Не указан'}\n"
        text += f"📍 <b>Адрес:</b> {measurement.address or 'Не указан'}\n"
        text += f"👷 <b>Замерщик:</b> {measurer.full_name}\n"
        text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

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
        text = "🔄 <b>Изменен статус замера</b>\n\n"
        text += f"📋 <b>Замер #{measurement.id}</b>\n"
        text += f"👤 <b>Клиент:</b> {measurement.client_name}\n"
        text += f"📍 <b>Адрес:</b> {measurement.address}\n\n"
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

    # Уведомление старому замерщику
    if old_measurer:
        try:
            text = "⚠️ <b>Вы сняты с замера</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n"
            text += f"👤 <b>Клиент:</b> {measurement.contact_name or 'Не указан'}\n"
            text += f"📍 <b>Адрес:</b> {measurement.address or 'Не указан'}\n\n"
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
    await send_assignment_notification_to_measurer(bot, new_measurer, measurement)

    # Уведомление менеджеру
    if manager:
        try:
            text = "🔄 <b>Изменен замерщик на вашем заказе</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n"
            text += f"👤 <b>Клиент:</b> {measurement.contact_name or 'Не указан'}\n"
            text += f"📍 <b>Адрес:</b> {measurement.address or 'Не указан'}\n\n"

            if old_measurer:
                text += f"<b>Старый замерщик:</b> {old_measurer.full_name}\n"

            text += f"<b>Новый замерщик:</b> {new_measurer.full_name}\n"

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

    # Формируем текст уведомления
    text = "✅ <b>Замер выполнен!</b>\n\n"
    text += f"📋 <b>Замер #{measurement.id}</b>\n"
    text += f"👤 <b>Клиент:</b> {measurement.contact_name or 'Не указан'}\n"
    text += f"📍 <b>Адрес:</b> {measurement.address or 'Не указан'}\n"

    if measurement.measurer:
        text += f"👷 <b>Замерщик:</b> {measurement.measurer.full_name}\n"

    if measurement.completed_at:
        text += f"📅 <b>Завершено:</b> {measurement.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

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
