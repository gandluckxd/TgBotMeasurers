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

from database.models import Base, User, Measurement, UserRole, MeasurementStatus
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


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Получить пользователя по Telegram ID"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


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
    result = await session.execute(
        select(Measurement).where(Measurement.id == measurement_id)
    )
    return result.scalar_one_or_none()


async def get_measurement_by_amocrm_id(session: AsyncSession, amocrm_lead_id: int) -> Measurement | None:
    """Получить замер по ID сделки в AmoCRM"""
    result = await session.execute(
        select(Measurement).where(Measurement.amocrm_lead_id == amocrm_lead_id)
    )
    return result.scalar_one_or_none()


async def get_measurements_by_status(
    session: AsyncSession,
    status: MeasurementStatus,
    limit: int | None = None
) -> list[Measurement]:
    """Получить замеры по статусу"""
    query = select(Measurement).where(Measurement.status == status).order_by(Measurement.created_at.desc())

    if limit:
        query = query.limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_measurements_by_measurer(
    session: AsyncSession,
    measurer_id: int,
    status: MeasurementStatus | None = None
) -> list[Measurement]:
    """Получить замеры по замерщику"""
    query = select(Measurement).where(Measurement.measurer_id == measurer_id)

    if status:
        query = query.where(Measurement.status == status)

    query = query.order_by(Measurement.created_at.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_measurements_by_manager(
    session: AsyncSession,
    manager_id: int,
    status: MeasurementStatus | None = None
) -> list[Measurement]:
    """Получить замеры по менеджеру"""
    query = select(Measurement).where(Measurement.manager_id == manager_id)

    if status:
        query = query.where(Measurement.status == status)

    query = query.order_by(Measurement.created_at.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


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
        status=MeasurementStatus.PENDING
    )
    session.add(measurement)
    await session.commit()
    await session.refresh(measurement)
    logger.info(f"Создан новый замер: {measurement}")
    return measurement
