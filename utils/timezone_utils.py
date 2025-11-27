"""Утилиты для работы с временными зонами"""
from datetime import datetime, timezone, timedelta
from typing import Optional


# Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))


def to_moscow_time(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Конвертировать datetime в московское время (UTC+3)

    Args:
        dt: Datetime объект (предполагается UTC если нет timezone info)

    Returns:
        Datetime в московском времени или None если входной dt=None
    """
    if dt is None:
        return None

    # Если у datetime нет timezone info, считаем его UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(MOSCOW_TZ)


def format_moscow_time(dt: Optional[datetime], format_str: str = '%d.%m.%Y %H:%M') -> str:
    """
    Отформатировать datetime в московском времени

    Args:
        dt: Datetime объект для форматирования
        format_str: Строка форматирования (по умолчанию '%d.%m.%Y %H:%M')

    Returns:
        Отформатированная строка или 'Не указано' если dt=None
    """
    if dt is None:
        return 'Не указано'

    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(format_str)


def timestamp_to_moscow_time(timestamp: Optional[int]) -> Optional[datetime]:
    """
    Конвертировать unix timestamp в московское время

    Args:
        timestamp: Unix timestamp (секунды с 1970-01-01)

    Returns:
        Datetime в московском времени или None если timestamp=None
    """
    if timestamp is None:
        return None

    utc_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return utc_dt.astimezone(MOSCOW_TZ)


def moscow_now() -> datetime:
    """
    Получить текущее время в московском часовом поясе (UTC+3)

    Returns:
        Datetime объект с текущим московским временем
    """
    return datetime.now(MOSCOW_TZ)
