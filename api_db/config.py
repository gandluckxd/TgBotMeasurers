"""Конфигурация API для работы с БД Altawin"""
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки базы данных Firebird
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "192.168.1.251"),
    "port": int(os.getenv("DB_PORT", "3050")),
    "database": os.getenv("DB_NAME", "D:/AltawinDB/altawinOffice.FDB"),
    "user": os.getenv("DB_USER", "sysdba"),
    "password": os.getenv("DB_PASSWORD", "masterkey"),
    "charset": os.getenv("DB_CHARSET", "WIN1251")
}

# Настройки сервера API
SERVER_HOST = os.getenv("API_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("API_PORT", "8001"))
