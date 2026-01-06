import asyncio
import aiosqlite
from sqlalchemy import text
from config import DATABASE_URL
from database import async_session_maker
from utils import logger

def get_db_path():
    return DATABASE_URL.replace('sqlite+aiosqlite:///', '')

async def migrate_users_table():
    db_path = get_db_path()
    logger.info(f'[Миграция 1] Начинаем миграцию таблицы users: {db_path}')
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute('PRAGMA table_info(users)')
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        logger.info(f'Существующие колонки в users: {existing_columns}')
        migrations = []
        if 'api_id' not in existing_columns:
            migrations.append('ALTER TABLE users ADD COLUMN api_id INTEGER')
            logger.info('Добавляем колонку api_id')
        if 'api_hash' not in existing_columns:
            migrations.append('ALTER TABLE users ADD COLUMN api_hash VARCHAR(255)')
            logger.info('Добавляем колонку api_hash')
        if 'phone_number' not in existing_columns:
            migrations.append('ALTER TABLE users ADD COLUMN phone_number VARCHAR(50)')
            logger.info('Добавляем колонку phone_number')
        if 'has_client_auth' not in existing_columns:
            migrations.append('ALTER TABLE users ADD COLUMN has_client_auth BOOLEAN DEFAULT 0')
            logger.info('Добавляем колонку has_client_auth')
        if not migrations:
            logger.info('✅ [Миграция 1] Все колонки уже существуют, миграция не требуется')
            return True
        for migration in migrations:
            try:
                await db.execute(migration)
                logger.info(f'✅ Выполнено: {migration}')
            except Exception as e:
                logger.error(f'❌ Ошибка при выполнении {migration}: {e}')
                raise
        await db.commit()
        logger.info('✅ [Миграция 1] Миграция таблицы users завершена успешно!')
        return True

async def migrate_delay_seconds():
    db_path = get_db_path()
    logger.info(f'[Миграция 2] Начинаем миграцию delay_seconds: {db_path}')
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute('PRAGMA table_info(mailing_campaigns)')
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        if 'delay_seconds' not in existing_columns:
            try:
                await db.execute('ALTER TABLE mailing_campaigns ADD COLUMN delay_seconds INTEGER DEFAULT 5')
                logger.info('✅ Добавлена колонка delay_seconds')
                await db.commit()
                await db.execute('UPDATE mailing_campaigns SET delay_seconds = 5 WHERE delay_seconds IS NULL')
                await db.commit()
                logger.info('✅ Обновлены существующие записи значением по умолчанию (5 секунд)')
            except Exception as e:
                logger.error(f'❌ Ошибка при добавлении колонки delay_seconds: {e}')
                raise
        else:
            logger.info('✅ [Миграция 2] Колонка delay_seconds уже существует, миграция не требуется')
        logger.info('✅ [Миграция 2] Миграция delay_seconds завершена успешно!')
        return True

async def migrate_max_recipients():
    db_path = get_db_path()
    logger.info(f'[Миграция 3] Начинаем миграцию max_recipients: {db_path}')
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute('PRAGMA table_info(mailing_campaigns)')
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        if 'max_recipients' not in existing_columns:
            await db.execute('ALTER TABLE mailing_campaigns ADD COLUMN max_recipients INTEGER')
            await db.commit()
            logger.info('✅ Добавлена колонка max_recipients')
        else:
            logger.info('✅ [Миграция 3] Колонка max_recipients уже существует, миграция не требуется')
        logger.info('✅ [Миграция 3] Миграция max_recipients завершена успешно!')
        return True

async def migrate_report_lists():
    db_path = get_db_path()
    logger.info(f'[Миграция 4] Начинаем миграцию report_lists: {db_path}')
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='report_receiver_lists'")
        table_exists = await cursor.fetchone()
        if not table_exists:
            await db.execute('\n                CREATE TABLE report_receiver_lists (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    name VARCHAR(255) NOT NULL,\n                    is_active BOOLEAN DEFAULT 1,\n                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n                )\n            ')
            logger.info('✅ Создана таблица report_receiver_lists')
            await db.execute("\n                INSERT INTO report_receiver_lists (name, is_active)\n                VALUES ('Основной список', 1)\n            ")
            await db.commit()
            logger.info("✅ Создан дефолтный список 'Основной список'")
        cursor = await db.execute('PRAGMA table_info(report_receivers)')
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        if 'list_id' not in existing_columns:
            cursor = await db.execute("SELECT id FROM report_receiver_lists WHERE name = 'Основной список' LIMIT 1")
            default_list = await cursor.fetchone()
            default_list_id = default_list[0] if default_list else 1
            await db.execute('ALTER TABLE report_receivers ADD COLUMN list_id INTEGER')
            logger.info('✅ Добавлена колонка list_id в report_receivers')
            await db.execute(f'UPDATE report_receivers SET list_id = {default_list_id} WHERE list_id IS NULL')
            logger.info(f'✅ Обновлены существующие получатели (привязаны к списку ID {default_list_id})')
            await db.execute('\n                CREATE TABLE report_receivers_new (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    list_id INTEGER NOT NULL,\n                    identifier VARCHAR(255) NOT NULL,\n                    identifier_type VARCHAR(20) NOT NULL,\n                    telegram_id INTEGER,\n                    is_active BOOLEAN DEFAULT 1,\n                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                    FOREIGN KEY (list_id) REFERENCES report_receiver_lists(id)\n                )\n            ')
            await db.execute('\n                INSERT INTO report_receivers_new \n                (id, list_id, identifier, identifier_type, telegram_id, is_active, created_at)\n                SELECT id, list_id, identifier, identifier_type, telegram_id, is_active, created_at\n                FROM report_receivers\n            ')
            await db.execute('DROP TABLE report_receivers')
            await db.execute('ALTER TABLE report_receivers_new RENAME TO report_receivers')
            logger.info('✅ Таблица report_receivers обновлена с обязательным list_id')
        await db.commit()
        logger.info('✅ [Миграция 4] Миграция report_lists завершена успешно!')
        return True

