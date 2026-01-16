"""Модели базы данных"""
from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, String, DateTime, Enum, ForeignKey, Text, Integer, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from utils.timezone_utils import moscow_now


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class UserRole(PyEnum):
    """Роли пользователей"""
    ADMIN = "admin"
    SUPERVISOR = "supervisor"  # Руководитель - может управлять замерами, но не создавать ссылки
    MANAGER = "manager"
    MEASURER = "measurer"
    OBSERVER = "observer"  # Наблюдатель - получает уведомления о всех замерах, может просматривать все замеры


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now, onupdate=moscow_now)

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
    assigned_measurer_names: Mapped[list["MeasurerNameAssignment"]] = relationship(
        "MeasurerNameAssignment",
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

    # Код заказа из Altawin (получаем из AmoCRM поле ID: 809853)
    altawin_order_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # Уникальный код заказа из Altawin

    # Контактная информация (только из AmoCRM, т.к. в Altawin нет)
    contact_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Имя контакта

    # LEGACY ПОЛЯ (для обратной совместимости со старыми записями)
    # Для НОВЫХ записей эти данные получаем динамически из Altawin по altawin_order_code
    # Для СТАРЫХ записей (без altawin_order_code) используем эти поля
    order_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    delivery_zone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    windows_count: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    windows_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

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

    # Кто подтвердил/распределил замер (админ или руководитель)
    confirmed_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[confirmed_by_user_id]
    )

    # === ИСТОРИЯ АВТОМАТИЧЕСКОГО РАСПРЕДЕЛЕНИЯ ===
    # Кто был автоматически назначен (до подтверждения админом)
    auto_assigned_measurer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    auto_assigned_measurer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[auto_assigned_measurer_id]
    )

    # Причина автоназначения: 'dealer', 'zone', 'round_robin', 'none'
    assignment_reason: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )

    # Название компании из AmoCRM (если назначение по дилеру)
    dealer_company_name: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # Значение поля "Замерщик" из компании в AmoCRM (если назначение по дилеру)
    dealer_field_value: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now, onupdate=moscow_now)

    def __repr__(self) -> str:
        return f"<Measurement(id={self.id}, amocrm_lead_id={self.amocrm_lead_id}, status={self.status.value})>"

    def get_altawin_data(self):
        """
        Получить актуальные данные из Altawin по коду заказа
        Для старых записей без кода - возвращает данные из legacy-полей БД

        Returns:
            AltawinOrderData или None если нет ни кода, ни legacy-данных
        """
        # Если есть код заказа Altawin - загружаем актуальные данные из Altawin
        if self.altawin_order_code:
            from services.altawin import altawin_client
            return altawin_client.get_order_data(self.altawin_order_code)

        # Fallback для старых записей без кода - используем legacy-поля из БД
        # Проверяем, есть ли хоть какие-то данные в старых полях
        if not any([self.order_number, self.address, self.delivery_zone,
                    self.contact_phone, self.windows_count, self.windows_area]):
            return None

        # Создаем объект AltawinOrderData из legacy-полей
        from services.altawin import AltawinOrderData
        return AltawinOrderData(
            order_id=0,  # Для старых записей нет ID из Altawin
            order_number=self.order_number or "",
            total_price=None,
            qty_izd=self.windows_count,  # Количество окон
            area_izd=self.windows_area,   # Площадь окон
            zone=self.delivery_zone,
            measurer=None,
            address=self.address,
            agreement_date=None,
            agreement_no=None,
            phone=self.contact_phone
        )

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

    def get_info_text(self, detailed: bool = True, show_admin_info: bool = False) -> str:
        """
        Унифицированная форматированная информация о замере

        Args:
            detailed: Показывать детальную информацию (временные метки, ID сделки)
            show_admin_info: Показывать информацию для админов/руководителей (кто подтвердил)

        Порядок вывода:
        1. Заголовок (Замер #)
        2. Основная информация о заказе (из Altawin)
        3. Контактные данные
        4. Дополнительные параметры из Altawin
        5. Статус и назначение
        6. Информация о подтверждении (только для админов)
        7. Временные метки (если detailed=True)
        """
        text = f"📋 <b>Замер #{self.id}</b>\n\n"

        # Получаем актуальные данные из Altawin
        altawin_data = self.get_altawin_data()

        # === БЛОК 1: Основная информация о заказе ===
        text += f"📄 <b>Сделка:</b> {self.lead_name}\n"

        # Номер заказа из Altawin
        if altawin_data and altawin_data.order_number:
            text += f"🔢 <b>Номер заказа:</b> {altawin_data.order_number}\n"

        # Адрес из Altawin
        if altawin_data and altawin_data.address:
            text += f"📍 <b>Адрес:</b> {altawin_data.address}\n"

        # Зона доставки из Altawin
        if altawin_data and altawin_data.zone:
            text += f"🚚 <b>Зона доставки:</b> {altawin_data.zone}\n"

        text += "\n"

        # === БЛОК 2: Контактные данные ===
        if self.contact_name:
            text += f"👤 <b>Контакт:</b> {self.contact_name}\n"

        # Телефон из Altawin
        if altawin_data and altawin_data.phone:
            from utils.phone_formatter import format_phone_for_telegram
            text += f"📞 <b>Телефон:</b> {format_phone_for_telegram(altawin_data.phone)}\n"

        # Ответственный в AmoCRM
        if self.responsible_user_name:
            text += f"👨‍💼 <b>Ответственный в AmoCRM:</b> {self.responsible_user_name}\n"

        text += "\n"

        # === БЛОК 3: Параметры окон из Altawin ===
        has_window_info = False
        if altawin_data and altawin_data.qty_izd:
            text += f"🪟 <b>Количество окон:</b> {altawin_data.qty_izd}\n"
            has_window_info = True

        if altawin_data and altawin_data.area_izd:
            text += f"📐 <b>Площадь окон:</b> {altawin_data.area_izd} м²\n"
            has_window_info = True

        if has_window_info:
            text += "\n"

        # === БЛОК 4: Статус и назначение ===
        text += f"📊 <b>Статус:</b> {self.status_text}\n"

        # Замерщик
        if self.measurer:
            text += f"👷 <b>Замерщик:</b> {self.measurer.full_name}\n"

        # === БЛОК 5: Информация о подтверждении и распределении (ТОЛЬКО для админов/руководителей) ===
        if show_admin_info:
            # Показываем информацию о предложенном замерщике для статуса PENDING_CONFIRMATION
            if self.status == MeasurementStatus.PENDING_CONFIRMATION and self.auto_assigned_measurer:
                text += "\n⚡️ <b>Система предлагает:</b>\n"
                text += f"  👷 {self.auto_assigned_measurer.full_name}\n"

                if self.assignment_reason:
                    reason_text = {
                        'dealer': '🏢 Привязанный замерщик',
                        'zone': '🗺 Зона',
                        'round_robin': '🔄 По очереди',
                        'none': '❌ Не назначен'
                    }.get(self.assignment_reason, '❓ Неизвестно')
                    text += f"  📌 Причина: {reason_text}\n"

                    # Если назначение по дилеру - показываем доп информацию
                    if self.assignment_reason == 'dealer':
                        if self.dealer_company_name:
                            text += f"  🏢 Компания: {self.dealer_company_name}\n"
                    elif self.assignment_reason == 'zone' and self.delivery_zone:
                        text += f"  🗺 Зона: {self.delivery_zone}\n"

            # История автоматического распределения (для подтвержденных замеров)
            elif self.assignment_reason and self.status != MeasurementStatus.PENDING_CONFIRMATION:
                text += "\n📊 <b>История распределения:</b>\n"

                reason_text = {
                    'dealer': '🏢 Привязанный замерщик',
                    'zone': '🗺 Зона',
                    'round_robin': '🔄 По очереди',
                    'none': '❌ Не назначен'
                }.get(self.assignment_reason, '❓ Неизвестно')

                text += f"  📌 Причина: {reason_text}\n"

                # Если назначение по дилеру - показываем доп информацию
                if self.assignment_reason == 'dealer':
                    if self.dealer_company_name:
                        text += f"  🏢 Компания: {self.dealer_company_name}\n"
                    if self.dealer_field_value:
                        text += f"  👷 Привязанный замерщик: {self.dealer_field_value}\n"
                elif self.assignment_reason == 'zone' and self.delivery_zone:
                    text += f"  🗺 Зона: {self.delivery_zone}\n"

                # Если замерщик был изменён
                if self.auto_assigned_measurer and self.measurer:
                    if self.auto_assigned_measurer.id != self.measurer.id:
                        text += f"  🔄 Изначально: {self.auto_assigned_measurer.full_name}\n"
                        text += f"  ✅ Назначен: {self.measurer.full_name}\n"
                    else:
                        text += f"  ✅ Подтверждён: {self.auto_assigned_measurer.full_name}\n"

            # Кто подтвердил
            if self.confirmed_by:
                text += f"  👤 Подтвердил: {self.confirmed_by.full_name}\n"

        # === БЛОК 6: Временные метки (детальная информация) ===
        if detailed:
            from utils.timezone_utils import format_moscow_time

            text += f"\n🆔 <b>ID сделки в AmoCRM:</b> {self.amocrm_lead_id}\n"

            # Конвертируем времена в московское время
            if self.created_at:
                text += f"📅 <b>Создано:</b> {format_moscow_time(self.created_at)}\n"

            if self.assigned_at:
                text += f"📅 <b>Назначено:</b> {format_moscow_time(self.assigned_at)}\n"

            if self.completed_at:
                text += f"📅 <b>Выполнено:</b> {format_moscow_time(self.completed_at)}\n"

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now, onupdate=moscow_now)

    def __repr__(self) -> str:
        return f"<InviteLink(token={self.token}, role={self.role.value}, uses={self.current_uses}/{self.max_uses or '∞'})>"

    @property
    def is_valid(self) -> bool:
        """Проверка, действительна ли ссылка"""
        if not self.is_active:
            return False

        # Проверка срока действия
        if self.expires_at and moscow_now() > self.expires_at:
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)

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


