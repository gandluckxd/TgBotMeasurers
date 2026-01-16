"""Модуль для экспорта данных в Google Sheets"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Measurement, User
from database.database import db
from config import settings
from loguru import logger
from utils.timezone_utils import format_moscow_time, moscow_now


class GoogleSheetsExporter:
    """Класс для экспорта данных замеров в Google Sheets"""

    def __init__(self, credentials_file: str, spreadsheet_id: str):
        """
        Инициализация экспортера

        Args:
            credentials_file: Путь к файлу credentials.json
            spreadsheet_id: ID Google таблицы
        """
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None

    def connect(self):
        """Подключение к Google Sheets API"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]

            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            logger.info(f"Успешное подключение к Google Sheets: {self.spreadsheet.title}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Sheets: {e}")
            return False

    async def get_measurements_data(self) -> List[List[str]]:
        """
        Получение данных всех замеров из БД

        Returns:
            Список строк для записи в таблицу
        """
        from sqlalchemy.orm import joinedload

        async for session in db.get_session():
            # Получаем все замеры с связанными данными
            query = (
                select(Measurement)
                .options(
                    joinedload(Measurement.measurer),
                    joinedload(Measurement.manager),
                    joinedload(Measurement.auto_assigned_measurer),
                    joinedload(Measurement.confirmed_by)
                )
                .order_by(Measurement.created_at.desc())
            )
            result = await session.execute(query)
            measurements = result.scalars().unique().all()

            # Формируем данные для таблицы
            data = []

            for m in measurements:
                # Получаем связанные данные
                measurer_name = m.measurer.full_name if m.measurer else "Не назначен"
                contact_name = m.contact_name or "—"
                manager_name = m.manager.full_name if m.manager else (m.responsible_user_name or "—")
                zone = m.delivery_zone or "—"
                address = m.address or "—"
                windows_count = m.windows_count or "—"
                windows_area = m.windows_area or "—"

                # Новые поля для автоматического распределения
                auto_assigned_measurer_name = m.auto_assigned_measurer.full_name if m.auto_assigned_measurer else "—"

                # Основание автоматического распределения
                assignment_reason_map = {
                    'dealer': 'Привязанный замерщик',
                    'zone': 'Зона доставки',
                    'round_robin': 'По очереди',
                    'none': 'Не распределено'
                }
                assignment_reason = assignment_reason_map.get(m.assignment_reason, "—")

                # Кто распределил
                assigned_by = m.confirmed_by.full_name if m.confirmed_by else "—"

                # Итоговый замерщик
                final_measurer = m.measurer.full_name if m.measurer else "Не назначен"

                # Стоимость из названия сделки (если есть)
                # Предполагаем, что стоимость может быть в названии сделки
                cost = "—"  # По умолчанию

                # Даты
                assigned_date = m.assigned_at.strftime('%d.%m.%Y %H:%M') if m.assigned_at else "—"
                completed_date = m.completed_at.strftime('%d.%m.%Y %H:%M') if m.completed_at else "—"

                row = [
                    m.order_number or "—",         # Номер заказа
                    contact_name,                  # Контакт
                    manager_name,                  # Менеджер
                    zone,                          # Зона
                    address,                       # Адрес
                    windows_count,                 # Количество окон
                    windows_area,                  # Площадь окон
                    cost,                          # Стоимость
                    auto_assigned_measurer_name,   # Автоматически распределенный замерщик
                    assignment_reason,             # Основание автоматического распределения
                    assigned_by,                   # Кто распределил
                    final_measurer,                # Итоговый замерщик
                    assigned_date,                 # Дата назначения
                    completed_date                 # Дата выполнения
                ]
                data.append(row)

            logger.info(f"Получено {len(data)} записей замеров для экспорта")
            return data

    def update_sheet(self, data: List[List[str]]):
        """
        Обновление данных в таблице

        Args:
            data: Данные для записи
        """
        try:
            # Получаем первый лист или создаем новый
            try:
                worksheet = self.spreadsheet.worksheet("Замеры")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(title="Замеры", rows=1000, cols=20)

            # Время последнего обновления
            last_update_time = format_moscow_time(moscow_now(), '%d.%m.%Y %H:%M:%S')

            # Строка 1 - время обновления
            worksheet.update_acell('A1', f'Последнее обновление: {last_update_time}')
            worksheet.format('A1:N1', {
                "textFormat": {"italic": True, "fontSize": 10}
            })

            # Строка 2 - заголовки (записываем только если их ещё нет)
            current_headers = worksheet.row_values(2)
            if not current_headers or current_headers[0] != "Номер заказа":
                headers = [
                    "Номер заказа",
                    "Контакт",
                    "Менеджер",
                    "Зона",
                    "Адрес",
                    "Количество окон",
                    "Площадь окон",
                    "Стоимость",
                    "Автоматически распределенный замерщик",
                    "Основание автоматического распределения",
                    "Кто распределил",
                    "Итоговый замерщик",
                    "Дата назначения замера",
                    "Дата выполнения замера"
                ]
                worksheet.update('A2:N2', [headers], value_input_option='USER_ENTERED')

            # Очищаем старые данные начиная с 3-й строки
            all_values = worksheet.get_all_values()
            if len(all_values) > 2:
                last_row = len(all_values)
                worksheet.batch_clear([f'A3:N{last_row}'])

            # Записываем данные начиная с A3
            if data:
                end_row = 2 + len(data)  # 2 (заголовки) + количество строк данных
                range_notation = f'A3:N{end_row}'
                worksheet.update(range_notation, data, value_input_option='USER_ENTERED')

            logger.info(f"Данные успешно обновлены в Google Sheets. Записано строк: {len(data)}")

        except Exception as e:
            logger.error(f"Ошибка обновления данных в Google Sheets: {e}")
            raise

    async def export_all(self):
        """Полный цикл экспорта данных"""
        try:
            # Подключаемся к Google Sheets
            if not self.connect():
                logger.error("Не удалось подключиться к Google Sheets")
                return False

            # Получаем данные
            data = await self.get_measurements_data()

            # Обновляем таблицу
            self.update_sheet(data)

            logger.info("Экспорт данных успешно завершен")
            return True

        except Exception as e:
            logger.error(f"Ошибка при экспорте данных: {e}")
            return False


async def export_to_google_sheets():
    """Функция для экспорта данных в Google Sheets"""
    exporter = GoogleSheetsExporter(
        credentials_file=settings.google_credentials_file,
        spreadsheet_id=settings.google_spreadsheet_id
    )

    await exporter.export_all()
