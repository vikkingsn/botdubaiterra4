"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token (для управления ботом)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telegram Client API (для отправки сообщений от имени пользователя)
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")  # Номер телефона в формате +79991234567

# Главный администратор (фиксированный Telegram ID)
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", "0"))

# Настройки базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")

# Настройки рассылок
MIN_DELAY_SECONDS = 300  # 5 минут
MAX_DELAY_SECONDS = 660  # 11 минут

# Настройки логирования
LOG_FILE = "bot.log"
LOG_LEVEL = "INFO"
