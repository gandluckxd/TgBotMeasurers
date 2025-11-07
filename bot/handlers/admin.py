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
    MeasurementStatus,
    UserRole
)
from bot.keyboards.inline import (
    get_measurers_keyboard,
    get_main_menu_keyboard,
    get_measurement_actions_keyboard,
    get_users_list_keyboard,
    get_user_detail_keyboard,
    get_role_selection_keyboard
)
from bot.keyboards.reply import (
    get_admin_commands_keyboard
)
from bot.utils.notifications import (
    send_assignment_notification_to_measurer,
    send_assignment_notification_to_manager,
    send_measurer_change_notification
)
from config import settings

# Создаем роутер для администраторских команд
admin_router = Router()


def is_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return telegram_id in settings.admin_ids_list


@admin_router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    if not is_admin(message.from_user.id):
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
        text += "Вы вошли как <b>Администратор</b>\n\n"
        text += "📋 Используйте меню ниже для управления замерами:\n\n"
        text += "Доступные команды:\n"
        text += "/menu - Главное меню\n"
        text += "/users - Управление пользователями\n"
        text += "/measurers - Список замерщиков\n"
        text += "/pending - Новые замеры\n"
        text += "/all - Все замеры\n"

        # Reply клавиатура с быстрыми командами
        reply_keyboard = get_admin_commands_keyboard()
        await message.answer(text, reply_markup=reply_keyboard, parse_mode="HTML")

        # Inline клавиатура с главным меню
        inline_keyboard = get_main_menu_keyboard("admin")
        await message.answer(
            "📋 <b>Или используйте кнопки ниже:</b>",
            reply_markup=inline_keyboard,
            parse_mode="HTML"
        )


