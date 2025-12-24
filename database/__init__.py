"""
Пакет для работы с базой данных
"""
from database.models import init_db, close_db

__all__ = ['init_db', 'close_db']
