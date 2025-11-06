"""Обработчики команд замерщика"""
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from database import (
    get_db,
    get_user_by_telegram_id,
    get_measurement_by_id,
    get_measurements_by_measurer,
    get_or_create_user,
    MeasurementStatus,
    UserRole
)
from bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_measurement_actions_keyboard,
    get_back_button
)
from bot.utils.notifications import (
    send_status_change_notification,
    send_completion_notification
)

# Создаем роутер для команд замерщика
measurer_router = Router()


@measurer_router.message(Command("start"))
async def cmd_start_measurer(message: Message):
    """Обработчик команды /start для замерщика"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        # Если пользователь не существует, создаем его как замерщика
        if not user:
            user = await get_or_create_user(
                session=session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                role=UserRole.MEASURER
            )

        # Проверяем роль
        if user.role != UserRole.MEASURER:
            # Это администратор или менеджер, пропускаем
            return

        text = f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
        text += "Вы вошли как <b>Замерщик</b>\n\n"
        text += "📋 Используйте меню ниже для управления вашими замерами:\n\n"
        text += "Доступные команды:\n"
        text += "/menu - Главное меню\n"
        text += "/my - Мои замеры\n"

        keyboard = get_main_menu_keyboard("measurer")

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@measurer_router.message(Command("menu"))
async def cmd_menu_measurer(message: Message):
    """Обработчик команды /menu для замерщика"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.MEASURER:
            return

        keyboard = get_main_menu_keyboard("measurer")
        await message.answer("📋 <b>Главное меню замерщика:</b>", reply_markup=keyboard, parse_mode="HTML")


