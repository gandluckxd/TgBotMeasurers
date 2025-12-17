"""Утилиты для форматирования телефонных номеров"""
import re


def format_phone_for_telegram(phone: str) -> str:
    """
    Форматирует телефон для кликабельности в Telegram

    Принимает различные форматы:
    - +7 (999) 123-45-67
    - 8 (999) 123-45-67
    - 89991234567
    - +79991234567
    - 79991234567

    Возвращает кликабельную ссылку для Telegram: <a href="tel:+79991234567">+7 (999) 123-45-67</a>

    Args:
        phone: Номер телефона в любом формате

    Returns:
        Отформатированная HTML-ссылка для Telegram
    """
    if not phone:
        return ""

    # Убираем все символы кроме цифр и +
    clean_phone = re.sub(r'[^\d+]', '', phone)

    # Если номер начинается с 8, заменяем на +7
    if clean_phone.startswith('8') and len(clean_phone) == 11:
        clean_phone = '+7' + clean_phone[1:]

    # Если номер начинается с 7 без +, добавляем +
    elif clean_phone.startswith('7') and not clean_phone.startswith('+'):
        clean_phone = '+' + clean_phone

    # Если номер не начинается с +, добавляем +7 (предполагаем российский номер)
    elif not clean_phone.startswith('+'):
        if len(clean_phone) == 10:
            clean_phone = '+7' + clean_phone
        else:
            # Возвращаем как есть, если формат неизвестен
            return phone

    # Форматируем для красивого отображения
    # Для российских номеров (+7XXXXXXXXXX)
    if clean_phone.startswith('+7') and len(clean_phone) == 12:
        # +7 (999) 123-45-67
        display_phone = f"+7 ({clean_phone[2:5]}) {clean_phone[5:8]}-{clean_phone[8:10]}-{clean_phone[10:12]}"
    else:
        # Для других номеров отображаем как есть
        display_phone = clean_phone

    # Возвращаем кликабельную ссылку
    return f'<a href="tel:{clean_phone}">{display_phone}</a>'


def normalize_phone(phone: str) -> str:
    """
    Нормализует телефон к формату +7XXXXXXXXXX (для хранения в БД)

    Args:
        phone: Номер телефона в любом формате

    Returns:
        Нормализованный номер в формате +7XXXXXXXXXX
    """
    if not phone:
        return ""

    # Убираем все символы кроме цифр и +
    clean_phone = re.sub(r'[^\d+]', '', phone)

    # Если номер начинается с 8, заменяем на +7
    if clean_phone.startswith('8') and len(clean_phone) == 11:
        clean_phone = '+7' + clean_phone[1:]

    # Если номер начинается с 7 без +, добавляем +
    elif clean_phone.startswith('7') and not clean_phone.startswith('+'):
        clean_phone = '+' + clean_phone

    # Если номер не начинается с +, добавляем +7 (предполагаем российский номер)
    elif not clean_phone.startswith('+'):
        if len(clean_phone) == 10:
            clean_phone = '+7' + clean_phone

    return clean_phone
