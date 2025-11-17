-- Миграция: добавление полей для отслеживания подтверждений и уведомлений
-- Дата: 2025-01-17
-- Описание:
--   1. Добавляет информацию о том, кто подтвердил/распределил замер
--   2. Добавляет поля для сохранения message_id и chat_id уведомлений в Telegram

-- === ТАБЛИЦА MEASUREMENTS ===
-- Добавляем поле confirmed_by_user_id
ALTER TABLE measurements ADD COLUMN confirmed_by_user_id INTEGER;

-- Добавляем внешний ключ на таблицу users
ALTER TABLE measurements ADD CONSTRAINT fk_measurements_confirmed_by_user
    FOREIGN KEY (confirmed_by_user_id) REFERENCES users(id) ON DELETE SET NULL;

-- Добавляем индекс для ускорения запросов
CREATE INDEX ix_measurements_confirmed_by_user_id ON measurements(confirmed_by_user_id);

-- === ТАБЛИЦА NOTIFICATIONS ===
-- Добавляем поле для хранения ID сообщения в Telegram
ALTER TABLE notifications ADD COLUMN telegram_message_id BIGINT;

-- Добавляем поле для хранения ID чата в Telegram
ALTER TABLE notifications ADD COLUMN telegram_chat_id BIGINT;

-- Добавляем индекс для ускорения поиска уведомлений по замеру и типу
CREATE INDEX ix_notifications_measurement_type ON notifications(measurement_id, notification_type);
