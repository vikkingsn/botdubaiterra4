# Настройка проекта после клонирования с GitHub

Если вы клонировали проект с GitHub, выполните эти шаги для настройки:

## 🚀 Быстрая настройка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME

# 2. Установите зависимости
pip install -r requirements.txt

# 3. Создайте .env файл
cp .env.example .env

# 4. Отредактируйте .env и добавьте ваши данные
nano .env  # или используйте любой редактор

# 5. Запустите бота
python3 main.py
```

---

## 📝 Подробная инструкция

### Шаг 1: Клонирование

```bash
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME
```

### Шаг 2: Установка зависимостей

```bash
# Создайте виртуальное окружение (рекомендуется)
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt
```

### Шаг 3: Создание .env файла

Файл `.env` **НЕ** хранится в репозитории по соображениям безопасности.

```bash
# Скопируйте пример
cp .env.example .env

# Или создайте вручную
touch .env
```

Отредактируйте `.env` и добавьте:

```env
BOT_TOKEN=ваш_токен_от_BotFather
MAIN_ADMIN_ID=ваш_telegram_id
DATABASE_URL=sqlite+aiosqlite:///bot.db
```

### Шаг 4: Получение токена бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в `.env`

### Шаг 5: Получение Telegram ID

1. Откройте [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте `/start`
3. Скопируйте ваш ID в `.env`

### Шаг 6: Запуск

```bash
python3 main.py
```

---

## ✅ Проверка

После запуска проверьте:

1. **Логи**: Должно быть "Бот запущен..."
2. **Telegram**: Отправьте `/start` боту, должно прийти приветствие
3. **База данных**: Должен создаться файл `bot.db`

---

## 🔄 Обновление проекта

Если проект на GitHub обновился:

```bash
# Получите последние изменения
git pull

# Обновите зависимости (если requirements.txt изменился)
pip install --upgrade -r requirements.txt

# Перезапустите бота
python3 main.py
```

---

## 🐛 Проблемы?

### "ModuleNotFoundError"
→ Выполните: `pip install -r requirements.txt`

### "BOT_TOKEN не установлен"
→ Проверьте файл `.env`, убедитесь что он существует и заполнен

### "Permission denied"
→ Используйте: `python3 main.py` вместо `python main.py`

---

## 📚 Дополнительная документация

- [START_HERE.md](START_HERE.md) - Быстрый старт
- [DEPLOYMENT.md](DEPLOYMENT.md) - Развертывание
- [GITHUB_SETUP.md](GITHUB_SETUP.md) - Размещение на GitHub
