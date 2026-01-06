from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Optional

def get_templates_keyboard(templates: List, page: int=0, per_page: int=5, for_selection: bool=True) -> InlineKeyboardMarkup:
    keyboard = []
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_templates = templates[start_idx:end_idx]
    for template in page_templates:
        if for_selection:
            keyboard.append([InlineKeyboardButton(text=f'📝 {template.name}', callback_data=f'template_{template.id}')])
        else:
            keyboard.append([InlineKeyboardButton(text=f'📝 {template.name}', callback_data=f'template_{template.id}'), InlineKeyboardButton(text='✏️', callback_data=f'edit_template_{template.id}'), InlineKeyboardButton(text='🗑️', callback_data=f'delete_template_{template.id}')])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text='◀️ Назад', callback_data=f'templates_page_{page}_{(1 if for_selection else 0)}'))
    if end_idx < len(templates):
        nav_buttons.append(InlineKeyboardButton(text='Вперед ▶️', callback_data=f'templates_page_{page + 1}_{(1 if for_selection else 0)}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_delay_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    keyboard.append([InlineKeyboardButton(text='15 сек ⭐', callback_data='delay_15'), InlineKeyboardButton(text='30 сек ⭐', callback_data='delay_30')])
    keyboard.append([InlineKeyboardButton(text='60 сек (безопасно)', callback_data='delay_60'), InlineKeyboardButton(text='120 сек (очень безопасно)', callback_data='delay_120')])
    keyboard.append([InlineKeyboardButton(text='10 сек ⚠️', callback_data='delay_10'), InlineKeyboardButton(text='5 сек ⚠️⚠️', callback_data='delay_5')])
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_max_recipients_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    keyboard.append([InlineKeyboardButton(text='10 получателей', callback_data='max_recipients_10'), InlineKeyboardButton(text='50 получателей', callback_data='max_recipients_50')])
    keyboard.append([InlineKeyboardButton(text='100 получателей', callback_data='max_recipients_100'), InlineKeyboardButton(text='300 получателей', callback_data='max_recipients_300')])
    keyboard.append([InlineKeyboardButton(text='500 получателей', callback_data='max_recipients_500')])
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirm_mailing_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить', callback_data=f'confirm_mailing_{campaign_id}'), InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')]])

def get_duplicates_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Отправить дубли', callback_data=f'send_duplicates_{campaign_id}'), InlineKeyboardButton(text='❌ Пропустить', callback_data=f'skip_duplicates_{campaign_id}')]])

def get_campaigns_keyboard(campaigns: List, page: int=0, per_page: int=5) -> InlineKeyboardMarkup:
    keyboard = []
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_campaigns = campaigns[start_idx:end_idx]
    for campaign in page_campaigns:
        status_emoji = {'pending': '⏳', 'processing': '🔄', 'completed': '✅', 'failed': '❌'}.get(campaign.status, '❓')
        keyboard.append([InlineKeyboardButton(text=f'{status_emoji} #{campaign.id} - {campaign.campaign_id}', callback_data=f'campaign_{campaign.id}')])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text='◀️ Назад', callback_data=f'campaigns_page_{page - 1}'))
    if end_idx < len(campaigns):
        nav_buttons.append(InlineKeyboardButton(text='Вперед ▶️', callback_data=f'campaigns_page_{page + 1}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton(text='❌ Закрыть', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_main_keyboard(is_admin: bool=False) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text='📧 Новая рассылка')], [KeyboardButton(text='📊 Мои рассылки')], [KeyboardButton(text='👥 Группы')]]
    if is_admin:
        keyboard.append([KeyboardButton(text='📝 Шаблоны')])
        keyboard.append([KeyboardButton(text='⚙️ Настройки')])
    keyboard.append([KeyboardButton(text='ℹ️ Помощь')])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='❌ Отмена')]], resize_keyboard=True)

def get_recipients_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='👥 В группе')], [KeyboardButton(text='❌ Отмена')]], resize_keyboard=True)
