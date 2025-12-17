"""Обработчики команд администратора"""
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from database import (
    get_db,
    get_user_by_telegram_id,
    get_all_measurers,
    get_measurement_by_id,
    get_measurements_by_status,
    get_all_users,
    get_user_by_id,
    update_user_role,
    toggle_user_active,
    update_user_amocrm_id,
    get_recent_notifications,
    MeasurementStatus,
    UserRole
)
from utils.timezone_utils import moscow_now
from bot.keyboards.inline import (
    get_measurers_keyboard,
    get_main_menu_keyboard,
    get_measurement_actions_keyboard,
    get_users_list_keyboard,
    get_user_detail_keyboard,
    get_role_selection_keyboard,
    get_amocrm_account_keyboard,
    get_amocrm_users_keyboard
)
from bot.keyboards.reply import (
    get_admin_commands_keyboard,
    get_keyboard_by_role
)
from bot.utils.notifications import (
    send_assignment_notification_to_measurer,
    send_assignment_notification_to_manager,
    send_measurer_change_notification,
    send_assignment_notification_to_observers
)
from bot.utils.logging_decorators import log_command, log_callback
from bot.filters import HasAdminAccess
from config import settings

# Создаем роутер для администраторских команд
admin_router = Router()


def is_admin_or_supervisor(telegram_id: int) -> bool:
    """
    Проверка, является ли пользователь администратором или руководителем
    Руководитель имеет ПОЛНЫЙ функционал администратора!
    """
    # Проверяем, является ли пользователь администратором из конфига
    if telegram_id in settings.admin_ids_list:
        return True

    # Это будет проверено через middleware - если пользователь руководитель
    # Но для совместимости оставляем базовую проверку
    return False

# Для обратной совместимости
is_admin = is_admin_or_supervisor


