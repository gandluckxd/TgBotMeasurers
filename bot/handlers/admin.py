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
    send_measurer_change_notification
)
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


@admin_router.message(Command("start"))
async def cmd_start(message: Message, has_admin_access: bool = False):
    """Обработчик команды /start для администратора и руководителя"""
    # Проверяем права доступа (админ или руководитель)
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer(
            "⚠️ У вас нет доступа к этой команде.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

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
        text += "/menu - Главное меню\n"
        text += "/users - Пользователи\n"
        text += "/all - Все замеры (последние 20)\n"
        text += "/pending - Замеры в работе\n"
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


@admin_router.message(Command("menu"))
async def cmd_menu(message: Message, has_admin_access: bool = False, user_role: UserRole = None):
    """Обработчик команды /menu для администратора и руководителя"""
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    # Определяем роль для клавиатуры
    role_for_keyboard = "supervisor" if user_role == UserRole.SUPERVISOR else "admin"
    keyboard = get_main_menu_keyboard(role_for_keyboard)

    menu_title = "Главное меню руководителя" if user_role == UserRole.SUPERVISOR else "Главное меню администратора"
    await message.answer(f"📋 <b>{menu_title}:</b>", reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("measurers"))
async def cmd_measurers(message: Message, has_admin_access: bool = False):
    """Показать список замерщиков"""
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

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


@admin_router.message(Command("pending"))
async def cmd_pending(message: Message, has_admin_access: bool = False):
    """Показать замеры в работе (со статусом ASSIGNED)"""
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    async for session in get_db():
        measurements = await get_measurements_by_status(session, MeasurementStatus.ASSIGNED)

        if not measurements:
            await message.answer("✅ Нет замеров в работе")
            return

        await message.answer(f"🔄 <b>Замеры в работе ({len(measurements)}):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением с inline кнопкой
        for measurement in measurements:
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("all"))
async def cmd_all(message: Message, has_admin_access: bool = False):
    """Показать все замеры"""
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    async for session in get_db():
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from database.models import Measurement

        result = await session.execute(
            select(Measurement)
            .options(
                joinedload(Measurement.measurer),
                joinedload(Measurement.manager),
                joinedload(Measurement.confirmed_by)
            )
            .order_by(Measurement.created_at.desc())
            .limit(20)
        )
        measurements = list(result.scalars().unique().all())

        if not measurements:
            await message.answer("❌ Нет замеров")
            return

        await message.answer(f"📊 <b>Все замеры (последние 20):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением с inline кнопкой
        for measurement in measurements:
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("measurement"))
async def cmd_measurement(message: Message, has_admin_access: bool = False):
    """Показать информацию о замере по ID

    Использование: /measurement <ID замера>
    Пример: /measurement 123
    """
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

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


@admin_router.message(Command("assign"))
async def cmd_assign(message: Message, has_admin_access: bool = False):
    """Назначить замерщика на замер по ID

    Использование: /assign <ID замера>
    Пример: /assign 123
    """
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

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


@admin_router.callback_query(F.data.startswith("assign:"))
async def handle_assign_measurer(callback: CallbackQuery, has_admin_access: bool = False):
    """Обработка назначения замерщика на замер"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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
            measurement.assigned_at = datetime.now()

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
                    joinedload(Measurement.confirmed_by)
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

                # ВАЖНО: Обновляем уведомления о подтверждении у других админов/руководителей
                for notif_data in notifications_data:
                    try:
                        # Редактируем сообщение, добавляя информацию о том, что замер уже распределен
                        confirmed_by_name = "другим руководителем"
                        if measurement.confirmed_by:
                            confirmed_by_name = measurement.confirmed_by.full_name

                        await callback.bot.edit_message_text(
                            chat_id=notif_data['telegram_chat_id'],
                            message_id=notif_data['telegram_message_id'],
                            text=f"✅ <b>Замер #{measurement.id} уже распределен</b>\n\n"
                                 f"Распределил: {confirmed_by_name}\n"
                                 f"Замерщик: {measurer.full_name}",
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


@admin_router.callback_query(F.data.startswith("confirm_assignment:"))
async def handle_confirm_assignment(callback: CallbackQuery, has_admin_access: bool = False):
    """Обработка подтверждения распределения замерщика"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

    try:
        # Парсим callback data: confirm_assignment:measurement_id
        measurement_id = int(callback.data.split(":")[1])

        async for session in get_db():
            from sqlalchemy import select
            from database.models import Measurement

            measurement = await get_measurement_by_id(session, measurement_id)

            if not measurement:
                await callback.answer("❌ Замер не найден", show_alert=True)
                return

            if not measurement.measurer:
                await callback.answer("❌ Замерщик не назначен", show_alert=True)
                return

            # Проверяем, что замер в статусе ожидания подтверждения
            if measurement.status != MeasurementStatus.PENDING_CONFIRMATION:
                await callback.answer("⚠️ Этот замер уже был подтвержден", show_alert=True)
                return

            # Подтверждаем назначение
            measurement.status = MeasurementStatus.ASSIGNED
            measurement.assigned_at = datetime.now()

            # Сохраняем кто подтвердил
            measurement.confirmed_by_user_id = callback.from_user.id

            # ВАЖНО: Обновляем счётчик round-robin только при подтверждении!
            # Делаем это ДО коммита, пока сессия активна
            if measurement.delivery_zone is None or measurement.delivery_zone == "":
                # Нет зоны доставки = использовался round-robin
                from services.zone_service import ZoneService
                zone_service = ZoneService(session)
                await zone_service.update_round_robin_counter(measurement.measurer.id)
                logger.info(f"Round-robin счётчик обновлён при подтверждении на замерщика {measurement.measurer.id}")

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
                    joinedload(Measurement.confirmed_by)
                )
                .where(Measurement.id == measurement.id)
            )
            measurement = result.scalar_one()

            # Обновляем сообщение (с информацией для админа)
            new_text = "✅ <b>Распределение подтверждено!</b>\n\n"
            new_text += measurement.get_info_text(detailed=True, show_admin_info=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await callback.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")

            # Отправляем уведомления замерщику
            await send_assignment_notification_to_measurer(callback.bot, measurement.measurer, measurement, measurement.measurer.full_name)
            logger.info(f"Отправлено уведомление замерщику {measurement.measurer.full_name}")

            # Отправляем уведомление менеджеру
            if measurement.manager:
                await send_assignment_notification_to_manager(
                    callback.bot,
                    measurement.manager,
                    measurement,
                    measurement.measurer
                )
                logger.info(f"Отправлено уведомление менеджеру {measurement.manager.full_name}")

            # ВАЖНО: Обновляем уведомления о подтверждении у других админов/руководителей
            for notif_data in notifications_data:
                try:
                    # Редактируем сообщение, добавляя информацию о том, что замер уже распределен
                    confirmed_by_name = "другим руководителем"
                    if measurement.confirmed_by:
                        confirmed_by_name = measurement.confirmed_by.full_name

                    await callback.bot.edit_message_text(
                        chat_id=notif_data['telegram_chat_id'],
                        message_id=notif_data['telegram_message_id'],
                        text=f"✅ <b>Замер #{measurement.id} уже распределен</b>\n\n"
                             f"Подтвердил: {confirmed_by_name}\n"
                             f"Замерщик: {measurement.measurer.full_name}",
                        parse_mode="HTML"
                    )
                    logger.info(f"Обновлено уведомление у пользователя {notif_data['recipient_id']}")
                except Exception as e:
                    logger.warning(f"Не удалось обновить уведомление {notif_data['id']}: {e}")

            await callback.answer(f"✅ Распределение подтверждено. {measurement.measurer.full_name} назначен на замер")
            logger.info(f"Замер #{measurement.id} подтвержден руководителем {callback.from_user.id}, замерщик: {measurement.measurer.full_name}")

    except Exception as e:
        logger.error(f"Ошибка при подтверждении распределения: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при подтверждении распределения", show_alert=True)


@admin_router.callback_query(F.data.startswith("change_measurer:"))
async def handle_change_measurer(callback: CallbackQuery, has_admin_access: bool = False):
    """Обработка изменения замерщика"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("list:"))
async def handle_list(callback: CallbackQuery, has_admin_access: bool = False):
    """Обработка запросов списков замеров"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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
                        joinedload(Measurement.confirmed_by)
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

@admin_router.message(F.text == "📋 Главное меню")
async def handle_main_menu_button(message: Message, has_admin_access: bool = False, user_role: UserRole = None):
    """Обработка нажатия кнопки Главное меню"""
    if not has_admin_access and not is_admin(message.from_user.id):
        return
    await cmd_menu(message, has_admin_access=has_admin_access, user_role=user_role)


@admin_router.message(F.text == "👤 Пользователи")
async def handle_users_button(message: Message, has_admin_access: bool = False):
    """Обработка нажатия кнопки Пользователи"""
    if not has_admin_access and not is_admin(message.from_user.id):
        return
    await cmd_users(message, has_admin_access=has_admin_access)


@admin_router.message(F.text == "🔄 Замеры в работе")
async def handle_in_work_button(message: Message, has_admin_access: bool = False):
    """Обработка нажатия кнопки Замеры в работе"""
    if not has_admin_access and not is_admin(message.from_user.id):
        return
    await cmd_pending(message, has_admin_access=has_admin_access)


@admin_router.message(F.text == "📊 Все замеры")
async def handle_all_button(message: Message, has_admin_access: bool = False):
    """Обработка нажатия кнопки Все замеры"""
    if not has_admin_access and not is_admin(message.from_user.id):
        return
    await cmd_all(message, has_admin_access=has_admin_access)


@admin_router.message(F.text == "🗺 Управление зонами")
async def handle_zones_button(message: Message, has_admin_access: bool = False):
    """Обработка нажатия кнопки Управление зонами"""
    if not has_admin_access and not is_admin(message.from_user.id):
        return

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


# ========================================
# Управление пользователями
# ========================================

@admin_router.message(Command("users"))
async def cmd_users(message: Message, has_admin_access: bool = False):
    """Показать список всех пользователей"""
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    async for session in get_db():
        users = await get_all_users(session)

        if not users:
            await message.answer("❌ Нет зарегистрированных пользователей")
            return

        keyboard = get_users_list_keyboard(users, page=0)
        text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"
        text += "✅ - активен | ⛔ - неактивен\n"
        text += "👑 - админ | 👔 - руководитель | 💼 - менеджер | 👷 - замерщик"

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "users_list")
async def handle_users_list(callback: CallbackQuery, has_admin_access: bool = False):
    """Показать список пользователей"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("users_page:"))
async def handle_users_page(callback: CallbackQuery, has_admin_access: bool = False):
    """Переключение страницы списка пользователей"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("user_detail:"))
