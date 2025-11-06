"""Обработчики команд менеджера"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from database import (
    get_db,
    get_user_by_telegram_id,
    get_measurement_by_id,
    get_measurements_by_manager,
    get_or_create_user,
    MeasurementStatus,
    UserRole
)
from bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_back_button
)

# Создаем роутер для команд менеджера
manager_router = Router()


@manager_router.message(Command("start"))
async def cmd_start_manager(message: Message):
    """Обработчик команды /start для менеджера"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        # Если пользователь не существует, создаем его как менеджера
        if not user:
            user = await get_or_create_user(
                session=session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                role=UserRole.MANAGER
            )

        # Проверяем роль
        if user.role != UserRole.MANAGER:
            # Это администратор или замерщик, пропускаем
            return

        text = f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
        text += "Вы вошли как <b>Менеджер</b>\n\n"
        text += "📋 Используйте меню ниже для отслеживания ваших заказов:\n\n"
        text += "Доступные команды:\n"
        text += "/menu - Главное меню\n"
        text += "/orders - Мои заказы\n"

        keyboard = get_main_menu_keyboard("manager")

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@manager_router.message(Command("menu"))
async def cmd_menu_manager(message: Message):
    """Обработчик команды /menu для менеджера"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.MANAGER:
            return

        keyboard = get_main_menu_keyboard("manager")
        await message.answer("📋 <b>Главное меню менеджера:</b>", reply_markup=keyboard, parse_mode="HTML")


@manager_router.message(Command("orders"))
async def cmd_my_orders(message: Message):
    """Показать мои заказы"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        if not user or user.role != UserRole.MANAGER:
            await message.answer("⚠️ У вас нет доступа к этой команде.")
            return

        # Получаем все заказы менеджера
        measurements = await get_measurements_by_manager(session, user.id)

        if not measurements:
            await message.answer("✅ У вас нет заказов с замерами")
            return

        text = f"📋 <b>Ваши заказы ({len(measurements)}):</b>\n\n"

        for measurement in measurements:
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=True)
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@manager_router.callback_query(F.data.startswith("manager:"))
async def handle_manager_measurements(callback: CallbackQuery):
    """Обработка запросов заказов менеджера"""
    try:
        filter_type = callback.data.split(":")[1]

        async for session in get_db():
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user or user.role != UserRole.MANAGER:
                await callback.answer("⚠️ У вас нет доступа", show_alert=True)
                return

            # Получаем заказы менеджера
            if filter_type == "all":
                measurements = await get_measurements_by_manager(session, user.id)
                title = "📋 Все заказы"

            elif filter_type == "pending":
                measurements = await get_measurements_by_manager(
                    session, user.id, MeasurementStatus.PENDING
                )
                title = "⏳ Ожидают назначения"

            elif filter_type == "completed":
                measurements = await get_measurements_by_manager(
                    session, user.id, MeasurementStatus.COMPLETED
                )
                title = "✅ Выполненные замеры"

            else:
                await callback.answer("❌ Неизвестный фильтр")
                return

            if not measurements:
                text = f"{title}\n\n❌ Нет заказов"
            else:
                text = f"<b>{title} ({len(measurements)}):</b>\n\n"

                for measurement in measurements[:10]:  # Показываем первые 10
                    text += f"━━━━━━━━━━━━━━━\n"
                    text += measurement.get_info_text(detailed=True)
                    text += "\n"

            keyboard = get_main_menu_keyboard("manager")

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении заказов: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при получении заказов", show_alert=True)
