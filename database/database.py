"""Управление базой данных"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import select
from loguru import logger

from database.models import Base, User, Measurement, InviteLink, UserRole, MeasurementStatus
from config import settings


class Database:
    """Класс для управления подключением к базе данных"""

    def __init__(self, url: str, echo: bool = False):
        self.engine: AsyncEngine = create_async_engine(url, echo=echo)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        """Создание всех таблиц"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы базы данных созданы")

    async def drop_tables(self):
        """Удаление всех таблиц (для тестирования)"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Таблицы базы данных удалены")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Получение сессии для работы с БД"""
        async with self.session_factory() as session:
            yield session

    async def close(self):
        """Закрытие подключения к БД"""
        await self.engine.dispose()
        logger.info("Подключение к базе данных закрыто")


# Глобальный экземпляр базы данных
db = Database(settings.database_url, echo=settings.log_level == "DEBUG")


# Вспомогательные функции для работы с БД
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД"""
    async for session in db.get_session():
        yield session


# Алиас для совместимости с новым кодом
get_session = get_db


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Получить пользователя по Telegram ID"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    role: UserRole = UserRole.MEASURER
) -> User:
    """Создать нового пользователя (без проверки на существование)"""
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        role=role
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Создан новый пользователь: {user}")
    return user


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    role: UserRole = UserRole.MEASURER
) -> User:
    """Получить или создать пользователя"""
    user = await get_user_by_telegram_id(session, telegram_id)

    if not user:
        user = await create_user(session, telegram_id, username, first_name, last_name, role)
    else:
        # Обновляем информацию о пользователе
        updated = False
        if username and user.username != username:
            user.username = username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True

        if updated:
            await session.commit()
            await session.refresh(user)

    return user


async def get_all_measurers(session: AsyncSession) -> list[User]:
    """Получить всех активных замерщиков"""
    result = await session.execute(
        select(User).where(
            User.role == UserRole.MEASURER,
            User.is_active == True
        )
    )
    return list(result.scalars().all())


async def get_measurement_by_id(session: AsyncSession, measurement_id: int) -> Measurement | None:
    """Получить замер по ID"""
    from sqlalchemy.orm import joinedload

    result = await session.execute(
        select(Measurement)
        .options(joinedload(Measurement.measurer), joinedload(Measurement.manager))
        .where(Measurement.id == measurement_id)
    )
    return result.scalar_one_or_none()


async def get_measurement_by_amocrm_id(session: AsyncSession, amocrm_lead_id: int) -> Measurement | None:
    """Получить замер по ID сделки в AmoCRM"""
    from sqlalchemy.orm import joinedload

    result = await session.execute(
        select(Measurement)
        .options(joinedload(Measurement.measurer), joinedload(Measurement.manager))
        .where(Measurement.amocrm_lead_id == amocrm_lead_id)
    )
    return result.scalar_one_or_none()


async def get_measurements_by_status(
    session: AsyncSession,
    status: MeasurementStatus,
    limit: int | None = None
) -> list[Measurement]:
    """Получить замеры по статусу"""
    from sqlalchemy.orm import joinedload

    query = (
        select(Measurement)
        .options(joinedload(Measurement.measurer), joinedload(Measurement.manager))
        .where(Measurement.status == status)
        .order_by(Measurement.created_at.desc())
    )

    if limit:
        query = query.limit(limit)

    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def get_measurements_by_measurer(
    session: AsyncSession,
    measurer_id: int,
    status: MeasurementStatus | None = None
) -> list[Measurement]:
    """Получить замеры по замерщику"""
    from sqlalchemy.orm import joinedload

    query = (
        select(Measurement)
        .options(joinedload(Measurement.measurer), joinedload(Measurement.manager))
        .where(Measurement.measurer_id == measurer_id)
    )

    if status:
        query = query.where(Measurement.status == status)

    query = query.order_by(Measurement.created_at.desc())

    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def get_measurements_by_manager(
    session: AsyncSession,
    manager_id: int,
    status: MeasurementStatus | None = None
) -> list[Measurement]:
    """Получить замеры по менеджеру"""
    from sqlalchemy.orm import joinedload

    query = (
        select(Measurement)
        .options(joinedload(Measurement.measurer), joinedload(Measurement.manager))
        .where(Measurement.manager_id == manager_id)
    )

    if status:
        query = query.where(Measurement.status == status)

    query = query.order_by(Measurement.created_at.desc())

    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def create_measurement(
    session: AsyncSession,
    amocrm_lead_id: int,
    client_name: str,
    address: str,
    client_phone: str | None = None,
    description: str | None = None,
    manager_id: int | None = None
) -> Measurement:
    """Создать новый замер"""
    measurement = Measurement(
        amocrm_lead_id=amocrm_lead_id,
        client_name=client_name,
        client_phone=client_phone,
        address=address,
        description=description,
        manager_id=manager_id,
        status=MeasurementStatus.ASSIGNED
    )
    session.add(measurement)
    await session.commit()
    await session.refresh(measurement)
    logger.info(f"Создан новый замер: {measurement}")
    return measurement


# Функции для управления пользователями
async def get_all_users(session: AsyncSession, role: UserRole | None = None) -> list[User]:
    """Получить всех пользователей, опционально с фильтром по роли"""
    query = select(User)

    if role:
        query = query.where(User.role == role)

    query = query.order_by(User.created_at.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Получить пользователя по ID"""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def update_user_role(
    session: AsyncSession,
    user_id: int,
    new_role: UserRole
) -> User | None:
    """Изменить роль пользователя"""
    user = await get_user_by_id(session, user_id)

    if not user:
        return None

    old_role = user.role
    user.role = new_role
    await session.commit()
    await session.refresh(user)

    logger.info(f"Роль пользователя {user.telegram_id} изменена: {old_role.value} -> {new_role.value}")
    return user


