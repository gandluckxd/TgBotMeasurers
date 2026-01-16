"""Упрощенная конфигурация для sheets_exporter"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
import sys


# Определяем путь к .env файлу рядом с исполняемым файлом
if getattr(sys, 'frozen', False):
    # Запущен как EXE (PyInstaller)
    application_path = os.path.dirname(sys.executable)
else:
    # Запущен как скрипт Python
    application_path = os.path.dirname(os.path.abspath(__file__))

ENV_FILE_PATH = os.path.join(application_path, '.env')


class ExporterSettings(BaseSettings):
    """Настройки для экспортера (только необходимые параметры)"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'  # Игнорировать лишние поля из .env
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./measurerers_bot.db",
        description="URL базы данных"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Уровень логирования")

    # Google Sheets
    google_credentials_file: str = Field(
        default="credentials.json",
        description="Путь к файлу credentials.json для Google Sheets"
    )
    google_spreadsheet_id: str = Field(
        description="ID Google таблицы для экспорта"
    )
    google_export_interval: int = Field(
        default=300,
        description="Интервал экспорта в секундах (по умолчанию 300 = 5 минут)"
    )


# Создаем экземпляр настроек для экспортера
settings = ExporterSettings()