async def handle_user_detail(callback: CallbackQuery, has_admin_access: bool = False):
    """Показать детали пользователя"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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
                "measurer": "Замерщик"
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

            text += f"<b>Создан:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"

            keyboard = get_user_detail_keyboard(user.id, user.role.value, user.is_active)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении деталей пользователя: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_change_role:"))
async def handle_user_change_role(callback: CallbackQuery, has_admin_access: bool = False):
    """Показать меню выбора роли"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("user_set_role:"))
async def handle_user_set_role(callback: CallbackQuery, has_admin_access: bool = False):
    """Установить роль пользователя"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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
                "measurer": "Замерщик"
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


@admin_router.callback_query(F.data.startswith("user_toggle:"))
async def handle_user_toggle(callback: CallbackQuery, has_admin_access: bool = False):
    """Переключить статус активности пользователя"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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
                "measurer": "Замерщик"
            }

            text = f"👤 <b>Информация о пользователе</b>\n\n"
            text += f"<b>ID:</b> {user.id}\n"
            text += f"<b>Telegram ID:</b> {user.telegram_id}\n"
            text += f"<b>Имя:</b> {user.full_name}\n"

            if user.username:
                text += f"<b>Username:</b> @{user.username}\n"

            text += f"<b>Роль:</b> {role_names.get(user.role.value, user.role.value)}\n"
            text += f"<b>Статус:</b> {'✅ Активен' if user.is_active else '⛔ Неактивен'}\n"

            keyboard = get_user_detail_keyboard(user.id, user.role.value, user.is_active)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при переключении статуса: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data == "measurers_list")
