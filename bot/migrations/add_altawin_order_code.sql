-- Миграция: Добавление поля altawin_order_code в таблицу measurements
-- Дата: 2024-12-24
-- Описание: Добавляем поле для хранения уникального кода заказа из Altawin

-- Добавляем новое поле altawin_order_code
ALTER TABLE measurements ADD COLUMN altawin_order_code VARCHAR(100);

-- Создаем индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_measurements_altawin_order_code
ON measurements(altawin_order_code);

-- ПРИМЕЧАНИЕ: Старые поля (order_number, address, delivery_zone, contact_phone, windows_count, windows_area)
-- оставляем в БД для совместимости, но они больше не будут обновляться из AmoCRM.
-- Эти данные теперь получаются динамически из Altawin при каждом отображении.
