"""Скрипт для применения миграции базы данных"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import db
from loguru import logger


async def apply_migration():
    """Применить миграцию для добавления новых полей"""
    logger.info("Начало применения миграции...")

    try:
        # Получаем информацию о таблице
        async with db.engine.begin() as conn:
            from sqlalchemy import text

            # Проверяем существующие колонки
            result = await conn.execute(text("PRAGMA table_info(measurements)"))
            columns = [row[1] for row in result.fetchall()]

            logger.info(f"Текущие колонки: {columns}")

            # Проверяем, есть ли уже новые поля
            if "order_number" in columns:
                logger.info("✅ Новые поля уже существуют в таблице!")
                return

            logger.info("Применяю миграцию для SQLite...")

            # Создаем временную таблицу с новой структурой
            await conn.execute(text("""
                CREATE TABLE measurements_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amocrm_lead_id INTEGER UNIQUE NOT NULL,
                    lead_name VARCHAR(500) NOT NULL,
                    responsible_user_name VARCHAR(500),
                    contact_name VARCHAR(500),
                    contact_phone VARCHAR(50),
                    address TEXT,
                    delivery_zone VARCHAR(500),
                    order_number VARCHAR(100),
                    windows_count VARCHAR(50),
                    windows_area VARCHAR(50),
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
                )
            """))

            logger.info("Создана временная таблица measurements_new")

            # Проверяем, есть ли данные в старой таблице
            result = await conn.execute(text("SELECT COUNT(*) FROM measurements"))
            count = result.fetchone()[0]
            logger.info(f"Найдено {count} записей в старой таблице")

            if count > 0:
                # Копируем данные из старой таблицы (только существующие поля)
                await conn.execute(text("""
                    INSERT INTO measurements_new
                    (id, amocrm_lead_id, lead_name, responsible_user_name,
                     contact_name, contact_phone, address, delivery_zone,
                     description, notes, status, measurer_id, manager_id,
                     created_at, assigned_at, completed_at, updated_at)
                    SELECT
                        id, amocrm_lead_id, lead_name, responsible_user_name,
                        contact_name, contact_phone, address, delivery_zone,
                        description, notes, status, measurer_id, manager_id,
                        created_at, assigned_at, completed_at, updated_at
                    FROM measurements
                """))
                logger.info(f"Скопировано {count} записей")

            # Удаляем старую таблицу
            await conn.execute(text("DROP TABLE measurements"))
            logger.info("Удалена старая таблица measurements")

            # Переименовываем новую таблицу
            await conn.execute(text("ALTER TABLE measurements_new RENAME TO measurements"))
            logger.info("Переименована measurements_new -> measurements")

            # Создаем индекс для номера заказа
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_measurements_order_number
                ON measurements(order_number)
            """))
            logger.info("Создан индекс idx_measurements_order_number")

            # Создаем индекс для amocrm_lead_id (если еще не существует)
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_measurements_amocrm_lead_id
                ON measurements(amocrm_lead_id)
            """))
            logger.info("Создан индекс idx_measurements_amocrm_lead_id")

            # Создаем индекс для status (если еще не существует)
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_measurements_status
                ON measurements(status)
            """))
            logger.info("Создан индекс idx_measurements_status")

            logger.info("✅ Миграция успешно применена!")

    except Exception as e:
        logger.error(f"❌ Ошибка при применении миграции: {e}", exc_info=True)
        raise


async def main():
    """Главная функция"""
    logger.info("=" * 60)
    logger.info("Миграция базы данных: Добавление полей окон из AmoCRM")
    logger.info("=" * 60)

    try:
        await apply_migration()
        logger.info("Миграция завершена успешно!")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")
        sys.exit(1)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
