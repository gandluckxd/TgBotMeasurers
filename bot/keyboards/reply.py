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

    # Все кнопки по одной в строке
    builder.row(KeyboardButton(text="📋 Главное меню"))
    builder.row(KeyboardButton(text="👤 Пользователи"))
    builder.row(KeyboardButton(text="📊 Все замеры"))
    builder.row(KeyboardButton(text="🔄 Замеры в работе"))
    builder.row(KeyboardButton(text="🗺 Управление зонами"))

    return builder.as_markup(resize_keyboard=True)


def get_measurer_commands_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать клавиатуру с быстрыми командами для замерщика
    ТОЛЬКО 2 команды: Все замеры и Замеры в работе

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()

    # Только 2 кнопки как требует пользователь!
    builder.row(
        KeyboardButton(text="📊 Мои замеры"),
        KeyboardButton(text="🔄 Мои замеры в работе")
    )

    return builder.as_markup(resize_keyboard=True)


def get_manager_commands_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать клавиатуру с быстрыми командами для менеджера
    ТОЛЬКО 2 команды: Все замеры и Замеры в работе

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()

    # Только 2 кнопки как требует пользователь!
    builder.row(
        KeyboardButton(text="📊 Мои заказы"),
        KeyboardButton(text="🔄 Заказы в работе")
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
