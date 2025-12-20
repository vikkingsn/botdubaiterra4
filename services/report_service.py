"""
Сервис для генерации отчетов
"""
from datetime import datetime
from typing import List, Dict
from database import crud
from database.models import MailingCampaign, Template, User, SendingHistory
from utils.formatters import format_personal_report, format_summary_report
from utils.logger import logger


async def generate_personal_report(campaign_id: int) -> Optional[str]:
    """
    Генерирует персональный отчет для владельца рассылки
    
    Возвращает отформатированный текст отчета или None
    """
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        return None
    
    template = await crud.get_template(campaign.template_id)
    if not template:
        return None
    
    owner = await crud.get_user_by_telegram_id(campaign.owner_id)
    if not owner:
        return None
    
    # Получаем историю отправок
    history = await crud.get_campaign_sending_history(campaign_id)
    
    # Получаем список дублей из recipients
    from database.models import Recipient, async_session_maker
    from sqlalchemy import select
    
    duplicates = []
    async with async_session_maker() as session:
        result = await session.execute(
            select(Recipient).where(
                Recipient.campaign_id == campaign_id,
                Recipient.is_duplicate == True
            )
        )
        duplicate_recipients = list(result.scalars().all())
        duplicates = [r.recipient_identifier for r in duplicate_recipients]
    
    # Формируем отчет
    report = format_personal_report(campaign, template, owner, history, duplicates)
    
    return report


async def generate_summary_report(date: Optional[datetime] = None) -> str:
    """
    Генерирует сводный отчет по всем рассылкам за день
    
    Если date не указан, используется текущая дата
    """
    if not date:
        date = datetime.now()
    
    # Получаем все рассылки за день
    campaigns = await crud.get_daily_campaigns(date)
    
    if not campaigns:
        return f"📈 СВОДНЫЙ ОТЧЕТ ПО РАССЫЛКАМ\n\nПериод: {date.strftime('%d.%m.%Y')}\n\nРассылок за день не было."
    
    # Получаем шаблоны и владельцев
    template_ids = list(set(c.template_id for c in campaigns))
    owner_ids = list(set(c.owner_id for c in campaigns))
    
    templates = {}
    owners = {}
    
    for template_id in template_ids:
        template = await crud.get_template(template_id)
        if template:
            templates[template_id] = template
    
    for owner_id in owner_ids:
        owner = await crud.get_user_by_telegram_id(owner_id)
        if owner:
            owners[owner_id] = owner
    
    # Получаем статистику ошибок
    start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
    error_stats = await crud.get_error_statistics(start_date, end_date)
    
    # Формируем отчет
    report = format_summary_report(campaigns, templates, owners, error_stats, date)
    
    return report


async def send_summary_reports_to_receivers(bot, date: Optional[datetime] = None):
    """
    Отправляет сводные отчеты всем получателям из списка
    
    Используется для автоматической отправки отчетов
    """
    if not date:
        date = datetime.now()
    
    report = await generate_summary_report(date)
    
    # Получаем список получателей
    receivers = await crud.get_all_report_receivers()
    
    if not receivers:
        logger.info("Нет получателей сводных отчетов")
        return
    
    # Отправляем отчет каждому получателю
    for receiver in receivers:
        try:
            if receiver.telegram_id:
                await bot.send_message(
                    chat_id=receiver.telegram_id,
                    text=report,
                    parse_mode="Markdown"
                )
                logger.info(f"Сводный отчет отправлен получателю {receiver.identifier}")
            else:
                # Пытаемся найти пользователя по username
                if receiver.identifier_type == "username":
                    try:
                        await bot.send_message(
                            chat_id=f"@{receiver.identifier.lstrip('@')}",
                            text=report,
                            parse_mode="Markdown"
                        )
                        logger.info(f"Сводный отчет отправлен получателю {receiver.identifier}")
                    except Exception as e:
                        logger.warning(f"Не удалось отправить отчет {receiver.identifier}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сводного отчета {receiver.identifier}: {e}")
