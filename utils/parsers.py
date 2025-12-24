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
    https://t.me/groupname -> groupname (для групп/каналов)
    @groupname -> groupname (для групп/каналов)
    """
    identifier = identifier.strip()
    
    # Удаляем @ в начале
    if identifier.startswith("@"):
        identifier = identifier[1:]
    
    # Обработка ссылок
    if "t.me/" in identifier or "telegram.me/" in identifier:
        # Извлекаем username/groupname из ссылки
        # Поддерживаем как https://t.me/username, так и https://t.me/c/chat_id/123
        match = re.search(r'(?:t\.me/|telegram\.me/)(?:c/)?([a-zA-Z0-9_]+)', identifier)
        if match:
            identifier = match.group(1)
    
    # Удаляем все недопустимые символы для username/groupname
    # Для групп/каналов допустимы те же символы, что и для username
    identifier = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
    
    return identifier.lower() if identifier else ""


def parse_recipients_list(text: str) -> List[Dict]:
    """
    Парсит список получателей из текста
    
    Поддерживает:
    - @username (пользователи)
    - user_id (числа, включая отрицательные для групп)
    - Ссылки (https://t.me/user, t.me/user)
    - Группы/каналы (@groupname, https://t.me/groupname)
    - Приватные группы (https://t.me/joinchat/HASH, t.me/+HASH)
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
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            # Это user_id или chat_id (может быть отрицательным для групп)
            identifier_type = "chat_id"
        elif part.startswith("@"):
            # Может быть как пользователь, так и группа/канал
            identifier_type = "username"  # Pyrogram сам определит тип чата
        elif "t.me" in part or "telegram.me" in part:
            # Проверяем, это invite-ссылка или обычная ссылка
            if "joinchat" in part or "/+" in part:
                identifier_type = "invite_link"  # Приватная группа по invite-ссылке
            else:
                identifier_type = "link"  # Может быть ссылка на пользователя или группу
        else:
            # Пытаемся определить как username (может быть группа)
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
