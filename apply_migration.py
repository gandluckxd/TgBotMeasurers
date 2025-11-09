"""Скрипт применения миграции базы данных"""
import sqlite3
import sys
from pathlib import Path

def apply_migration():
    """Применить миграцию к базе данных"""
    db_path = Path(__file__).parent / "measurerers_bot.db"
    migration_path = Path(__file__).parent / "migrations" / "001_update_measurements_fields.sql"

    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        return False

    if not migration_path.exists():
        print(f"[ERROR] Migration file not found: {migration_path}")
        return False

    print(f"[DB] Applying migration to database: {db_path}")
    print(f"[SQL] Migration file: {migration_path}")

    try:
        # Читаем SQL скрипт
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Выполняем миграцию
        print("\n[RUN] Executing migration...")
        cursor.executescript(sql_script)
        conn.commit()

        print("[OK] Migration applied successfully!")

        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(measurements)")
        columns = cursor.fetchall()

        print("\n[INFO] Table measurements structure:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        conn.close()
        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
