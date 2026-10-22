# Деплой бота на VPS

Боту нужен постоянный процесс и доступ к `api.telegram.org`.
Российские VPS не подходят (ТСПУ блокирует Telegram API), поэтому берём
недорогой сервер в Нидерландах/Германии у провайдера с оплатой картами РФ.

## 1. Аренда сервера

- Подойдут: is*hosting (NL/ES, карты МИР/СБП/ЮMoney), Aeza (EU), аналоги.
- Тариф: минимальный (1 vCPU / 512–1024 МБ RAM / ~20 ГБ SSD), ~300–400 ₽/мес.
- ОС при заказе: **Ubuntu 24.04 LTS**.
- После заказа на почту придут: IP, login (обычно `root`), пароль.

## 2. Вход на сервер

Windows (PowerShell):

```powershell
ssh root@ВАШ_IP
# при первом входе — yes, затем пароль
```

## 3. Установка Docker + запуск

На сервере по одному:

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/eegang/trainapp.git
cd trainapp
cp .env.example .env
nano .env        # вписать BOT_TOKEN и ALLOWED_USER_IDS
docker compose up -d --build
docker compose logs -f bot   # убедиться, что бот zapустился
```

`Ctrl+C` — выйти из логов, бот продолжит работать (restart: unless-stopped
переживает даже перезагрузку сервера).

## 4. Перенос существующей базы (сохранить историю тренировок)

Локальная `training_bot.db` кладётся в volume контейнера:

```bash
# на сервере, пока бот остановлен:
docker compose stop bot
docker run --rm -v trainapp_bot-data:/data -v ~/trainapp:/src alpine \
  cp /src/transfer.db /data/training_bot.db
# ~/trainapp/transfer.db — ваша локальная training_bot.db,
# загруженная заранее, например:
#   scp training_bot.db root@ВАШ_IP:~/trainapp/transfer.db
docker compose up -d bot
```

## 5. Обновление кода

С локальной машины (после `git push` на GitHub):

```bash
ssh root@ВАШ_IP "cd ~/trainapp && git pull && docker compose up -d --build"
```

## 6. Полезное

- Логи: `docker compose logs -f bot`
- Перезапуск: `docker compose restart bot`
- Остановить: `docker compose down` (данные в volume останутся)
- Бэкап базы: `docker run --rm -v trainapp_bot-data:/data alpine tar czf - /data > backup.tgz`
