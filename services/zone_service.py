"""Сервис для работы с зонами доставки"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from loguru import logger

from database.models import DeliveryZone, MeasurerZone, User, UserRole, RoundRobinCounter


class ZoneService:
    """Сервис для управления зонами доставки"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_zone(self, zone_name: str) -> Optional[DeliveryZone]:
        """
        Создать новую зону доставки

        Args:
            zone_name: Название зоны

        Returns:
            DeliveryZone или None если зона уже существует
        """
        # Проверяем, существует ли уже такая зона
        existing_zone = await self.get_zone_by_name(zone_name)
        if existing_zone:
            logger.warning(f"Зона '{zone_name}' уже существует")
            return None

        zone = DeliveryZone(zone_name=zone_name)
        self.session.add(zone)
        await self.session.commit()
        await self.session.refresh(zone)

        logger.info(f"Создана новая зона: {zone_name}")
        return zone

    async def get_zone_by_name(self, zone_name: str) -> Optional[DeliveryZone]:
        """Получить зону по названию"""
        stmt = select(DeliveryZone).where(DeliveryZone.zone_name == zone_name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_zone_by_id(self, zone_id: int) -> Optional[DeliveryZone]:
        """Получить зону по ID"""
        stmt = select(DeliveryZone).where(DeliveryZone.id == zone_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_zones(self) -> List[DeliveryZone]:
        """Получить все зоны доставки"""
        stmt = select(DeliveryZone).order_by(DeliveryZone.zone_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_zone(self, zone_id: int) -> bool:
        """
        Удалить зону доставки

        Args:
            zone_id: ID зоны

        Returns:
            True если зона удалена, False если не найдена
        """
        zone = await self.get_zone_by_id(zone_id)
        if not zone:
            logger.warning(f"Зона с ID {zone_id} не найдена")
            return False

        await self.session.delete(zone)
        await self.session.commit()
        logger.info(f"Зона '{zone.zone_name}' удалена")
        return True

    async def assign_zone_to_measurer(self, user_id: int, zone_id: int) -> Optional[MeasurerZone]:
        """
        Назначить зону замерщику

        Args:
            user_id: ID пользователя
            zone_id: ID зоны

        Returns:
            MeasurerZone или None если уже назначена или пользователь не замерщик
        """
        # Проверяем, что пользователь - замерщик
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or user.role != UserRole.MEASURER:
            logger.warning(f"Пользователь {user_id} не является замерщиком")
            return None

        # Проверяем, не назначена ли уже эта зона
        stmt = select(MeasurerZone).where(
            and_(
                MeasurerZone.user_id == user_id,
                MeasurerZone.zone_id == zone_id
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.warning(f"Зона {zone_id} уже назначена замерщику {user_id}")
            return None

        assignment = MeasurerZone(user_id=user_id, zone_id=zone_id)
        self.session.add(assignment)
        await self.session.commit()
        await self.session.refresh(assignment)

        logger.info(f"Зона {zone_id} назначена замерщику {user_id}")
        return assignment

    async def remove_zone_from_measurer(self, user_id: int, zone_id: int) -> bool:
        """
        Убрать зону у замерщика

        Args:
            user_id: ID пользователя
            zone_id: ID зоны

        Returns:
            True если зона удалена, False если не найдена
        """
        stmt = select(MeasurerZone).where(
            and_(
                MeasurerZone.user_id == user_id,
                MeasurerZone.zone_id == zone_id
            )
        )
        result = await self.session.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            logger.warning(f"Назначение зоны {zone_id} замерщику {user_id} не найдено")
            return False

        await self.session.delete(assignment)
        await self.session.commit()
        logger.info(f"Зона {zone_id} удалена у замерщика {user_id}")
        return True

    async def get_measurer_zones(self, user_id: int) -> List[DeliveryZone]:
        """Получить все зоны замерщика"""
        stmt = (
            select(DeliveryZone)
            .join(MeasurerZone)
            .where(MeasurerZone.user_id == user_id)
            .order_by(DeliveryZone.zone_name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_measurers_by_zone(self, zone_name: str) -> List[User]:
        """
        Получить всех замерщиков, назначенных на зону

        Args:
            zone_name: Название зоны

        Returns:
            Список пользователей-замерщиков
        """
        stmt = (
            select(User)
            .join(MeasurerZone)
            .join(DeliveryZone)
            .where(
                and_(
                    DeliveryZone.zone_name == zone_name,
                    User.role == UserRole.MEASURER,
                    User.is_active == True
                )
            )
            .options(joinedload(User.assigned_zones))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_next_measurer_round_robin_preview(self) -> Optional[User]:
        """
        Получить следующего замерщика для round-robin распределения БЕЗ обновления счётчика
        Используется для предварительного просмотра (когда замер ещё не подтверждён)

        Returns:
            User или None если нет доступных замерщиков
        """
        # Получаем всех активных замерщиков
        stmt = (
            select(User)
            .where(
                and_(
                    User.role == UserRole.MEASURER,
                    User.is_active == True
                )
            )
            .order_by(User.id)
        )
        result = await self.session.execute(stmt)
        measurers = list(result.scalars().all())

        if not measurers:
            logger.warning("Нет доступных замерщиков для round-robin распределения")
            return None

        # Получаем или создаем счетчик
        stmt = select(RoundRobinCounter).where(RoundRobinCounter.id == 1)
        result = await self.session.execute(stmt)
        counter = result.scalar_one_or_none()

        if not counter:
            # Если счётчика нет, возвращаем первого замерщика
            logger.info(f"Round-robin (preview) выбран первый замерщик: {measurers[0].full_name}")
            return measurers[0]

        # Находим следующего замерщика (БЕЗ обновления счётчика!)
        if counter.last_assigned_user_id:
            # Ищем индекс последнего назначенного замерщика
            try:
                last_idx = next(i for i, m in enumerate(measurers) if m.id == counter.last_assigned_user_id)
                next_idx = (last_idx + 1) % len(measurers)
            except StopIteration:
                # Если последний назначенный не найден, начинаем сначала
                next_idx = 0
        else:
            next_idx = 0

        next_measurer = measurers[next_idx]
        logger.info(f"Round-robin (preview) выбран замерщик: {next_measurer.full_name} (ID: {next_measurer.id})")
        return next_measurer

    async def update_round_robin_counter(self, measurer_id: int) -> None:
        """
        Обновить счётчик round-robin на конкретного замерщика
        Вызывается ТОЛЬКО при подтверждении замера руководителем

        Args:
            measurer_id: ID замерщика, которого подтвердили
        """
        # Получаем или создаем счетчик
        stmt = select(RoundRobinCounter).where(RoundRobinCounter.id == 1)
        result = await self.session.execute(stmt)
        counter = result.scalar_one_or_none()

        if not counter:
            counter = RoundRobinCounter(id=1)
            self.session.add(counter)

        # Обновляем счетчик
        counter.last_assigned_user_id = measurer_id
        counter.last_assigned_at = datetime.now()
        await self.session.commit()

        logger.info(f"Round-robin счётчик обновлён на замерщика ID: {measurer_id}")

    async def get_next_measurer_round_robin(self) -> Optional[User]:
        """
        Получить следующего замерщика для round-robin распределения С обновлением счётчика

        ВНИМАНИЕ: Эта функция устарела и не должна использоваться!
        Используйте get_next_measurer_round_robin_preview() вместо неё.

        Returns:
            User или None если нет доступных замерщиков
        """
        logger.warning("Вызвана устаревшая функция get_next_measurer_round_robin()! Используйте get_next_measurer_round_robin_preview()")

        # Получаем замерщика без обновления счётчика
        measurer = await self.get_next_measurer_round_robin_preview()

        if measurer:
            # Обновляем счётчик
            await self.update_round_robin_counter(measurer.id)

        return measurer

    async def assign_measurer_by_zone(self, delivery_zone: Optional[str]) -> Optional[User]:
        """
        Назначить замерщика на основе зоны доставки (БЕЗ обновления счётчика round-robin)

        Эта функция только ПРЕДЛАГАЕТ замерщика, но НЕ обновляет счётчик.
        Счётчик обновляется только при подтверждении руководителем!

        Args:
            delivery_zone: Название зоны доставки из AmoCRM

        Returns:
            User - предложенный замерщик
        """
        if not delivery_zone:
            logger.info("Зона доставки не указана, используем round-robin (preview)")
            return await self.get_next_measurer_round_robin_preview()

        # Ищем замерщиков для данной зоны
        measurers = await self.get_measurers_by_zone(delivery_zone)

        if measurers:
            # Если есть замерщики для этой зоны, выбираем первого
            # В будущем можно добавить более сложную логику выбора
            selected = measurers[0]
            logger.info(f"Для зоны '{delivery_zone}' выбран замерщик: {selected.full_name}")
            return selected
        else:
            logger.info(f"Для зоны '{delivery_zone}' нет назначенных замерщиков, используем round-robin (preview)")
            return await self.get_next_measurer_round_robin_preview()

    async def get_unassigned_zones(self) -> List[DeliveryZone]:
        """Получить список зон, которые не назначены ни одному замерщику"""
        stmt = (
            select(DeliveryZone)
            .outerjoin(MeasurerZone)
            .group_by(DeliveryZone.id)
            .having(func.count(MeasurerZone.id) == 0)
            .order_by(DeliveryZone.zone_name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_zones_not_assigned_to_measurer(self, user_id: int) -> List[DeliveryZone]:
        """Получить зоны, которые не назначены конкретному замерщику"""
        # Получаем все зоны замерщика
        assigned_zones = await self.get_measurer_zones(user_id)
        assigned_zone_ids = [z.id for z in assigned_zones]

        # Получаем все зоны, которые не в списке назначенных
        if assigned_zone_ids:
            stmt = (
                select(DeliveryZone)
                .where(DeliveryZone.id.notin_(assigned_zone_ids))
                .order_by(DeliveryZone.zone_name)
            )
        else:
            stmt = select(DeliveryZone).order_by(DeliveryZone.zone_name)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
