"""Модели базы данных"""
from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, String, DateTime, Enum, ForeignKey, Text, Integer, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class UserRole(PyEnum):
    """Роли пользователей"""
    ADMIN = "admin"
    SUPERVISOR = "supervisor"  # Руководитель - может управлять замерами, но не создавать ссылки
    MANAGER = "manager"
    MEASURER = "measurer"


class MeasurementStatus(PyEnum):
    """Статусы замеров"""
    PENDING_CONFIRMATION = "pending_confirmation"  # Ожидает подтверждения руководителем
    ASSIGNED = "assigned"  # Назначен замерщику (по умолчанию при назначении)
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
    assigned_zones: Mapped[list["MeasurerZone"]] = relationship(
        "MeasurerZone",
        back_populates="user",
        cascade="all, delete-orphan"
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
    lead_name: Mapped[str] = mapped_column(String(500), nullable=False)  # Наименование сделки
    responsible_user_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Ответственный

    # Контактная информация
    contact_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Имя контакта
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Телефон контакта

    # Адресная информация
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Адрес (ID: 809475)
    delivery_zone: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Зона доставки (ID: 808753)

    # Дополнительная информация
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статус и назначение
    status: Mapped[MeasurementStatus] = mapped_column(
        Enum(MeasurementStatus),
        default=MeasurementStatus.ASSIGNED,
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
            MeasurementStatus.PENDING_CONFIRMATION: "⏳ Ожидает подтверждения",
            MeasurementStatus.ASSIGNED: "📋 В работе",
            MeasurementStatus.COMPLETED: "✅ Выполнен",
            MeasurementStatus.CANCELLED: "❌ Отменен",
        }
        return status_map.get(self.status, "❓ Неизвестен")

    def get_info_text(self, detailed: bool = True) -> str:
        """Форматированная информация о замере"""
        text = f"📋 <b>Замер #{self.id}</b>\n\n"

        # Наименование сделки
        text += f"📄 <b>Сделка:</b> {self.lead_name}\n"

        # Ответственный
        if self.responsible_user_name:
            text += f"👤 <b>Ответственный:</b> {self.responsible_user_name}\n"

        # Адрес
        if self.address:
            text += f"📍 <b>Адрес:</b> {self.address}\n"

        # Зона доставки
        if self.delivery_zone:
            text += f"🚚 <b>Зона доставки:</b> {self.delivery_zone}\n"

        # Имя контакта
        if self.contact_name:
            text += f"👨‍💼 <b>Контакт:</b> {self.contact_name}\n"

        # Телефон контакта
        if self.contact_phone:
            text += f"📞 <b>Телефон:</b> {self.contact_phone}\n"

        text += f"\n📊 <b>Статус:</b> {self.status_text}\n"

        # Замерщик
        if self.measurer:
            text += f"👷 <b>Замерщик:</b> {self.measurer.full_name}\n"

        if detailed:
            text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {self.amocrm_lead_id}\n"
            text += f"📅 <b>Создано:</b> {self.created_at.strftime('%d.%m.%Y %H:%M')}\n"

            if self.assigned_at:
                text += f"📅 <b>Назначено:</b> {self.assigned_at.strftime('%d.%m.%Y %H:%M')}\n"

            if self.completed_at:
                text += f"📅 <b>Выполнено:</b> {self.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

        return text


class InviteLink(Base):
    """Модель пригласительной ссылки"""
    __tablename__ = "invite_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Уникальный токен ссылки
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Роль, которую получит пользователь по этой ссылке
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    # Кто создал ссылку
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])

    # Параметры ссылки
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = неограниченно
    current_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Срок действия
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # None = бессрочная

    # Активность
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<InviteLink(token={self.token}, role={self.role.value}, uses={self.current_uses}/{self.max_uses or '∞'})>"

    @property
    def is_valid(self) -> bool:
        """Проверка, действительна ли ссылка"""
        if not self.is_active:
            return False

        # Проверка срока действия
        if self.expires_at and datetime.now() > self.expires_at:
            return False

        # Проверка лимита использований
        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return False

        return True

    @property
    def role_text(self) -> str:
        """Текстовое представление роли на русском"""
        role_map = {
            UserRole.ADMIN: "👑 Администратор",
            UserRole.SUPERVISOR: "👔 Руководитель",
            UserRole.MANAGER: "💼 Менеджер",
            UserRole.MEASURER: "👷 Замерщик",
        }
        return role_map.get(self.role, "❓ Неизвестная роль")

    def get_info_text(self) -> str:
        """Форматированная информация о ссылке"""
        text = f"🔗 <b>Пригласительная ссылка</b>\n\n"
        text += f"🎭 <b>Роль:</b> {self.role_text}\n"
        text += f"📊 <b>Использований:</b> {self.current_uses}"

        if self.max_uses:
            text += f" / {self.max_uses}\n"
        else:
            text += " / ∞\n"

        if self.expires_at:
            text += f"⏰ <b>Действительна до:</b> {self.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
        else:
            text += "⏰ <b>Срок действия:</b> Бессрочная\n"

        status = "✅ Активна" if self.is_valid else "❌ Неактивна"
        text += f"📌 <b>Статус:</b> {status}\n"

        text += f"📅 <b>Создана:</b> {self.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"🔑 <b>Токен:</b> <code>{self.token}</code>\n"

        return text


class DeliveryZone(Base):
    """Модель зоны доставки"""
    __tablename__ = 'delivery_zones'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Связь с замерщиками через промежуточную таблицу
    measurer_assignments: Mapped[list["MeasurerZone"]] = relationship(
        'MeasurerZone',
        back_populates='zone',
        cascade='all, delete-orphan'
    )

    def __repr__(self) -> str:
        return f"<DeliveryZone(id={self.id}, zone_name='{self.zone_name}')>"


class MeasurerZone(Base):
    """Модель привязки зоны к замерщику"""
    __tablename__ = 'measurer_zones'
    __table_args__ = (
        UniqueConstraint('user_id', 'zone_id', name='unique_user_zone'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Связи
    zone: Mapped["DeliveryZone"] = relationship('DeliveryZone', back_populates='measurer_assignments')
    user: Mapped["User"] = relationship('User', back_populates='assigned_zones')

    def __repr__(self) -> str:
        return f"<MeasurerZone(user_id={self.user_id}, zone_id={self.zone_id})>"


class RoundRobinCounter(Base):
    """Модель счетчика для round-robin распределения"""
    __tablename__ = 'round_robin_counter'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_assigned_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<RoundRobinCounter(last_assigned_user_id={self.last_assigned_user_id})>"


class Notification(Base):
    """Модель уведомления"""
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Кому было отправлено уведомление
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])

    # Текст уведомления
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Тип уведомления (для фильтрации)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Связь с замером (если уведомление связано с замером)
    measurement_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("measurements.id", ondelete="SET NULL"), nullable=True
    )

    # Успешно ли было отправлено
    is_sent: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Временная метка
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.notification_type}, recipient_id={self.recipient_id})>"
