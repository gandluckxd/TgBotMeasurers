-- Миграция для добавления дополнительных полей из AmoCRM
-- Дата: 2025-01-13
-- Описание: Добавляем поля для номера заказа, количества и площади окон

-- Добавляем поле order_number (Номер заказа в Альтавин Основной, ID: 667253)
ALTER TABLE measurements
ADD COLUMN IF NOT EXISTS order_number VARCHAR(100);

-- Добавляем поле windows_count (Количество окон, ID: 676403)
ALTER TABLE measurements
ADD COLUMN IF NOT EXISTS windows_count VARCHAR(50);

-- Добавляем поле windows_area (Площадь окон, ID: 808751)
ALTER TABLE measurements
ADD COLUMN IF NOT EXISTS windows_area VARCHAR(50);

-- Индексы для оптимизации поиска по номеру заказа
CREATE INDEX IF NOT EXISTS idx_measurements_order_number
ON measurements(order_number);

-- Комментарии к полям для документации
COMMENT ON COLUMN measurements.order_number IS '№ в Альтавин Основной (AmoCRM field ID: 667253)';
COMMENT ON COLUMN measurements.windows_count IS 'Количество окон (AmoCRM field ID: 676403)';
COMMENT ON COLUMN measurements.windows_area IS 'Площадь окон в м² (AmoCRM field ID: 808751)';
