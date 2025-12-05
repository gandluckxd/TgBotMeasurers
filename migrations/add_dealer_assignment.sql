-- Миграция: добавление дилерского распределения замеров
-- Дата: 2025-01-28
-- Описание:
--   1. Создаёт таблицу measurer_names для хранения имён замерщиков (дилеров)
--   2. Создаёт таблицу measurer_name_assignments для связи имён с пользователями
--   3. Добавляет поля в measurements для отслеживания истории распределения
--   4. Добавляет индексы для оптимизации запросов

-- === ТАБЛИЦА MEASURER_NAMES ===
-- Хранит имена замерщиков (дилеров) из AmoCRM
CREATE TABLE IF NOT EXISTS measurer_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- === ТАБЛИЦА MEASURER_NAME_ASSIGNMENTS ===
-- Связь между именами замерщиков и пользователями бота
-- ВАЖНО: measurer_name_id UNIQUE - одно имя может быть привязано только к одному пользователю
CREATE TABLE IF NOT EXISTS measurer_name_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    measurer_name_id INTEGER NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (measurer_name_id) REFERENCES measurer_names(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_measurer_name UNIQUE (user_id, measurer_name_id)
);

-- === ТАБЛИЦА MEASUREMENTS - НОВЫЕ ПОЛЯ ===
-- Добавляем поля для отслеживания истории автоматического распределения

-- Кто был автоматически назначен (до подтверждения админом)
ALTER TABLE measurements ADD COLUMN auto_assigned_measurer_id INTEGER;

-- Причина автоназначения: 'dealer', 'zone', 'round_robin', 'none'
ALTER TABLE measurements ADD COLUMN assignment_reason VARCHAR(50);

-- Название компании из AmoCRM (если назначение по дилеру)
ALTER TABLE measurements ADD COLUMN dealer_company_name VARCHAR(500);

-- Значение поля "Замерщик" из компании в AmoCRM (если назначение по дилеру)
ALTER TABLE measurements ADD COLUMN dealer_field_value VARCHAR(500);

-- === ИНДЕКСЫ ===
-- Индексы для таблицы measurements
CREATE INDEX IF NOT EXISTS ix_measurements_auto_assigned_measurer_id
    ON measurements(auto_assigned_measurer_id);

CREATE INDEX IF NOT EXISTS ix_measurements_assignment_reason
    ON measurements(assignment_reason);

-- Индексы для таблицы measurer_name_assignments
CREATE INDEX IF NOT EXISTS ix_measurer_name_assignments_user_id
    ON measurer_name_assignments(user_id);

CREATE INDEX IF NOT EXISTS ix_measurer_name_assignments_measurer_name_id
    ON measurer_name_assignments(measurer_name_id);

-- Индекс для быстрого поиска имён
CREATE INDEX IF NOT EXISTS ix_measurer_names_name
    ON measurer_names(name);