@admin_router.message(Command("start"), HasAdminAccess())
async def cmd_start(message: Message, user_role: UserRole = None):
    """Обработчик команды /start для администратора и руководителя"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user:
            from database import get_or_create_user
            user = await get_or_create_user(
                session=session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                role=UserRole.ADMIN
            )

        text = f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"

        # Определяем роль для отображения
        if user.role == UserRole.ADMIN:
            text += "Вы вошли как <b>Администратор</b>\n\n"
        elif user.role == UserRole.SUPERVISOR:
            text += "Вы вошли как <b>Руководитель</b>\n\n"
        else:
            text += "Вы вошли как <b>Администратор</b>\n\n"

        text += "📋 Используйте меню ниже для управления:\n\n"
        text += "Доступные команды:\n"
        text += "/pending_confirmation - Замеры ожидающие подтверждения\n"
        text += "/pending - Замеры в работе\n"
        text += "/all - Все замеры (последние 20)\n"
        text += "/users - Пользователи\n"
        text += "/notifications - Уведомления\n"

        # Reply клавиатура с быстрыми командами
        reply_keyboard = get_admin_commands_keyboard()
        await message.answer(text, reply_markup=reply_keyboard, parse_mode="HTML")

        # Inline клавиатура с главным меню (определяем роль для клавиатуры)
        role_for_keyboard = "supervisor" if user.role == UserRole.SUPERVISOR else "admin"
        inline_keyboard = get_main_menu_keyboard(role_for_keyboard)
        await message.answer(
            "📋 <b>Или используйте кнопки ниже:</b>",
            reply_markup=inline_keyboard,
            parse_mode="HTML"
        )


@admin_router.message(Command("menu"), HasAdminAccess())
async def cmd_menu(message: Message, user_role: UserRole = None):
    """Обработчик команды /menu для администратора и руководителя"""
    # Определяем роль для клавиатуры
    role_for_keyboard = "supervisor" if user_role == UserRole.SUPERVISOR else "admin"
    keyboard = get_main_menu_keyboard(role_for_keyboard)

    menu_title = "Главное меню руководителя" if user_role == UserRole.SUPERVISOR else "Главное меню администратора"
    await message.answer(f"📋 <b>{menu_title}:</b>", reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("measurers"), HasAdminAccess())
async def cmd_measurers(message: Message):
    """Показать список замерщиков"""
    async for session in get_db():
        measurers = await get_all_measurers(session)

        if not measurers:
            await message.answer("❌ Нет зарегистрированных замерщиков")
            return

        text = "👥 <b>Список замерщиков:</b>\n\n"
        for idx, measurer in enumerate(measurers, 1):
            text += f"{idx}. {measurer.full_name}"
            if measurer.username:
                text += f" (@{measurer.username})"
            text += f" - ID: {measurer.telegram_id}\n"

        await message.answer(text, parse_mode="HTML")


@admin_router.message(Command("pending"), HasAdminAccess())
async def cmd_pending(message: Message):
    """Показать замеры в работе (со статусом ASSIGNED)"""
    import asyncio

    async for session in get_db():
        measurements = await get_measurements_by_status(session, MeasurementStatus.ASSIGNED)

        if not measurements:
            await message.answer("✅ Нет замеров в работе")
            return

        await message.answer(f"🔄 <b>Замеры в работе ({len(measurements)}):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением с inline кнопкой
        for i, measurement in enumerate(measurements):
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")

            # Задержка после каждого 3-го сообщения, чтобы избежать Flood Control
            if (i + 1) % 3 == 0 and i + 1 < len(measurements):
                await asyncio.sleep(0.5)


@admin_router.message(Command("pending_confirmation"), HasAdminAccess())
async def cmd_pending_confirmation(message: Message):
    """Показать замеры ожидающие подтверждения (со статусом PENDING_CONFIRMATION)"""
    import asyncio

    async for session in get_db():
        measurements = await get_measurements_by_status(session, MeasurementStatus.PENDING_CONFIRMATION)

        if not measurements:
            await message.answer("✅ Нет замеров ожидающих подтверждения")
            return

        await message.answer(f"⏳ <b>Замеры ожидающие подтверждения ({len(measurements)}):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением с inline кнопкой
        for i, measurement in enumerate(measurements):
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")

            # Задержка после каждого 3-го сообщения, чтобы избежать Flood Control
            if (i + 1) % 3 == 0 and i + 1 < len(measurements):
                await asyncio.sleep(0.5)


@admin_router.message(Command("all"), HasAdminAccess())
async def cmd_all(message: Message):
    """Показать все замеры"""
    import asyncio

    async for session in get_db():
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from database.models import Measurement

        result = await session.execute(
            select(Measurement)
            .options(
                joinedload(Measurement.measurer),
                joinedload(Measurement.manager),
                joinedload(Measurement.confirmed_by),
                joinedload(Measurement.auto_assigned_measurer)
            )
            .order_by(Measurement.created_at.asc())
            .limit(20)
        )
        measurements = list(result.scalars().unique().all())

        if not measurements:
            await message.answer("❌ Нет замеров")
            return

        await message.answer(f"📊 <b>Все замеры (последние 20):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением с inline кнопкой
        for i, measurement in enumerate(measurements):
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")

            # Задержка после каждого 3-го сообщения, чтобы избежать Flood Control
            if (i + 1) % 3 == 0 and i + 1 < len(measurements):
                await asyncio.sleep(0.5)


@admin_router.message(Command("measurement"), HasAdminAccess())
async def cmd_measurement(message: Message):
    """Показать информацию о замере по ID

    Использование: /measurement <ID замера>
    Пример: /measurement 123
    """
    # Парсим ID замера из команды
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "⚠️ Укажите ID замера\n\n"
            "Использование: <code>/measurement ID_замера</code>\n"
            "Пример: <code>/measurement 123</code>",
            parse_mode="HTML"
        )
        return

    try:
        measurement_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID замера должен быть числом")
        return

    async for session in get_db():
        measurement = await get_measurement_by_id(session, measurement_id)

        if not measurement:
            await message.answer(f"❌ Замер #{measurement_id} не найден")
            return

        text = measurement.get_info_text(detailed=True, show_admin_info=True)

        keyboard = get_measurement_actions_keyboard(
            measurement.id,
            is_admin=True,
            current_status=measurement.status
        )

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("assign"), HasAdminAccess())
async def cmd_assign(message: Message):
    """Назначить замерщика на замер по ID

    Использование: /assign <ID замера>
    Пример: /assign 123
    """
    # Парсим ID замера из команды
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "⚠️ Укажите ID замера\n\n"
            "Использование: <code>/assign ID_замера</code>\n"
            "Пример: <code>/assign 123</code>",
            parse_mode="HTML"
        )
        return

    try:
        measurement_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ ID замера должен быть числом")
        return

    async for session in get_db():
        measurement = await get_measurement_by_id(session, measurement_id)

        if not measurement:
            await message.answer(f"❌ Замер #{measurement_id} не найден")
            return

        measurers = await get_all_measurers(session)

        if not measurers:
            await message.answer("❌ Нет доступных замерщиков")
            return

        text = measurement.get_info_text(detailed=True, show_admin_info=True)
        text += "\n\n👇 <b>Выберите замерщика:</b>"

        keyboard = get_measurers_keyboard(measurers, measurement.id)

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("assign:"), HasAdminAccess())
async def handle_assign_measurer(callback: CallbackQuery):
    """Обработка назначения замерщика на замер"""


    try:
        # Парсим callback data: assign:measurement_id:measurer_id
        parts = callback.data.split(":")
        measurement_id = int(parts[1])
        measurer_id = int(parts[2])

        async for session in get_db():
            # Получаем замер и замерщика
            measurement = await get_measurement_by_id(session, measurement_id)

            if not measurement:
                await callback.answer("❌ Замер не найден", show_alert=True)
                return

            from sqlalchemy import select
            from database.models import User, Measurement

            result = await session.execute(select(User).where(User.id == measurer_id))
            measurer = result.scalar_one_or_none()

            if not measurer:
                await callback.answer("❌ Замерщик не найден", show_alert=True)
                return

            # Сохраняем старого замерщика и старый статус для проверки
            old_measurer = measurement.measurer
            old_status = measurement.status
            was_confirmed = old_status == MeasurementStatus.ASSIGNED

            # Назначаем замерщика и ставим статус "Назначен"
            measurement.measurer_id = measurer.id
            measurement.status = MeasurementStatus.ASSIGNED
            measurement.assigned_at = moscow_now()

            # Сохраняем кто подтвердил/распределил
            measurement.confirmed_by_user_id = callback.from_user.id

            # ВАЖНО: При первом подтверждении обновляем счётчик round-robin
            # Делаем это ДО коммита, пока сессия активна
            if not was_confirmed and (measurement.delivery_zone is None or measurement.delivery_zone == ""):
                from services.zone_service import ZoneService
                zone_service = ZoneService(session)
                await zone_service.update_round_robin_counter(measurer.id)
                logger.info(f"Round-robin счётчик обновлён при первом назначении на замерщика {measurer.id}")
            elif was_confirmed and old_measurer and old_measurer.id != measurer.id:
                # При смене уже подтверждённого замера также обновляем счётчик
                if measurement.delivery_zone is None or measurement.delivery_zone == "":
                    from services.zone_service import ZoneService
                    zone_service = ZoneService(session)
                    await zone_service.update_round_robin_counter(measurer.id)
                    logger.info(f"Round-robin счётчик обновлён при смене замерщика на {measurer.id}")

            # ВАЖНО: Сохраняем ID старого замерщика ДО коммита (для перезагрузки после коммита)
            old_measurer_id = old_measurer.id if old_measurer else None

            # Получаем уведомления для обновления ДО коммита
            notifications_data = []
            if not was_confirmed:
                from database import get_pending_notifications_for_measurement
                notifications = await get_pending_notifications_for_measurement(session, measurement.id)
                # Извлекаем данные из ORM объектов ДО коммита
                for notification in notifications:
                    notifications_data.append({
                        'id': notification.id,
                        'recipient_id': notification.recipient_id,
                        'telegram_chat_id': notification.telegram_chat_id,
                        'telegram_message_id': notification.telegram_message_id
                    })

            await session.commit()

            # ВАЖНО: После коммита перезагружаем measurement с eager loading всех relationships
            # чтобы избежать ошибки greenlet_spawn при вызове get_info_text()
            from sqlalchemy.orm import joinedload
            result = await session.execute(
                select(Measurement)
                .options(
                    joinedload(Measurement.measurer),
                    joinedload(Measurement.manager),
                    joinedload(Measurement.confirmed_by),
                    joinedload(Measurement.auto_assigned_measurer)
                )
                .where(Measurement.id == measurement.id)
            )
            measurement = result.scalar_one()

            # Перезагружаем замерщика (новый объект после коммита)
            result = await session.execute(select(User).where(User.id == measurer_id))
            measurer = result.scalar_one()

            # Если был старый замерщик, тоже перезагружаем его
            old_measurer_obj = None
            if old_measurer_id:
                result = await session.execute(select(User).where(User.id == old_measurer_id))
                old_measurer_obj = result.scalar_one_or_none()

            # Обновляем сообщение (с информацией для админа)
            new_text = "✅ <b>Замерщик назначен!</b>\n\n"
            new_text += measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await callback.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")

            # Логика уведомлений зависит от того, был ли замер подтвержден ранее
            if was_confirmed and old_measurer_obj and old_measurer_obj.id != measurer.id:
                # Замер УЖЕ БЫЛ подтвержден - это реальная смена замерщика
                # Отправляем уведомления через функцию смены замерщика
                await send_measurer_change_notification(
                    callback.bot,
                    old_measurer_obj,
                    measurer,
                    measurement,
                    measurement.manager
                )
            else:
                # Замер НЕ БЫЛ подтвержден (PENDING_CONFIRMATION) - это первое назначение
                # Старый замерщик был просто предложен системой, уведомлять его НЕ НУЖНО
                # Отправляем уведомления только новому замерщику и менеджеру
                await send_assignment_notification_to_measurer(callback.bot, measurer, measurement, measurer.full_name)

                if measurement.manager:
                    await send_assignment_notification_to_manager(
                        callback.bot,
                        measurement.manager,
                        measurement,
                        measurer
                    )

                # Отправляем уведомление наблюдателям
                await send_assignment_notification_to_observers(callback.bot, measurement, measurer)

                # ВАЖНО: Обновляем уведомления о подтверждении у других админов/руководителей
                # Получаем имя пользователя, который распределил замер
                confirmed_by_name = callback.from_user.full_name
                if not confirmed_by_name:
                    confirmed_by_name = callback.from_user.first_name or "Руководитель"

                for notif_data in notifications_data:
                    try:
                        # Формируем расширенный текст уведомления
                        notification_text = f"✅ <b>Замер #{measurement.id} уже распределен</b>\n\n"

                        # Информация о замере
                        notification_text += f"📄 <b>Сделка:</b> {measurement.lead_name}\n"
                        if measurement.order_number:
                            notification_text += f"🔢 <b>Номер заказа:</b> {measurement.order_number}\n"

                        notification_text += "\n"

                        # Информация о распределении
                        notification_text += f"🔄 <b>Действие:</b> Изменен замерщик\n"
                        notification_text += f"👤 <b>Распределил:</b> {confirmed_by_name}\n"
                        notification_text += f"👷 <b>Замерщик:</b> {measurer.full_name}\n"

                        await callback.bot.edit_message_text(
                            chat_id=notif_data['telegram_chat_id'],
                            message_id=notif_data['telegram_message_id'],
                            text=notification_text,
                            parse_mode="HTML"
                        )
                        logger.info(f"Обновлено уведомление у пользователя {notif_data['recipient_id']}")
                    except Exception as e:
                        logger.warning(f"Не удалось обновить уведомление {notif_data['id']}: {e}")

            await callback.answer(f"✅ Замер назначен на {measurer.full_name}")
            logger.info(f"Замер #{measurement.id} назначен на замерщика {measurer.id}")

    except Exception as e:
        logger.error(f"Ошибка при назначении замерщика: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при назначении замерщика", show_alert=True)


@admin_router.callback_query(F.data.startswith("confirm_assignment:"), HasAdminAccess())
async def handle_confirm_assignment(callback: CallbackQuery):
    """Обработка подтверждения распределения замерщика"""


    try:
        # Парсим callback data: confirm_assignment:measurement_id
        measurement_id = int(callback.data.split(":")[1])

        async for session in get_db():
            from sqlalchemy import select
            from database.models import Measurement, User

            measurement = await get_measurement_by_id(session, measurement_id)

            if not measurement:
                await callback.answer("❌ Замер не найден", show_alert=True)
                return

            # Проверяем, что замер в статусе ожидания подтверждения
            if measurement.status != MeasurementStatus.PENDING_CONFIRMATION:
                await callback.answer("⚠️ Этот замер уже был подтвержден", show_alert=True)
                return

            # Проверяем, что есть предложенный замерщик
            if not measurement.auto_assigned_measurer:
                await callback.answer("❌ Нет предложенного замерщика для подтверждения", show_alert=True)
                return

            # Подтверждаем назначение: переносим auto_assigned_measurer в measurer
            measurement.measurer_id = measurement.auto_assigned_measurer_id
            measurement.status = MeasurementStatus.ASSIGNED
            measurement.assigned_at = moscow_now()

            # Сохраняем кто подтвердил
            measurement.confirmed_by_user_id = callback.from_user.id

            # ВАЖНО: Обновляем счётчик round-robin только при подтверждении!
            # Делаем это ДО коммита, пока сессия активна
            if measurement.assignment_reason == 'round_robin':
                # Использовался round-robin - обновляем счётчик
                from services.zone_service import ZoneService
                zone_service = ZoneService(session)
                await zone_service.update_round_robin_counter(measurement.measurer_id)
                logger.info(f"Round-robin счётчик обновлён при подтверждении на замерщика {measurement.measurer_id}")

            # ВАЖНО: Получаем уведомления ДО коммита, пока сессия активна
            # И сразу извлекаем нужные данные, чтобы избежать ошибки greenlet_spawn
            from database import get_pending_notifications_for_measurement
            notifications = await get_pending_notifications_for_measurement(session, measurement.id)
            # Извлекаем данные из ORM объектов ДО коммита
            notifications_data = []
            for notification in notifications:
                notifications_data.append({
                    'id': notification.id,
                    'recipient_id': notification.recipient_id,
                    'telegram_chat_id': notification.telegram_chat_id,
                    'telegram_message_id': notification.telegram_message_id
                })

            await session.commit()

            # ВАЖНО: После коммита перезагружаем measurement с eager loading всех relationships
            # чтобы избежать ошибки greenlet_spawn при вызове get_info_text()
            from sqlalchemy.orm import joinedload
            result = await session.execute(
                select(Measurement)
                .options(
                    joinedload(Measurement.measurer),
                    joinedload(Measurement.manager),
                    joinedload(Measurement.confirmed_by),
                    joinedload(Measurement.auto_assigned_measurer)
                )
                .where(Measurement.id == measurement.id)
            )
            measurement = result.scalar_one()

            # ВАЖНО: Явно перезагружаем замерщика (новый объект после коммита)
            # Это гарантирует, что объект замерщика будет доступен
            measurer_obj_from_db = None
            if measurement.measurer_id:
                result = await session.execute(select(User).where(User.id == measurement.measurer_id))
                measurer_obj_from_db = result.scalar_one_or_none()
                logger.info(f"DEBUG: Перезагружен замерщик ID {measurement.measurer_id}: {measurer_obj_from_db}")

            # ВАЖНО: Сохраняем нужные данные в переменные ДО выхода из сессии
            # Добавляем отладочный лог
            logger.info(f"DEBUG: После перезагрузки measurement.measurer_id = {measurement.measurer_id}, measurement.measurer = {measurement.measurer}, measurer_obj_from_db = {measurer_obj_from_db}")

            # ВАЖНО: Используем явно перезагруженного замерщика для получения имени
            measurer_full_name = measurer_obj_from_db.full_name if measurer_obj_from_db else "Неизвестен"
            manager_full_name = measurement.manager.full_name if measurement.manager else None
            measurement_id = measurement.id
            measurement_status = measurement.status
            measurement_lead_name = measurement.lead_name
            measurement_order_number = measurement.order_number

            # ВАЖНО: Получаем текст для обновления сообщения ВНУТРИ сессии
            info_text = measurement.get_info_text(detailed=True, show_admin_info=True)

            # Сохраняем ссылки на связанные объекты для отправки уведомлений
            # ВАЖНО: Создаем временные объекты с нужными данными
            # чтобы избежать проблем с закрытой сессией
            class UserData:
                def __init__(self, user):
                    if user:
                        self.full_name = user.full_name
                        self.telegram_id = user.telegram_id
                        self.id = user.id

            class MeasurementData:
                def __init__(self, meas):
                    self.id = meas.id
                    self.lead_name = meas.lead_name
                    self.order_number = meas.order_number
                    self.address = meas.address
                    self.delivery_zone = meas.delivery_zone
                    self.contact_name = meas.contact_name
                    self.contact_phone = meas.contact_phone
                    self.responsible_user_name = meas.responsible_user_name
                    self.windows_count = meas.windows_count
                    self.windows_area = meas.windows_area
                    self.status_text = meas.status_text
                    self.amocrm_lead_id = meas.amocrm_lead_id
                    self.created_at = meas.created_at
                    self.assigned_at = meas.assigned_at

            # ВАЖНО: Используем явно перезагруженного замерщика для создания UserData
            measurer_obj = UserData(measurer_obj_from_db) if measurer_obj_from_db else None
            manager_obj = UserData(measurement.manager) if measurement.manager else None
            measurement_obj = MeasurementData(measurement)

            # Добавляем отладочный лог
            logger.info(f"DEBUG: measurer_obj = {measurer_obj}, has telegram_id = {hasattr(measurer_obj, 'telegram_id') if measurer_obj else False}")

            # Обновляем сообщение (с информацией для админа)
            new_text = "✅ <b>Распределение подтверждено!</b>\n\n"
            new_text += info_text

            keyboard = get_measurement_actions_keyboard(
                measurement_id,
                is_admin=True,
                current_status=measurement_status
            )

            await callback.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")

            # Отправляем уведомления замерщику (используем measurement_obj вместо measurement)
            if measurer_obj:
                await send_assignment_notification_to_measurer(callback.bot, measurer_obj, measurement_obj, measurer_full_name)
                logger.info(f"Отправлено уведомление замерщику {measurer_full_name}")

            # Отправляем уведомление менеджеру (используем measurement_obj вместо measurement)
            if manager_obj:
                await send_assignment_notification_to_manager(
                    callback.bot,
                    manager_obj,
                    measurement_obj,
                    measurer_obj
                )
                logger.info(f"Отправлено уведомление менеджеру {manager_full_name}")

            # Отправляем уведомление наблюдателям (используем measurement_obj вместо measurement)
            if measurer_obj:
                await send_assignment_notification_to_observers(callback.bot, measurement_obj, measurer_obj)
                logger.info(f"Отправлены уведомления наблюдателям о назначении {measurer_full_name}")

            # ВАЖНО: Обновляем уведомления о подтверждении у других админов/руководителей
            # Получаем имя пользователя, который подтвердил замер
            confirmed_by_name = callback.from_user.full_name
            if not confirmed_by_name:
                confirmed_by_name = callback.from_user.first_name or "Руководитель"

            for notif_data in notifications_data:
                try:
                    # Формируем расширенный текст уведомления
                    notification_text = f"✅ <b>Замер #{measurement_id} уже распределен</b>\n\n"

                    # Информация о замере
                    notification_text += f"📄 <b>Сделка:</b> {measurement_lead_name}\n"
                    if measurement_order_number:
                        notification_text += f"🔢 <b>Номер заказа:</b> {measurement_order_number}\n"

                    notification_text += "\n"

                    # Информация о распределении
                    notification_text += f"✅ <b>Действие:</b> Подтверждено автоматическое распределение\n"
                    notification_text += f"👤 <b>Подтвердил:</b> {confirmed_by_name}\n"
                    notification_text += f"👷 <b>Замерщик:</b> {measurer_full_name}\n"

                    await callback.bot.edit_message_text(
                        chat_id=notif_data['telegram_chat_id'],
                        message_id=notif_data['telegram_message_id'],
                        text=notification_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"Обновлено уведомление у пользователя {notif_data['recipient_id']}")
                except Exception as e:
                    logger.warning(f"Не удалось обновить уведомление {notif_data['id']}: {e}")

            await callback.answer(f"✅ Распределение подтверждено. {measurer_full_name} назначен на замер")
            logger.info(f"Замер #{measurement_id} подтвержден руководителем {callback.from_user.id}, замерщик: {measurer_full_name}")

    except Exception as e:
        logger.error(f"Ошибка при подтверждении распределения: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при подтверждении распределения", show_alert=True)


@admin_router.callback_query(F.data.startswith("change_measurer:"), HasAdminAccess())
async def handle_change_measurer(callback: CallbackQuery):
    """Обработка изменения замерщика"""


    try:
        # Парсим callback data: change_measurer:measurement_id
        measurement_id = int(callback.data.split(":")[1])

        async for session in get_db():
            measurement = await get_measurement_by_id(session, measurement_id)

            if not measurement:
                await callback.answer("❌ Замер не найден", show_alert=True)
                return

            measurers = await get_all_measurers(session)

            if not measurers:
                await callback.answer("❌ Нет доступных замерщиков", show_alert=True)
                return

            text = "🔄 <b>Выберите нового замерщика:</b>\n\n"
            text += measurement.get_info_text(detailed=True, show_admin_info=True)
            text += "\n\n👇 <b>Выберите замерщика:</b>"

            keyboard = get_measurers_keyboard(measurers, measurement.id)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при изменении замерщика: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при изменении замерщика", show_alert=True)


@admin_router.callback_query(F.data.startswith("list:"), HasAdminAccess())
async def handle_list(callback: CallbackQuery):
    """Обработка запросов списков замеров"""


    try:
        list_type = callback.data.split(":")[1]

        async for session in get_db():
            if list_type == "all":
                from sqlalchemy import select
                from sqlalchemy.orm import joinedload
                from database.models import Measurement

                result = await session.execute(
                    select(Measurement)
                    .options(
                        joinedload(Measurement.measurer),
                        joinedload(Measurement.manager),
                        joinedload(Measurement.confirmed_by),
                        joinedload(Measurement.auto_assigned_measurer)
                    )
                    .order_by(Measurement.created_at.desc())
                    .limit(20)
                )
                measurements = list(result.scalars().unique().all())
                title = "📊 Все замеры (последние 20)"

            elif list_type == "pending_confirmation":
                # Замеры ожидающие подтверждения
                status = MeasurementStatus.PENDING_CONFIRMATION
                measurements = await get_measurements_by_status(session, status)
                title = "⏳ Замеры ожидающие подтверждения"

            elif list_type in ["assigned", "completed", "cancelled"]:
                status = MeasurementStatus(list_type)
                measurements = await get_measurements_by_status(session, status)

                status_titles = {
                    "assigned": "🔄 Замеры в работе",
                    "completed": "✅ Выполненные замеры",
                    "cancelled": "❌ Отмененные замеры"
                }
                title = status_titles.get(list_type, "📋 Замеры")
            else:
                await callback.answer("❌ Неизвестный тип списка")
                return

            if not measurements:
                text = f"{title}\n\n❌ Нет замеров"
                keyboard = get_main_menu_keyboard("admin")
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                # Отправляем заголовок
                await callback.message.edit_text(f"<b>{title} ({len(measurements)}):</b>", parse_mode="HTML")

                # Отправляем каждый замер отдельным сообщением с inline кнопкой
                for measurement in measurements:
                    msg_text = measurement.get_info_text(detailed=True, show_admin_info=True)

                    keyboard = get_measurement_actions_keyboard(
                        measurement.id,
                        is_admin=True,
                        current_status=measurement.status
                    )

                    await callback.bot.send_message(
                        callback.message.chat.id,
                        msg_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )

            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении списка: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении списка", show_alert=True)


# ========================================
# Обработчики текстовых кнопок (Reply Keyboard)
# ========================================

@admin_router.message(F.text == "📋 Главное меню", HasAdminAccess())
async def handle_main_menu_button(message: Message, user_role: UserRole = None):
    """Обработка нажатия кнопки Главное меню"""
    await cmd_menu(message, user_role=user_role)


@admin_router.message(F.text == "👤 Пользователи", HasAdminAccess())
async def handle_users_button(message: Message):
    """Обработка нажатия кнопки Пользователи"""
    await cmd_users(message)


@admin_router.message(F.text == "🔄 Замеры в работе", HasAdminAccess())
async def handle_in_work_button(message: Message):
    """Обработка нажатия кнопки Замеры в работе"""
    await cmd_pending(message)


@admin_router.message(F.text == "📊 Все замеры", HasAdminAccess())
async def handle_all_button(message: Message):
    """Обработка нажатия кнопки Все замеры"""
    await cmd_all(message)


@admin_router.message(F.text == "⏳ Ожидают подтверждения", HasAdminAccess())
async def handle_pending_confirmation_button(message: Message):
    """Обработка нажатия кнопки Ожидают подтверждения"""
    await cmd_pending_confirmation(message)


@admin_router.message(F.text == "🗺 Управление зонами", HasAdminAccess())
async def handle_zones_button(message: Message):
    """Обработка нажатия кнопки Управление зонами"""


    from bot.keyboards.inline import get_zones_menu_keyboard

    text = (
        "🗺 <b>Управление зонами доставки</b>\n\n"
        "Здесь вы можете:\n"
        "• Добавлять и удалять зоны доставки\n"
        "• Назначать зоны замерщикам\n"
        "• Просматривать текущие назначения\n\n"
        "Выберите действие:"
    )

    await message.answer(
        text,
        reply_markup=get_zones_menu_keyboard()
    )


@admin_router.message(Command("hide"), HasAdminAccess())
async def cmd_hide_keyboard(message: Message):
    """Скрыть клавиатуру команд"""
    from bot.keyboards.reply import remove_keyboard

    await message.answer(
        "✅ Клавиатура скрыта.\n\n"
        "Чтобы снова показать клавиатуру, используйте команду /menu",
        reply_markup=remove_keyboard()
    )


# ========================================
# Управление пользователями
# ========================================

@admin_router.message(Command("users"), HasAdminAccess())
async def cmd_users(message: Message):
    """Показать список всех пользователей"""
    async for session in get_db():
        users = await get_all_users(session)

        if not users:
            await message.answer("❌ Нет зарегистрированных пользователей")
            return

        keyboard = get_users_list_keyboard(users, page=0)
        text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"
        text += "✅ - активен | ⛔ - неактивен\n"
        text += "👑 - админ | 👔 - руководитель | 💼 - менеджер | 👷 - замерщик | 👀 - наблюдатель"

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "users_list", HasAdminAccess())
async def handle_users_list(callback: CallbackQuery):
    """Показать список пользователей"""


    try:
        async for session in get_db():
            users = await get_all_users(session)

            keyboard = get_users_list_keyboard(users, page=0)
            text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"
            text += "✅ - активен | ⛔ - неактивен\n"
            text += "👑 - админ | 👔 - руководитель | 💼 - менеджер | 👷 - замерщик"

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении списка", show_alert=True)


@admin_router.callback_query(F.data.startswith("users_page:"), HasAdminAccess())
async def handle_users_page(callback: CallbackQuery):
    """Переключение страницы списка пользователей"""


    try:
        page = int(callback.data.split(":")[1])

        async for session in get_db():
            users = await get_all_users(session)
            keyboard = get_users_list_keyboard(users, page=page)

            text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"
            text += "✅ - активен | ⛔ - неактивен\n"
            text += "👑 - админ | 👔 - руководитель | 💼 - менеджер | 👷 - замерщик"

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при переключении страницы: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_detail:"), HasAdminAccess())
async def handle_user_detail(callback: CallbackQuery):
    """Показать детали пользователя"""


    try:
        user_id = int(callback.data.split(":")[1])

        async for session in get_db():
            user = await get_user_by_id(session, user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            role_names = {
                "admin": "Администратор",
                "supervisor": "Руководитель",
                "manager": "Менеджер",
                "measurer": "Замерщик",
                "observer": "Наблюдатель"
            }

            text = f"👤 <b>Информация о пользователе</b>\n\n"
            text += f"<b>ID:</b> {user.id}\n"
            text += f"<b>Telegram ID:</b> {user.telegram_id}\n"
            text += f"<b>Имя:</b> {user.full_name}\n"

            if user.username:
                text += f"<b>Username:</b> @{user.username}\n"

            text += f"<b>Роль:</b> {role_names.get(user.role.value, user.role.value)}\n"
            text += f"<b>Статус:</b> {'✅ Активен' if user.is_active else '⛔ Неактивен'}\n"

            # Информация об AmoCRM аккаунте
            if user.amocrm_user_id:
                text += f"<b>AmoCRM:</b> ✅ Привязан (ID: {user.amocrm_user_id})\n"
            else:
                text += f"<b>AmoCRM:</b> ⚠️ Не привязан\n"

            # Информация об имени замерщика (только для замерщиков)
            if user.role.value == "measurer":
                from services.measurer_name_service import MeasurerNameService
                name_service = MeasurerNameService(session)
                measurer_name = await name_service.get_measurer_name_by_user_id(user.id)
                if measurer_name:
                    text += f"<b>Имя замерщика (AmoCRM):</b> {measurer_name}\n"
                else:
                    text += f"<b>Имя замерщика (AmoCRM):</b> ⚠️ Не установлено\n"

            text += f"<b>Создан:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"

            keyboard = get_user_detail_keyboard(user.id, user.role.value, user.is_active)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении деталей пользователя: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_change_role:"), HasAdminAccess())
async def handle_user_change_role(callback: CallbackQuery):
    """Показать меню выбора роли"""


    try:
        user_id = int(callback.data.split(":")[1])

        async for session in get_db():
            user = await get_user_by_id(session, user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            text = f"🔄 <b>Изменение роли пользователя</b>\n\n"
            text += f"<b>Пользователь:</b> {user.full_name}\n"
            text += f"<b>Текущая роль:</b> {user.role.value}\n\n"
            text += "Выберите новую роль:"

            keyboard = get_role_selection_keyboard(user.id)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при изменении роли: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_set_role:"), HasAdminAccess())
async def handle_user_set_role(callback: CallbackQuery):
    """Установить роль пользователя"""


    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        new_role = parts[2]

        async for session in get_db():
            user_role = UserRole(new_role)
            user = await update_user_role(session, user_id, user_role)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            role_names = {
                "admin": "Администратор",
                "supervisor": "Руководитель",
                "manager": "Менеджер",
                "measurer": "Замерщик",
                "observer": "Наблюдатель"
            }

            await callback.answer(
                f"✅ Роль изменена на: {role_names.get(new_role, new_role)}",
                show_alert=True
            )

            # Обновляем информацию о пользователе
            text = f"👤 <b>Информация о пользователе</b>\n\n"
            text += f"<b>ID:</b> {user.id}\n"
            text += f"<b>Telegram ID:</b> {user.telegram_id}\n"
            text += f"<b>Имя:</b> {user.full_name}\n"

            if user.username:
                text += f"<b>Username:</b> @{user.username}\n"

            text += f"<b>Роль:</b> {role_names.get(user.role.value, user.role.value)}\n"
            text += f"<b>Статус:</b> {'✅ Активен' if user.is_active else '⛔ Неактивен'}\n"

            # Информация об имени замерщика (только для замерщиков)
            if user.role.value == "measurer":
                from services.measurer_name_service import MeasurerNameService
                name_service = MeasurerNameService(session)
                measurer_name = await name_service.get_measurer_name_by_user_id(user.id)
                if measurer_name:
                    text += f"<b>Имя замерщика (AmoCRM):</b> {measurer_name}\n"
                else:
                    text += f"<b>Имя замерщика (AmoCRM):</b> ⚠️ Не установлено\n"

            keyboard = get_user_detail_keyboard(user.id, user.role.value, user.is_active)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

            # Отправляем уведомление пользователю с новой клавиатурой
            try:
                notification_text = f"🔔 <b>Ваша роль изменена</b>\n\n"
                notification_text += f"Новая роль: <b>{role_names.get(new_role, new_role)}</b>"

                # Получаем клавиатуру для новой роли
                reply_keyboard = get_keyboard_by_role(new_role)

                await callback.bot.send_message(
                    user.telegram_id,
                    notification_text,
                    parse_mode="HTML",
                    reply_markup=reply_keyboard
                )
            except Exception:
                pass  # Пользователь может не запускать бота

    except Exception as e:
        logger.error(f"Ошибка при установке роли: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при установке роли", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_toggle:"), HasAdminAccess())
async def handle_user_toggle(callback: CallbackQuery):
    """Переключить статус активности пользователя"""


    try:
        user_id = int(callback.data.split(":")[1])

        async for session in get_db():
            user = await toggle_user_active(session, user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            status_text = "активирован" if user.is_active else "деактивирован"
            await callback.answer(f"✅ Пользователь {status_text}", show_alert=True)

            # Обновляем информацию
            role_names = {
                "admin": "Администратор",
                "supervisor": "Руководитель",
                "manager": "Менеджер",
                "measurer": "Замерщик",
                "observer": "Наблюдатель"
            }

            text = f"👤 <b>Информация о пользователе</b>\n\n"
            text += f"<b>ID:</b> {user.id}\n"
            text += f"<b>Telegram ID:</b> {user.telegram_id}\n"
            text += f"<b>Имя:</b> {user.full_name}\n"

            if user.username:
                text += f"<b>Username:</b> @{user.username}\n"

            text += f"<b>Роль:</b> {role_names.get(user.role.value, user.role.value)}\n"
            text += f"<b>Статус:</b> {'✅ Активен' if user.is_active else '⛔ Неактивен'}\n"

            # Информация об имени замерщика (только для замерщиков)
            if user.role.value == "measurer":
                from services.measurer_name_service import MeasurerNameService
                name_service = MeasurerNameService(session)
                measurer_name = await name_service.get_measurer_name_by_user_id(user.id)
                if measurer_name:
                    text += f"<b>Имя замерщика (AmoCRM):</b> {measurer_name}\n"
                else:
                    text += f"<b>Имя замерщика (AmoCRM):</b> ⚠️ Не установлено\n"

            keyboard = get_user_detail_keyboard(user.id, user.role.value, user.is_active)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при переключении статуса: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data == "measurers_list", HasAdminAccess())
async def handle_measurers_list(callback: CallbackQuery):
    """Показать список замерщиков через callback"""


    try:
        async for session in get_db():
            measurers = await get_all_measurers(session)

            if not measurers:
                text = "❌ Нет зарегистрированных замерщиков"
            else:
                text = "👥 <b>Список замерщиков:</b>\n\n"
                for idx, measurer in enumerate(measurers, 1):
                    text += f"{idx}. {measurer.full_name}"
                    if measurer.username:
                        text += f" (@{measurer.username})"
                    text += f" - ID: {measurer.telegram_id}\n"

            keyboard = get_main_menu_keyboard("admin")
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении списка замерщиков: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении списка", show_alert=True)


@admin_router.callback_query(F.data == "admin_menu", HasAdminAccess())
async def handle_admin_menu(callback: CallbackQuery, user_role: UserRole = None):
    """Обработчик кнопки 'В главное меню'"""


    try:
        # Удаляем текущее сообщение с замером
        try:
            await callback.message.delete()
        except Exception:
            pass  # Игнорируем ошибки удаления

        # Определяем роль для клавиатуры
        role_for_keyboard = "supervisor" if user_role == UserRole.SUPERVISOR else "admin"
        keyboard = get_main_menu_keyboard(role_for_keyboard)

        menu_title = "Главное меню руководителя" if user_role == UserRole.SUPERVISOR else "Главное меню администратора"

        # Отправляем новое сообщение с главным меню
        await callback.bot.send_message(
            callback.message.chat.id,
            f"📋 <b>{menu_title}:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


# ========================================
# Управление AmoCRM аккаунтами
# ========================================

@admin_router.callback_query(F.data.startswith("user_amocrm:"), HasAdminAccess())
async def handle_user_amocrm(callback: CallbackQuery):
    """Показать меню управления AmoCRM аккаунтом пользователя"""


    try:
        user_id = int(callback.data.split(":")[1])

        async for session in get_db():
            user = await get_user_by_id(session, user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            text = f"🔗 <b>Управление AmoCRM аккаунтом</b>\n\n"
            text += f"<b>Пользователь:</b> {user.full_name}\n\n"

            if user.amocrm_user_id:
                text += f"<b>Статус:</b> ✅ Аккаунт привязан\n"
                text += f"<b>AmoCRM ID:</b> {user.amocrm_user_id}\n"
            else:
                text += f"<b>Статус:</b> ⚠️ Аккаунт не привязан\n"

            keyboard = get_amocrm_account_keyboard(user.id, user.amocrm_user_id is not None)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при отображении меню AmoCRM: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_amocrm_select:"), HasAdminAccess())
async def handle_user_amocrm_select(callback: CallbackQuery):
    """Показать список пользователей AmoCRM для привязки"""


    try:
        user_id = int(callback.data.split(":")[1])

        async for session in get_db():
            user = await get_user_by_id(session, user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            # Получаем список пользователей AmoCRM через API
            from services.amocrm import amocrm_client

            await callback.answer("⏳ Загружаю пользователей AmoCRM...", show_alert=False)

            amocrm_users = await amocrm_client.get_all_users()

            if not amocrm_users:
                await callback.answer(
                    "❌ Не удалось получить список пользователей AmoCRM",
                    show_alert=True
                )
                return

            text = f"👥 <b>Выберите пользователя AmoCRM</b>\n\n"
            text += f"<b>Привязка для:</b> {user.full_name}\n\n"
            text += f"Найдено пользователей: {len(amocrm_users)}"

            keyboard = get_amocrm_users_keyboard(user.id, amocrm_users, page=0)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при загрузке пользователей AmoCRM: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки пользователей", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_amocrm_page:"), HasAdminAccess())
async def handle_user_amocrm_page(callback: CallbackQuery):
    """Переключение страницы списка пользователей AmoCRM"""


    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        page = int(parts[2])

        async for session in get_db():
            user = await get_user_by_id(session, user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            # Получаем список пользователей AmoCRM
            from services.amocrm import amocrm_client
            amocrm_users = await amocrm_client.get_all_users()

            if not amocrm_users:
                await callback.answer("❌ Не удалось получить список", show_alert=True)
                return

            text = f"👥 <b>Выберите пользователя AmoCRM</b>\n\n"
            text += f"<b>Привязка для:</b> {user.full_name}\n\n"
            text += f"Найдено пользователей: {len(amocrm_users)}"

            keyboard = get_amocrm_users_keyboard(user.id, amocrm_users, page=page)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при переключении страницы: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_amocrm_link:"), HasAdminAccess())
async def handle_user_amocrm_link(callback: CallbackQuery):
    """Привязать пользователя к аккаунту AmoCRM"""


    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        amocrm_user_id = int(parts[2])

        async for session in get_db():
            # Обновляем AmoCRM ID пользователя
            user = await update_user_amocrm_id(session, user_id, amocrm_user_id)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            # Получаем информацию о пользователе AmoCRM для отображения
            from services.amocrm import amocrm_client
            amocrm_user_info = await amocrm_client.get_user(amocrm_user_id)

            amocrm_user_name = "Неизвестный"
            if amocrm_user_info:
                amocrm_user_name = amocrm_user_info.get("name", "Неизвестный")

            await callback.answer(
                f"✅ Аккаунт привязан к {amocrm_user_name}",
                show_alert=True
            )

            # Возвращаемся к меню управления аккаунтом
            text = f"🔗 <b>Управление AmoCRM аккаунтом</b>\n\n"
            text += f"<b>Пользователь:</b> {user.full_name}\n\n"
            text += f"<b>Статус:</b> ✅ Аккаунт привязан\n"
            text += f"<b>AmoCRM ID:</b> {user.amocrm_user_id}\n"
            text += f"<b>AmoCRM имя:</b> {amocrm_user_name}\n"

            keyboard = get_amocrm_account_keyboard(user.id, True)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

            logger.info(
                f"Пользователь {user.telegram_id} привязан к AmoCRM аккаунту {amocrm_user_id} ({amocrm_user_name})"
            )

    except Exception as e:
        logger.error(f"Ошибка при привязке аккаунта: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при привязке аккаунта", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_amocrm_unlink:"), HasAdminAccess())
async def handle_user_amocrm_unlink(callback: CallbackQuery):
    """Отвязать пользователя от аккаунта AmoCRM"""


    try:
        user_id = int(callback.data.split(":")[1])

        async for session in get_db():
            # Отвязываем аккаунт (устанавливаем None)
            user = await update_user_amocrm_id(session, user_id, None)

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            await callback.answer("✅ Аккаунт отвязан", show_alert=True)

            # Возвращаемся к меню управления аккаунтом
            text = f"🔗 <b>Управление AmoCRM аккаунтом</b>\n\n"
            text += f"<b>Пользователь:</b> {user.full_name}\n\n"
            text += f"<b>Статус:</b> ⚠️ Аккаунт не привязан\n"

            keyboard = get_amocrm_account_keyboard(user.id, False)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

            logger.info(f"Пользователь {user.telegram_id} отвязан от AmoCRM аккаунта")

    except Exception as e:
        logger.error(f"Ошибка при отвязке аккаунта: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при отвязке аккаунта", show_alert=True)


# ========================================
# Просмотр уведомлений
# ========================================

@admin_router.message(Command("notifications"), HasAdminAccess())
async def cmd_notifications(message: Message):
    """Показать последние отправленные уведомления"""
    import asyncio
    import re

    async for session in get_db():
        notifications = await get_recent_notifications(session, limit=20)

        if not notifications:
            await message.answer("📭 Нет отправленных уведомлений")
            return

        await message.answer(f"🔔 <b>Последние {len(notifications)} уведомлений:</b>", parse_mode="HTML")

        # Группируем уведомления по 3 в одно сообщение, чтобы избежать Flood Control
        batch_size = 3
        notification_types = {
            "assignment": "📋 Назначение",
            "completion": "✅ Завершение",
            "change": "🔄 Изменение",
            "status_change": "🔄 Статус",
            "new_lead": "🆕 Заявка",
            "manager_notification": "💼 Менеджер"
        }

        for i in range(0, len(notifications), batch_size):
            batch = notifications[i:i + batch_size]
            batch_texts = []

            for notification in batch:
                text = f"📨 <b>#{notification.id}</b>\n"
                text += f"👤 {notification.recipient.full_name}"
                if notification.recipient.username:
                    text += f" (@{notification.recipient.username})"
                text += f"\n📅 {notification.sent_at.strftime('%d.%m %H:%M')}"
                text += f"\n🏷 {notification_types.get(notification.notification_type, notification.notification_type)}"

                # Краткий текст уведомления
                clean_text = re.sub('<[^<]+?>', '', notification.message_text)
                if len(clean_text) > 150:
                    clean_text = clean_text[:150] + "..."
                text += f"\n💬 {clean_text}"

                batch_texts.append(text)

            # Объединяем уведомления разделителем
            combined_text = "\n\n━━━━━━━━━━━━━━━\n\n".join(batch_texts)
            await message.answer(combined_text, parse_mode="HTML")

            # Небольшая задержка между пакетами, чтобы избежать Flood Control
            if i + batch_size < len(notifications):
                await asyncio.sleep(0.5)


@admin_router.callback_query(F.data == "notifications", HasAdminAccess())
async def handle_notifications_callback(callback: CallbackQuery, user_role: UserRole = None):
    """Обработчик кнопки 'Уведомления'"""
    import asyncio
    import re

    try:
        async for session in get_db():
            notifications = await get_recent_notifications(session, limit=20)

            # Создаем простую клавиатуру только с кнопкой "Назад"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="◀️ Главное меню", callback_data="admin_menu")
            keyboard = builder.as_markup()

            if not notifications:
                await callback.message.edit_text(
                    "📭 <b>Нет отправленных уведомлений</b>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await callback.answer()
                return

            # Удаляем текущее сообщение
            try:
                await callback.message.delete()
            except Exception:
                pass

            # Отправляем заголовок с кнопкой "Назад"
            await callback.bot.send_message(
                callback.message.chat.id,
                f"🔔 <b>Последние {len(notifications)} уведомлений:</b>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            # Группируем уведомления по 3 в одно сообщение
            batch_size = 3
            notification_types = {
                "assignment": "📋 Назначение",
                "completion": "✅ Завершение",
                "change": "🔄 Изменение",
                "status_change": "🔄 Статус",
                "new_lead": "🆕 Заявка",
                "manager_notification": "💼 Менеджер"
            }

            for i in range(0, len(notifications), batch_size):
                batch = notifications[i:i + batch_size]
                batch_texts = []

                for notification in batch:
                    text = f"📨 <b>#{notification.id}</b>\n"
                    text += f"👤 {notification.recipient.full_name}"
                    if notification.recipient.username:
                        text += f" (@{notification.recipient.username})"
                    text += f"\n📅 {notification.sent_at.strftime('%d.%m %H:%M')}"
                    text += f"\n🏷 {notification_types.get(notification.notification_type, notification.notification_type)}"

                    # Краткий текст уведомления
                    clean_text = re.sub('<[^<]+?>', '', notification.message_text)
                    if len(clean_text) > 150:
                        clean_text = clean_text[:150] + "..."
                    text += f"\n💬 {clean_text}"

                    batch_texts.append(text)

                # Объединяем уведомления разделителем
                combined_text = "\n\n━━━━━━━━━━━━━━━\n\n".join(batch_texts)
                await callback.bot.send_message(
                    callback.message.chat.id,
                    combined_text,
                    parse_mode="HTML"
                )

                # Небольшая задержка между пакетами
                if i + batch_size < len(notifications):
                    await asyncio.sleep(0.5)

            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении уведомлений: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении уведомлений", show_alert=True)


@admin_router.message(F.text == "🔔 Уведомления", HasAdminAccess())
async def handle_notifications_button(message: Message):
    """Обработка нажатия кнопки Уведомления"""
    await cmd_notifications(message)


