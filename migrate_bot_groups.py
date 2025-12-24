"""
Миграция для добавления таблицы bot_groups
"""
import asyncio
import aiosqlite
from config import DATABASE_URL
from utils.logger import logger


async def migrate_database():
    """Добавить таблицу bot_groups"""
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    logger.info(f"Начинаем миграцию базы данных: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        # Проверяем, существует ли таблица
        cursor = await db.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='bot_groups'
        """)
        table_exists = await cursor.fetchone()
        
        if not table_exists:
            # Создаем таблицу bot_groups
            await db.execute("""
                CREATE TABLE bot_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE NOT NULL,
                    title VARCHAR(255),
                    username VARCHAR(255),
                    chat_type VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    members_count INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем индекс для chat_id
            await db.execute("""
                CREATE INDEX idx_bot_groups_chat_id ON bot_groups(chat_id)
            """)
            
            await db.commit()
            logger.info("✅ Таблица bot_groups создана")
        else:
            logger.info("✅ Таблица bot_groups уже существует, миграция не требуется")
        
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

