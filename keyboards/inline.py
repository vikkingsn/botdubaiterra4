"""
Инлайн-клавиатуры
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional


def get_templates_keyboard(templates: List, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для выбора шаблона"""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_templates = templates[start_idx:end_idx]
    
    for template in page_templates:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📝 {template.name}",
                callback_data=f"template_{template.id}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"templates_page_{page - 1}")
        )
    if end_idx < len(templates):
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"templates_page_{page + 1}")
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_mailing_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения рассылки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_mailing_{campaign_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ]
    ])


def get_duplicates_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для обработки дублей"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить дубли", callback_data=f"send_duplicates_{campaign_id}"),
            InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip_duplicates_{campaign_id}")
        ]
    ])


def get_campaigns_keyboard(campaigns: List, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для выбора рассылки"""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_campaigns = campaigns[start_idx:end_idx]
    
    for campaign in page_campaigns:
        status_emoji = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "failed": "❌"
        }.get(campaign.status, "❓")
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status_emoji} #{campaign.id} - {campaign.campaign_id}",
                callback_data=f"campaign_{campaign.id}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"campaigns_page_{page - 1}")
        )
    if end_idx < len(campaigns):
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"campaigns_page_{page + 1}")
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
