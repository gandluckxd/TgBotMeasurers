"""
PyInstaller hook для системы логирования
Создает папку logs/ при запуске EXE
"""
import os
import sys
from pathlib import Path

# Определяем базовый путь в зависимости от того, запущен ли бот как EXE
if getattr(sys, 'frozen', False):
    # Запущен как EXE (PyInstaller)
    base_path = os.path.dirname(sys.executable)
else:
    # Запущен как скрипт Python
    base_path = os.path.dirname(os.path.abspath(__file__))

# Создаем папку logs/ если её нет
logs_dir = Path(base_path) / 'logs'
logs_dir.mkdir(exist_ok=True)

print(f"[Logging Hook] Logs directory: {logs_dir}")
