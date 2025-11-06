"""Система уведомлений для пользователей"""
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from loguru import logger
from typing import Optional

from database.models import Measurement, User
from bot.keyboards.inline import get_measurers_keyboard, get_measurement_actions_keyboard


async def send_new_measurement_to_admin(
    bot: Bot,
    admin_telegram_id: int,
    measurement: Measurement
):
    """
    Отправить уведомление администратору о новом замере

    Args:
        bot: Экземпляр бота
        admin_telegram_id: Telegram ID администратора
        measurement: Объект замера
    """
    try:
        from database import get_db, get_all_measurers

        # Получаем список замерщиков для кнопок
        async for session in get_db():
            measurers = await get_all_measurers(session)

            if not measurers:
                # Если нет замерщиков, отправляем просто уведомление
                text = "⚠️ <b>Новый замер, но нет доступных замерщиков!</b>\n\n"
                text += measurement.get_info_text(detailed=True)

                await bot.send_message(
                    chat_id=admin_telegram_id,
                    text=text,
                    parse_mode="HTML"
                )
            else:
                # Отправляем уведомление с кнопками выбора замерщика
                text = "🆕 <b>Новый замер!</b>\n\n"
                text += measurement.get_info_text(detailed=True)
                text += "\n\n👇 <b>Выберите замерщика:</b>"

                keyboard = get_measurers_keyboard(measurers, measurement.id)

                await bot.send_message(
                    chat_id=admin_telegram_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            logger.info(f"Отправлено уведомление о замере #{measurement.id} администратору {admin_telegram_id}")

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
    try:
        text = "📋 <b>Вам назначен новый замер!</b>\n\n"
        text += measurement.get_info_text(detailed=True)

        keyboard = get_measurement_actions_keyboard(
            measurement.id,
            is_admin=False,
            current_status=measurement.status
        )

        await bot.send_message(
            chat_id=measurer.telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        logger.info(f"Отправлено уведомление о назначении замера #{measurement.id} замерщику {measurer.telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления замерщику {measurer.telegram_id}: {e}")
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
    try:
        text = "✅ <b>Замерщик назначен на ваш заказ</b>\n\n"
        text += f"📋 <b>Замер #{measurement.id}</b>\n"
        text += f"👤 <b>Клиент:</b> {measurement.client_name}\n"
        text += f"📍 <b>Адрес:</b> {measurement.address}\n"
        text += f"👷 <b>Замерщик:</b> {measurer.full_name}\n"
        text += f"📊 <b>Статус:</b> {measurement.status_text}\n"

        await bot.send_message(
            chat_id=manager.telegram_id,
            text=text,
            parse_mode="HTML"
        )

        logger.info(f"Отправлено уведомление о назначении менеджеру {manager.telegram_id}")

    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления менеджеру {manager.telegram_id}: {e}")
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
    # Уведомление старому замерщику
    if old_measurer:
        try:
            text = "⚠️ <b>Вы сняты с замера</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n"
            text += f"👤 <b>Клиент:</b> {measurement.client_name}\n"
            text += f"📍 <b>Адрес:</b> {measurement.address}\n\n"
            text += f"Замер переназначен на: {new_measurer.full_name}"

            await bot.send_message(
                chat_id=old_measurer.telegram_id,
                text=text,
                parse_mode="HTML"
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
            text += f"👤 <b>Клиент:</b> {measurement.client_name}\n"
            text += f"📍 <b>Адрес:</b> {measurement.address}\n\n"

            if old_measurer:
                text += f"<b>Старый замерщик:</b> {old_measurer.full_name}\n"

            text += f"<b>Новый замерщик:</b> {new_measurer.full_name}\n"

            await bot.send_message(
                chat_id=manager.telegram_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления менеджеру: {e}")


async def send_completion_notification(
    bot: Bot,
    measurement: Measurement,
    manager: Optional[User] = None
):
    """
    Отправить уведомление о завершении замера

    Args:
        bot: Экземпляр бота
        measurement: Объект замера
        manager: Менеджер (если есть)
    """
    if manager:
        try:
            text = "✅ <b>Замер выполнен!</b>\n\n"
            text += f"📋 <b>Замер #{measurement.id}</b>\n"
            text += f"👤 <b>Клиент:</b> {measurement.client_name}\n"
            text += f"📍 <b>Адрес:</b> {measurement.address}\n"

            if measurement.measurer:
                text += f"👷 <b>Замерщик:</b> {measurement.measurer.full_name}\n"

            if measurement.completed_at:
                text += f"📅 <b>Завершено:</b> {measurement.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

            await bot.send_message(
                chat_id=manager.telegram_id,
                text=text,
                parse_mode="HTML"
            )

            logger.info(f"Отправлено уведомление о завершении менеджеру {manager.telegram_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о завершении: {e}")
