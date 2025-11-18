"""
Скрипт для проверки применения миграции add_confirmed_by_user_id
Проверяет наличие всех необходимых полей и индексов в базе данных
"""
import sqlite3
from pathlib import Path

def check_migration():
    """Проверяет применение миграции в базе данных"""

    DB_PATH = Path(__file__).parent / "measurerers_bot.db"

    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        return

    print("Proverka migracii bazy dannyh...\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # === PROVERKA TABLICY MEASUREMENTS ===
    print("Tablica MEASUREMENTS:")

    cursor.execute("PRAGMA table_info(measurements)")
    measurements_columns = {row[1]: row[2] for row in cursor.fetchall()}

    if 'confirmed_by_user_id' in measurements_columns:
        print(f"  [OK] confirmed_by_user_id suschestvuet")
        print(f"       Tip: {measurements_columns['confirmed_by_user_id']}")
    else:
        print("  [ERROR] confirmed_by_user_id NE NAIDENO")

    # Proveryaem indeksy dlya measurements
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='measurements'")
    measurements_indexes = [row[0] for row in cursor.fetchall()]

    if 'ix_measurements_confirmed_by_user_id' in measurements_indexes:
        print("  [OK] Indeks ix_measurements_confirmed_by_user_id suschestvuet")
    else:
        print("  [ERROR] Indeks ix_measurements_confirmed_by_user_id NE NAIDEN")

    # === PROVERKA TABLICY NOTIFICATIONS ===
    print("\nTabl ica NOTIFICATIONS:")

    cursor.execute("PRAGMA table_info(notifications)")
    notifications_columns = {row[1]: row[2] for row in cursor.fetchall()}

    if 'telegram_message_id' in notifications_columns:
        print(f"  [OK] telegram_message_id suschestvuet")
        print(f"       Tip: {notifications_columns['telegram_message_id']}")
    else:
        print("  [ERROR] telegram_message_id NE NAIDENO")

    if 'telegram_chat_id' in notifications_columns:
        print(f"  [OK] telegram_chat_id suschestvuet")
        print(f"       Tip: {notifications_columns['telegram_chat_id']}")
    else:
        print("  [ERROR] telegram_chat_id NE NAIDENO")

    # Proveryaem indeksy dlya notifications
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notifications'")
    notifications_indexes = [row[0] for row in cursor.fetchall()]

    if 'ix_notifications_measurement_type' in notifications_indexes:
        print("  [OK] Indeks ix_notifications_measurement_type suschestvuet")
    else:
        print("  [ERROR] Indeks ix_notifications_measurement_type NE NAIDEN")

    # === ITOGOVAYA PROVERKA ===
    print("\n" + "="*60)

    all_fields_ok = (
        'confirmed_by_user_id' in measurements_columns and
        'telegram_message_id' in notifications_columns and
        'telegram_chat_id' in notifications_columns
    )

    all_indexes_ok = (
        'ix_measurements_confirmed_by_user_id' in measurements_indexes and
        'ix_notifications_measurement_type' in notifications_indexes
    )

    if all_fields_ok and all_indexes_ok:
        print("[OK] VSE POLYA I INDEKSY MIGRACII PRIMENENY USPESHNO")
        print("\nBaza dannyh gotova k ispolzovaniyu!")
    elif all_fields_ok and not all_indexes_ok:
        print("[WARNING] POLYA DOBAVLENY, NO INDEKSY OTSUTSTVUYUT")
        print("\nIndeksy ne kritichny, no rekomenduetsya ih dobavit dlya proizvoditelnosti")
        print("Vypolnite SQL iz faila: migrations/add_confirmed_by_user_id.sql")
    else:
        print("[ERROR] MIGRACIYA PRIMENENA NE POLNOSTYU")
        print("\nNeobhodimo vypolnit migraciyu!")
        print("Fail migracii: migrations/add_confirmed_by_user_id.sql")

        if 'confirmed_by_user_id' not in measurements_columns:
            print("\n[WARNING] Otsutstvuet pole: confirmed_by_user_id v tablice measurements")
        if 'telegram_message_id' not in notifications_columns:
            print("[WARNING] Otsutstvuet pole: telegram_message_id v tablice notifications")
        if 'telegram_chat_id' not in notifications_columns:
            print("[WARNING] Otsutstvuet pole: telegram_chat_id v tablice notifications")

    # === DOPOLNITELNAYA INFORMACIYA ===
    print("\n" + "="*60)
    print("Dopolnitelnaya informaciya:")

    # Proveryaem kolichestvo zapisej s zapolnennym confirmed_by_user_id
    cursor.execute("SELECT COUNT(*) FROM measurements WHERE confirmed_by_user_id IS NOT NULL")
    confirmed_count = cursor.fetchone()[0]
    print(f"  - Zamerov s podtverzhdeniem: {confirmed_count}")

    # Proveryaem kolichestvo uvedomlenij s message_id
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE telegram_message_id IS NOT NULL")
    notifications_count = cursor.fetchone()[0]
    print(f"  - Uvedomlenij s message_id: {notifications_count}")

    conn.close()

if __name__ == "__main__":
    check_migration()
