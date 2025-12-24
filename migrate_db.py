"""
Скрипт для миграции базы данных - добавление новых колонок в таблицу users
"""
import asyncio
import aiosqlite
from config import DATABASE_URL
from utils.logger import logger


async def migrate_database():
    """Добавляет новые колонки в таблицу users"""
    # Извлекаем путь к файлу из DATABASE_URL (sqlite+aiosqlite:///bot.db)
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    
    logger.info(f"Начинаем миграцию базы данных: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        # Проверяем, какие колонки уже существуют
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]  # col[1] - это имя колонки
        
        logger.info(f"Существующие колонки в users: {existing_columns}")
        
        # Добавляем недостающие колонки
        migrations = []
        
        if "api_id" not in existing_columns:
            migrations.append("ALTER TABLE users ADD COLUMN api_id INTEGER")
            logger.info("Добавляем колонку api_id")
        
        if "api_hash" not in existing_columns:
            migrations.append("ALTER TABLE users ADD COLUMN api_hash VARCHAR(255)")
            logger.info("Добавляем колонку api_hash")
        
        if "phone_number" not in existing_columns:
            migrations.append("ALTER TABLE users ADD COLUMN phone_number VARCHAR(50)")
            logger.info("Добавляем колонку phone_number")
        
        if "has_client_auth" not in existing_columns:
            migrations.append("ALTER TABLE users ADD COLUMN has_client_auth BOOLEAN DEFAULT 0")
            logger.info("Добавляем колонку has_client_auth")
        
        if not migrations:
            logger.info("✅ Все колонки уже существуют, миграция не требуется")
            return
        
        # Выполняем миграции
        for migration in migrations:
            try:
                await db.execute(migration)
                logger.info(f"✅ Выполнено: {migration}")
            except Exception as e:
                logger.error(f"❌ Ошибка при выполнении {migration}: {e}")
                raise
        
        await db.commit()
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

