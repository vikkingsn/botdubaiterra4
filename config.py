"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

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
