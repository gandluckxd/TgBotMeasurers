"""Тест подключения к БД Altawin"""
import fdb
from config import settings

print("=" * 60)
print("TEST PODKLYUCHENIYA K BD ALTAWIN")
print("=" * 60)

print(f"\nParametry podklyucheniya:")
print(f"  Host: {settings.altawin_db_host}")
print(f"  Port: {settings.altawin_db_port}")
print(f"  Database: {settings.altawin_db_path}")
print(f"  User: {settings.altawin_db_user}")
print(f"  Charset: {settings.altawin_db_charset}")

print(f"\n--- Podklyuchenie cherez fdb 2.0.4 ---")

try:
    # Используем fdb.connect с отдельными параметрами (как в рабочем проекте)
    connection = fdb.connect(
        host=settings.altawin_db_host,
        port=settings.altawin_db_port,
        database=settings.altawin_db_path,
        user=settings.altawin_db_user,
        password=settings.altawin_db_password,
        charset=settings.altawin_db_charset
    )

    print("[OK] PODKLYUCHENIE USPESHNO!")

    # Пробуем выполнить тестовый запрос
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders")
    count = cursor.fetchone()[0]
    print(f"[OK] Kolichestvo zakazov v BD: {count}")

    cursor.close()
    connection.close()

    print("\n" + "=" * 60)
    print("PODKLYUCHENIE RABOTAET!")
    print("=" * 60)

except Exception as e:
    print(f"[ERROR] OSHIBKA: {e}")
    print(f"   Tip oshibki: {type(e).__name__}")

print("\nTest zavershen.")
