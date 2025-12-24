"""
Скрипт для миграции базы данных - создание таблицы report_receiver_lists и обновление report_receivers
"""
import asyncio
import aiosqlite
from config import DATABASE_URL
from utils.logger import logger


async def migrate_database():
    """Создает таблицу списков получателей и обновляет таблицу получателей"""
    # Извлекаем путь к файлу из DATABASE_URL (sqlite+aiosqlite:///bot.db)
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    
    logger.info(f"Начинаем миграцию базы данных: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        # Проверяем, существует ли таблица report_receiver_lists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='report_receiver_lists'"
        )
        table_exists = await cursor.fetchone()
        
        if not table_exists:
            # Создаем таблицу списков получателей
            await db.execute("""
                CREATE TABLE report_receiver_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Создана таблица report_receiver_lists")
            
            # Создаем дефолтный список для существующих получателей
            await db.execute("""
                INSERT INTO report_receiver_lists (name, is_active)
                VALUES ('Основной список', 1)
            """)
            await db.commit()
            logger.info("✅ Создан дефолтный список 'Основной список'")
        
        # Проверяем, есть ли колонка list_id в report_receivers
        cursor = await db.execute("PRAGMA table_info(report_receivers)")
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        
        if "list_id" not in existing_columns:
            # Получаем ID дефолтного списка
            cursor = await db.execute("SELECT id FROM report_receiver_lists WHERE name = 'Основной список' LIMIT 1")
            default_list = await cursor.fetchone()
            default_list_id = default_list[0] if default_list else 1
            
            # Добавляем колонку list_id
            await db.execute("ALTER TABLE report_receivers ADD COLUMN list_id INTEGER")
            logger.info("✅ Добавлена колонка list_id в report_receivers")
            
            # Обновляем существующие записи
            await db.execute(f"UPDATE report_receivers SET list_id = {default_list_id} WHERE list_id IS NULL")
            logger.info(f"✅ Обновлены существующие получатели (привязаны к списку ID {default_list_id})")
            
            # Делаем list_id обязательным (через создание новой таблицы)
            # Для SQLite нужно пересоздать таблицу
            await db.execute("""
                CREATE TABLE report_receivers_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    identifier VARCHAR(255) NOT NULL,
                    identifier_type VARCHAR(20) NOT NULL,
                    telegram_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (list_id) REFERENCES report_receiver_lists(id)
                )
            """)
            
            # Копируем данные
            await db.execute("""
                INSERT INTO report_receivers_new 
                (id, list_id, identifier, identifier_type, telegram_id, is_active, created_at)
                SELECT id, list_id, identifier, identifier_type, telegram_id, is_active, created_at
                FROM report_receivers
            """)
            
            # Удаляем старую таблицу
            await db.execute("DROP TABLE report_receivers")
            
            # Переименовываем новую таблицу
            await db.execute("ALTER TABLE report_receivers_new RENAME TO report_receivers")
            
            logger.info("✅ Таблица report_receivers обновлена с обязательным list_id")
        
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

