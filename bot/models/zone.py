from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class DeliveryZone(Base):
    """Модель зоны доставки"""
    __tablename__ = 'delivery_zones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.now)

    # Связь с замерщиками через промежуточную таблицу
    measurer_assignments = relationship('MeasurerZone', back_populates='zone', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<DeliveryZone(id={self.id}, zone_name='{self.zone_name}')>"


class MeasurerZone(Base):
    """Модель привязки зоны к замерщику"""
    __tablename__ = 'measurer_zones'
    __table_args__ = (
        UniqueConstraint('user_id', 'zone_id', name='unique_user_zone'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    zone_id = Column(Integer, ForeignKey('delivery_zones.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    # Связи
    zone = relationship('DeliveryZone', back_populates='measurer_assignments')
    user = relationship('User', back_populates='assigned_zones')

    def __repr__(self):
        return f"<MeasurerZone(user_id={self.user_id}, zone_id={self.zone_id})>"


class RoundRobinCounter(Base):
    """Модель счетчика для round-robin распределения"""
    __tablename__ = 'round_robin_counter'

    id = Column(Integer, primary_key=True)
    last_assigned_user_id = Column(Integer, nullable=True)
    last_assigned_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<RoundRobinCounter(last_assigned_user_id={self.last_assigned_user_id})>"
