# Altawin DB API

Микросервис для работы с базой данных Altawin (Firebird).

## Установка и запуск

### 1. Создание виртуального окружения
```bash
# Используйте Python 3.10 32-bit (для совместимости с 32-bit Firebird Client)
py -3.10-32 -m venv venv
```

### 2. Установка зависимостей
```bash
venv\Scripts\pip.exe install -r requirements.txt
```

### 3. Настройка
Отредактируйте файл `.env` и укажите параметры подключения к БД Altawin:
```
DB_HOST=192.168.1.251
DB_PORT=3050
DB_NAME=D:/AltawinDB/altawinOffice.FDB
DB_USER=sysdba
DB_PASSWORD=masterkey
DB_CHARSET=WIN1251

API_HOST=127.0.0.1
API_PORT=8001
```

### 4. Запуск API сервера
```bash
venv\Scripts\python.exe main.py
```

Сервер будет доступен по адресу: http://127.0.0.1:8001

## API Endpoints

### GET /
Информация о сервисе

### GET /health
Проверка здоровья сервиса и подключения к БД

### GET /api/orders/{order_code}
Получить данные заказа по уникальному коду

**Пример запроса:**
```bash
curl http://127.0.0.1:8001/api/orders/GP!282!PG8$6J78gbbg87J6$8
```

**Пример ответа:**
```json
{
  "order_id": 123,
  "order_number": "12345",
  "total_price": 50000.0,
  "qty_izd": 3.0,
  "area_izd": 15.5,
  "zone": "Зона 1",
  "measurer": "Иванов И.И.",
  "address": "г. Москва, ул. Ленина, д. 1",
  "agreement_date": "2025-01-15",
  "agreement_no": "Д-12345",
  "phone": "79991234567"
}
```

## Стек технологий

- **Python**: 3.10.11 (32-bit)
- **FastAPI**: 0.104.1
- **FDB**: 2.0.4 (Firebird database driver)
- **Uvicorn**: 0.24.0

## Требования

- Python 3.10 (32-bit)
- Firebird Client 32-bit (fbclient.dll)
- Доступ к серверу БД Altawin (192.168.1.251:3050)
