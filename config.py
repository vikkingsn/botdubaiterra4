import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE_NUMBER = os.getenv('PHONE_NUMBER', '')
MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID', '0'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///bot.db')
MIN_DELAY_SECONDS = 300
MAX_DELAY_SECONDS = 660
LOG_FILE = 'bot.log'
LOG_LEVEL = 'INFO'
