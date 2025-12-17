"""Обработчики регистрации пользователей через инвайт-ссылки"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject
from loguru import logger

from database.database import (
    get_session,
    get_invite_link_by_token,
    use_invite_link,
    create_user,
    get_user_by_telegram_id
)
from database.models import UserRole
from bot.keyboards.reply import (
    get_admin_commands_keyboard,
    get_measurer_commands_keyboard,
    get_manager_commands_keyboard,
    get_observer_commands_keyboard
)
from bot.utils.logging_decorators import log_command

# Создаем роутер для регистрации
registration_router = Router(name="registration")


@registration_router.message(CommandStart(deep_link=True))
@log_command
async def cmd_start_with_invite(message: Message, command: CommandObject):
    """
    Обработка команды /start с инвайт-ссылкой
    Формат: /start <token>
    """
    telegram_id = message.from_user.id
    token = command.args  # Получаем токен из deep link

    if not token:
        await message.answer(
            "❌ <b>Ошибка:</b> Не указан токен приглашения.\n\n"
            "Пожалуйста, используйте полную ссылку-приглашение."
        )
        return

    logger.info(f"Попытка регистрации пользователя {telegram_id} по токену {token[:10]}...")

    # Проверяем, не зарегистрирован ли уже пользователь
    async for session in get_session():
        existing_user = await get_user_by_telegram_id(session, telegram_id)

        if existing_user:
            # Пользователь уже зарегистрирован
            role_emoji = {
                UserRole.ADMIN: "👑",
                UserRole.SUPERVISOR: "👔",
                UserRole.MANAGER: "💼",
                UserRole.MEASURER: "👷",
                UserRole.OBSERVER: "👁"
            }

            keyboard = None
            if existing_user.role == UserRole.ADMIN:
                keyboard = get_admin_commands_keyboard()
            elif existing_user.role == UserRole.SUPERVISOR:
                keyboard = get_admin_commands_keyboard()  # У руководителя та же клавиатура, что у админа
            elif existing_user.role == UserRole.MANAGER:
                keyboard = get_manager_commands_keyboard()
            elif existing_user.role == UserRole.MEASURER:
                keyboard = get_measurer_commands_keyboard()
            elif existing_user.role == UserRole.OBSERVER:
                keyboard = get_observer_commands_keyboard()

            await message.answer(
                f"👋 <b>С возвращением!</b>\n\n"
                f"Вы уже зарегистрированы в системе.\n"
                f"Ваша роль: {role_emoji.get(existing_user.role, '❓')} <b>{existing_user.role.value.upper()}</b>",
                reply_markup=keyboard
            )
            return

        # Получаем пригласительную ссылку
        invite_link = await get_invite_link_by_token(session, token)

        if not invite_link:
            await message.answer(
                "❌ <b>Ошибка:</b> Пригласительная ссылка не найдена.\n\n"
                "Возможно, ссылка устарела или была удалена. "
                "Попросите администратора создать новую ссылку."
            )
            return

        # Проверяем валидность ссылки
        if not invite_link.is_valid:
            reasons = []
            if not invite_link.is_active:
                reasons.append("она деактивирована")
            if invite_link.expires_at and invite_link.expires_at < invite_link.created_at:
                reasons.append("истек срок действия")
            if invite_link.max_uses and invite_link.current_uses >= invite_link.max_uses:
                reasons.append("исчерпан лимит использований")

            reason_text = ", ".join(reasons) if reasons else "неизвестная причина"

            await message.answer(
                f"❌ <b>Ссылка недействительна</b>\n\n"
                f"Причина: {reason_text}.\n\n"
                f"Попросите администратора создать новую ссылку."
            )
            return

        # Создаем нового пользователя
        try:
            user = await create_user(
                session,
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                role=invite_link.role
            )

            # Используем ссылку (увеличиваем счетчик)
            await use_invite_link(session, invite_link)

            # Определяем клавиатуру в зависимости от роли
            keyboard = None
            role_description = ""

            if user.role == UserRole.ADMIN:
                keyboard = get_admin_commands_keyboard()
                role_description = (
                    "Вы можете:\n"
                    "• Создавать пригласительные ссылки\n"
                    "• Управлять пользователями\n"
                    "• Управлять замерами\n"
                    "• Назначать замерщиков"
                )
            elif user.role == UserRole.SUPERVISOR:
                keyboard = get_admin_commands_keyboard()
                role_description = (
                    "Вы можете:\n"
                    "• Управлять замерами\n"
                    "• Назначать замерщиков\n"
                    "• Просматривать всех пользователей"
                )
            elif user.role == UserRole.MANAGER:
                keyboard = get_manager_commands_keyboard()
                role_description = (
                    "Вы можете:\n"
                    "• Просматривать свои заказы\n"
                    "• Отслеживать статусы замеров"
                )
            elif user.role == UserRole.MEASURER:
                keyboard = get_measurer_commands_keyboard()
                role_description = (
                    "Вы можете:\n"
                    "• Просматривать назначенные вам замеры\n"
                    "• Обновлять статусы замеров\n"
                    "• Добавлять заметки"
                )
            elif user.role == UserRole.OBSERVER:
                keyboard = get_observer_commands_keyboard()
                role_description = (
                    "Вы можете:\n"
                    "• Просматривать все замеры всех замерщиков\n"
                    "• Получать уведомления о всех распределенных замерах"
                )

            role_emoji = {
                UserRole.ADMIN: "👑",
                UserRole.SUPERVISOR: "👔",
                UserRole.MANAGER: "💼",
                UserRole.MEASURER: "👷",
                UserRole.OBSERVER: "👁"
            }

            role_names = {
                UserRole.ADMIN: "Администратор",
                UserRole.SUPERVISOR: "Руководитель",
                UserRole.MANAGER: "Менеджер",
                UserRole.MEASURER: "Замерщик",
                UserRole.OBSERVER: "Наблюдатель"
            }

            await message.answer(
                f"✅ <b>Добро пожаловать в систему!</b>\n\n"
                f"Вы успешно зарегистрированы.\n\n"
                f"Ваша роль: {role_emoji.get(user.role, '❓')} <b>{role_names.get(user.role, user.role.value)}</b>\n\n"
                f"{role_description}\n\n"
                f"Используйте кнопки ниже для быстрого доступа к командам.",
                reply_markup=keyboard
            )

            logger.success(
                f"Новый пользователь зарегистрирован: {telegram_id} "
                f"({user.full_name}) с ролью {user.role.value}"
            )

        except Exception as e:
            logger.error(f"Ошибка при создании пользователя: {e}", exc_info=True)
            await message.answer(
                "❌ <b>Произошла ошибка</b>\n\n"
                "Не удалось завершить регистрацию. "
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )


@registration_router.message(CommandStart())
@log_command
async def cmd_start_without_invite(message: Message):
    """
    Обработка команды /start без инвайт-ссылки
    """
    telegram_id = message.from_user.id

    # Проверяем, зарегистрирован ли пользователь
    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)

        if user:
            # Пользователь уже зарегистрирован
            role_emoji = {
                UserRole.ADMIN: "👑",
                UserRole.SUPERVISOR: "👔",
                UserRole.MANAGER: "💼",
                UserRole.MEASURER: "👷",
                UserRole.OBSERVER: "👁"
            }

            keyboard = None
            if user.role == UserRole.ADMIN:
                keyboard = get_admin_commands_keyboard()
            elif user.role == UserRole.SUPERVISOR:
                keyboard = get_admin_commands_keyboard()
            elif user.role == UserRole.MANAGER:
                keyboard = get_manager_commands_keyboard()
            elif user.role == UserRole.MEASURER:
                keyboard = get_measurer_commands_keyboard()
            elif user.role == UserRole.OBSERVER:
                keyboard = get_observer_commands_keyboard()

            await message.answer(
                f"👋 <b>Здравствуйте!</b>\n\n"
                f"Ваша роль: {role_emoji.get(user.role, '❓')} <b>{user.role.value.upper()}</b>\n\n"
                f"Используйте кнопки ниже для работы с системой.",
                reply_markup=keyboard
            )
        else:
            # Пользователь не зарегистрирован
            await message.answer(
                "👋 <b>Добро пожаловать!</b>\n\n"
                "Для доступа к системе управления замерами вам нужна пригласительная ссылка.\n\n"
                "Пожалуйста, обратитесь к администратору для получения доступа."
            )
