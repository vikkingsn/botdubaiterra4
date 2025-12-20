"""
Валидация данных
"""
from typing import Optional
import re


def validate_template_name(name: str) -> tuple[bool, Optional[str]]:
    """Валидация названия шаблона"""
    if not name or not name.strip():
        return False, "Название шаблона не может быть пустым"
    
    if len(name) > 255:
        return False, "Название шаблона слишком длинное (максимум 255 символов)"
    
    return True, None


def validate_template_text(text: str) -> tuple[bool, Optional[str]]:
    """Валидация текста шаблона"""
    if not text or not text.strip():
        return False, "Текст шаблона не может быть пустым"
    
    if len(text) > 4096:
        return False, "Текст шаблона слишком длинный (максимум 4096 символов)"
    
    # Проверка на валидный Markdown (базовая)
    # Можно расширить при необходимости
    
    return True, None


def validate_telegram_id(user_id: str) -> tuple[bool, Optional[int]]:
    """Валидация Telegram ID"""
    try:
        telegram_id = int(user_id)
        if telegram_id <= 0:
            return False, None
        return True, telegram_id
    except ValueError:
        return False, None


def validate_username(username: str) -> tuple[bool, Optional[str]]:
    """Валидация username"""
    if not username:
        return False, None
    
    # Удаляем @ если есть
    username = username.lstrip("@")
    
    # Telegram username: 5-32 символа, буквы, цифры, подчеркивания
    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
        return False, None
    
    return True, username
