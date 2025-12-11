"""Обработчики команд наблюдателя"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from database import (
    get_db,
    get_user_by_telegram_id,
    get_measurement_by_id,
    get_measurements_by_status,
    get_or_create_user,
    MeasurementStatus,
    UserRole
)

# Создаем роутер для команд наблюдателя
observer_router = Router()


@observer_router.message(Command("start"))
async def cmd_start_observer(message: Message, user_role: UserRole = None):
    """Обработчик команды /start для наблюдателя"""
    # Проверяем, что это наблюдатель
    if user_role != UserRole.OBSERVER:
        return

    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.OBSERVER:
            return

        text = f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
        text += "Вы вошли как <b>Наблюдатель</b>\n\n"
        text += "📋 Используйте кнопки ниже для просмотра замеров:\n\n"
        text += "Доступные команды:\n"
        text += "• 📊 Все замеры - просмотр всех замеров всех замерщиков\n"
        text += "• 🔄 Замеры в работе - текущие активные замеры всех замерщиков\n\n"
        text += "❗️ <b>Важно:</b> Вы получаете уведомления о всех распределенных замерах."

        # Reply клавиатура
        from bot.keyboards.reply import get_observer_commands_keyboard
        reply_keyboard = get_observer_commands_keyboard()

        await message.answer(text, reply_markup=reply_keyboard, parse_mode="HTML")


@observer_router.message(Command("all"))
async def cmd_all_measurements(message: Message, user_role: UserRole = None):
    """Показать все замеры всех замерщиков"""
    logger.info(f"Observer cmd_all: user_role={user_role}, user_id={message.from_user.id}")

    # Проверяем, что это наблюдатель
    if user_role != UserRole.OBSERVER:
        logger.info(f"Observer cmd_all: Not observer, skipping. user_role={user_role}")
        return

    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.OBSERVER:
            logger.warning(f"Observer cmd_all: User not found or not observer in DB")
            return

        # Получаем все замеры (последние 20)
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
            await message.answer("✅ Нет замеров")
            return

        await message.answer(f"📊 <b>Все замеры (последние 20):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением
        for measurement in measurements:
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=False)

            # Для наблюдателя показываем только информацию просмотра (без кнопок действий)
            await message.answer(msg_text, parse_mode="HTML")


@observer_router.message(Command("pending"))
async def cmd_pending_measurements(message: Message, user_role: UserRole = None):
    """Показать замеры в работе всех замерщиков"""
    logger.info(f"Observer cmd_pending: user_role={user_role}, user_id={message.from_user.id}")

    # Проверяем, что это наблюдатель
    if user_role != UserRole.OBSERVER:
        logger.info(f"Observer cmd_pending: Not observer, skipping. user_role={user_role}")
        return

    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.OBSERVER:
            logger.warning(f"Observer cmd_pending: User not found or not observer in DB")
            return

        # Получаем все замеры в работе (статус ASSIGNED)
        measurements = await get_measurements_by_status(session, MeasurementStatus.ASSIGNED)

        if not measurements:
            await message.answer("✅ Нет замеров в работе")
            return

        await message.answer(f"🔄 <b>Замеры в работе ({len(measurements)}):</b>", parse_mode="HTML")

        # Отправляем каждый замер отдельным сообщением
        for measurement in measurements:
            msg_text = measurement.get_info_text(detailed=True, show_admin_info=False)

            # Для наблюдателя показываем только информацию просмотра (без кнопок действий)
            await message.answer(msg_text, parse_mode="HTML")


# ========================================
# Обработчики текстовых кнопок (Reply Keyboard)
# ========================================

@observer_router.message(F.text == "🔄 Замеры в работе")
async def handle_pending_button(message: Message, user_role: UserRole = None):
    """Обработка нажатия кнопки Замеры в работе"""
    # Проверяем, что это наблюдатель
    if user_role != UserRole.OBSERVER:
        return

    await cmd_pending_measurements(message, user_role=user_role)


@observer_router.message(F.text == "📊 Все замеры")
async def handle_all_button(message: Message, user_role: UserRole = None):
    """Обработка нажатия кнопки Все замеры"""
    # Проверяем, что это наблюдатель
    if user_role != UserRole.OBSERVER:
        return

    await cmd_all_measurements(message, user_role=user_role)
