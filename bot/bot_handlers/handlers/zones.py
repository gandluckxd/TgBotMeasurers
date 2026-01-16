"""Обработчики для управления зонами доставки"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from database import get_db, get_user_by_telegram_id, get_all_measurers, UserRole
from services.zone_service import ZoneService
from bot_handlers.keyboards.inline import (
    get_zones_menu_keyboard,
    get_zones_list_keyboard,
    get_zone_detail_keyboard,
    get_measurers_for_zone_keyboard,
    get_zones_for_measurer_keyboard,
    get_measurer_zones_keyboard
)
from config import settings

# Создаем роутер для управления зонами
zones_router = Router()


class ZoneStates(StatesGroup):
    """Состояния для работы с зонами"""
    waiting_for_zone_name = State()
    selecting_measurer_for_zone = State()
    selecting_zone_for_measurer = State()


def is_admin_or_supervisor(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором или руководителем"""
    # Проверяем, является ли пользователь администратором из конфига
    return telegram_id in settings.admin_ids_list


@zones_router.message(Command("zones"))
async def zones_command(message: Message):
    """Команда /zones для быстрого доступа к управлению зонами"""
    telegram_id = message.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await message.answer("❌ У вас нет доступа к этой функции")
        return

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


@zones_router.callback_query(F.data == "manage_zones")
async def show_zones_menu(callback: CallbackQuery):
    """Показать меню управления зонами"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    text = (
        "🗺 <b>Управление зонами доставки</b>\n\n"
        "Здесь вы можете:\n"
        "• Добавлять и удалять зоны доставки\n"
        "• Назначать зоны замерщикам\n"
        "• Просматривать текущие назначения\n\n"
        "Выберите действие:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_zones_menu_keyboard()
    )
    await callback.answer()


@zones_router.callback_query(F.data == "view_all_zones")
async def view_all_zones(callback: CallbackQuery):
    """Показать список всех зон"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    async for session in get_db():
        zone_service = ZoneService(session)
        zones = await zone_service.get_all_zones()

        if not zones:
            text = "📋 <b>Список зон доставки</b>\n\nЗоны пока не добавлены."
            await callback.message.edit_text(
                text,
                reply_markup=get_zones_list_keyboard([])
            )
        else:
            text = f"📋 <b>Список зон доставки</b>\n\nВсего зон: {len(zones)}\n"
            await callback.message.edit_text(
                text,
                reply_markup=get_zones_list_keyboard(zones)
            )

    await callback.answer()


@zones_router.callback_query(F.data == "add_zone")
async def start_add_zone(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления новой зоны"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    await callback.message.edit_text(
        "📝 <b>Добавление новой зоны</b>\n\n"
        "Введите название зоны доставки:"
    )
    await state.set_state(ZoneStates.waiting_for_zone_name)
    await callback.answer()


@zones_router.message(ZoneStates.waiting_for_zone_name)
async def process_zone_name(message: Message, state: FSMContext):
    """Обработка ввода названия зоны"""
    zone_name = message.text.strip()

    if not zone_name:
        await message.answer("❌ Название зоны не может быть пустым. Попробуйте еще раз:")
        return

    async for session in get_db():
        zone_service = ZoneService(session)
        zone = await zone_service.create_zone(zone_name)

        if zone:
            await message.answer(
                f"✅ Зона <b>'{zone_name}'</b> успешно добавлена!",
                reply_markup=get_zones_menu_keyboard()
            )
            logger.info(f"Пользователь {message.from_user.id} добавил зону: {zone_name}")
        else:
            await message.answer(
                f"❌ Зона <b>'{zone_name}'</b> уже существует.",
                reply_markup=get_zones_menu_keyboard()
            )

    await state.clear()