@measurer_router.message(Command("my"))
async def cmd_my_measurements(message: Message):
    """Показать мои замеры"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.MEASURER:
            await message.answer("⚠️ У вас нет доступа к этой команде.")
            return

        # Получаем все активные замеры замерщика
        measurements = await get_measurements_by_measurer(session, user.id)

        # Фильтруем только незавершенные
        active_measurements = [
            m for m in measurements
            if m.status not in [MeasurementStatus.COMPLETED, MeasurementStatus.CANCELLED]
        ]

        if not active_measurements:
            await message.answer("✅ У вас нет активных замеров")
            return

        text = f"📋 <b>Ваши активные замеры ({len(active_measurements)}):</b>\n\n"

        for measurement in active_measurements:
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=False)
            text += "\n"

        await message.answer(text, parse_mode="HTML")

        # Отправляем каждый замер с кнопками действий
        for measurement in active_measurements:
            msg_text = measurement.get_info_text(detailed=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=False,
                current_status=measurement.status
            )

            await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")


@measurer_router.callback_query(F.data.startswith("status:"))
async def handle_status_change(callback: CallbackQuery):
    """Обработка изменения статуса замера"""
    try:
        # Парсим callback data: status:measurement_id:new_status
        parts = callback.data.split(":")
        measurement_id = int(parts[1])
        new_status_str = parts[2]

        async for session in get_db():
            # Получаем пользователя
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            # Получаем замер
            measurement = await get_measurement_by_id(session, measurement_id)

            if not measurement:
                await callback.answer("❌ Замер не найден", show_alert=True)
                return

            # Проверяем права доступа
            if user.role == UserRole.MEASURER and measurement.measurer_id != user.id:
                await callback.answer("⚠️ Это не ваш замер", show_alert=True)
                return

            # Сохраняем старый статус
            old_status = measurement.status
            old_status_text = measurement.status_text

            # Обновляем статус
            new_status = MeasurementStatus(new_status_str)
            measurement.status = new_status

            # Обновляем временные метки
            if new_status == MeasurementStatus.COMPLETED:
                measurement.completed_at = datetime.now()
            elif new_status == MeasurementStatus.IN_PROGRESS and not measurement.assigned_at:
                measurement.assigned_at = datetime.now()

            await session.commit()
            await session.refresh(measurement)

            # Обновляем сообщение
            new_text = f"✅ <b>Статус обновлен!</b>\n\n"
            new_text += measurement.get_info_text(detailed=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=(user.role == UserRole.ADMIN),
                current_status=measurement.status
            )

            await callback.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")

            # Отправляем уведомления
            if measurement.manager:
                await send_status_change_notification(
                    callback.bot,
                    measurement.manager,
                    measurement,
                    old_status_text,
                    measurement.status_text
                )

                # Если замер завершен, отправляем специальное уведомление
                if new_status == MeasurementStatus.COMPLETED:
                    await send_completion_notification(
                        callback.bot,
                        measurement,
                        measurement.manager
                    )

            status_messages = {
                MeasurementStatus.IN_PROGRESS: "🔄 Замер в процессе выполнения",
                MeasurementStatus.COMPLETED: "✅ Замер завершен",
                MeasurementStatus.CANCELLED: "❌ Замер отменен",
            }

            await callback.answer(status_messages.get(new_status, "✅ Статус обновлен"))
            logger.info(f"Статус замера #{measurement.id} изменен с {old_status.value} на {new_status.value}")

    except Exception as e:
        logger.error(f"Ошибка при изменении статуса: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)


@measurer_router.callback_query(F.data.startswith("details:"))
async def handle_details(callback: CallbackQuery):
    """Показать детальную информацию о замере"""
    try:
        measurement_id = int(callback.data.split(":")[1])

        async for session in get_db():
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            measurement = await get_measurement_by_id(session, measurement_id)

            if not measurement:
                await callback.answer("❌ Замер не найден", show_alert=True)
                return

            # Проверяем права доступа
            if user.role == UserRole.MEASURER and measurement.measurer_id != user.id:
                await callback.answer("⚠️ Это не ваш замер", show_alert=True)
                return

            text = measurement.get_info_text(detailed=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=(user.role == UserRole.ADMIN),
                current_status=measurement.status
            )

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при показе деталей: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при показе деталей", show_alert=True)


@measurer_router.callback_query(F.data.startswith("my:"))
async def handle_my_measurements(callback: CallbackQuery):
    """Обработка запросов моих замеров"""
    try:
        status_filter = callback.data.split(":")[1]

        async for session in get_db():
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user or user.role != UserRole.MEASURER:
                await callback.answer("⚠️ У вас нет доступа", show_alert=True)
                return

            # Получаем замеры замерщика
            if status_filter == "assigned":
                measurements = await get_measurements_by_measurer(
                    session, user.id, MeasurementStatus.ASSIGNED
                )
                title = "📋 Назначенные замеры"

            elif status_filter == "in_progress":
                measurements = await get_measurements_by_measurer(
                    session, user.id, MeasurementStatus.IN_PROGRESS
                )
                title = "🔄 Замеры в процессе"

            elif status_filter == "completed":
                measurements = await get_measurements_by_measurer(
                    session, user.id, MeasurementStatus.COMPLETED
                )
                title = "✅ Выполненные замеры"
            else:
                await callback.answer("❌ Неизвестный фильтр")
                return

            if not measurements:
                text = f"{title}\n\n❌ Нет замеров"
            else:
                text = f"<b>{title} ({len(measurements)}):</b>\n\n"

                for measurement in measurements[:10]:  # Показываем первые 10
                    text += f"━━━━━━━━━━━━━━━\n"
                    text += measurement.get_info_text(detailed=False)
                    text += "\n"

            keyboard = get_main_menu_keyboard("measurer")

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении замеров: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении замеров", show_alert=True)


@measurer_router.callback_query(F.data == "menu")
async def handle_back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback.from_user.id)

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        role_map = {
            UserRole.ADMIN: "admin",
            UserRole.MEASURER: "measurer",
            UserRole.MANAGER: "manager"
        }

        role = role_map.get(user.role, "measurer")
        keyboard = get_main_menu_keyboard(role)

        text = "📋 <b>Главное меню:</b>"

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
