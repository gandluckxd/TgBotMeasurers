# -*- coding: utf-8 -*-
"""
Скрипт для безопасного применения миграции add_dealer_assignment
Проверяет наличие таблиц и колонок перед добавлением
"""
import sqlite3
import sys
import io
from pathlib import Path

# Настройка кодировки для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Путь к базе данных
DB_PATH = Path(__file__).parent.parent / "measurerers_bot.db"

def table_exists(cursor, table_name):
    """Проверяет существование таблицы"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def column_exists(cursor, table_name, column_name):
    """Проверяет существование колонки в таблице"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def index_exists(cursor, index_name):
    """Проверяет существование индекса"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,)
    )
    return cursor.fetchone() is not None

def apply_migration():
    """Применяет миграцию к базе данных"""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("🔄 Применение миграции add_dealer_assignment...")

        # === ТАБЛИЦА MEASURER_NAMES ===
        print("\n📋 Создание таблицы measurer_names...")

        if not table_exists(cursor, "measurer_names"):
            print("  ➕ Создание таблицы measurer_names...")
            cursor.execute("""
                CREATE TABLE measurer_names (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✅ Таблица measurer_names создана")
        else:
            print("  ⏭️  Таблица measurer_names уже существует")

        # === ТАБЛИЦА MEASURER_NAME_ASSIGNMENTS ===
        print("\n📋 Создание таблицы measurer_name_assignments...")

        if not table_exists(cursor, "measurer_name_assignments"):
            print("  ➕ Создание таблицы measurer_name_assignments...")
            cursor.execute("""
                CREATE TABLE measurer_name_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    measurer_name_id INTEGER NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (measurer_name_id) REFERENCES measurer_names(id) ON DELETE CASCADE,
                    CONSTRAINT unique_user_measurer_name UNIQUE (user_id, measurer_name_id)
                )
            """)
            print("  ✅ Таблица measurer_name_assignments создана")
        else:
            print("  ⏭️  Таблица measurer_name_assignments уже существует")

        # === ТАБЛИЦА MEASUREMENTS - НОВЫЕ ПОЛЯ ===
        print("\n📋 Обработка таблицы measurements...")

        # Добавляем auto_assigned_measurer_id если не существует
        if not column_exists(cursor, "measurements", "auto_assigned_measurer_id"):
            print("  ➕ Добавление поля auto_assigned_measurer_id...")
            cursor.execute("""
                ALTER TABLE measurements
                ADD COLUMN auto_assigned_measurer_id INTEGER
            """)
            print("  ✅ Поле auto_assigned_measurer_id добавлено")
        else:
            print("  ⏭️  Поле auto_assigned_measurer_id уже существует")

        # Добавляем assignment_reason если не существует
        if not column_exists(cursor, "measurements", "assignment_reason"):
            print("  ➕ Добавление поля assignment_reason...")
            cursor.execute("""
                ALTER TABLE measurements
                ADD COLUMN assignment_reason VARCHAR(50)
            """)
            print("  ✅ Поле assignment_reason добавлено")
        else:
            print("  ⏭️  Поле assignment_reason уже существует")

        # Добавляем dealer_company_name если не существует
        if not column_exists(cursor, "measurements", "dealer_company_name"):
            print("  ➕ Добавление поля dealer_company_name...")
            cursor.execute("""
                ALTER TABLE measurements
                ADD COLUMN dealer_company_name VARCHAR(500)
            """)
            print("  ✅ Поле dealer_company_name добавлено")
        else:
            print("  ⏭️  Поле dealer_company_name уже существует")

        # Добавляем dealer_field_value если не существует
        if not column_exists(cursor, "measurements", "dealer_field_value"):
            print("  ➕ Добавление поля dealer_field_value...")
            cursor.execute("""
                ALTER TABLE measurements
                ADD COLUMN dealer_field_value VARCHAR(500)
            """)
            print("  ✅ Поле dealer_field_value добавлено")
        else:
            print("  ⏭️  Поле dealer_field_value уже существует")

        # === ИНДЕКСЫ ===
        print("\n📋 Создание индексов...")

        # Индекс для auto_assigned_measurer_id
        if not index_exists(cursor, "ix_measurements_auto_assigned_measurer_id"):
            print("  ➕ Создание индекса ix_measurements_auto_assigned_measurer_id...")
            cursor.execute("""
                CREATE INDEX ix_measurements_auto_assigned_measurer_id
                ON measurements(auto_assigned_measurer_id)
            """)
            print("  ✅ Индекс ix_measurements_auto_assigned_measurer_id создан")
        else:
            print("  ⏭️  Индекс ix_measurements_auto_assigned_measurer_id уже существует")

        # Индекс для assignment_reason
        if not index_exists(cursor, "ix_measurements_assignment_reason"):
            print("  ➕ Создание индекса ix_measurements_assignment_reason...")
            cursor.execute("""
                CREATE INDEX ix_measurements_assignment_reason
                ON measurements(assignment_reason)
            """)
            print("  ✅ Индекс ix_measurements_assignment_reason создан")
        else:
            print("  ⏭️  Индекс ix_measurements_assignment_reason уже существует")

        # Индекс для user_id в measurer_name_assignments
        if not index_exists(cursor, "ix_measurer_name_assignments_user_id"):
            print("  ➕ Создание индекса ix_measurer_name_assignments_user_id...")
            cursor.execute("""
                CREATE INDEX ix_measurer_name_assignments_user_id
                ON measurer_name_assignments(user_id)
            """)
            print("  ✅ Индекс ix_measurer_name_assignments_user_id создан")
        else:
            print("  ⏭️  Индекс ix_measurer_name_assignments_user_id уже существует")

        # Индекс для measurer_name_id в measurer_name_assignments
        if not index_exists(cursor, "ix_measurer_name_assignments_measurer_name_id"):
            print("  ➕ Создание индекса ix_measurer_name_assignments_measurer_name_id...")
            cursor.execute("""
                CREATE INDEX ix_measurer_name_assignments_measurer_name_id
                ON measurer_name_assignments(measurer_name_id)
            """)
            print("  ✅ Индекс ix_measurer_name_assignments_measurer_name_id создан")
        else:
            print("  ⏭️  Индекс ix_measurer_name_assignments_measurer_name_id уже существует")

        # Индекс для name в measurer_names
        if not index_exists(cursor, "ix_measurer_names_name"):
            print("  ➕ Создание индекса ix_measurer_names_name...")
            cursor.execute("""
                CREATE INDEX ix_measurer_names_name
                ON measurer_names(name)
            """)
            print("  ✅ Индекс ix_measurer_names_name создан")
        else:
            print("  ⏭️  Индекс ix_measurer_names_name уже существует")

        # Сохраняем изменения
        conn.commit()
        print("\n✅ Миграция успешно применена!")
        print("\n📊 Статистика:")

        # Показываем количество записей в новых таблицах
        cursor.execute("SELECT COUNT(*) FROM measurer_names")
        measurer_names_count = cursor.fetchone()[0]
        print(f"  • Имён замерщиков: {measurer_names_count}")

        cursor.execute("SELECT COUNT(*) FROM measurer_name_assignments")
        assignments_count = cursor.fetchone()[0]
        print(f"  • Привязок имён: {assignments_count}")

        cursor.execute("SELECT COUNT(*) FROM measurements WHERE assignment_reason IS NOT NULL")
        measurements_with_reason = cursor.fetchone()[0]
        print(f"  • Замеров с причиной назначения: {measurements_with_reason}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Ошибка при применении миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    apply_migration()
