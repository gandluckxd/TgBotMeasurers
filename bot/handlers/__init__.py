"""Обработчики команд бота"""
from bot.handlers.admin import admin_router
from bot.handlers.measurer import measurer_router
from bot.handlers.manager import manager_router

__all__ = [
    "admin_router",
    "measurer_router",
    "manager_router",
]
