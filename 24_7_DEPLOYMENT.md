# 🚀 Размещение бота для работы 24/7

## Проблема

Бот работает только когда включен ваш компьютер. Чтобы он работал постоянно, нужно разместить его на сервере.

---

## ✅ Варианты решения

### 1. 🆓 Бесплатные облачные платформы (рекомендуется для начала)

#### Railway.app (самый простой)
- ✅ Бесплатный тариф: $5 кредитов/месяц (обычно хватает)
- ✅ Автоматическое развертывание с GitHub
- ✅ Простая настройка
- ✅ Автоматический перезапуск при сбоях

#### Render.com
- ✅ Бесплатный тариф (с ограничениями)
- ✅ Автоматическое развертывание
- ⚠️ Может "засыпать" после 15 минут бездействия (на бесплатном тарифе)

#### Heroku
- ⚠️ Больше нет бесплатного тарифа
- 💰 От $7/месяц

---

### 2. 💰 VPS сервер (лучший вариант для постоянной работы)

#### Популярные провайдеры:
- **DigitalOcean** - от $4/месяц
- **Linode** - от $5/месяц  
- **Vultr** - от $2.50/месяц
- **Hetzner** - от €4/месяц (лучшее соотношение цена/качество)

#### Преимущества:
- ✅ Полный контроль
- ✅ Работает 24/7 без ограничений
- ✅ Можно разместить несколько ботов
- ✅ Больше ресурсов

---

### 3. 🏠 Домашний сервер (если есть старый компьютер)

- ✅ Бесплатно
- ⚠️ Нужен стабильный интернет
- ⚠️ Нужно настроить роутер
- ⚠️ Электричество 24/7

---

## 🚀 Быстрое решение: Railway.app

### Шаг 1: Подготовка проекта

Убедитесь, что проект на GitHub:

```bash
cd /Users/aspbr/Documents/botdubaiterra4

# Проверьте статус
git status

# Если есть изменения, закоммитьте и отправьте
git add .
git commit -m "Готово к развертыванию на Railway"
git push
```

### Шаг 2: Создайте аккаунт на Railway

