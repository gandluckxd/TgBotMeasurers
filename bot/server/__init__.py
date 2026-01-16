"""Модуль веб-сервера для приема webhook"""
from server.app import app, set_webhook_processor
from server.webhook import WebhookProcessor

__all__ = [
    "app",
    "set_webhook_processor",
    "WebhookProcessor",
]
