"""
Скрипт для миграции базы данных - добавление колонки delay_seconds в таблицу mailing_campaigns
"""
import asyncio
import aiosqlite
from config import DATABASE_URL
from utils.logger import logger


async def migrate_database():
    """Добавляет колонку delay_seconds в таблицу mailing_campaigns"""
    # Извлекаем путь к файлу из DATABASE_URL (sqlite+aiosqlite:///bot.db)
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    
    logger.info(f"Начинаем миграцию базы данных: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        # Проверяем, какие колонки уже существуют
        cursor = await db.execute("PRAGMA table_info(mailing_campaigns)")
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]  # col[1] - это имя колонки
        
        logger.info(f"Существующие колонки в mailing_campaigns: {existing_columns}")
        
        # Добавляем недостающую колонку
        if "delay_seconds" not in existing_columns:
            try:
                await db.execute("ALTER TABLE mailing_campaigns ADD COLUMN delay_seconds INTEGER DEFAULT 5")
                logger.info("✅ Добавлена колонка delay_seconds")
                await db.commit()
                
                # Обновляем существующие записи значением по умолчанию
                await db.execute("UPDATE mailing_campaigns SET delay_seconds = 5 WHERE delay_seconds IS NULL")
                await db.commit()
                logger.info("✅ Обновлены существующие записи значением по умолчанию (5 секунд)")
            except Exception as e:
                logger.error(f"❌ Ошибка при добавлении колонки delay_seconds: {e}")
                raise
        else:
            logger.info("✅ Колонка delay_seconds уже существует, миграция не требуется")
        
        logger.info("✅ Миграция базы данных завершена успешно!")


async def main():
    """Главная функция"""
    try:
        await migrate_database()
    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {e}", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