@zones_router.callback_query(F.data.startswith("zone_detail:"))
async def show_zone_detail(callback: CallbackQuery):
    """Показать детали зоны"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    zone_id = int(callback.data.split(":")[1])

    async for session in get_db():
        zone_service = ZoneService(session)
        zone = await zone_service.get_zone_by_id(zone_id)

        if not zone:
            await callback.answer("Зона не найдена", show_alert=True)
            return

        # Получаем замерщиков для этой зоны
        measurers = await zone_service.get_measurers_by_zone(zone.zone_name)

        text = f"🗺 <b>Зона: {zone.zone_name}</b>\n\n"

        if measurers:
            text += f"👷 <b>Назначенные замерщики ({len(measurers)}):</b>\n"
            for measurer in measurers:
                text += f"  • {measurer.full_name}\n"
        else:
            text += "⚠️ Зона не назначена ни одному замерщику\n"

        text += f"\n📅 Создана: {zone.created_at.strftime('%d.%m.%Y %H:%M')}"

        await callback.message.edit_text(
            text,
            reply_markup=get_zone_detail_keyboard(zone_id)
        )

    await callback.answer()


@zones_router.callback_query(F.data.startswith("confirm_delete_zone:"))
async def confirm_delete_zone(callback: CallbackQuery):
    """Показать подтверждение удаления зоны"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    zone_id = int(callback.data.split(":")[1])

    async for session in get_db():
        zone_service = ZoneService(session)
        zone = await zone_service.get_zone_by_id(zone_id)

        if not zone:
            await callback.answer("Зона не найдена", show_alert=True)
            return

        # Получаем количество замерщиков в этой зоне
        measurers = await zone_service.get_measurers_by_zone(zone.zone_name)
        measurers_count = len(measurers)

        text = (
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы действительно хотите удалить зону <b>'{zone.zone_name}'</b>?\n\n"
        )

        if measurers_count > 0:
            text += (
                f"⚠️ <b>Внимание!</b> У этой зоны есть {measurers_count} "
                f"{'назначенный замерщик' if measurers_count == 1 else 'назначенных замерщика'}.\n"
                f"При удалении зоны все привязки к замерщикам будут удалены!"
            )
        else:
            text += "✅ У этой зоны нет назначенных замерщиков."

        from bot_handlers.keyboards.inline import get_delete_zone_confirmation_keyboard
        await callback.message.edit_text(
            text,
            reply_markup=get_delete_zone_confirmation_keyboard(zone_id)
        )

    await callback.answer()


@zones_router.callback_query(F.data.startswith("delete_zone:"))
async def delete_zone(callback: CallbackQuery):
    """Удалить зону (после подтверждения)"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    zone_id = int(callback.data.split(":")[1])

    async for session in get_db():
        zone_service = ZoneService(session)
        zone = await zone_service.get_zone_by_id(zone_id)

        if not zone:
            await callback.answer("Зона не найдена", show_alert=True)
            return

        zone_name = zone.zone_name
        success = await zone_service.delete_zone(zone_id)

        if success:
            await callback.message.edit_text(
                f"✅ Зона <b>'{zone_name}'</b> успешно удалена!",
                reply_markup=get_zones_menu_keyboard()
            )
            logger.info(f"Пользователь {telegram_id} удалил зону: {zone_name}")
        else:
            await callback.answer("Ошибка при удалении зоны", show_alert=True)

    await callback.answer()


@zones_router.callback_query(F.data == "assign_zones_to_measurers")
async def show_measurers_for_assignment(callback: CallbackQuery):
    """Показать список замерщиков для назначения зон"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    async for session in get_db():
        measurers = await get_all_measurers(session)

        if not measurers:
            text = "📋 <b>Управление зонами замерщиков</b>\n\n⚠️ Замерщики еще не добавлены."
            await callback.message.edit_text(
                text,
                reply_markup=get_zones_menu_keyboard()
            )
        else:
            text = (
                f"📋 <b>Управление зонами замерщиков</b>\n\n"
                f"Выберите замерщика для назначения зон:\n\n"
                f"Всего замерщиков: {len(measurers)}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=get_measurers_for_zone_keyboard(measurers)
            )

    await callback.answer()