async def handle_measurers_list(callback: CallbackQuery, has_admin_access: bool = False):
    """Показать список замерщиков через callback"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data == "admin_menu")
async def handle_admin_menu(callback: CallbackQuery, has_admin_access: bool = False, user_role: UserRole = None):
    """Обработчик кнопки 'В главное меню'"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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

@admin_router.callback_query(F.data.startswith("user_amocrm:"))
async def handle_user_amocrm(callback: CallbackQuery, has_admin_access: bool = False):
    """Показать меню управления AmoCRM аккаунтом пользователя"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("user_amocrm_select:"))
async def handle_user_amocrm_select(callback: CallbackQuery, has_admin_access: bool = False):
    """Показать список пользователей AmoCRM для привязки"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("user_amocrm_page:"))
async def handle_user_amocrm_page(callback: CallbackQuery, has_admin_access: bool = False):
    """Переключение страницы списка пользователей AmoCRM"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("user_amocrm_link:"))
async def handle_user_amocrm_link(callback: CallbackQuery, has_admin_access: bool = False):
    """Привязать пользователя к аккаунту AmoCRM"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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


@admin_router.callback_query(F.data.startswith("user_amocrm_unlink:"))
async def handle_user_amocrm_unlink(callback: CallbackQuery, has_admin_access: bool = False):
    """Отвязать пользователя от аккаунта AmoCRM"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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

@admin_router.message(Command("notifications"))
async def cmd_notifications(message: Message, has_admin_access: bool = False):
    """Показать последние отправленные уведомления"""
    if not has_admin_access and not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    async for session in get_db():
        notifications = await get_recent_notifications(session, limit=20)

        if not notifications:
            await message.answer("📭 Нет отправленных уведомлений")
            return

        await message.answer(f"🔔 <b>Последние {len(notifications)} уведомлений:</b>", parse_mode="HTML")

        # Отправляем каждое уведомление отдельным сообщением
        for notification in notifications:
            text = f"📨 <b>Уведомление #{notification.id}</b>\n\n"

            # Получатель
            recipient = notification.recipient
            text += f"👤 <b>Кому:</b> {recipient.full_name}"
            if recipient.username:
                text += f" (@{recipient.username})"
            text += "\n"

            # Дата отправки
            text += f"📅 <b>Когда:</b> {notification.sent_at.strftime('%d.%m.%Y %H:%M:%S')}\n"

            # Тип уведомления
            notification_types = {
                "assignment": "📋 Назначение замера",
                "completion": "✅ Завершение замера",
                "change": "🔄 Изменение замерщика",
                "status_change": "🔄 Изменение статуса",
                "new_lead": "🆕 Новая заявка",
                "manager_notification": "💼 Уведомление менеджера"
            }
            type_text = notification_types.get(notification.notification_type, notification.notification_type)
            text += f"🏷 <b>Тип:</b> {type_text}\n\n"

            # Текст уведомления (убираем HTML теги для краткости)
            import re
            clean_text = re.sub('<[^<]+?>', '', notification.message_text)
            # Ограничиваем длину текста
            if len(clean_text) > 500:
                clean_text = clean_text[:500] + "..."
            text += f"💬 <b>Текст:</b>\n{clean_text}"

            await message.answer(text, parse_mode="HTML")


@admin_router.callback_query(F.data == "notifications")
async def handle_notifications_callback(callback: CallbackQuery, has_admin_access: bool = False, user_role: UserRole = None):
    """Обработчик кнопки 'Уведомления'"""
    if not has_admin_access and not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

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

            # Отправляем каждое уведомление отдельным сообщением
            for notification in notifications:
                text = f"📨 <b>Уведомление #{notification.id}</b>\n\n"

                # Получатель
                recipient = notification.recipient
                text += f"👤 <b>Кому:</b> {recipient.full_name}"
                if recipient.username:
                    text += f" (@{recipient.username})"
                text += "\n"

                # Дата отправки
                text += f"📅 <b>Когда:</b> {notification.sent_at.strftime('%d.%m.%Y %H:%M:%S')}\n"

                # Тип уведомления
                notification_types = {
                    "assignment": "📋 Назначение замера",
                    "completion": "✅ Завершение замера",
                    "change": "🔄 Изменение замерщика",
                    "status_change": "🔄 Изменение статуса",
                    "new_lead": "🆕 Новая заявка",
                    "manager_notification": "💼 Уведомление менеджера"
                }
                type_text = notification_types.get(notification.notification_type, notification.notification_type)
                text += f"🏷 <b>Тип:</b> {type_text}\n\n"

                # Текст уведомления (убираем HTML теги для краткости)
                import re
                clean_text = re.sub('<[^<]+?>', '', notification.message_text)
                # Ограничиваем длину текста
                if len(clean_text) > 500:
                    clean_text = clean_text[:500] + "..."
                text += f"💬 <b>Текст:</b>\n{clean_text}"

                await callback.bot.send_message(
                    callback.message.chat.id,
                    text,
                    parse_mode="HTML"
                )

            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении уведомлений: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении уведомлений", show_alert=True)


@admin_router.message(F.text == "🔔 Уведомления")
async def handle_notifications_button(message: Message, has_admin_access: bool = False):
    """Обработка нажатия кнопки Уведомления"""
    if not has_admin_access and not is_admin(message.from_user.id):
        return
    await cmd_notifications(message, has_admin_access=has_admin_access)


