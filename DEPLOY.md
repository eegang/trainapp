# Деплой бота

Боту нужен постоянный процесс и доступ к `api.telegram.org`
(с российских серверов API сейчас блокируется — учитывай это при выборе).

## Вариант 1 (простой): Bothost — специализированный хостинг ботов

Регистрация: https://bothost.ru. Тариф Start — бесплатно (1 бот, 256 МБ RAM,
но со «спящим режимом»), Active — 99 ₽/мес (24/7, без сна, оплата картой РФ).

### Создание бота в панели

1. **Git URL репозитория:** `https://github.com/eegang/trainapp.git` (с `.git`!)
2. **Ветка:** `master` (не `main`!)
3. **Главный файл:** `main.py` (обычно определяется автоматически)
4. **Галочку «Использовать собственный Dockerfile» НЕ включать** —
   авто-сборки для aiogram+bотa из requirements.txt достаточно.
5. **Переменные окружения** (в панели, аналог .env):

   ```
   BOT_TOKEN=123:твой-токен-от-BotFather
   ALLOWED_USER_IDS=123456789
   DB_PATH=/app/data/training_bot.db
   ```

   `DB_PATH` обязателен: `/app/data` — единственная папка, которая на Bothost
   сохраняется между деплоями и рестартами. В код/Git база не попадает.

### Перенос существующей базы (чтобы не потерять историю)

1. Задеплоить бота и остановить его в панели.
2. Через **файловый менеджер** в панели залить локальный `training_bot.db`
   в папку `data/` (именно так: `training_bot.db`).
3. Запустить бота.

### Замечания

- На бесплатном тарифе сон: сообщения копятся в Telegram (до 24 ч) и
  обрабатываются после пробуждения; таймеры рабочего времени во время сна
  не идут. Для постоянного бота лучше Active (99 ₽/мес).
- Логи видны в панели в реальном времени.

## Вариант 2: свой VPS + Docker (если Bothost разонравится)

VPS в Нидерландах/Германии у провайдера с оплатой картами РФ
(is*hosting, Aeza, ~300–400 ₽/мес), ОС Ubuntu 24.04.

### Установка

```bash
ssh root@ВАШ_IP
curl -fsSL https://get.docker.com | sh
git clone https://github.com/eegang/trainapp.git
cd trainapp
cp .env.example .env
nano .env        # вписать BOT_TOKEN и ALLOWED_USER_IDS
docker compose up -d --build
docker compose logs -f bot   # Ctrl+C — выйти, бот останется работать
```

### Перенос базы в volume

```bash
scp training_bot.db root@ВАШ_IP:~/trainapp/transfer.db
docker compose stop bot
docker run --rm -v trainapp_bot-data:/app/data -v ~/trainapp:/src alpine \
  cp /src/transfer.db /app/data/training_bot.db
docker compose up -d bot
```

### Обновление кода

```bash
ssh root@ВАШ_IP "cd ~/trainapp && git pull && docker compose up -d --build"
```

### Полезное

- Логи: `docker compose logs -f bot`
- Перезапуск: `docker compose restart bot`
- Остановить: `docker compose down` (данные в volume останутся)
- Бэкап базы: `docker run --rm -v trainapp_bot-data:/app/data alpine tar czf - /app/data > backup.tgz`
