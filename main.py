"""
Главный файл для запуска бота
"""
import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, MAIN_ADMIN_ID
from database.models import init_db, close_db
from handlers import admin, user, mailing
from utils.logger import logger


async def on_startup():
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")
    
    logger.info(f"Бот запущен. Администратор: {MAIN_ADMIN_ID}")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("Закрытие соединений...")
    await close_db()
    logger.info("Бот остановлен")


async def main():
    """Главная функция"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Проверьте файл .env")
        sys.exit(1)
    
    if not MAIN_ADMIN_ID:
        logger.error("MAIN_ADMIN_ID не установлен! Проверьте файл .env")
        sys.exit(1)
    
    # Создаем бота и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры
    dp.include_router(admin.router)
    dp.include_router(user.router)
    dp.include_router(mailing.router)
    
    # Обработчики запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        logger.info("Запуск бота...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)
