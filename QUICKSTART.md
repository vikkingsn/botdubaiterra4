# Быстрый старт

## 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

## 2. Настройка

Создайте файл `.env`:

```env
BOT_TOKEN=ваш_токен_бота
MAIN_ADMIN_ID=ваш_telegram_id
DATABASE_URL=sqlite+aiosqlite:///bot.db
```

**Как получить токен:**
- Найдите @BotFather в Telegram
- Отправьте `/newbot`
- Следуйте инструкциям

**Как узнать Telegram ID:**
- Найдите @userinfobot в Telegram
- Отправьте `/start`
- Скопируйте ваш ID

## 3. Запуск

```bash
python3 main.py
```

## 4. Первое использование

### Для администратора:

1. Создайте шаблон: `/add_template` или кнопка "📝 Шаблоны"
2. Настройте получателей отчетов: `/set_report_receivers`

### Для пользователей:

1. Запустите рассылку: `/new_mailing` или кнопка "📧 Новая рассылка"
2. Выберите шаблон
3. Введите список получателей
4. Подтвердите запуск

## Формат получателей

```
@user1, 123456789, @user2
https://t.me/user3
```

Поддерживаются: @username, user_id, ссылки t.me/...