1. Зайдите на [railway.app](https://railway.app)
2. Нажмите "Start a New Project"
3. Войдите через GitHub
4. Выберите "Deploy from GitHub repo"
5. Выберите ваш репозиторий `botdubaiterra4`

### Шаг 3: Настройте переменные окружения

В настройках проекта Railway:

1. Перейдите в **Variables**
2. Добавьте переменные:
   - `BOT_TOKEN` = `8558311268:AAFmtj9ZTr56ZziEGgsS5wY6tG9sinHkoXE`
   - `MAIN_ADMIN_ID` = `120661515`
   - `DATABASE_URL` = `sqlite+aiosqlite:///bot.db`

### Шаг 4: Настройте команду запуска

В настройках проекта:

1. Перейдите в **Settings** → **Deploy**
2. В поле **Start Command** укажите:
   ```
   python3 main.py
   ```

### Шаг 5: Деплой

Railway автоматически:
- ✅ Установит зависимости из `requirements.txt`
- ✅ Запустит бота
- ✅ Будет автоматически перезапускать при сбоях

---

## 🖥️ Решение: VPS сервер (DigitalOcean)

### Шаг 1: Создайте VPS

1. Зарегистрируйтесь на [digitalocean.com](https://www.digitalocean.com)
2. Создайте Droplet:
   - **OS**: Ubuntu 22.04
   - **Plan**: Basic $4/месяц (самый дешевый)
   - **Region**: Выберите ближайший
3. Дождитесь создания (1-2 минуты)

### Шаг 2: Подключитесь к серверу

```bash
# Получите IP адрес сервера из панели DigitalOcean
ssh root@YOUR_SERVER_IP
```

### Шаг 3: Установите зависимости

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Python и pip
apt install -y python3 python3-pip python3-venv git

# Создание пользователя для бота (опционально, но рекомендуется)
adduser botuser
usermod -aG sudo botuser
su - botuser
```

### Шаг 4: Клонируйте проект

```bash
# Перейдите в домашнюю директорию
cd ~

# Клонируйте проект с GitHub
git clone https://github.com/YOUR_USERNAME/botdubaiterra4.git
cd botdubaiterra4

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### Шаг 5: Создайте .env файл

```bash
nano .env
```

Добавьте:
```env
BOT_TOKEN=8558311268:AAFmtj9ZTr56ZziEGgsS5wY6tG9sinHkoXE
MAIN_ADMIN_ID=120661515
DATABASE_URL=sqlite+aiosqlite:///bot.db
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### Шаг 6: Настройте автозапуск через systemd

Создайте файл сервиса:

```bash
sudo nano /etc/systemd/system/mailing-bot.service
```

Добавьте содержимое:

```ini
[Unit]
Description=Telegram Mailing Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/botdubaiterra4
Environment="PATH=/home/botuser/botdubaiterra4/venv/bin"
ExecStart=/home/botuser/botdubaiterra4/venv/bin/python3 /home/botuser/botdubaiterra4/main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/mailing-bot.log
StandardError=append:/var/log/mailing-bot-error.log

[Install]
WantedBy=multi-user.target
```

**Важно**: Замените `botuser` на ваше имя пользователя, если создали другого.

### Шаг 7: Запустите сервис

```bash
# Перезагрузите systemd
sudo systemctl daemon-reload

# Включите автозапуск
sudo systemctl enable mailing-bot

# Запустите бота
sudo systemctl start mailing-bot

# Проверьте статус
sudo systemctl status mailing-bot

# Посмотрите логи
sudo journalctl -u mailing-bot -f
```

### Шаг 8: Управление ботом

```bash
# Остановить
sudo systemctl stop mailing-bot

# Запустить
sudo systemctl start mailing-bot

# Перезапустить
sudo systemctl restart mailing-bot

# Посмотреть статус
sudo systemctl status mailing-bot

# Посмотреть логи
sudo journalctl -u mailing-bot -n 50
```

---

## 🔄 Обновление бота на сервере

### Если используете Railway:
- Просто сделайте `git push` - Railway автоматически обновит

### Если используете VPS:

```bash
# Подключитесь к серверу
ssh user@server_ip

# Перейдите в директорию проекта
cd ~/botdubaiterra4

# Получите обновления
git pull

# Перезапустите бота
sudo systemctl restart mailing-bot
```

---

## 📊 Мониторинг

### Проверка работы бота:

```bash
# На VPS
sudo systemctl status mailing-bot

# Логи
sudo journalctl -u mailing-bot -f

# В Telegram
# Отправьте /start боту - должен ответить
```

---

## 🛡️ Безопасность

### На VPS сервере:

1. **Настройте firewall:**
```bash
sudo ufw allow 22/tcp
sudo ufw enable
```

2. **Используйте SSH ключи вместо паролей**

3. **Регулярно обновляйте систему:**
```bash
sudo apt update && sudo apt upgrade -y
```

4. **Не храните токены в коде** - только в .env

---

## 💡 Рекомендации

### Для начала:
- 🆓 **Railway.app** - самый простой вариант, бесплатно

### Для постоянной работы:
- 💰 **VPS (DigitalOcean/Hetzner)** - полный контроль, от $4/месяц

### Для нескольких ботов:
- 💰 **VPS** - можно разместить все на одном сервере

---

## ✅ Чеклист развертывания

- [ ] Проект загружен на GitHub
- [ ] Создан аккаунт на платформе (Railway/VPS)
- [ ] Настроены переменные окружения (BOT_TOKEN, MAIN_ADMIN_ID)
- [ ] Бот запущен и работает
- [ ] Проверена работа в Telegram
- [ ] Настроен автозапуск (для VPS)
- [ ] Настроен мониторинг

---

## 🆘 Решение проблем

### Бот не отвечает:
1. Проверьте логи на сервере
2. Проверьте, что бот запущен
3. Проверьте токен в переменных окружения

### Ошибки при запуске:
1. Проверьте логи: `sudo journalctl -u mailing-bot -n 100`
2. Убедитесь, что все зависимости установлены
3. Проверьте права доступа к файлам

---

## 📚 Полезные ссылки

- [Railway.app](https://railway.app)
- [DigitalOcean](https://www.digitalocean.com)
- [Hetzner](https://www.hetzner.com)
- [Vultr](https://www.vultr.com)

---

**Готово!** Теперь ваш бот будет работать 24/7! 🎉

