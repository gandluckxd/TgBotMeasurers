"""Простой обработчик для установки имени замерщика"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from database import get_db, get_user_by_id
from services.measurer_name_service import MeasurerNameService
from config import settings

# Создаем роутер
measurer_names_router = Router()


class MeasurerNameStates(StatesGroup):
    """Состояния для ввода имени"""
    waiting_for_name = State()


def is_admin_or_supervisor(telegram_id: int) -> bool:
    """Проверка прав администратора"""
    return telegram_id in settings.admin_ids_list


@measurer_names_router.callback_query(F.data.startswith("user_set_measurer_name:"))
async def start_set_measurer_name(callback: CallbackQuery, state: FSMContext):
    """Начать процесс установки имени замерщика"""
    telegram_id = callback.from_user.id

    if not is_admin_or_supervisor(telegram_id):
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    async for session in get_db():
        user = await get_user_by_id(session, user_id)

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Получаем текущее имя
        name_service = MeasurerNameService(session)
        current_name = await name_service.get_measurer_name_by_user_id(user_id)

        if current_name:
            text = (
                f"👷 <b>Текущее имя замерщика:</b> {current_name}\n\n"
                f"Введите новое имя замерщика (как в AmoCRM):\n\n"
                f"💡 Имя будет нормализовано автоматически"
            )
        else:
            text = (
                f"👷 <b>Установка имени замерщика</b>\n\n"
                f"Пользователь: {user.full_name}\n\n"
                f"Введите имя замерщика (как оно указано в поле \"Замерщик\" компании в AmoCRM):\n\n"
                f"💡 Имя будет нормализовано автоматически (приведено к нижнему регистру)"
            )

        await callback.message.edit_text(text)
        await state.update_data(user_id=user_id)
        await state.set_state(MeasurerNameStates.waiting_for_name)
        await callback.answer()


@measurer_names_router.message(MeasurerNameStates.waiting_for_name)
async def process_measurer_name(message: Message, state: FSMContext):
    """Обработка ввода имени замерщика"""
    name = message.text.strip()

    if not name:
        await message.answer("❌ Имя не может быть пустым. Попробуйте еще раз:")
        return

    data = await state.get_data()
    user_id = data.get("user_id")

    async for session in get_db():
        name_service = MeasurerNameService(session)
        user = await get_user_by_id(session, user_id)

        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            await state.clear()
            return

        # Устанавливаем имя (метод сам нормализует)
        success = await name_service.set_measurer_name_for_user(user_id, name)

        if success:
            normalized = name_service.normalize_name(name)

            # Создаем клавиатуру с кнопкой "Назад"
            from bot.keyboards.inline import get_user_detail_keyboard
            keyboard = get_user_detail_keyboard(user_id, user.role.value, user.is_active)

            await message.answer(
                f"✅ Имя замерщика установлено!\n\n"
                f"Пользователь: {user.full_name}\n"
                f"Введенное имя: {name}\n"
                f"Нормализованное: {normalized}\n\n"
                f"Теперь при создании замеров в AmoCRM с этим именем в поле \"Замерщик\" "
                f"компании, система будет автоматически предлагать {user.full_name}",
                reply_markup=keyboard
            )
        else:
            # Создаем клавиатуру с кнопкой "Назад" даже при ошибке
            from bot.keyboards.inline import get_user_detail_keyboard
            keyboard = get_user_detail_keyboard(user_id, user.role.value, user.is_active)

            await message.answer(
                f"❌ Не удалось установить имя. Возможно, это имя уже используется другим замерщиком.",
                reply_markup=keyboard
            )

        await state.clear()