async def toggle_user_active(
    session: AsyncSession,
    user_id: int
) -> User | None:
    """Переключить статус активности пользователя"""
    user = await get_user_by_id(session, user_id)

    if not user:
        return None

    user.is_active = not user.is_active
    await session.commit()
    await session.refresh(user)

    status = "активирован" if user.is_active else "деактивирован"
    logger.info(f"Пользователь {user.telegram_id} {status}")
    return user


async def create_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
    role: UserRole = UserRole.MEASURER
) -> User:
    """Создать пользователя по Telegram ID с указанной ролью"""
    # Проверяем, не существует ли уже такой пользователь
    existing_user = await get_user_by_telegram_id(session, telegram_id)

    if existing_user:
        # Если пользователь существует, обновляем его роль
        return await update_user_role(session, existing_user.id, role)

    # Создаем нового пользователя
    user = User(
        telegram_id=telegram_id,
        role=role,
        is_active=True
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Создан новый пользователь с ID {telegram_id} и ролью {role.value}")
    return user


# ============================================================================
# Функции для работы с пригласительными ссылками
# ============================================================================

async def create_invite_link(
    session: AsyncSession,
    created_by_id: int,
    role: UserRole,
    max_uses: int | None = None,
    expires_at = None
) -> InviteLink:
    """
    Создать новую пригласительную ссылку

    Args:
        session: Сессия БД
        created_by_id: ID пользователя, создавшего ссылку
        role: Роль для новых пользователей
        max_uses: Максимальное количество использований (None = неограниченно)
        expires_at: Дата истечения срока действия (None = бессрочная)

    Returns:
        Созданная пригласительная ссылка
    """
    import secrets

    # Генерируем уникальный токен
    token = secrets.token_urlsafe(32)

    invite_link = InviteLink(
        token=token,
        role=role,
        created_by_id=created_by_id,
        max_uses=max_uses,
        current_uses=0,
        expires_at=expires_at,
        is_active=True
    )

    session.add(invite_link)
    await session.commit()
    await session.refresh(invite_link)

    logger.info(f"Создана пригласительная ссылка с токеном {token[:10]}... для роли {role.value}")
    return invite_link


async def get_invite_link_by_token(
    session: AsyncSession,
    token: str
) -> InviteLink | None:
    """
    Получить пригласительную ссылку по токену

    Args:
        session: Сессия БД
        token: Токен ссылки

    Returns:
        Пригласительная ссылка или None
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(InviteLink).where(InviteLink.token == token).options(
        selectinload(InviteLink.created_by)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_all_invite_links(
    session: AsyncSession,
    include_inactive: bool = False
) -> list[InviteLink]:
    """
    Получить все пригласительные ссылки

    Args:
        session: Сессия БД
        include_inactive: Включить неактивные ссылки

    Returns:
        Список пригласительных ссылок
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(InviteLink).options(
        selectinload(InviteLink.created_by)
    )

    if not include_inactive:
        query = query.where(InviteLink.is_active == True)

    query = query.order_by(InviteLink.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def use_invite_link(
    session: AsyncSession,
    invite_link: InviteLink
) -> bool:
    """
    Использовать пригласительную ссылку (увеличить счетчик использований)

    Args:
        session: Сессия БД
        invite_link: Пригласительная ссылка

    Returns:
        True если ссылка была успешно использована
    """
    if not invite_link.is_valid:
        logger.warning(f"Попытка использовать недействительную ссылку {invite_link.token}")
        return False

    invite_link.current_uses += 1

    # Если достигнут лимит использований, деактивируем ссылку
    if invite_link.max_uses and invite_link.current_uses >= invite_link.max_uses:
        invite_link.is_active = False
        logger.info(f"Ссылка {invite_link.token[:10]}... деактивирована (достигнут лимит)")

    await session.commit()
    await session.refresh(invite_link)

    logger.info(f"Ссылка {invite_link.token[:10]}... использована ({invite_link.current_uses}/{invite_link.max_uses or '∞'})")
    return True


async def toggle_invite_link_active(
    session: AsyncSession,
    link_id: int
) -> InviteLink | None:
    """
    Переключить активность пригласительной ссылки

    Args:
        session: Сессия БД
        link_id: ID ссылки

    Returns:
        Обновленная ссылка или None
    """
    from sqlalchemy import select

    query = select(InviteLink).where(InviteLink.id == link_id)
    result = await session.execute(query)
    invite_link = result.scalar_one_or_none()

    if not invite_link:
        logger.warning(f"Пригласительная ссылка с ID {link_id} не найдена")
        return None

    invite_link.is_active = not invite_link.is_active
    await session.commit()
    await session.refresh(invite_link)

    status = "активирована" if invite_link.is_active else "деактивирована"
    logger.info(f"Ссылка {invite_link.token[:10]}... {status}")
    return invite_link


async def delete_invite_link(
    session: AsyncSession,
    link_id: int
) -> bool:
    """
    Удалить пригласительную ссылку

    Args:
        session: Сессия БД
        link_id: ID ссылки

    Returns:
        True если ссылка была удалена
    """
    from sqlalchemy import select, delete

    query = select(InviteLink).where(InviteLink.id == link_id)
    result = await session.execute(query)
    invite_link = result.scalar_one_or_none()

    if not invite_link:
        logger.warning(f"Пригласительная ссылка с ID {link_id} не найдена")
        return False

    token_preview = invite_link.token[:10]
    await session.delete(invite_link)
    await session.commit()

    logger.info(f"Удалена пригласительная ссылка {token_preview}...")
    return True
