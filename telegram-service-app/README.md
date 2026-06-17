# Telegram Service Mini App

MVP для продажи услуг внутри Telegram:

- бот отправляет кнопку для открытия Mini App;
- Mini App показывает каталог услуг и цены;
- клиент выбирает услугу и оставляет комментарий к заказу;
- backend сохраняет заказ в SQLite;
- владельцу приходит уведомление в Telegram;
- у уведомления есть кнопки для смены статуса заказа;
- клиент видит свои заказы и статусы в Mini App;
- клиент получает сообщение в Telegram при смене статуса;
- оплата пока в статусе `pending`, чтобы позже подключить YooKassa, CloudPayments, Robokassa, Telegram Stars или другой провайдер.

## Структура

```text
app/
  bot.py              # Telegram-бот
  config.py           # настройки из .env
  db.py               # SQLite
  main.py             # FastAPI backend + раздача Mini App
  products.py         # каталог услуг
  static/             # интерфейс Mini App
```

## Быстрый запуск

1. Создай бота через [@BotFather](https://t.me/BotFather) и получи токен.
2. Скопируй `.env.example` в `.env`.
3. Заполни:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
ADMIN_TELEGRAM_ID=123456789
WEB_APP_URL=https://your-public-url.example.com
ADMIN_SECRET=change-this-secret
ALLOW_DEV_USER=0
```

Для локального просмотра в браузере можно оставить:

```env
WEB_APP_URL=http://127.0.0.1:8000
ALLOW_DEV_USER=1
```

Для запуска Mini App внутри Telegram нужен публичный HTTPS URL. Для разработки удобно использовать ngrok, Cloudflare Tunnel или деплой на сервер.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск backend и Mini App

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Открой в браузере:

```text
http://127.0.0.1:8000
```

## Запуск бота

Во втором терминале:

```bash
python -m app.bot
```

## Деплой на Render

Для постоянной HTTPS-ссылки без локального туннеля проект подготовлен под Render.

1. Создай новый GitHub-репозиторий.
2. Загрузи туда содержимое этой папки, кроме `.env`.
3. В Render выбери **New +** -> **Blueprint** и подключи репозиторий.
4. После создания сервиса зайди в **Environment** и заполни:

```env
TELEGRAM_BOT_TOKEN=токен от BotFather
WEB_APP_URL=https://имя-сервиса.onrender.com
```

5. Нажми **Manual Deploy** -> **Deploy latest commit**.

На Render бот работает через Telegram webhook в том же FastAPI-приложении. Отдельно запускать `python -m app.bot` на хостинге не нужно.

Команды бота:

- `/start` - открыть каталог услуг;
- `/orders` - последние заказы, доступно только `ADMIN_TELEGRAM_ID`;
- `/status ORD-... done` - сменить статус заказа.

Доступные статусы:

- `new`
- `in_progress`
- `done`
- `cancelled`

## Админ API

Последние заказы:

```bash
curl -H "X-Admin-Secret: change-this-secret" http://127.0.0.1:8000/api/admin/orders
```

Смена статуса:

```bash
curl -X PATCH ^
  -H "X-Admin-Secret: change-this-secret" ^
  -H "Content-Type: application/json" ^
  -d "{\"status\":\"in_progress\"}" ^
  http://127.0.0.1:8000/api/admin/orders/ORD-20260617-ABCD1234
```

## Что подключать дальше

1. Реальную оплату: YooKassa, CloudPayments, Robokassa или Telegram Stars.
2. Админ-панель со списком заказов и фильтрами.
3. Загрузку файлов от клиента.
4. Уведомления клиенту при смене статуса.
