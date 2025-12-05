"""Обработчики команд бота"""
from bot.handlers.admin import admin_router
from bot.handlers.measurer import measurer_router
from bot.handlers.manager import manager_router
from bot.handlers.registration import registration_router
from bot.handlers.invite_links import invite_links_router
from bot.handlers.zones import zones_router
from bot.handlers.measurer_names import measurer_names_router

__all__ = [
    "registration_router",  # Регистрация должна быть первой
    "invite_links_router",  # Управление пригласительными ссылками
    "zones_router",  # Управление зонами доставки
    "measurer_names_router",  # Управление именами замерщиков из AmoCRM
    "admin_router",
    "measurer_router",
    "manager_router",
]