async def migrate_bot_groups():
    db_path = get_db_path()
    logger.info(f'[Миграция 5] Начинаем миграцию bot_groups: {db_path}')
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("\n            SELECT name FROM sqlite_master \n            WHERE type='table' AND name='bot_groups'\n        ")
        table_exists = await cursor.fetchone()
        if not table_exists:
            await db.execute('\n                CREATE TABLE bot_groups (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    chat_id INTEGER UNIQUE NOT NULL,\n                    title VARCHAR(255),\n                    username VARCHAR(255),\n                    chat_type VARCHAR(50) NOT NULL,\n                    is_active BOOLEAN DEFAULT 1,\n                    members_count INTEGER,\n                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n                )\n            ')
            await db.execute('\n                CREATE INDEX idx_bot_groups_chat_id ON bot_groups(chat_id)\n            ')
            await db.commit()
            logger.info('✅ Таблица bot_groups создана')
        else:
            logger.info('✅ [Миграция 5] Таблица bot_groups уже существует, миграция не требуется')
        logger.info('✅ [Миграция 5] Миграция bot_groups завершена успешно!')
        return True

async def migrate_template_media():
    logger.info('[Миграция 6] Начинаем миграцию template_media')
    try:
        async with async_session_maker() as session:
            result = await session.execute(text('PRAGMA table_info(templates)'))
            columns = [row[1] for row in result.fetchall()]
            if 'media_type' not in columns:
                logger.info('Добавляем колонку media_type...')
                await session.execute(text('ALTER TABLE templates ADD COLUMN media_type VARCHAR(50)'))
                logger.info('✅ Колонка media_type добавлена')
            else:
                logger.info('Колонка media_type уже существует')
            if 'media_file_id' not in columns:
                logger.info('Добавляем колонку media_file_id...')
                await session.execute(text('ALTER TABLE templates ADD COLUMN media_file_id VARCHAR(255)'))
                logger.info('✅ Колонка media_file_id добавлена')
            else:
                logger.info('Колонка media_file_id уже существует')
            if 'media_file_unique_id' not in columns:
                logger.info('Добавляем колонку media_file_unique_id...')
                await session.execute(text('ALTER TABLE templates ADD COLUMN media_file_unique_id VARCHAR(255)'))
                logger.info('✅ Колонка media_file_unique_id добавлена')
            else:
                logger.info('Колонка media_file_unique_id уже существует')
            await session.commit()
            logger.info('✅ [Миграция 6] Миграция template_media завершена успешно')
            return True
    except Exception as e:
        logger.error(f'❌ Ошибка при миграции template_media: {e}', exc_info=True)
        return False

async def run_all_migrations():
    logger.info('=' * 60)
    logger.info('🚀 Начинаем выполнение всех миграций базы данных')
    logger.info('=' * 60)
    migrations = [('Users Table', migrate_users_table), ('Delay Seconds', migrate_delay_seconds), ('Max Recipients', migrate_max_recipients), ('Report Lists', migrate_report_lists), ('Bot Groups', migrate_bot_groups), ('Template Media', migrate_template_media)]
    results = []
    for name, migration_func in migrations:
        try:
            logger.info(f'\n📋 Выполняем миграцию: {name}')
            result = await migration_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f'❌ Ошибка при выполнении миграции {name}: {e}', exc_info=True)
            results.append((name, False))
    logger.info('\n' + '=' * 60)
    logger.info('📊 Результаты миграций:')
    logger.info('=' * 60)
    for name, result in results:
        status = '✅ Успешно' if result else '❌ Ошибка'
        logger.info(f'{status}: {name}')
    logger.info('=' * 60)
    all_success = all((result for _, result in results))
    if all_success:
        logger.info('🎉 Все миграции выполнены успешно!')
    else:
        logger.warning('⚠️ Некоторые миграции завершились с ошибками')
    return all_success

async def main():
    try:
        success = await run_all_migrations()
        return 0 if success else 1
    except Exception as e:
        logger.error(f'Критическая ошибка при выполнении миграций: {e}', exc_info=True)
        return 1
if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
