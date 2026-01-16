# Структура проекта

## Корень
```
TgBotMeasurers/
├── bot/            # Основное приложение
├── api_db/         # API для работы с Firebird
└── README.md       # Документация
```

## bot/
```
bot/
├── venv/                           # Виртуальное окружение
├── bot_handlers/                   # Telegram бот
│   ├── handlers/                   # Обработчики команд
│   ├── keyboards/                  # Клавиатуры
│   ├── middlewares/                # Middleware
│   ├── utils/                      # Утилиты
│   └── main.py                     # Запуск бота
├── server/                         # FastAPI webhook сервер
│   ├── app.py                      # FastAPI приложение
│   └── webhook.py                  # Обработка webhook AmoCRM
├── database/                       # База данных
│   ├── models.py                   # SQLAlchemy модели
│   └── database.py                 # CRUD операции
├── services/                       # Внешние сервисы
│   ├── amocrm.py                   # AmoCRM API клиент
│   ├── altawin.py                  # Altawin API клиент (HTTP)
│   └── zone_service.py             # Логика распределения
├── migrations/                     # Миграции Alembic
├── main.py                         # Точка входа
├── config.py                       # Конфигурация
├── requirements.txt                # Зависимости
└── .env                            # Переменные окружения
```

## api_db/
```
api_db/
├── venv/                   # Виртуальное окружение (Python 3.10-32)
├── main.py                 # FastAPI приложение
├── database.py             # Работа с Firebird (fdb)
├── config.py               # Конфигурация
├── requirements.txt        # Зависимости (fdb 2.0.4)
├── .env                    # Переменные окружения
└── README.md               # Документация API
```

## Зависимости

### bot/requirements.txt
- aiogram 3.13.1
- fastapi 0.115.4
- sqlalchemy 2.0.35
- httpx 0.27.2 (для обращения к api_db)
- и другие...

### api_db/requirements.txt
- fastapi 0.104.1
- fdb 2.0.4
- uvicorn 0.24.0
- pydantic 2.5.0

## Запуск

1. **Запустить API DB:**
   ```bash
   cd api_db
   venv\Scripts\python.exe main.py
   ```

2. **Запустить Bot:**
   ```bash
   cd bot
   venv\Scripts\python.exe main.py
   ```

