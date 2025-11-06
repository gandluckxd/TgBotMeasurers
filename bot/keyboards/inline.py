"""Inline клавиатуры для бота"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List

from database.models import User, Measurement, MeasurementStatus


def get_measurers_keyboard(measurers: List[User], measurement_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с замерщиками для назначения

    Args:
        measurers: Список замерщиков
        measurement_id: ID замера

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    for measurer in measurers:
        builder.button(
            text=f"👷 {measurer.full_name}",
            callback_data=f"assign:{measurement_id}:{measurer.id}"
        )

    # Размещаем кнопки в 2 колонки
    builder.adjust(2)

    return builder.as_markup()


def get_measurement_actions_keyboard(
    measurement_id: int,
    is_admin: bool = False,
    current_status: MeasurementStatus = MeasurementStatus.PENDING
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с действиями для замера

    Args:
        measurement_id: ID замера
        is_admin: Является ли пользователь администратором
        current_status: Текущий статус замера

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Кнопки для замерщика
    if current_status == MeasurementStatus.ASSIGNED:
        builder.button(
            text="🔄 Начать выполнение",
            callback_data=f"status:{measurement_id}:in_progress"
        )
    elif current_status == MeasurementStatus.IN_PROGRESS:
        builder.button(
            text="✅ Завершить",
            callback_data=f"status:{measurement_id}:completed"
        )

    # Кнопки для администратора
    if is_admin:
        builder.button(
            text="🔄 Изменить замерщика",
            callback_data=f"change_measurer:{measurement_id}"
        )

        if current_status not in [MeasurementStatus.COMPLETED, MeasurementStatus.CANCELLED]:
            builder.button(
                text="❌ Отменить замер",
                callback_data=f"status:{measurement_id}:cancelled"
            )

    # Кнопка просмотра деталей
    builder.button(
        text="📋 Детали",
        callback_data=f"details:{measurement_id}"
    )

    # Размещаем кнопки в 2 колонки
    builder.adjust(2)

    return builder.as_markup()


def get_measurement_status_keyboard(measurement_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для изменения статуса замера

    Args:
        measurement_id: ID замера

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    statuses = [
        ("📋 Назначен", MeasurementStatus.ASSIGNED),
        ("🔄 В процессе", MeasurementStatus.IN_PROGRESS),
        ("✅ Выполнен", MeasurementStatus.COMPLETED),
        ("❌ Отменен", MeasurementStatus.CANCELLED),
    ]

    for text, status in statuses:
        builder.button(
            text=text,
            callback_data=f"status:{measurement_id}:{status.value}"
        )

    builder.button(
        text="◀️ Назад",
        callback_data=f"back:{measurement_id}"
    )

    # Размещаем кнопки в 2 колонки
    builder.adjust(2)

    return builder.as_markup()


def get_main_menu_keyboard(role: str) -> InlineKeyboardMarkup:
    """
    Создать главное меню в зависимости от роли

    Args:
        role: Роль пользователя (admin, measurer, manager)

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    if role == "admin":
        builder.button(text="📋 Новые замеры", callback_data="list:pending")
        builder.button(text="🔄 В процессе", callback_data="list:in_progress")
        builder.button(text="✅ Выполненные", callback_data="list:completed")
        builder.button(text="📊 Все замеры", callback_data="list:all")
        builder.button(text="👥 Замерщики", callback_data="measurers_list")

    elif role == "measurer":
        builder.button(text="📋 Мои замеры", callback_data="my:assigned")
        builder.button(text="🔄 В процессе", callback_data="my:in_progress")
        builder.button(text="✅ Выполненные", callback_data="my:completed")

    elif role == "manager":
        builder.button(text="📋 Мои заказы", callback_data="manager:all")
        builder.button(text="⏳ Ожидают", callback_data="manager:pending")
        builder.button(text="✅ Выполненные", callback_data="manager:completed")

    # Размещаем кнопки в 2 колонки
    builder.adjust(2)

    return builder.as_markup()


def get_confirmation_keyboard(action: str, measurement_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру подтверждения действия

    Args:
        action: Действие для подтверждения
        measurement_id: ID замера

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Подтвердить",
        callback_data=f"confirm:{action}:{measurement_id}"
    )
    builder.button(
        text="❌ Отмена",
        callback_data=f"cancel:{action}:{measurement_id}"
    )

    builder.adjust(2)

    return builder.as_markup()


def get_back_button(callback_data: str = "menu") -> InlineKeyboardMarkup:
    """
    Создать кнопку "Назад"

    Args:
        callback_data: Callback data для кнопки

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data=callback_data)
    return builder.as_markup()
