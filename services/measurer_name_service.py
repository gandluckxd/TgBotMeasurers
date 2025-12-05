"""Сервис для работы с именами замерщиков (дилерами)"""
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.models import MeasurerName, MeasurerNameAssignment, User, UserRole


class MeasurerNameService:
    """Сервис для управления именами замерщиков"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Нормализовать имя замерщика для сравнения

        Args:
            name: Исходное имя

        Returns:
            Нормализованное имя (lower case, без лишних пробелов)
        """
        return name.strip().lower()

    async def create_measurer_name(self, name: str) -> Optional[MeasurerName]:
        """
        Создать новое имя замерщика

        Args:
            name: Название имени замерщика (дилера)

        Returns:
            MeasurerName или None если имя уже существует
        """
        # Нормализуем имя для проверки
        normalized = self.normalize_name(name)

        # Проверяем, существует ли уже такое имя
        existing = await self.get_measurer_name_by_name(name)
        if existing:
            logger.warning(f"Имя замерщика '{name}' уже существует")
            return None

        # Сохраняем нормализованное имя
        measurer_name = MeasurerName(name=normalized)
        self.session.add(measurer_name)
        await self.session.commit()
        await self.session.refresh(measurer_name)

        logger.info(f"Создано новое имя замерщика: {normalized}")
        return measurer_name

    async def get_measurer_name_by_name(self, name: str) -> Optional[MeasurerName]:
        """
        Получить имя замерщика по названию

        Args:
            name: Название имени замерщика

        Returns:
            MeasurerName или None
        """
        normalized = self.normalize_name(name)
        stmt = select(MeasurerName).where(MeasurerName.name == normalized)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_measurer_name_by_id(self, measurer_name_id: int) -> Optional[MeasurerName]:
        """
        Получить имя замерщика по ID

        Args:
            measurer_name_id: ID имени замерщика

        Returns:
            MeasurerName или None
        """
        stmt = select(MeasurerName).where(MeasurerName.id == measurer_name_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_measurer_names(self) -> List[MeasurerName]:
        """Получить все имена замерщиков"""
        stmt = select(MeasurerName).order_by(MeasurerName.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_measurer_name(self, measurer_name_id: int) -> bool:
        """
        Удалить имя замерщика

        Args:
            measurer_name_id: ID имени замерщика

        Returns:
            True если имя удалено, False если не найдено
        """
        measurer_name = await self.get_measurer_name_by_id(measurer_name_id)
        if not measurer_name:
            logger.warning(f"Имя замерщика с ID {measurer_name_id} не найдено")
            return False

        await self.session.delete(measurer_name)
        await self.session.commit()
        logger.info(f"Имя замерщика '{measurer_name.name}' удалено")
        return True

    async def assign_measurer_name_to_user(
        self, user_id: int, measurer_name_id: int
    ) -> Optional[MeasurerNameAssignment]:
        """
        Назначить имя замерщика пользователю

        Args:
            user_id: ID пользователя
            measurer_name_id: ID имени замерщика

        Returns:
            MeasurerNameAssignment или None если уже назначено или пользователь не замерщик
        """
        # Проверяем, что пользователь - замерщик
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or user.role != UserRole.MEASURER:
            logger.warning(f"Пользователь {user_id} не является замерщиком")
            return None

        # Проверяем, не назначено ли уже это имя КОМУ-ЛИБО (UNIQUE constraint на measurer_name_id)
        stmt = select(MeasurerNameAssignment).where(
            MeasurerNameAssignment.measurer_name_id == measurer_name_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if existing.user_id == user_id:
                logger.warning(
                    f"Имя замерщика {measurer_name_id} уже назначено пользователю {user_id}"
                )
            else:
                logger.warning(
                    f"Имя замерщика {measurer_name_id} уже назначено другому пользователю {existing.user_id}"
                )
            return None

        assignment = MeasurerNameAssignment(
            user_id=user_id,
            measurer_name_id=measurer_name_id
        )
        self.session.add(assignment)
        await self.session.commit()
        await self.session.refresh(assignment)

        logger.info(f"Имя замерщика {measurer_name_id} назначено пользователю {user_id}")
        return assignment

    async def remove_measurer_name_from_user(
        self, user_id: int, measurer_name_id: int
    ) -> bool:
        """
        Убрать имя замерщика у пользователя

        Args:
            user_id: ID пользователя
            measurer_name_id: ID имени замерщика

        Returns:
            True если имя удалено, False если не найдено
        """
        stmt = select(MeasurerNameAssignment).where(
            and_(
                MeasurerNameAssignment.user_id == user_id,
                MeasurerNameAssignment.measurer_name_id == measurer_name_id
            )
        )
        result = await self.session.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            logger.warning(
                f"Назначение имени замерщика {measurer_name_id} пользователю {user_id} не найдено"
            )
            return False

        await self.session.delete(assignment)
        await self.session.commit()
        logger.info(f"Имя замерщика {measurer_name_id} удалено у пользователя {user_id}")
        return True

    async def get_user_measurer_names(self, user_id: int) -> List[MeasurerName]:
        """
        Получить все имена замерщиков пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Список имён замерщиков
        """
        stmt = (
            select(MeasurerName)
            .join(MeasurerNameAssignment)
            .where(MeasurerNameAssignment.user_id == user_id)
            .order_by(MeasurerName.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_by_measurer_name(self, measurer_name: str) -> Optional[User]:
        """
        Получить пользователя по имени замерщика (КЛЮЧЕВОЙ МЕТОД для распределения)

        Args:
            measurer_name: Название имени замерщика из AmoCRM

        Returns:
            User или None если не найден или неактивен
        """
        normalized = self.normalize_name(measurer_name)

        stmt = (
            select(User)
            .join(MeasurerNameAssignment)
            .join(MeasurerName)
            .where(
                and_(
                    MeasurerName.name == normalized,
                    User.role == UserRole.MEASURER,
                    User.is_active == True
                )
            )
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            logger.info(f"Найден замерщик {user.full_name} для имени '{measurer_name}'")
        else:
            logger.warning(f"Не найден активный замерщик для имени '{measurer_name}'")

        return user

    async def get_measurer_names_not_assigned_to_user(
        self, user_id: int
    ) -> List[MeasurerName]:
        """
        Получить имена замерщиков, не назначенные пользователю

        Args:
            user_id: ID пользователя

        Returns:
            Список доступных имён замерщиков
        """
        # Получаем все имена пользователя
        assigned_names = await self.get_user_measurer_names(user_id)
        assigned_name_ids = [n.id for n in assigned_names]

        # Получаем все имена, которые не в списке назначенных
        if assigned_name_ids:
            stmt = (
                select(MeasurerName)
                .where(MeasurerName.id.notin_(assigned_name_ids))
                .order_by(MeasurerName.name)
            )
        else:
            stmt = select(MeasurerName).order_by(MeasurerName.name)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unassigned_measurer_names(self) -> List[MeasurerName]:
        """
        Получить список имён замерщиков, которые не назначены ни одному пользователю

        Returns:
            Список неназначенных имён
        """
        # Получаем все measurer_name_id которые уже назначены
        stmt = select(MeasurerNameAssignment.measurer_name_id).distinct()
        result = await self.session.execute(stmt)
        assigned_ids = [row[0] for row in result.all()]

        # Получаем имена, которых нет в списке назначенных
        if assigned_ids:
            stmt = (
                select(MeasurerName)
                .where(MeasurerName.id.notin_(assigned_ids))
                .order_by(MeasurerName.name)
            )
        else:
            stmt = select(MeasurerName).order_by(MeasurerName.name)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_measurer_name_by_user_id(self, user_id: int) -> Optional[str]:
        """
        Получить имя замерщика для пользователя (простой метод)

        Args:
            user_id: ID пользователя

        Returns:
            Имя замерщика или None
        """
        stmt = (
            select(MeasurerName)
            .join(MeasurerNameAssignment)
            .where(MeasurerNameAssignment.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        measurer_name = result.scalar_one_or_none()

        return measurer_name.name if measurer_name else None

    async def set_measurer_name_for_user(self, user_id: int, name: str) -> bool:
        """
        Установить имя замерщика для пользователя (простой метод)

        Args:
            user_id: ID пользователя
            name: Имя замерщика

        Returns:
            True если установлено успешно, False в случае ошибки
        """
        try:
            # Проверяем, что пользователь - замерщик
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user or user.role != UserRole.MEASURER:
                logger.warning(f"Пользователь {user_id} не является замерщиком")
                return False

            # Нормализуем имя
            normalized = self.normalize_name(name)

            # Ищем или создаем MeasurerName
            measurer_name = await self.get_measurer_name_by_name(normalized)
            if not measurer_name:
                measurer_name = MeasurerName(name=normalized)
                self.session.add(measurer_name)
                await self.session.flush()
                logger.info(f"Создано новое имя замерщика: {normalized}")

            # Проверяем, есть ли уже связь у пользователя
            stmt = select(MeasurerNameAssignment).where(
                MeasurerNameAssignment.user_id == user_id
            )
            result = await self.session.execute(stmt)
            existing_assignment = result.scalar_one_or_none()

            if existing_assignment:
                # Проверяем, не используется ли новое имя кем-то еще
                stmt = select(MeasurerNameAssignment).where(
                    and_(
                        MeasurerNameAssignment.measurer_name_id == measurer_name.id,
                        MeasurerNameAssignment.user_id != user_id
                    )
                )
                result = await self.session.execute(stmt)
                other_user_assignment = result.scalar_one_or_none()

                if other_user_assignment:
                    logger.warning(
                        f"Имя '{normalized}' уже используется другим замерщиком"
                    )
                    return False

                # Обновляем существующую связь
                existing_assignment.measurer_name_id = measurer_name.id
                logger.info(f"Обновлено имя для пользователя {user_id}: {normalized}")
            else:
                # Проверяем, не используется ли это имя кем-то еще
                stmt = select(MeasurerNameAssignment).where(
                    MeasurerNameAssignment.measurer_name_id == measurer_name.id
                )
                result = await self.session.execute(stmt)
                other_user_assignment = result.scalar_one_or_none()

                if other_user_assignment:
                    logger.warning(
                        f"Имя '{normalized}' уже используется другим замерщиком"
                    )
                    return False

                # Создаем новую связь
                assignment = MeasurerNameAssignment(
                    user_id=user_id,
                    measurer_name_id=measurer_name.id
                )
                self.session.add(assignment)
                logger.info(f"Создана связь для пользователя {user_id}: {normalized}")

            await self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Ошибка установки имени замерщика: {e}", exc_info=True)
            await self.session.rollback()
            return False
