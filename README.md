# Система управления замерами

Telegram бот для управления замерами с интеграцией AmoCRM и базой данных Altawin (Firebird).

## Архитектура проекта

Проект разделен на два микросервиса:

```
TgBotMeasurers/
├── bot/                    # Основное приложение (Telegram бот + AmoCRM webhook)
│   ├── bot_handlers/       # Обработчики команд Telegram бота
│   ├── server/             # FastAPI сервер для AmoCRM webhook
│   ├── database/           # Модели и функции работы с БД SQLite
│   ├── services/           # Сервисы (AmoCRM, Altawin API клиент)
│   ├── main.py             # Точка входа
│   └── requirements.txt    # Зависимости
│
└── api_db/                 # Микросервис для работы с БД Altawin (Firebird)
    ├── main.py             # FastAPI приложение
    ├── database.py         # Работа с Firebird
    ├── config.py           # Конфигурация
    └── requirements.txt    # Зависимости (fdb 2.0.4)
```

## Быстрый старт

### 1. API для работы с БД Altawin

```bash
cd api_db

# Создать виртуальное окружение (Python 3.10 32-bit)
py -3.10-32 -m venv venv

# Установить зависимости
venv\Scripts\pip.exe install -r requirements.txt

# Настроить .env файл (параметры БД Firebird)

# Запустить API сервер
venv\Scripts\python.exe main.py
```

API будет доступен по адресу: http://127.0.0.1:8001

### 2. Основное приложение (бот)

```bash
cd bot

# Создать виртуальное окружение (можно любую версию Python 3.11+)
python -m venv venv

# Установить зависимости
venv\Scripts\pip.exe install -r requirements.txt

# Настроить .env файл (токены, API ключи)

# Запустить приложение
venv\Scripts\python.exe main.py
```

Бот и webhook сервер запустятся автоматически.

## Требования

### API для БД Altawin
- Python 3.10 (32-bit)
- Firebird Client 32-bit (fbclient.dll)
- Доступ к серверу БД Altawin

### Основное приложение
- Python 3.11+ (любая разрядность)
- Telegram Bot Token
- AmoCRM API credentials
- Доступ к API БД Altawin

## Настройка

### api_db/.env
```env
DB_HOST=192.168.1.251
DB_PORT=3050
DB_NAME=D:/AltawinDB/altawinOffice.FDB
DB_USER=sysdba
DB_PASSWORD=masterkey
DB_CHARSET=WIN1251

API_HOST=127.0.0.1
API_PORT=8001
```

### bot/.env
```env
# Telegram Bot
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789

# AmoCRM
AMOCRM_SUBDOMAIN=your_subdomain
AMOCRM_ACCESS_TOKEN=your_token
# ... другие параметры AmoCRM

# Altawin API
ALTAWIN_API_URL=http://127.0.0.1:8001

# Webhook (для AmoCRM)
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_PATH=/webhook/amocrm

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8020
```

## Документация API

### Altawin DB API

**GET /api/orders/{order_code}**
Получить данные заказа по уникальному коду

Пример:
```bash
curl http://127.0.0.1:8001/api/orders/GP!282!PG8$6J78gbbg87J6$8
```

## Основные компоненты

### Bot (bot/)
- **bot_handlers/** - Обработчики Telegram команд
- **server/** - FastAPI сервер для приема webhook от AmoCRM
- **database/** - SQLAlchemy модели и операции с БД
- **services/** - Интеграции (AmoCRM, Altawin API)

### API DB (api_db/)
- **main.py** - FastAPI приложение с REST API
- **database.py** - Прямое подключение к Firebird БД
- **config.py** - Настройки подключения

## Как это работает

1. AmoCRM отправляет webhook при создании/изменении сделки
2. Bot получает webhook и извлекает код заказа Altawin
3. Bot запрашивает данные заказа через API DB
4. API DB подключается к Firebird и возвращает данные
5. Bot создает замер в своей БД и уведомляет участников

## Проблемы и решения

**Ошибка "unavailable database"**
- Проверьте VPN (должен быть отключен для локальной сети)
- Убедитесь что API DB запущен
- Проверьте параметры подключения в api_db/.env

**Ошибка "connection refused" при обращении к API**
- Убедитесь что API DB запущен (http://127.0.0.1:8001)
- Проверьте URL в bot/.env (ALTAWIN_API_URL)

## Разработка

Структура разделена на два независимых проекта для:
- Изоляции зависимостей (разные версии Python, библиотеки)
- Упрощения развертывания
- Возможности масштабирования каждого сервиса отдельно

## Лицензия

Частный проект