@admin_router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Обработчик команды /menu"""
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    keyboard = get_main_menu_keyboard("admin")
    await message.answer("📋 <b>Главное меню администратора:</b>", reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("measurers"))
async def cmd_measurers(message: Message):
    """Показать список замерщиков"""
    if not is_admin(message.from_user.id):
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
async def cmd_pending(message: Message):
    """Показать новые замеры, ожидающие назначения"""
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    async for session in get_db():
        measurements = await get_measurements_by_status(session, MeasurementStatus.PENDING)

        if not measurements:
            await message.answer("✅ Нет новых замеров, ожидающих назначения")
            return

        text = f"📋 <b>Новые замеры ({len(measurements)}):</b>\n\n"

        for measurement in measurements:
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=False)
            text += "\n"

        await message.answer(text, parse_mode="HTML")

        # Отправляем каждый замер с кнопками для назначения
        measurers = await get_all_measurers(session)

        if measurers:
            for measurement in measurements:
                msg_text = measurement.get_info_text(detailed=True)
                msg_text += "\n\n👇 <b>Выберите замерщика:</b>"

                keyboard = get_measurers_keyboard(measurers, measurement.id)

                await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("all"))
async def cmd_all(message: Message):
    """Показать все замеры"""
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ У вас нет доступа к этой команде.")
        return

    async for session in get_db():
        from sqlalchemy import select
        from database.models import Measurement

        result = await session.execute(
            select(Measurement).order_by(Measurement.created_at.desc()).limit(20)
        )
        measurements = list(result.scalars().all())

        if not measurements:
            await message.answer("❌ Нет замеров")
            return

        text = f"📊 <b>Все замеры (последние 20):</b>\n\n"

        for measurement in measurements:
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=False)
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("assign:"))
async def handle_assign_measurer(callback: CallbackQuery):
    """Обработка назначения замерщика на замер"""
    if not is_admin(callback.from_user.id):
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
            from database.models import User

            result = await session.execute(select(User).where(User.id == measurer_id))
            measurer = result.scalar_one_or_none()

            if not measurer:
                await callback.answer("❌ Замерщик не найден", show_alert=True)
                return

            # Сохраняем старого замерщика для уведомления
            old_measurer = measurement.measurer

            # Назначаем замерщика
            measurement.measurer_id = measurer.id
            measurement.status = MeasurementStatus.ASSIGNED
            measurement.assigned_at = datetime.now()

            await session.commit()
            await session.refresh(measurement)

            # Обновляем сообщение
            new_text = "✅ <b>Замерщик назначен!</b>\n\n"
            new_text += measurement.get_info_text(detailed=True)

            keyboard = get_measurement_actions_keyboard(
                measurement.id,
                is_admin=True,
                current_status=measurement.status
            )

            await callback.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")

            # Отправляем уведомления
            await send_assignment_notification_to_measurer(callback.bot, measurer, measurement)

            if measurement.manager:
                await send_assignment_notification_to_manager(
                    callback.bot,
                    measurement.manager,
                    measurement,
                    measurer
                )

            # Если был старый замерщик, отправляем ему уведомление
            if old_measurer and old_measurer.id != measurer.id:
                await send_measurer_change_notification(
                    callback.bot,
                    old_measurer,
                    measurer,
                    measurement,
                    measurement.manager
                )

            await callback.answer(f"✅ Замер назначен на {measurer.full_name}")
            logger.info(f"Замер #{measurement.id} назначен на замерщика {measurer.id}")

    except Exception as e:
        logger.error(f"Ошибка при назначении замерщика: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при назначении замерщика", show_alert=True)


@admin_router.callback_query(F.data.startswith("change_measurer:"))
async def handle_change_measurer(callback: CallbackQuery):
    """Обработка изменения замерщика"""
    if not is_admin(callback.from_user.id):
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
            text += measurement.get_info_text(detailed=True)
            text += "\n\n👇 <b>Выберите замерщика:</b>"

            keyboard = get_measurers_keyboard(measurers, measurement.id)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при изменении замерщика: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при изменении замерщика", show_alert=True)


@admin_router.callback_query(F.data.startswith("list:"))
async def handle_list(callback: CallbackQuery):
    """Обработка запросов списков замеров"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

    try:
        list_type = callback.data.split(":")[1]

        async for session in get_db():
            if list_type == "all":
                from sqlalchemy import select
                from database.models import Measurement

                result = await session.execute(
                    select(Measurement).order_by(Measurement.created_at.desc()).limit(20)
                )
                measurements = list(result.scalars().all())
                title = "📊 Все замеры (последние 20)"

            elif list_type in ["pending", "assigned", "in_progress", "completed"]:
                status = MeasurementStatus(list_type)
                measurements = await get_measurements_by_status(session, status)

                status_titles = {
                    "pending": "📋 Новые замеры",
                    "assigned": "📋 Назначенные замеры",
                    "in_progress": "🔄 Замеры в процессе",
                    "completed": "✅ Выполненные замеры"
                }
                title = status_titles.get(list_type, "📋 Замеры")
            else:
                await callback.answer("❌ Неизвестный тип списка")
                return

            if not measurements:
                text = f"{title}\n\n❌ Нет замеров"
            else:
                text = f"<b>{title} ({len(measurements)}):</b>\n\n"

                for measurement in measurements[:10]:  # Показываем первые 10
                    text += f"━━━━━━━━━━━━━━━\n"
                    text += measurement.get_info_text(detailed=False)
                    text += "\n"

            keyboard = get_main_menu_keyboard("admin")

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении списка: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении списка", show_alert=True)


# ========================================
# Обработчики текстовых кнопок (Reply Keyboard)
# ========================================

@admin_router.message(F.text == "📋 Главное меню")
async def handle_main_menu_button(message: Message):
    """Обработка нажатия кнопки Главное меню"""
    if not is_admin(message.from_user.id):
        return
    await cmd_menu(message)


@admin_router.message(F.text == "👤 Пользователи")
async def handle_users_button(message: Message):
    """Обработка нажатия кнопки Пользователи"""
    if not is_admin(message.from_user.id):
        return
    await cmd_users(message)


