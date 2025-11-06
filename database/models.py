"""Модели базы данных"""
from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, String, DateTime, Enum, ForeignKey, Text, Integer
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class UserRole(PyEnum):
    """Роли пользователей"""
    ADMIN = "admin"
    MEASURER = "measurer"
    MANAGER = "manager"


class MeasurementStatus(PyEnum):
    """Статусы замеров"""
    PENDING = "pending"  # Ожидает назначения замерщика
    ASSIGNED = "assigned"  # Назначен замерщик
    IN_PROGRESS = "in_progress"  # В процессе выполнения
    COMPLETED = "completed"  # Выполнен
    CANCELLED = "cancelled"  # Отменен


class User(Base):
    """Модель пользователя бота"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    # AmoCRM данные (для менеджеров)
    amocrm_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Связи
    measurements_as_measurer: Mapped[list["Measurement"]] = relationship(
        "Measurement",
        foreign_keys="Measurement.measurer_id",
        back_populates="measurer"
    )
    measurements_as_manager: Mapped[list["Measurement"]] = relationship(
        "Measurement",
        foreign_keys="Measurement.manager_id",
        back_populates="manager"
    )

    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, role={self.role.value})>"

    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else self.username or f"User_{self.telegram_id}"


class Measurement(Base):
    """Модель замера"""
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Данные из AmoCRM
    amocrm_lead_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(500), nullable=False)
    client_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)

    # Дополнительная информация
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статус и назначение
    status: Mapped[MeasurementStatus] = mapped_column(
        Enum(MeasurementStatus),
        default=MeasurementStatus.PENDING,
        nullable=False,
        index=True
    )

    # Связь с замерщиком
    measurer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    measurer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[measurer_id],
        back_populates="measurements_as_measurer"
    )

    # Связь с менеджером
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    manager: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[manager_id],
        back_populates="measurements_as_manager"
    )

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Measurement(id={self.id}, amocrm_lead_id={self.amocrm_lead_id}, status={self.status.value})>"

    @property
    def status_text(self) -> str:
        """Текстовое представление статуса на русском"""
        status_map = {
            MeasurementStatus.PENDING: "⏳ Ожидает назначения",
            MeasurementStatus.ASSIGNED: "📋 Назначен",
            MeasurementStatus.IN_PROGRESS: "🔄 В процессе",
            MeasurementStatus.COMPLETED: "✅ Выполнен",
            MeasurementStatus.CANCELLED: "❌ Отменен",
        }
        return status_map.get(self.status, "❓ Неизвестен")

    def get_info_text(self, detailed: bool = True) -> str:
        """Форматированная информация о замере"""
        text = f"📋 <b>Замер #{self.id}</b>\n\n"
        text += f"👤 <b>Клиент:</b> {self.client_name}\n"

        if self.client_phone:
            text += f"📞 <b>Телефон:</b> {self.client_phone}\n"

        text += f"📍 <b>Адрес:</b> {self.address}\n"
        text += f"📊 <b>Статус:</b> {self.status_text}\n"

        if self.measurer:
            text += f"👷 <b>Замерщик:</b> {self.measurer.full_name}\n"

        if detailed:
            if self.manager:
                text += f"👔 <b>Менеджер:</b> {self.manager.full_name}\n"

            if self.description:
                text += f"\n📝 <b>Описание:</b>\n{self.description}\n"

            if self.notes:
                text += f"\n💬 <b>Заметки:</b>\n{self.notes}\n"

            text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {self.amocrm_lead_id}\n"
            text += f"📅 <b>Создано:</b> {self.created_at.strftime('%d.%m.%Y %H:%M')}\n"

            if self.assigned_at:
                text += f"📅 <b>Назначено:</b> {self.assigned_at.strftime('%d.%m.%Y %H:%M')}\n"

            if self.completed_at:
                text += f"📅 <b>Выполнено:</b> {self.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

        return text