@zones_router.callback_query(F.data.startswith("measurer_zones:"))
async def show_measurer_zones(callback: CallbackQuery):
    """Показать зоны замерщика"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    measurer_id = int(callback.data.split(":")[1])

    async for session in get_db():
        from database import get_user_by_id
        measurer = await get_user_by_id(session, measurer_id)

        if not measurer:
            await callback.answer("Замерщик не найден", show_alert=True)
            return

        zone_service = ZoneService(session)
        assigned_zones = await zone_service.get_measurer_zones(measurer_id)
        available_zones = await zone_service.get_zones_not_assigned_to_measurer(measurer_id)

        text = f"👷 <b>Замерщик: {measurer.full_name}</b>\n\n"

        if assigned_zones:
            text += f"🗺 <b>Назначенные зоны ({len(assigned_zones)}):</b>\n"
            for zone in assigned_zones:
                text += f"  • {zone.zone_name}\n"
        else:
            text += "⚠️ Зоны не назначены\n"

        if available_zones:
            text += f"\n📋 <b>Доступно для назначения:</b> {len(available_zones)} зон"

        await callback.message.edit_text(
            text,
            reply_markup=get_measurer_zones_keyboard(measurer_id, assigned_zones, available_zones)
        )

    await callback.answer()


@zones_router.callback_query(F.data.startswith("add_zone_to_measurer:"))
async def add_zone_to_measurer(callback: CallbackQuery):
    """Назначить зону замерщику"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    _, measurer_id, zone_id = callback.data.split(":")
    measurer_id = int(measurer_id)
    zone_id = int(zone_id)

    async for session in get_db():
        zone_service = ZoneService(session)
        zone = await zone_service.get_zone_by_id(zone_id)

        from database import get_user_by_id
        measurer = await get_user_by_id(session, measurer_id)

        if not zone or not measurer:
            await callback.answer("Ошибка: зона или замерщик не найдены", show_alert=True)
            return

        assignment = await zone_service.assign_zone_to_measurer(measurer_id, zone_id)

        if assignment:
            await callback.answer(f"✅ Зона '{zone.zone_name}' назначена замерщику {measurer.full_name}")
            logger.info(f"Пользователь {telegram_id} назначил зону {zone.zone_name} замерщику {measurer.full_name}")

            # Обновляем отображение
            await show_measurer_zones(callback)
        else:
            await callback.answer("Зона уже назначена этому замерщику", show_alert=True)


@zones_router.callback_query(F.data.startswith("remove_zone_from_measurer:"))
async def remove_zone_from_measurer(callback: CallbackQuery):
    """Убрать зону у замерщика"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    _, measurer_id, zone_id = callback.data.split(":")
    measurer_id = int(measurer_id)
    zone_id = int(zone_id)

    async for session in get_db():
        zone_service = ZoneService(session)
        zone = await zone_service.get_zone_by_id(zone_id)

        from database import get_user_by_id
        measurer = await get_user_by_id(session, measurer_id)

        if not zone or not measurer:
            await callback.answer("Ошибка: зона или замерщик не найдены", show_alert=True)
            return

        success = await zone_service.remove_zone_from_measurer(measurer_id, zone_id)

        if success:
            await callback.answer(f"✅ Зона '{zone.zone_name}' удалена у замерщика {measurer.full_name}")
            logger.info(f"Пользователь {telegram_id} удалил зону {zone.zone_name} у замерщика {measurer.full_name}")

            # Обновляем отображение
            await show_measurer_zones(callback)
        else:
            await callback.answer("Ошибка при удалении зоны", show_alert=True)


@zones_router.callback_query(F.data.startswith("show_available_zones:"))
async def show_available_zones(callback: CallbackQuery):
    """Показать доступные зоны для назначения замерщику"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    measurer_id = int(callback.data.split(":")[1])

    async for session in get_db():
        from database import get_user_by_id
        measurer = await get_user_by_id(session, measurer_id)

        if not measurer:
            await callback.answer("Замерщик не найден", show_alert=True)
            return

        zone_service = ZoneService(session)
        available_zones = await zone_service.get_zones_not_assigned_to_measurer(measurer_id)

        if not available_zones:
            await callback.answer("Нет доступных зон для назначения", show_alert=True)
            return

        text = (
            f"👷 <b>Замерщик: {measurer.full_name}</b>\n\n"
            f"📋 Выберите зону для назначения:"
        )

        await callback.message.edit_text(
            text,
            reply_markup=get_zones_for_measurer_keyboard(measurer_id, available_zones)
        )

    await callback.answer()


@zones_router.callback_query(F.data == "back_to_zones_menu")
async def back_to_zones_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню управления зонами"""
    await state.clear()
    await show_zones_menu(callback)


@zones_router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в главное меню администратора"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    await state.clear()

    # Определяем роль пользователя
    async for session in get_db():
        user = await get_user_by_telegram_id(session, telegram_id)
        if user:
            role = user.role.value
            from bot_handlers.keyboards.inline import get_main_menu_keyboard

            text = (
                f"👋 <b>Главное меню</b>\n\n"
                f"Ваша роль: {role}\n"
                f"Выберите действие:"
            )

            await callback.message.edit_text(
                text,
                reply_markup=get_main_menu_keyboard(role)
            )
            break

    await callback.answer()
