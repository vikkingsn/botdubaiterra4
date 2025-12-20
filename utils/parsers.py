"""
Парсеры для обработки списков получателей
"""
import re
from typing import List, Dict


def normalize_identifier(identifier: str) -> str:
    """
    Нормализует идентификатор получателя
    
    @user1 -> user1
    123456 -> 123456
    https://t.me/user1 -> user1
    t.me/user1 -> user1
    """
    identifier = identifier.strip()
    
    # Удаляем @ в начале
    if identifier.startswith("@"):
        identifier = identifier[1:]
    
    # Обработка ссылок
    if "t.me/" in identifier or "telegram.me/" in identifier:
        # Извлекаем username из ссылки
        match = re.search(r'(?:t\.me/|telegram\.me/)([a-zA-Z0-9_]+)', identifier)
        if match:
            identifier = match.group(1)
    
    # Удаляем все недопустимые символы для username
    identifier = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
    
    return identifier.lower() if identifier else ""


def parse_recipients_list(text: str) -> List[Dict]:
    """
    Парсит список получателей из текста
    
    Поддерживает:
    - @username
    - user_id (числа)
    - Ссылки (https://t.me/user, t.me/user)
    - Разделители: запятая, пробел, новая строка
    """
    # Разделяем по запятым, пробелам и переносам строк
    parts = re.split(r'[,\s\n]+', text)
    
    recipients = []
    seen = set()
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        normalized = normalize_identifier(part)
        
        # Пропускаем пустые или дубликаты
        if not normalized or normalized in seen:
            continue
        
        seen.add(normalized)
        
        # Определяем тип идентификатора
        if part.isdigit():
            identifier_type = "user_id"
        elif part.startswith("@"):
            identifier_type = "username"
        elif "t.me" in part or "telegram.me" in part:
            identifier_type = "link"
        else:
            # Пытаемся определить как username
            identifier_type = "username"
        
        recipients.append({
            "original": part,
            "normalized": normalized,
            "type": identifier_type
        })
    
    return recipients


def validate_recipients_list(recipients: List[Dict]) -> tuple[bool, str]:
    """
    Валидирует список получателей
    
    Возвращает (is_valid, error_message)
    """
    if not recipients:
        return False, "Список получателей пуст"
    
    if len(recipients) > 1000:
        return False, "Слишком много получателей (максимум 1000)"
    
    return True, ""


def format_recipient_list(recipients: List[Dict], max_display: int = 10) -> str:
    """Форматирует список получателей для отображения"""
    if not recipients:
        return "Список пуст"
    
    display_list = recipients[:max_display]
    lines = [f"• {rec['original']}" for rec in display_list]
    
    if len(recipients) > max_display:
        lines.append(f"\n... и еще {len(recipients) - max_display} получателей")
    
    return "\n".join(lines)
