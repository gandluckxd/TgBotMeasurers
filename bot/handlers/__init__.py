"""Обработчики команд бота"""
from bot.handlers.admin import admin_router
from bot.handlers.measurer import measurer_router
from bot.handlers.manager import manager_router
from bot.handlers.registration import registration_router
from bot.handlers.invite_links import invite_links_router

__all__ = [
    "registration_router",  # Регистрация должна быть первой
    "invite_links_router",  # Управление пригласительными ссылками
    "admin_router",
    "measurer_router",
    "manager_router",
]
