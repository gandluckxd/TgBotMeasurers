"""Конфигурация приложения"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
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


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Telegram Bot (опциональные для sheets_exporter)
    bot_token: str = Field(default="", description="Токен Telegram бота")
    admin_ids: str = Field(default="", description="ID администраторов через запятую")

    # AmoCRM
    amocrm_subdomain: str = Field(default="", description="Поддомен AmoCRM")
    amocrm_access_token: str = Field(default="", description="Access токен AmoCRM")
    amocrm_refresh_token: str = Field(default="", description="Refresh токен AmoCRM")
    amocrm_client_id: str = Field(default="", description="Client ID AmoCRM")
    amocrm_client_secret: str = Field(default="", description="Client Secret AmoCRM")
    amocrm_redirect_uri: str = Field(default="", description="Redirect URI AmoCRM")

    # Webhook
    webhook_host: str = Field(default="", description="Хост для webhook")
    webhook_path: str = Field(default="/webhook/amocrm", description="Путь webhook")
    webhook_secret: str = Field(default="", description="Секретный ключ webhook")

    # Server
    server_host: str = Field(default="0.0.0.0", description="Хост сервера")
    server_port: int = Field(default=8020, description="Порт сервера")

    # Database
    database_url: str = Field(
        default="",
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
        default="",
        description="ID Google таблицы для экспорта"
    )
    google_export_interval: int = Field(
        default=300,
        description="Интервал экспорта в секундах (по умолчанию 300 = 5 минут)"
    )

    @property
    def admin_ids_list(self) -> List[int]:
        """Возвращает список ID администраторов"""
        return [int(id_.strip()) for id_ in self.admin_ids.split(",") if id_.strip()]

    @property
    def webhook_url(self) -> str:
        """Полный URL webhook"""
        return f"{self.webhook_host}{self.webhook_path}"

    def model_post_init(self, __context) -> None:
        """Вызывается после инициализации модели"""
        # Если database_url пустой или относительный, заменяем на абсолютный путь
        if not self.database_url or self.database_url == "sqlite+aiosqlite:///./measurerers_bot.db":
            db_path = os.path.join(application_path, "measurerers_bot.db")
            db_path = db_path.replace("\\", "/")
            object.__setattr__(self, 'database_url', f"sqlite+aiosqlite:///{db_path}")


# Создаем глобальный экземпляр настроек
settings = Settings()
