"""
Скрипт для проверки применения миграции
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "measurerers_bot.db"

def check_migration():
    """Проверяет наличие всех полей из миграции"""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🔍 Проверка структуры базы данных...\n")

    # Проверяем таблицу measurements
    print("📋 Таблица MEASUREMENTS:")
    cursor.execute("PRAGMA table_info(measurements)")
    measurements_columns = {row[1]: row[2] for row in cursor.fetchall()}

    if "confirmed_by_user_id" in measurements_columns:
        print("  ✅ confirmed_by_user_id существует")
        print(f"     Тип: {measurements_columns['confirmed_by_user_id']}")
    else:
        print("  ❌ confirmed_by_user_id НЕ НАЙДЕНО")

    # Проверяем индексы для measurements
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='measurements'")
    measurements_indexes = [row[0] for row in cursor.fetchall()]

    if "ix_measurements_confirmed_by_user_id" in measurements_indexes:
        print("  ✅ Индекс ix_measurements_confirmed_by_user_id существует")
    else:
        print("  ❌ Индекс ix_measurements_confirmed_by_user_id НЕ НАЙДЕН")

    # Проверяем таблицу notifications
    print("\n📋 Таблица NOTIFICATIONS:")
    cursor.execute("PRAGMA table_info(notifications)")
    notifications_columns = {row[1]: row[2] for row in cursor.fetchall()}

    if "telegram_message_id" in notifications_columns:
        print("  ✅ telegram_message_id существует")
        print(f"     Тип: {notifications_columns['telegram_message_id']}")
    else:
        print("  ❌ telegram_message_id НЕ НАЙДЕНО")

    if "telegram_chat_id" in notifications_columns:
        print("  ✅ telegram_chat_id существует")
        print(f"     Тип: {notifications_columns['telegram_chat_id']}")
    else:
        print("  ❌ telegram_chat_id НЕ НАЙДЕНО")

    # Проверяем индексы для notifications
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notifications'")
    notifications_indexes = [row[0] for row in cursor.fetchall()]

    if "ix_notifications_measurement_type" in notifications_indexes:
        print("  ✅ Индекс ix_notifications_measurement_type существует")
    else:
        print("  ❌ Индекс ix_notifications_measurement_type НЕ НАЙДЕН")

    conn.close()

    # Итоговая проверка
    print("\n" + "="*50)
    all_ok = (
        "confirmed_by_user_id" in measurements_columns and
        "ix_measurements_confirmed_by_user_id" in measurements_indexes and
        "telegram_message_id" in notifications_columns and
        "telegram_chat_id" in notifications_columns and
        "ix_notifications_measurement_type" in notifications_indexes
    )

    if all_ok:
        print("✅ ВСЕ ПОЛЯ И ИНДЕКСЫ МИГРАЦИИ ПРИМЕНЕНЫ")
        return True
    else:
        print("❌ МИГРАЦИЯ ПРИМЕНЕНА НЕ ПОЛНОСТЬЮ")
        print("\nДля применения миграции выполните SQL из файла:")
        print("migrations/add_confirmed_by_user_id_fixed.sql")
        return False

if __name__ == "__main__":
    check_migration()
