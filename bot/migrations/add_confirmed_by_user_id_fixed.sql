-- Миграция: добавление полей для отслеживания подтверждений и уведомлений
-- Дата: 2025-01-17
-- Описание:
--   1. Добавляет информацию о том, кто подтвердил/распределил замер
--   2. Добавляет поля для сохранения message_id и chat_id уведомлений в Telegram
--
-- ВАЖНО: Эта версия пропускает confirmed_by_user_id, т.к. она уже существует

-- === ТАБЛИЦА MEASUREMENTS ===
-- Поле confirmed_by_user_id уже существует, пропускаем

-- Добавляем индекс для ускорения запросов
CREATE INDEX IF NOT EXISTS ix_measurements_confirmed_by_user_id ON measurements(confirmed_by_user_id);

-- === ТАБЛИЦА NOTIFICATIONS ===
-- Добавляем поле для хранения ID сообщения в Telegram
ALTER TABLE notifications ADD COLUMN telegram_message_id BIGINT;

-- Добавляем поле для хранения ID чата в Telegram
ALTER TABLE notifications ADD COLUMN telegram_chat_id BIGINT;

-- Добавляем индекс для ускорения поиска уведомлений по замеру и типу
CREATE INDEX IF NOT EXISTS ix_notifications_measurement_type ON notifications(measurement_id, notification_type);