class MeasurerName(Base):
    """Модель имени замерщика (дилера) из AmoCRM"""
    __tablename__ = 'measurer_names'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)

    # Связь с назначениями
    assignments: Mapped[list["MeasurerNameAssignment"]] = relationship(
        'MeasurerNameAssignment',
        back_populates='measurer_name',
        cascade='all, delete-orphan'
    )

    def __repr__(self) -> str:
        return f"<MeasurerName(id={self.id}, name='{self.name}')>"


class MeasurerNameAssignment(Base):
    """Модель привязки имени замерщика к пользователю"""
    __tablename__ = 'measurer_name_assignments'
    __table_args__ = (
        UniqueConstraint('user_id', 'measurer_name_id', name='unique_user_measurer_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    measurer_name_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("measurer_names.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now)

    # Связи
    measurer_name: Mapped["MeasurerName"] = relationship(
        'MeasurerName',
        back_populates='assignments'
    )
    user: Mapped["User"] = relationship('User', back_populates='assigned_measurer_names')

    def __repr__(self) -> str:
        return f"<MeasurerNameAssignment(user_id={self.user_id}, measurer_name_id={self.measurer_name_id})>"


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

    # ID сообщения в Telegram (для возможности редактирования/удаления)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # ID чата в Telegram
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Успешно ли было отправлено
    is_sent: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Временная метка
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=moscow_now, index=True)

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.notification_type}, recipient_id={self.recipient_id})>"
