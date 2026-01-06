import logging
import sys
import re
from datetime import datetime
from typing import List, Dict, Optional
from config import LOG_FILE, LOG_LEVEL
from database import MailingCampaign, SendingHistory, Template, User

def setup_logger():
    logger = logging.getLogger('mailing_bot')
    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
logger = setup_logger()

def normalize_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith('@'):
        identifier = identifier[1:]
    if 't.me/' in identifier or 'telegram.me/' in identifier:
        match = re.search('(?:t\\.me/|telegram\\.me/)(?:c/)?([a-zA-Z0-9_]+)', identifier)
        if match:
            identifier = match.group(1)
    identifier = re.sub('[^a-zA-Z0-9_]', '', identifier)
    return identifier.lower() if identifier else ''

def parse_recipients_list(text: str) -> List[Dict]:
    parts = re.split('[,\\s\\n]+', text)
    recipients = []
    seen = set()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        normalized = normalize_identifier(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if part.isdigit() or (part.startswith('-') and part[1:].isdigit()):
            identifier_type = 'chat_id'
        elif part.startswith('@'):
            identifier_type = 'username'
        elif 't.me' in part or 'telegram.me' in part:
            if 'joinchat' in part or '/+' in part:
                identifier_type = 'invite_link'
            else:
                identifier_type = 'link'
        else:
            identifier_type = 'username'
        recipients.append({'original': part, 'normalized': normalized, 'type': identifier_type})
    return recipients

def validate_recipients_list(recipients: List[Dict]) -> tuple[bool, str]:
    if not recipients:
        return (False, 'Список получателей пуст')
    if len(recipients) > 1000:
        return (False, 'Слишком много получателей (максимум 1000)')
    return (True, '')

def format_recipient_list(recipients: List[Dict], max_display: int=10) -> str:
    if not recipients:
        return 'Список пуст'
    display_list = recipients[:max_display]
    lines = [f'• {rec['original']}' for rec in display_list]
    if len(recipients) > max_display:
        lines.append(f'\n... и еще {len(recipients) - max_display} получателей')
    return '\n'.join(lines)

def validate_template_name(name: str) -> tuple[bool, Optional[str]]:
    if not name or not name.strip():
        return (False, 'Название шаблона не может быть пустым')
    if len(name) > 255:
        return (False, 'Название шаблона слишком длинное (максимум 255 символов)')
    return (True, None)

def validate_template_text(text: str) -> tuple[bool, Optional[str]]:
    if not text or not text.strip():
        return (False, 'Текст шаблона не может быть пустым')
    if len(text) > 4096:
        return (False, 'Текст шаблона слишком длинный (максимум 4096 символов)')
    return (True, None)

def validate_telegram_id(user_id: str) -> tuple[bool, Optional[int]]:
    try:
        telegram_id = int(user_id)
        if telegram_id <= 0:
            return (False, None)
        return (True, telegram_id)
    except ValueError:
        return (False, None)

def validate_username(username: str) -> tuple[bool, Optional[str]]:
    if not username:
        return (False, None)
    username = username.lstrip('@')
    if not re.match('^[a-zA-Z0-9_]{5,32}$', username):
        return (False, None)
    return (True, username)

def format_personal_report(campaign: MailingCampaign, template: Template, owner: User, history: List[SendingHistory], duplicates: List[str]) -> str:
    if campaign.started_at and campaign.completed_at:
        start_time = campaign.started_at.strftime('%H:%M')
        end_time = campaign.completed_at.strftime('%H:%M')
        date = campaign.started_at.strftime('%d.%m.%Y')
        time_range = f'{start_time} - {end_time} ({date})'
    elif campaign.started_at:
        time_range = campaign.started_at.strftime('%H:%M (%d.%m.%Y)')
    else:
        time_range = 'Не начата'
    total = campaign.total_recipients
    sent = campaign.sent_successfully
    failed = campaign.sent_failed
    dup_count = campaign.duplicates_count
    error_messages = {'blocked': 'пользователь заблокировал бота', 'invalid_user': 'пользователь не найден или не начинал диалог с ботом', 'deleted': 'аккаунт удален', 'privacy': 'ограничения приватности', 'rate_limit': 'превышен лимит сообщений', 'technical': 'техническая ошибка', 'unknown': 'неизвестная ошибка'}
    failed_recipients = []
    for h in history:
        if not h.success:
            error_msg = error_messages.get(h.error_type, 'неизвестная ошибка')
            failed_recipients.append(f'• {h.recipient_identifier} - {error_msg}')
    owner_username = (owner.username or 'не указан').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
    template_name = template.name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
    report = f"""📊 ВАШ ОТЧЕТ #{campaign.id}

Владелец: @{owner_username}
Шаблон: "{template_name}" (#{template.id})
Время рассылки: {time_range}

СТАТИСТИКА:
✅ Отправлено успешно: {sent} из {total}
❌ Не удалось отправить: {failed}
🔄 Дубли (пропущены): {dup_count}"""
    if failed_recipients:
        report += f'\n\nНЕОТПРАВЛЕННЫЕ:\n' + '\n'.join(failed_recipients)
    if duplicates:
        dup_list = ', '.join(duplicates[:10])
        if len(duplicates) > 10:
            dup_list += f', ... и еще {len(duplicates) - 10}'
        report += f'\n\nДУБЛИ (не отправлялись повторно):\n• {dup_list}'
    report += f'\n\nИДЕНТИФИКАТОР РАССЫЛКИ: {campaign.campaign_id}'
    return report

def format_summary_report(campaigns: List[MailingCampaign], templates: Dict[int, Template], owners: Dict[int, User], error_stats: Dict[str, int], date: datetime) -> str:
    date_str = date.strftime('%d.%m.%Y')
    report = f'📈 СВОДНЫЙ ОТЧЕТ ПО РАССЫЛКАМ\n\nПериод: {date_str}\nВсего рассылок за день: {len(campaigns)}\n\nДЕТАЛИ ПО РАССЫЛКАМ:\n\n'
    for idx, campaign in enumerate(campaigns, 1):
        template = templates.get(campaign.template_id)
        owner = owners.get(campaign.owner_id)
        template_name = template.name if template else 'Неизвестный шаблон'
        owner_name = f'@{owner.username}' if owner and owner.username else f'ID: {owner.telegram_id}' if owner else 'Неизвестен'
        report += f'{idx}. Рассылка #{campaign.id}\n   • Владелец: {owner_name}\n   • Шаблон: "{template_name}"\n   • Получателей: {campaign.total_recipients} | ✅ {campaign.sent_successfully} | ❌ {campaign.sent_failed}\n   • Дубли: {campaign.duplicates_count}\n\n'
    total_recipients = sum((c.total_recipients for c in campaigns))
    total_sent = sum((c.sent_successfully for c in campaigns))
    total_failed = sum((c.sent_failed for c in campaigns))
    total_duplicates = sum((c.duplicates_count for c in campaigns))
    unique_recipients = total_recipients - total_duplicates
    report += f'ОБЩАЯ СТАТИСТИКА:\n👥 Уникальных получателей: {unique_recipients}\n📨 Всего отправок: {total_sent}\n⚠️ Ошибок отправки: {total_failed}\n🔄 Обнаружено дублей: {total_duplicates}\n\n'
    if error_stats:
        report += 'ТОП-3 ПРИЧИН ОШИБОК:\n'
        error_messages = {'blocked': 'Пользователь заблокировал бота', 'invalid_user': 'Неверный username', 'deleted': 'Аккаунт удален', 'privacy': 'Ограничения приватности', 'rate_limit': 'Превышен лимит сообщений', 'technical': 'Техническая ошибка', 'unknown': 'Неизвестная ошибка'}
        sorted_errors = sorted(error_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        for idx, (error_type, count) in enumerate(sorted_errors, 1):
            error_msg = error_messages.get(error_type, error_type)
            report += f'{idx}. {error_msg} - {count}\n'
    return report

def format_campaign_preview(campaign: MailingCampaign, template: Template, recipients_count: int) -> str:
    return f'📧 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР РАССЫЛКИ\n\nШаблон: "{template.name}" (#{template.id})\nПолучателей: {recipients_count}\n\nТекст сообщения:\n━━━━━━━━━━━━━━━━━━━━\n{template.text}\n━━━━━━━━━━━━━━━━━━━━\n\nПодтвердите запуск рассылки?'

def format_error_message(error_type: str, details: str='') -> str:
    error_messages = {'blocked': 'Пользователь заблокировал бота', 'invalid_user': 'Неверный username', 'deleted': 'Аккаунт удален', 'privacy': 'Ограничения приватности', 'rate_limit': 'Превышен лимит сообщений', 'technical': 'Техническая ошибка', 'unknown': 'Неизвестная ошибка'}
    base_msg = error_messages.get(error_type, 'Неизвестная ошибка')
    if details:
        return f'{base_msg}: {details}'
    return base_msg
