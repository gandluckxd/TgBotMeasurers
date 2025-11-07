"""Обработчики для управления пригласительными ссылками (только для администраторов)"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from loguru import logger

from config import settings
from database.database import (
    get_session,
    create_invite_link,
    get_all_invite_links,
    get_invite_link_by_token,
    toggle_invite_link_active,
    delete_invite_link,
    get_user_by_telegram_id
)
from database.models import UserRole
from bot.keyboards.inline import (
    get_invite_links_keyboard,
    get_invite_link_detail_keyboard,
    get_invite_role_selection_keyboard,
    get_invite_options_keyboard,
    get_delete_invite_confirmation_keyboard
)

# Создаем роутер для пригласительных ссылок
invite_links_router = Router(name="invite_links")


def is_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return telegram_id in settings.admin_ids_list


@invite_links_router.message(Command("invites"))
async def cmd_invite_links(message: Message):
    """
    Команда для просмотра всех пригласительных ссылок
    Только для администраторов
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    async for session in get_session():
        links = await get_all_invite_links(session, include_inactive=True)

        if not links:
            await message.answer(
                "📝 <b>Пригласительные ссылки</b>\n\n"
                "Пока нет созданных ссылок.\n"
                "Используйте кнопку ниже для создания.",
                reply_markup=get_invite_links_keyboard([], page=0)
            )
            return

        text = f"📝 <b>Пригласительные ссылки</b>\n\n"
        text += f"Всего ссылок: {len(links)}\n"
        text += f"Активных: {sum(1 for l in links if l.is_valid)}\n\n"
        text += "Выберите ссылку для просмотра деталей:"

        await message.answer(
            text,
            reply_markup=get_invite_links_keyboard(links, page=0)
        )


@invite_links_router.callback_query(F.data == "invite_links")
async def show_invite_links(callback: CallbackQuery):
    """Показать список пригласительных ссылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    async for session in get_session():
        links = await get_all_invite_links(session, include_inactive=True)

        if not links:
            await callback.message.edit_text(
                "📝 <b>Пригласительные ссылки</b>\n\n"
                "Пока нет созданных ссылок.\n"
                "Используйте кнопку ниже для создания.",
                reply_markup=get_invite_links_keyboard([], page=0)
            )
        else:
            text = f"📝 <b>Пригласительные ссылки</b>\n\n"
            text += f"Всего ссылок: {len(links)}\n"
            text += f"Активных: {sum(1 for l in links if l.is_valid)}\n\n"
            text += "Выберите ссылку для просмотра деталей:"

            await callback.message.edit_text(
                text,
                reply_markup=get_invite_links_keyboard(links, page=0)
            )

    await callback.answer()


@invite_links_router.callback_query(F.data.startswith("invites_page:"))
async def navigate_invite_links(callback: CallbackQuery):
    """Навигация по страницам списка пригласительных ссылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    page = int(callback.data.split(":")[1])

    async for session in get_session():
        links = await get_all_invite_links(session, include_inactive=True)

        text = f"📝 <b>Пригласительные ссылки</b>\n\n"
        text += f"Всего ссылок: {len(links)}\n"
        text += f"Активных: {sum(1 for l in links if l.is_valid)}\n\n"
        text += "Выберите ссылку для просмотра деталей:"

        await callback.message.edit_text(
            text,
            reply_markup=get_invite_links_keyboard(links, page=page)
        )

    await callback.answer()


