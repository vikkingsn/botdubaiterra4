"""
Форматирование текста для отчетов и сообщений
"""
from datetime import datetime
from typing import List, Dict
from database.models import MailingCampaign, SendingHistory, Template, User
from utils.parsers import format_recipient_list


def format_personal_report(campaign: MailingCampaign, template: Template, 
                          owner: User, history: List[SendingHistory],
                          duplicates: List[str]) -> str:
    """Форматирует персональный отчет для владельца рассылки"""
    
    # Форматируем время рассылки
    if campaign.started_at and campaign.completed_at:
        start_time = campaign.started_at.strftime("%H:%M")
        end_time = campaign.completed_at.strftime("%H:%M")
        date = campaign.started_at.strftime("%d.%m.%Y")
        time_range = f"{start_time} - {end_time} ({date})"
    elif campaign.started_at:
        time_range = campaign.started_at.strftime("%H:%M (%d.%m.%Y)")
    else:
        time_range = "Не начата"
    
    # Статистика
    total = campaign.total_recipients
    sent = campaign.sent_successfully
    failed = campaign.sent_failed
    dup_count = campaign.duplicates_count
    
    # Группируем ошибки
    error_messages = {
        "blocked": "пользователь заблокировал бота",
        "invalid_user": "неверный username",
        "deleted": "аккаунт удален",
        "privacy": "ограничения приватности",
        "rate_limit": "превышен лимит сообщений",
        "technical": "техническая ошибка",
        "unknown": "неизвестная ошибка"
    }
    
    failed_recipients = []
    for h in history:
        if not h.success:
            error_msg = error_messages.get(h.error_type, "неизвестная ошибка")
            failed_recipients.append(f"• {h.recipient_identifier} - {error_msg}")
    
    # Формируем отчет
    report = f"""📊 ВАШ ОТЧЕТ #{campaign.id}

Владелец: @{owner.username or 'не указан'}
Шаблон: "{template.name}" (#{template.id})
Время рассылки: {time_range}

СТАТИСТИКА:
✅ Отправлено успешно: {sent} из {total}
❌ Не удалось отправить: {failed}
🔄 Дубли (пропущены): {dup_count}"""
    
    if failed_recipients:
        report += f"\n\nНЕОТПРАВЛЕННЫЕ:\n" + "\n".join(failed_recipients)
    
    if duplicates:
        dup_list = ", ".join(duplicates[:10])
        if len(duplicates) > 10:
            dup_list += f", ... и еще {len(duplicates) - 10}"
        report += f"\n\nДУБЛИ (не отправлялись повторно):\n• {dup_list}"
    
    report += f"\n\nИДЕНТИФИКАТОР РАССЫЛКИ: {campaign.campaign_id}"
    
    return report


def format_summary_report(campaigns: List[MailingCampaign], 
                         templates: Dict[int, Template],
                         owners: Dict[int, User],
                         error_stats: Dict[str, int],
                         date: datetime) -> str:
    """Форматирует сводный отчет для администраторов"""
    
    date_str = date.strftime("%d.%m.%Y")
    
    report = f"""📈 СВОДНЫЙ ОТЧЕТ ПО РАССЫЛКАМ

Период: {date_str}
Всего рассылок за день: {len(campaigns)}

ДЕТАЛИ ПО РАССЫЛКАМ:

"""
    
    # Детали по каждой рассылке
    for idx, campaign in enumerate(campaigns, 1):
        template = templates.get(campaign.template_id)
        owner = owners.get(campaign.owner_id)
        
        template_name = template.name if template else "Неизвестный шаблон"
        owner_name = f"@{owner.username}" if owner and owner.username else f"ID: {owner.telegram_id}" if owner else "Неизвестен"
        
        # Группируем ошибки для этой рассылки
        # (это упрощенная версия, в реальности нужно получать из БД)
        
        report += f"""{idx}. Рассылка #{campaign.id}
   • Владелец: {owner_name}
   • Шаблон: "{template_name}"
   • Получателей: {campaign.total_recipients} | ✅ {campaign.sent_successfully} | ❌ {campaign.sent_failed}
   • Дубли: {campaign.duplicates_count}

"""
    
    # Общая статистика
    total_recipients = sum(c.total_recipients for c in campaigns)
    total_sent = sum(c.sent_successfully for c in campaigns)
    total_failed = sum(c.sent_failed for c in campaigns)
    total_duplicates = sum(c.duplicates_count for c in campaigns)
    
    # Подсчет уникальных получателей (упрощенно)
    unique_recipients = total_recipients - total_duplicates
    
    report += f"""ОБЩАЯ СТАТИСТИКА:
👥 Уникальных получателей: {unique_recipients}
📨 Всего отправок: {total_sent}
⚠️ Ошибок отправки: {total_failed}
🔄 Обнаружено дублей: {total_duplicates}

"""
    
    # ТОП причин ошибок
    if error_stats:
        report += "ТОП-3 ПРИЧИН ОШИБОК:\n"
        error_messages = {
            "blocked": "Пользователь заблокировал бота",
            "invalid_user": "Неверный username",
            "deleted": "Аккаунт удален",
            "privacy": "Ограничения приватности",
            "rate_limit": "Превышен лимит сообщений",
            "technical": "Техническая ошибка",
            "unknown": "Неизвестная ошибка"
        }
        
        sorted_errors = sorted(error_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        for idx, (error_type, count) in enumerate(sorted_errors, 1):
            error_msg = error_messages.get(error_type, error_type)
            report += f"{idx}. {error_msg} - {count}\n"
    
    return report


def format_campaign_preview(campaign: MailingCampaign, template: Template, 
                           recipients_count: int) -> str:
    """Форматирует превью рассылки для подтверждения"""
    return f"""📧 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР РАССЫЛКИ

Шаблон: "{template.name}" (#{template.id})
Получателей: {recipients_count}

Текст сообщения:
━━━━━━━━━━━━━━━━━━━━
{template.text}
━━━━━━━━━━━━━━━━━━━━

Подтвердите запуск рассылки?"""


def format_error_message(error_type: str, details: str = "") -> str:
    """Форматирует сообщение об ошибке"""
    error_messages = {
        "blocked": "Пользователь заблокировал бота",
        "invalid_user": "Неверный username",
        "deleted": "Аккаунт удален",
        "privacy": "Ограничения приватности",
        "rate_limit": "Превышен лимит сообщений",
        "technical": "Техническая ошибка",
        "unknown": "Неизвестная ошибка"
    }
    
    base_msg = error_messages.get(error_type, "Неизвестная ошибка")
    if details:
        return f"{base_msg}: {details}"
    return base_msg
