"""
Скрипт для безопасного применения миграции add_confirmed_by_user_id
Проверяет наличие колонок перед добавлением
"""
import sqlite3
import sys
from pathlib import Path

# Путь к базе данных
DB_PATH = Path(__file__).parent.parent / "measurerers_bot.db"

def column_exists(cursor, table_name, column_name):
    """Проверяет существование колонки в таблице"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def index_exists(cursor, index_name):
    """Проверяет существование индекса"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None

def apply_migration():
    """Применяет миграцию к базе данных"""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("🔄 Применение миграции add_confirmed_by_user_id...")

        # === ТАБЛИЦА MEASUREMENTS ===
        print("\n📋 Обработка таблицы measurements...")

        # Добавляем confirmed_by_user_id если не существует
        if not column_exists(cursor, "measurements", "confirmed_by_user_id"):
            print("  ➕ Добавление поля confirmed_by_user_id...")
            cursor.execute("""
                ALTER TABLE measurements
                ADD COLUMN confirmed_by_user_id INTEGER
                REFERENCES users(id) ON DELETE SET NULL
            """)
            print("  ✅ Поле confirmed_by_user_id добавлено")
        else:
            print("  ⏭️  Поле confirmed_by_user_id уже существует")

        # Создаем индекс если не существует
        if not index_exists(cursor, "ix_measurements_confirmed_by_user_id"):
            print("  ➕ Создание индекса ix_measurements_confirmed_by_user_id...")
            cursor.execute("""
                CREATE INDEX ix_measurements_confirmed_by_user_id
                ON measurements(confirmed_by_user_id)
            """)
            print("  ✅ Индекс ix_measurements_confirmed_by_user_id создан")
        else:
            print("  ⏭️  Индекс ix_measurements_confirmed_by_user_id уже существует")

        # === ТАБЛИЦА NOTIFICATIONS ===
        print("\n📋 Обработка таблицы notifications...")

        # Добавляем telegram_message_id если не существует
        if not column_exists(cursor, "notifications", "telegram_message_id"):
            print("  ➕ Добавление поля telegram_message_id...")
            cursor.execute("""
                ALTER TABLE notifications
                ADD COLUMN telegram_message_id BIGINT
            """)
            print("  ✅ Поле telegram_message_id добавлено")
        else:
            print("  ⏭️  Поле telegram_message_id уже существует")

        # Добавляем telegram_chat_id если не существует
        if not column_exists(cursor, "notifications", "telegram_chat_id"):
            print("  ➕ Добавление поля telegram_chat_id...")
            cursor.execute("""
                ALTER TABLE notifications
                ADD COLUMN telegram_chat_id BIGINT
            """)
            print("  ✅ Поле telegram_chat_id добавлено")
        else:
            print("  ⏭️  Поле telegram_chat_id уже существует")

        # Создаем индекс если не существует
        if not index_exists(cursor, "ix_notifications_measurement_type"):
            print("  ➕ Создание индекса ix_notifications_measurement_type...")
            cursor.execute("""
                CREATE INDEX ix_notifications_measurement_type
                ON notifications(measurement_id, notification_type)
            """)
            print("  ✅ Индекс ix_notifications_measurement_type создан")
        else:
            print("  ⏭️  Индекс ix_notifications_measurement_type уже существует")

        # Сохраняем изменения
        conn.commit()
        print("\n✅ Миграция успешно применена!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Ошибка при применении миграции: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    apply_migration()
