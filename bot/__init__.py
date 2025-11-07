"""Telegram бот для управления замерами"""
from aiogram import Bot
from typing import Optional

# Глобальный экземпляр бота
_bot_instance: Optional[Bot] = None


def set_bot(bot: Bot) -> None:
    """
    Установить глобальный экземпляр бота

    Args:
        bot: Экземпляр бота
    """
    global _bot_instance
    _bot_instance = bot


def get_bot() -> Optional[Bot]:
    """
    Получить глобальный экземпляр бота

    Returns:
        Экземпляр бота или None
    """
    return _bot_instance