@invite_links_router.callback_query(F.data.startswith("invite_detail:"))
async def show_invite_detail(callback: CallbackQuery):
    """Показать детальную информацию о пригласительной ссылке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    link_id = int(callback.data.split(":")[1])

    async for session in get_session():
        # Получаем ссылку напрямую через query
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from database.models import InviteLink

        query = select(InviteLink).where(InviteLink.id == link_id).options(
            selectinload(InviteLink.created_by)
        )
        result = await session.execute(query)
        link = result.scalar_one_or_none()

        if not link:
            await callback.answer("❌ Ссылка не найдена", show_alert=True)
            return

        # Формируем URL для приглашения
        bot_username = (await callback.bot.get_me()).username
        invite_url = f"https://t.me/{bot_username}?start={link.token}"

        text = link.get_info_text()
        text += f"\n📎 <b>Ссылка:</b>\n<code>{invite_url}</code>\n"
        text += f"\n👤 <b>Создал:</b> {link.created_by.full_name}"

        await callback.message.edit_text(
            text,
            reply_markup=get_invite_link_detail_keyboard(link.id, link.is_active)
        )

    await callback.answer()


@invite_links_router.callback_query(F.data == "invite_create")
async def start_create_invite(callback: CallbackQuery):
    """Начать создание новой пригласительной ссылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await callback.message.edit_text(
        "➕ <b>Создание пригласительной ссылки</b>\n\n"
        "Выберите роль для новых пользователей:",
        reply_markup=get_invite_role_selection_keyboard()
    )

    await callback.answer()


@invite_links_router.callback_query(F.data.startswith("invite_role:"))
async def select_invite_role(callback: CallbackQuery):
    """Выбор роли для пригласительной ссылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    role = callback.data.split(":")[1]

    role_names = {
        "supervisor": "👔 Руководитель",
        "manager": "💼 Менеджер",
        "measurer": "👷 Замерщик"
    }

    await callback.message.edit_text(
        f"➕ <b>Создание ссылки для роли:</b> {role_names.get(role, role)}\n\n"
        "Выберите лимит использований:",
        reply_markup=get_invite_options_keyboard(role)
    )

    await callback.answer()


@invite_links_router.callback_query(F.data.startswith("invite_create_unlimited:"))
async def create_unlimited_invite(callback: CallbackQuery):
    """Создать пригласительную ссылку без ограничений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    role_str = callback.data.split(":")[1]
    role_map = {
        "supervisor": UserRole.SUPERVISOR,
        "manager": UserRole.MANAGER,
        "measurer": UserRole.MEASURER
    }
    role = role_map.get(role_str)

    if not role:
        await callback.answer("❌ Неверная роль", show_alert=True)
        return

    async for session in get_session():
        # Получаем пользователя
        user = await get_user_by_telegram_id(session, callback.from_user.id)

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Создаем ссылку
        link = await create_invite_link(
            session,
            created_by_id=user.id,
            role=role,
            max_uses=None,  # Без ограничений
            expires_at=None  # Бессрочная
        )

        # Формируем URL
        bot_username = (await callback.bot.get_me()).username
        invite_url = f"https://t.me/{bot_username}?start={link.token}"

        await callback.message.edit_text(
            "✅ <b>Пригласительная ссылка создана!</b>\n\n"
            f"{link.get_info_text()}\n"
            f"📎 <b>Ссылка:</b>\n<code>{invite_url}</code>\n\n"
            "Отправьте эту ссылку пользователю для регистрации.",
            reply_markup=get_invite_link_detail_keyboard(link.id, link.is_active)
        )

    await callback.answer("✅ Ссылка создана!")