@admin_router.message(F.text == "🆕 Новые замеры")
async def handle_pending_button(message: Message):
    """Обработка нажатия кнопки Новые замеры"""
    if not is_admin(message.from_user.id):
        return
    await cmd_pending(message)


@admin_router.message(F.text == "🔄 В процессе")
async def handle_in_progress_button(message: Message):
    """Обработка нажатия кнопки В процессе"""
    if not is_admin(message.from_user.id):
        return

    async for session in get_db():
        measurements = await get_measurements_by_status(session, MeasurementStatus.IN_PROGRESS)

        if not measurements:
            await message.answer("✅ Нет замеров в процессе выполнения")
            return

        text = f"🔄 <b>Замеры в процессе ({len(measurements)}):</b>\n\n"

        for measurement in measurements:
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=False)
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@admin_router.message(F.text == "👥 Замерщики")
async def handle_measurers_button(message: Message):
    """Обработка нажатия кнопки Замерщики"""
    if not is_admin(message.from_user.id):
        return
    await cmd_measurers(message)


@admin_router.message(F.text == "📊 Все замеры")
async def handle_all_button(message: Message):
    """Обработка нажатия кнопки Все замеры"""
    if not is_admin(message.from_user.id):
        return
    await cmd_all(message)


# ========================================
# Управление пользователями
# ========================================

@admin_router.message(Command("users"))
async def cmd_users(message: Message):
    """Показать список всех пользователей"""
    if not is_admin(message.from_user.id):
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
        text += "👑 - админ | 👔 - менеджер | 👷 - замерщик"

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "users_list")
async def handle_users_list(callback: CallbackQuery):
    """Показать список пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

    try:
        async for session in get_db():
            users = await get_all_users(session)

            keyboard = get_users_list_keyboard(users, page=0)
            text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"
            text += "✅ - активен | ⛔ - неактивен\n"
            text += "👑 - админ | 👔 - менеджер | 👷 - замерщик"

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении списка", show_alert=True)


@admin_router.callback_query(F.data.startswith("users_page:"))
async def handle_users_page(callback: CallbackQuery):
    """Переключение страницы списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ У вас нет прав для этого действия", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[1])

        async for session in get_db():
            users = await get_all_users(session)
            keyboard = get_users_list_keyboard(users, page=page)

            text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"
            text += "✅ - активен | ⛔ - неактивен\n"
            text += "👑 - админ | 👔 - менеджер | 👷 - замерщик"

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при переключении страницы: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_detail:"))
async def handle_user_detail(callback: CallbackQuery):
    """Показать детали пользователя"""
    if not is_admin(callback.from_user.id):
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
            text += f"<b>Создан:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"

            keyboard = get_user_detail_keyboard(user.id, user.role.value, user.is_active)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении деталей пользователя: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_change_role:"))
async def handle_user_change_role(callback: CallbackQuery):
    """Показать меню выбора роли"""
    if not is_admin(callback.from_user.id):
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
async def handle_user_set_role(callback: CallbackQuery):
    """Установить роль пользователя"""
    if not is_admin(callback.from_user.id):
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

            # Отправляем уведомление пользователю
            try:
                notification_text = f"🔔 <b>Ваша роль изменена</b>\n\n"
                notification_text += f"Новая роль: <b>{role_names.get(new_role, new_role)}</b>"
                await callback.bot.send_message(
                    user.telegram_id,
                    notification_text,
                    parse_mode="HTML"
                )
            except Exception:
                pass  # Пользователь может не запускать бота

    except Exception as e:
        logger.error(f"Ошибка при установке роли: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при установке роли", show_alert=True)


@admin_router.callback_query(F.data.startswith("user_toggle:"))
async def handle_user_toggle(callback: CallbackQuery):
    """Переключить статус активности пользователя"""
    if not is_admin(callback.from_user.id):
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
async def handle_measurers_list(callback: CallbackQuery):
    """Показать список замерщиков через callback"""
    if not is_admin(callback.from_user.id):
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


