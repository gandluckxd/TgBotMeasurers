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
from bot.filters import IsManager

# Создаем роутер для команд менеджера
manager_router = Router()


@manager_router.message(Command("start"), IsManager())
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

        text = f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
        text += "Вы вошли как <b>Менеджер</b>\n\n"
        text += "📋 Используйте меню ниже для отслеживания ваших заказов:\n\n"
        text += "Доступные команды:\n"
        text += "• 📊 Все замеры - просмотр всех ваших заказов\n"
        text += "• 🔄 Замеры в работе - текущие активные замеры\n"

        # Reply клавиатура
        from bot.keyboards.reply import get_manager_commands_keyboard
        reply_keyboard = get_manager_commands_keyboard()

        await message.answer(text, reply_markup=reply_keyboard, parse_mode="HTML")


@manager_router.message(Command("menu"), IsManager())
async def cmd_menu_manager(message: Message):
    """Обработчик команды /menu для менеджера"""
    async for session in get_db():
        keyboard = get_main_menu_keyboard("manager")
        await message.answer("📋 <b>Главное меню менеджера:</b>", reply_markup=keyboard, parse_mode="HTML")


@manager_router.message(Command("orders"), IsManager())
async def cmd_my_orders(message: Message):
    """Показать мои заказы"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

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


@manager_router.callback_query(F.data.startswith("manager:"), IsManager())
async def handle_manager_measurements(callback: CallbackQuery):
    """Обработка запросов заказов менеджера"""
    try:
        filter_type = callback.data.split(":")[1]

        async for session in get_db():
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            # Получаем заказы менеджера
            if filter_type == "all":
                # ВСЕ замеры менеджера
                measurements = await get_measurements_by_manager(session, user.id)
                title = "📊 Все заказы"

            elif filter_type == "in_progress":
                # ЗАМЕРЫ В РАБОТЕ (только ASSIGNED)
                measurements = await get_measurements_by_manager(
                    session, user.id, MeasurementStatus.ASSIGNED
                )
                title = "🔄 Замеры в работе"

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


# ========================================
# Обработчики текстовых кнопок (Reply Keyboard)
# ========================================

@manager_router.message(F.text == "📊 Мои заказы", IsManager())
async def handle_all_measurements_button(message: Message):
    """Обработка нажатия кнопки Мои заказы"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        # Получаем все заказы менеджера
        measurements = await get_measurements_by_manager(session, user.id)

        if not measurements:
            await message.answer("✅ У вас нет заказов с замерами")
            return

        text = f"📊 <b>Все ваши заказы ({len(measurements)}):</b>\n\n"

        for measurement in measurements[:20]:  # Показываем первые 20
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=True)
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@manager_router.message(F.text == "🔄 Заказы в работе", IsManager())
async def handle_in_progress_measurements_button(message: Message):
    """Обработка нажатия кнопки Заказы в работе"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)

        # Получаем замеры в работе (pending + assigned + in_progress)
        # Получаем замеры в работе (только ASSIGNED)
        measurements = await get_measurements_by_manager(
            session, user.id, MeasurementStatus.ASSIGNED
        )

        if not measurements:
            await message.answer("✅ Нет замеров в работе")
            return

        text = f"🔄 <b>Замеры в работе ({len(measurements)}):</b>\n\n"

        for measurement in measurements[:20]:  # Показываем первые 20
            text += f"━━━━━━━━━━━━━━━\n"
            text += measurement.get_info_text(detailed=True)
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@manager_router.message(Command("hide"), IsManager())
async def cmd_hide_keyboard(message: Message):
    """Скрыть клавиатуру команд"""
    async for session in get_db():
        from bot.keyboards.reply import remove_keyboard

        await message.answer(
            "✅ Клавиатура скрыта.\n\n"
            "Чтобы снова показать клавиатуру, используйте команду /start",
            reply_markup=remove_keyboard()
        )