@invite_links_router.callback_query(F.data.startswith("invite_create_uses:"))
async def create_limited_invite(callback: CallbackQuery):
    """Создать пригласительную ссылку с ограничением использований"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    role_str = parts[1]
    max_uses = int(parts[2])

    role_map = {
        "supervisor": UserRole.SUPERVISOR,
        "manager": UserRole.MANAGER,
        "measurer": UserRole.MEASURER
    }
    role = role_map.get(role_str)

    if not role:
        await callback.answer("❌ Неверная роль", show_alert=True)
        return

    async for session in get_session():
        # Получаем пользователя
        user = await get_user_by_telegram_id(session, callback.from_user.id)

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Создаем ссылку
        link = await create_invite_link(
            session,
            created_by_id=user.id,
            role=role,
            max_uses=max_uses,
            expires_at=None  # Бессрочная
        )

        # Формируем URL
        bot_username = (await callback.bot.get_me()).username
        invite_url = f"https://t.me/{bot_username}?start={link.token}"

        await callback.message.edit_text(
            "✅ <b>Пригласительная ссылка создана!</b>\n\n"
            f"{link.get_info_text()}\n"
            f"📎 <b>Ссылка:</b>\n<code>{invite_url}</code>\n\n"
            "Отправьте эту ссылку пользователю для регистрации.",
            reply_markup=get_invite_link_detail_keyboard(link.id, link.is_active)
        )

    await callback.answer("✅ Ссылка создана!")


@invite_links_router.callback_query(F.data.startswith("invite_toggle:"))
async def toggle_invite_active(callback: CallbackQuery):
    """Переключить активность пригласительной ссылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    link_id = int(callback.data.split(":")[1])

    async for session in get_session():
        link = await toggle_invite_link_active(session, link_id)

        if not link:
            await callback.answer("❌ Ссылка не найдена", show_alert=True)
            return

        # Обновляем информацию о ссылке
        # Формируем URL для приглашения
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from database.models import InviteLink

        query = select(InviteLink).where(InviteLink.id == link_id).options(
            selectinload(InviteLink.created_by)
        )
        result = await session.execute(query)
        link = result.scalar_one_or_none()

        if link:
            bot_username = (await callback.bot.get_me()).username
            invite_url = f"https://t.me/{bot_username}?start={link.token}"

            text = link.get_info_text()
            text += f"\n📎 <b>Ссылка:</b>\n<code>{invite_url}</code>\n"
            text += f"\n👤 <b>Создал:</b> {link.created_by.full_name}"

            await callback.message.edit_text(
                text,
                reply_markup=get_invite_link_detail_keyboard(link.id, link.is_active)
            )

        status = "активирована" if link.is_active else "деактивирована"
        await callback.answer(f"✅ Ссылка {status}")


@invite_links_router.callback_query(F.data.startswith("invite_delete_confirm:"))
async def confirm_delete_invite(callback: CallbackQuery):
    """Подтверждение удаления пригласительной ссылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    link_id = int(callback.data.split(":")[1])

    await callback.message.edit_text(
        "⚠️ <b>Подтверждение удаления</b>\n\n"
        "Вы уверены, что хотите удалить эту пригласительную ссылку?\n"
        "Это действие нельзя отменить.",
        reply_markup=get_delete_invite_confirmation_keyboard(link_id)
    )

    await callback.answer()


@invite_links_router.callback_query(F.data.startswith("invite_delete:"))
async def delete_invite(callback: CallbackQuery):
    """Удалить пригласительную ссылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    link_id = int(callback.data.split(":")[1])

    async for session in get_session():
        success = await delete_invite_link(session, link_id)

        if not success:
            await callback.answer("❌ Ссылка не найдена", show_alert=True)
            return

        # Возвращаемся к списку ссылок
        links = await get_all_invite_links(session, include_inactive=True)

        text = f"✅ <b>Ссылка удалена</b>\n\n"
        text += f"📝 <b>Пригласительные ссылки</b>\n\n"
        text += f"Всего ссылок: {len(links)}\n"
        text += f"Активных: {sum(1 for l in links if l.is_valid)}\n\n"

        if links:
            text += "Выберите ссылку для просмотра деталей:"
        else:
            text += "Пока нет созданных ссылок.\nИспользуйте кнопку ниже для создания."

        await callback.message.edit_text(
            text,
            reply_markup=get_invite_links_keyboard(links, page=0)
        )

    await callback.answer("✅ Ссылка удалена")


# Добавляем кнопку "Пригласительные ссылки" в быстрые команды админа
@invite_links_router.message(F.text == "🔗 Пригласительные ссылки")
async def quick_invite_links(message: Message):
    """Быстрая команда для просмотра пригласительных ссылок"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    await cmd_invite_links(message)
