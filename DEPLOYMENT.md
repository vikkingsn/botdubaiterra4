# Инструкция по развертыванию и запуску бота

## Требования к системе

### Минимальные требования:
- **Python 3.10 или выше**
- **Интернет-соединение** (для работы с Telegram API)
- **~100 МБ свободного места** на диске

### Проверка версии Python:
```bash
python3 --version
# Должно быть: Python 3.10.x или выше
```

Если Python не установлен:
- **macOS**: `brew install python3`
- **Linux (Ubuntu/Debian)**: `sudo apt-get install python3 python3-pip`
- **Windows**: Скачайте с [python.org](https://www.python.org/downloads/)

---

## Шаг 1: Подготовка проекта

### 1.1. Перейдите в директорию проекта:
```bash
cd /Users/aspbr/Documents/курсор
```

### 1.2. (Опционально) Создайте виртуальное окружение:
```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация (macOS/Linux):
source venv/bin/activate

# Активация (Windows):
venv\Scripts\activate
```

---

## Шаг 2: Установка зависимостей

```bash
pip install -r requirements.txt
```

Если возникают проблемы, попробуйте:
```bash
pip3 install -r requirements.txt
```

Или с обновлением pip:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Шаг 3: Получение токена бота

### 3.1. Создайте бота через BotFather:

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям:
   - Введите имя бота (например: "Мой бот рассылок")
   - Введите username бота (должен заканчиваться на `bot`, например: `my_mailing_bot`)
4. **Скопируйте токен**, который выдаст BotFather (выглядит как: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 3.2. (Опционально) Настройте бота:
- `/setdescription` - описание бота
- `/setabouttext` - информация о боте
- `/setuserpic` - аватар бота

---

## Шаг 4: Получение вашего Telegram ID

### Вариант 1: Через бота @userinfobot
1. Найдите [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте `/start`
3. Скопируйте ваш **ID** (число, например: `123456789`)

### Вариант 2: Через бота @getidsbot
1. Найдите [@getidsbot](https://t.me/getidsbot)
2. Отправьте любое сообщение
3. Скопируйте ваш **ID**

### Вариант 3: Через веб-версию Telegram
1. Откройте [web.telegram.org](https://web.telegram.org)
2. В адресной строке будет ваш ID после `#`

---

## Шаг 5: Создание файла .env

Создайте файл `.env` в корне проекта:

```bash
# В директории проекта
touch .env
```

Или создайте файл вручную с содержимым:

```env
BOT_TOKEN=ваш_токен_от_BotFather
MAIN_ADMIN_ID=ваш_telegram_id
DATABASE_URL=sqlite+aiosqlite:///bot.db
```

**Пример:**
```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
MAIN_ADMIN_ID=987654321
DATABASE_URL=sqlite+aiosqlite:///bot.db
```

⚠️ **ВАЖНО**: Не публикуйте файл `.env` в открытых репозиториях! Он уже добавлен в `.gitignore`.

---

## Шаг 6: Запуск бота

### 6.1. Запуск в обычном режиме:
```bash
python3 main.py
```

### 6.2. Запуск в фоновом режиме (Linux/macOS):
```bash
nohup python3 main.py > bot.log 2>&1 &
```

### 6.3. Запуск с помощью screen (рекомендуется):
```bash
# Установка screen (если нет)
# macOS: brew install screen
# Linux: sudo apt-get install screen

# Создание сессии
screen -S mailing_bot

# Запуск бота
python3 main.py

# Отключение: Ctrl+A, затем D
# Подключение обратно: screen -r mailing_bot
```

### 6.4. Запуск с помощью systemd (Linux, для автозапуска):
Создайте файл `/etc/systemd/system/mailing-bot.service`:

```ini
[Unit]
Description=Telegram Mailing Bot
After=network.target

[Service]
Type=simple
User=ваш_пользователь
WorkingDirectory=/путь/к/проекту
ExecStart=/usr/bin/python3 /путь/к/проекту/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl enable mailing-bot
sudo systemctl start mailing-bot
sudo systemctl status mailing-bot
```

---

## Шаг 7: Проверка работы

### 7.1. Проверьте логи:
```bash
tail -f bot.log
```

### 7.2. Проверьте в Telegram:
1. Найдите вашего бота по username
2. Отправьте `/start`
3. Должно прийти приветственное сообщение

### 7.3. Проверьте базу данных:
```bash
# Если используется SQLite
ls -lh bot.db
```

---

## Размещение на сервере

### Вариант 1: VPS (Virtual Private Server)

**Популярные провайдеры:**
- [DigitalOcean](https://www.digitalocean.com/) - от $4/месяц
- [Linode](https://www.linode.com/) - от $5/месяц
- [Vultr](https://www.vultr.com/) - от $2.50/месяц
- [Hetzner](https://www.hetzner.com/) - от €4/месяц

**Шаги:**
1. Создайте VPS (рекомендуется Ubuntu 22.04)
2. Подключитесь по SSH
3. Установите Python и зависимости
4. Загрузите проект (git clone или scp)
5. Настройте `.env`
6. Запустите через systemd или screen

### Вариант 2: Облачные платформы

#### Heroku:
```bash
# Установите Heroku CLI
heroku create your-bot-name
git push heroku main
heroku config:set BOT_TOKEN=ваш_токен
heroku config:set MAIN_ADMIN_ID=ваш_id
```

#### Railway:
1. Зарегистрируйтесь на [railway.app](https://railway.app)
2. Создайте новый проект
3. Подключите GitHub репозиторий
4. Добавьте переменные окружения в настройках

#### Render:
1. Зарегистрируйтесь на [render.com](https://render.com)
2. Создайте новый Web Service
3. Подключите репозиторий
4. Добавьте переменные окружения

### Вариант 3: Docker (опционально)

Создайте `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Запуск:
```bash
docker build -t mailing-bot .
docker run -d --name mailing-bot --env-file .env mailing-bot
```

---

## Устранение проблем

### Проблема: "BOT_TOKEN не установлен"
**Решение**: Проверьте файл `.env`, убедитесь что он в корне проекта и содержит правильный токен.

### Проблема: "ModuleNotFoundError"
**Решение**: Установите зависимости: `pip install -r requirements.txt`

### Проблема: "Permission denied"
**Решение**: 
```bash
chmod +x main.py
# Или
python3 main.py
```

### Проблема: Бот не отвечает
**Решение**:
1. Проверьте токен в `.env`
2. Проверьте логи: `tail -f bot.log`
3. Убедитесь что бот запущен: `ps aux | grep python`

### Проблема: Ошибки базы данных
**Решение**: Удалите `bot.db` и перезапустите бота (база создастся автоматически).

---

## Мониторинг и обслуживание

### Просмотр логов:
```bash
tail -f bot.log
```

### Проверка статуса процесса:
```bash
ps aux | grep python
```

### Остановка бота:
```bash
# Найти процесс
ps aux | grep main.py

# Остановить
kill <PID>
```

### Автоматический перезапуск при сбоях:
Используйте systemd (см. выше) или supervisor:

```bash
# Установка supervisor
sudo apt-get install supervisor

# Создайте /etc/supervisor/conf.d/mailing-bot.conf
[program:mailing-bot]
command=/usr/bin/python3 /путь/к/проекту/main.py
directory=/путь/к/проекту
autostart=true
autorestart=true
stderr_logfile=/var/log/mailing-bot.err.log
stdout_logfile=/var/log/mailing-bot.out.log
```

---

## Безопасность

1. ✅ **Никогда не публикуйте `.env` файл**
2. ✅ **Используйте сильные пароли для сервера**
3. ✅ **Регулярно обновляйте зависимости**: `pip install --upgrade -r requirements.txt`
4. ✅ **Делайте резервные копии базы данных**: `cp bot.db bot.db.backup`
5. ✅ **Ограничьте доступ к серверу через firewall**

---

## Резервное копирование

### Автоматическое резервное копирование базы данных:
```bash
# Создайте скрипт backup.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp bot.db backups/bot_$DATE.db
find backups/ -name "*.db" -mtime +7 -delete  # Удалить старше 7 дней
```

Добавьте в crontab:
```bash
crontab -e
# Добавьте строку:
0 2 * * * /путь/к/backup.sh
```

---

## Готово! 🎉

Бот должен быть запущен и готов к работе. Проверьте его в Telegram, отправив команду `/start`.
