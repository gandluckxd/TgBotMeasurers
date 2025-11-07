"""Reply клавиатуры для быстрого доступа к командам"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_admin_commands_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать клавиатуру с быстрыми командами для администратора

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()

    # Первая строка - основные команды
    builder.row(
        KeyboardButton(text="📋 Главное меню"),
        KeyboardButton(text="👤 Пользователи")
    )

    # Вторая строка - пригласительные ссылки
    builder.row(
        KeyboardButton(text="🔗 Пригласительные ссылки")
    )

    # Третья строка - замеры
    builder.row(
        KeyboardButton(text="🆕 Новые замеры"),
        KeyboardButton(text="🔄 В процессе")
    )

    # Четвёртая строка - списки
    builder.row(
        KeyboardButton(text="👥 Замерщики"),
        KeyboardButton(text="📊 Все замеры")
    )

    return builder.as_markup(resize_keyboard=True)


def get_measurer_commands_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать клавиатуру с быстрыми командами для замерщика

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()

    # Первая строка
    builder.row(
        KeyboardButton(text="📋 Главное меню"),
        KeyboardButton(text="📝 Мои замеры")
    )

    # Вторая строка
    builder.row(
        KeyboardButton(text="🔄 В работе"),
        KeyboardButton(text="✅ Выполненные")
    )

    return builder.as_markup(resize_keyboard=True)


def get_manager_commands_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать клавиатуру с быстрыми командами для менеджера

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()

    # Первая строка
    builder.row(
        KeyboardButton(text="📋 Главное меню"),
        KeyboardButton(text="📦 Мои заказы")
    )

    # Вторая строка
    builder.row(
        KeyboardButton(text="⏳ Ожидают"),
        KeyboardButton(text="✅ Выполнено")
    )

    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой отмены

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)


def get_keyboard_by_role(role: str) -> ReplyKeyboardMarkup:
    """
    Получить клавиатуру в зависимости от роли пользователя

    Args:
        role: Роль пользователя (admin, supervisor, manager, measurer)

    Returns:
        Reply клавиатура
    """
    if role in ["admin", "supervisor"]:
        return get_admin_commands_keyboard()
    elif role == "manager":
        return get_manager_commands_keyboard()
    elif role == "measurer":
        return get_measurer_commands_keyboard()
    else:
        return get_admin_commands_keyboard()  # По умолчанию
