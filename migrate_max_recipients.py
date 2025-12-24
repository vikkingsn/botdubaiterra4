"""
Миграция для добавления поля max_recipients в таблицу mailing_campaigns
"""
import asyncio
import aiosqlite
from config import DATABASE_URL
from utils.logger import logger


async def migrate_database():
    """Добавить поле max_recipients в таблицу mailing_campaigns"""
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    logger.info(f"Начинаем миграцию базы данных: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        # Проверяем, существует ли колонка
        cursor = await db.execute("PRAGMA table_info(mailing_campaigns)")
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        
        if "max_recipients" not in existing_columns:
            # Добавляем колонку max_recipients
            await db.execute("ALTER TABLE mailing_campaigns ADD COLUMN max_recipients INTEGER")
            await db.commit()
            logger.info("✅ Добавлена колонка max_recipients")
        else:
            logger.info("✅ Колонка max_recipients уже существует, миграция не требуется")
        
        logger.info("✅ Миграция базы данных завершена успешно!")


async def main():
    """Главная функция"""
    try:
        await migrate_database()
    except Exception as e:
        logger.error(f"Ошибка при миграции: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())

