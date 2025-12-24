"""
Миграция: Добавление поддержки медиа в шаблонах
"""
import asyncio
import sys
from sqlalchemy import text
from database.models import async_session_maker, engine
from utils.logger import logger


async def migrate():
    """Добавление полей для медиа в таблицу templates"""
    try:
        async with async_session_maker() as session:
            # Проверяем, существуют ли уже колонки
            result = await session.execute(text("PRAGMA table_info(templates)"))
            columns = [row[1] for row in result.fetchall()]
            
            # Добавляем media_type если его нет
            if "media_type" not in columns:
                logger.info("Добавляем колонку media_type...")
                await session.execute(text("ALTER TABLE templates ADD COLUMN media_type VARCHAR(50)"))
                logger.info("✅ Колонка media_type добавлена")
            else:
                logger.info("Колонка media_type уже существует")
            
            # Добавляем media_file_id если его нет
            if "media_file_id" not in columns:
                logger.info("Добавляем колонку media_file_id...")
                await session.execute(text("ALTER TABLE templates ADD COLUMN media_file_id VARCHAR(255)"))
                logger.info("✅ Колонка media_file_id добавлена")
            else:
                logger.info("Колонка media_file_id уже существует")
            
            # Добавляем media_file_unique_id если его нет
            if "media_file_unique_id" not in columns:
                logger.info("Добавляем колонку media_file_unique_id...")
                await session.execute(text("ALTER TABLE templates ADD COLUMN media_file_unique_id VARCHAR(255)"))
                logger.info("✅ Колонка media_file_unique_id добавлена")
            else:
                logger.info("Колонка media_file_unique_id уже существует")
            
            await session.commit()
            logger.info("✅ Миграция завершена успешно")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Ошибка при миграции: {e}", exc_info=True)
        return 1


async def main():
    """Главная функция"""
    logger.info("Начало миграции: добавление поддержки медиа в шаблонах")
    exit_code = await migrate()
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
