import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, MAIN_ADMIN_ID
from database import init_db, close_db
from handlers import router
from utils import logger

async def on_startup(bot: Bot):
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.warning(f"⚠️ Найден webhook: {webhook_info.url}. Удаляю...")
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook удален, используется polling")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при проверке webhook: {e}")
    
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")
    
    try:
        from services import get_user_client
        from config import API_ID, API_HASH, PHONE_NUMBER
        
        if API_ID and API_HASH and PHONE_NUMBER:
            logger.info("🔐 Общий Client API настроен в .env")
            logger.info("Пользователи без персональной настройки будут использовать общий Client API")
            logger.info("Для отправки от своего имени пользователи могут использовать /setup_my_client")
        else:
            logger.warning("⚠️ API_ID, API_HASH или PHONE_NUMBER не установлены в .env")
            logger.warning("Пользователи должны настроить свой Client API через /setup_my_client")
    except Exception as e:
        logger.error(f"Ошибка при проверке Client API: {e}")
    
    logger.info(f"Бот запущен. Администратор: {MAIN_ADMIN_ID}")

async def on_shutdown():
    logger.info("Закрытие соединений...")
    await close_db()
    
    try:
        from services import close_client
        await close_client()
    except Exception as e:
        logger.warning(f"Ошибка при закрытии Telegram Client: {e}")
    
    logger.info("Бот остановлен")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Проверьте файл .env")
        sys.exit(1)
    
    if not MAIN_ADMIN_ID:
        logger.error("MAIN_ADMIN_ID не установлен! Проверьте файл .env")
        sys.exit(1)
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.include_router(router)
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.warning(f"⚠️ Найден webhook: {webhook_info.url}. Удаляю...")
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook удален, используется polling")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при проверке webhook: {e}")
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        logger.info("Запуск бота...")
        
        try:
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                logger.warning(f"⚠️ Найден webhook: {webhook_info.url}. Удаляю...")
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("✅ Webhook удален, используется polling")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при проверке webhook: {e}")
        
        allowed_updates = list(set(list(dp.resolve_used_update_types()) + ["my_chat_member", "chat_member"]))
        logger.info(f"Разрешенные типы обновлений: {allowed_updates}")
        
        await dp.start_polling(bot, allowed_updates=allowed_updates, close_loop=False)
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
