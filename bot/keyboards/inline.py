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

    # Кнопки для замерщика - только "Завершить" если замер в работе
    if current_status == MeasurementStatus.IN_PROGRESS and not is_admin:
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
        role: Роль пользователя (admin, supervisor, measurer, manager)

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Руководитель (supervisor) имеет ПОЛНОСТЬЮ такое же меню как администратор!
    if role in ["admin", "supervisor"]:
        builder.button(text="📋 Новые замеры", callback_data="list:pending")
        builder.button(text="🔄 В процессе", callback_data="list:in_progress")
        builder.button(text="✅ Выполненные", callback_data="list:completed")
        builder.button(text="📊 Все замеры", callback_data="list:all")
        builder.button(text="👥 Замерщики", callback_data="measurers_list")
        builder.button(text="👤 Управление пользователями", callback_data="users_list")

    elif role == "measurer":
        # У замерщика ТОЛЬКО 2 команды: Все замеры и Замеры в работе
        builder.button(text="📊 Все замеры", callback_data="my:all")
        builder.button(text="🔄 Замеры в работе", callback_data="my:in_progress")

    elif role == "manager":
        # У менеджера ТОЛЬКО 2 команды: Все замеры и Замеры в работе
        builder.button(text="📊 Все замеры", callback_data="manager:all")
        builder.button(text="🔄 Замеры в работе", callback_data="manager:in_progress")

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


# Клавиатуры для управления пользователями
def get_users_list_keyboard(users: List[User], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру со списком пользователей

    Args:
        users: Список пользователей
        page: Номер страницы
        per_page: Количество пользователей на странице

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]

    role_emoji = {
        "admin": "👑",
        "supervisor": "👔",
        "manager": "💼",
        "measurer": "👷"
    }

    for user in page_users:
        emoji = role_emoji.get(user.role.value, "👤")
        status = "✅" if user.is_active else "⛔"
        text = f"{emoji} {status} {user.full_name} ({user.role.value})"
        builder.button(
            text=text,
            callback_data=f"user_detail:{user.id}"
        )

    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"users_page:{page-1}"
        ))
    if end_idx < len(users):
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"users_page:{page+1}"
        ))

    # Размещаем пользователей по одному в строке
    builder.adjust(1)

    # Добавляем навигацию
    if nav_buttons:
        builder.row(*nav_buttons)

    # Кнопка для управления пригласительными ссылками
    builder.row(InlineKeyboardButton(
        text="🔗 Пригласительные ссылки",
        callback_data="invite_links"
    ))

    # Кнопка назад в главное меню
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню",
        callback_data="menu"
    ))

    return builder.as_markup()


def get_user_detail_keyboard(user_id: int, current_role: str, is_active: bool) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с действиями для пользователя

    Args:
        user_id: ID пользователя
        current_role: Текущая роль пользователя
        is_active: Активен ли пользователь

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Кнопки изменения роли
    builder.button(
        text="🔄 Изменить роль",
        callback_data=f"user_change_role:{user_id}"
    )

    # Кнопка активации/деактивации
    if is_active:
        builder.button(
            text="⛔ Деактивировать",
            callback_data=f"user_toggle:{user_id}"
        )
    else:
        builder.button(
            text="✅ Активировать",
            callback_data=f"user_toggle:{user_id}"
        )

    # Кнопка назад
    builder.button(
        text="◀️ К списку",
        callback_data="users_list"
    )

    builder.adjust(1)
    return builder.as_markup()


def get_role_selection_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру выбора роли

    Args:
        user_id: ID пользователя

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    roles = [
        ("👔 Руководитель", "supervisor"),
        ("💼 Менеджер", "manager"),
        ("👷 Замерщик", "measurer")
    ]

    for text, role in roles:
        builder.button(
            text=text,
            callback_data=f"user_set_role:{user_id}:{role}"
        )

    builder.button(
        text="◀️ Отмена",
        callback_data=f"user_detail:{user_id}"
    )

    builder.adjust(1)
    return builder.as_markup()


def get_invite_links_keyboard(
    links: List["InviteLink"],
    page: int = 0,
    per_page: int = 5
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру со списком пригласительных ссылок

    Args:
        links: Список пригласительных ссылок
        page: Номер страницы
        per_page: Количество ссылок на странице

    Returns:
        Inline клавиатура
    """
    from database.models import UserRole

    builder = InlineKeyboardBuilder()

    # Рассчитываем пагинацию
    start = page * per_page
    end = start + per_page
    page_links = links[start:end]
    total_pages = (len(links) + per_page - 1) // per_page

    role_emoji = {
        UserRole.ADMIN: "👑",
        UserRole.SUPERVISOR: "👔",
        UserRole.MANAGER: "💼",
        UserRole.MEASURER: "👷"
    }

    # Добавляем ссылки
    for link in page_links:
        status = "✅" if link.is_valid else "❌"
        uses_text = f"{link.current_uses}"
        if link.max_uses:
            uses_text += f"/{link.max_uses}"
        else:
            uses_text += "/∞"

        builder.row(
            InlineKeyboardButton(
                text=f"{status} {role_emoji.get(link.role, '❓')} {link.role.value.title()} - {uses_text}",
                callback_data=f"invite_detail:{link.id}"
            )
        )

    # Добавляем навигацию
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"invites_page:{page - 1}")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"invites_page:{page + 1}")
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    # Добавляем кнопки действий
    builder.row(
        InlineKeyboardButton(text="➕ Создать ссылку", callback_data="invite_create")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu")
    )

    return builder.as_markup()


def get_invite_link_detail_keyboard(link_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для детальной информации о пригласительной ссылке

    Args:
        link_id: ID пригласительной ссылки
        is_active: Активна ли ссылка

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Кнопка активации/деактивации
    if is_active:
        builder.row(
            InlineKeyboardButton(
                text="🔴 Деактивировать",
                callback_data=f"invite_toggle:{link_id}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="🟢 Активировать",
                callback_data=f"invite_toggle:{link_id}"
            )
        )

    # Кнопка удаления
    builder.row(
        InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"invite_delete_confirm:{link_id}"
        )
    )

    # Кнопка назад
    builder.row(
        InlineKeyboardButton(
            text="🔙 К списку ссылок",
            callback_data="invite_links"
        )
    )

    return builder.as_markup()


def get_invite_role_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру выбора роли для новой пригласительной ссылки

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Добавляем роли (кроме ADMIN - ссылки для админов создавать нельзя)
    builder.row(
        InlineKeyboardButton(
            text="👔 Руководитель",
            callback_data="invite_role:supervisor"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💼 Менеджер",
            callback_data="invite_role:manager"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👷 Замерщик",
            callback_data="invite_role:measurer"
        )
    )

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="invite_links"
        )
    )

    return builder.as_markup()


def get_invite_options_keyboard(role: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру настройки параметров пригласительной ссылки

    Args:
        role: Роль для ссылки

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="♾️ Без ограничений",
            callback_data=f"invite_create_unlimited:{role}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="1️⃣ 1 использование",
            callback_data=f"invite_create_uses:{role}:1"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="5️⃣ 5 использований",
            callback_data=f"invite_create_uses:{role}:5"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔟 10 использований",
            callback_data=f"invite_create_uses:{role}:10"
        )
    )

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="invite_links"
        )
    )

    return builder.as_markup()


def get_delete_invite_confirmation_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру подтверждения удаления пригласительной ссылки

    Args:
        link_id: ID ссылки

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"invite_delete:{link_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"invite_detail:{link_id}"
        )
    )

    return builder.as_markup()
