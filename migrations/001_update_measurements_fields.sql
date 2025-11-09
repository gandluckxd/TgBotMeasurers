-- Миграция: обновление полей таблицы measurements для SQLite
-- Дата: 2025-01-09
-- Описание: Изменение структуры для хранения данных из AmoCRM

-- SQLite не поддерживает ALTER COLUMN и RENAME COLUMN напрямую
-- Поэтому создаем новую таблицу и копируем данные

-- 1. Создаем временную таблицу с новой структурой
CREATE TABLE measurements_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amocrm_lead_id INTEGER NOT NULL UNIQUE,
    lead_name VARCHAR(500) NOT NULL,
    responsible_user_name VARCHAR(500),
    contact_name VARCHAR(500),
    contact_phone VARCHAR(50),
    address TEXT,
    delivery_zone VARCHAR(500),
    description TEXT,
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'assigned',
    measurer_id INTEGER,
    manager_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    assigned_at DATETIME,
    completed_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (measurer_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 2. Копируем данные из старой таблицы
INSERT INTO measurements_new (
    id, amocrm_lead_id, lead_name, contact_phone, address,
    description, notes, status, measurer_id, manager_id,
    created_at, assigned_at, completed_at, updated_at
)
SELECT
    id, amocrm_lead_id, client_name, client_phone, address,
    description, notes, status, measurer_id, manager_id,
    created_at, assigned_at, completed_at, updated_at
FROM measurements;

-- 3. Удаляем старую таблицу
DROP TABLE measurements;

-- 4. Переименовываем новую таблицу
ALTER TABLE measurements_new RENAME TO measurements;

-- 5. Создаем индексы
CREATE UNIQUE INDEX idx_measurements_amocrm_lead_id ON measurements(amocrm_lead_id);
CREATE INDEX idx_measurements_status ON measurements(status);
