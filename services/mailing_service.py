"""
Сервис для обработки рассылок
"""
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Optional
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
)
from database import crud
from database.models import MailingCampaign, Template, Recipient
from utils.parsers import normalize_identifier
from utils.logger import logger
from config import MIN_DELAY_SECONDS, MAX_DELAY_SECONDS


async def send_with_error_handling(
    bot: Bot,
    recipient_identifier: str,
    text: str
) -> Dict:
    """
    Отправляет сообщение с обработкой всех возможных ошибок
    
    Возвращает:
    {
        "success": bool,
        "error_type": str,
        "error_details": str,
        "telegram_message_id": int | None
    }
    """
    try:
        # Определяем тип получателя и отправляем
        if recipient_identifier.isdigit():
            # Это user_id
            chat_id = int(recipient_identifier)
        else:
            # Это username - нужно получить user_id через get_chat
            # Но для упрощения попробуем отправить напрямую
            # В реальности лучше хранить user_id в базе
            username = recipient_identifier.lstrip("@")
            try:
                # Пытаемся получить информацию о пользователе
                chat = await bot.get_chat(f"@{username}")
                chat_id = chat.id
            except Exception:
                # Если не получилось, пробуем отправить по username (может не сработать)
                chat_id = f"@{username}"
        
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown"
        )
        
        return {
            "success": True,
            "error_type": None,
            "error_details": None,
            "telegram_message_id": message.message_id
        }
    
    except TelegramForbiddenError as e:
        # Пользователь заблокировал бота
        error_msg = str(e)
        if "blocked" in error_msg.lower() or "bot was blocked" in error_msg.lower():
            error_type = "blocked"
        else:
            error_type = "privacy"
        
        logger.warning(f"Ошибка отправки {recipient_identifier}: {error_type} - {error_msg}")
        return {
            "success": False,
            "error_type": error_type,
            "error_details": error_msg,
            "telegram_message_id": None
        }
    
    except TelegramBadRequest as e:
        error_msg = str(e)
        
        # Определяем тип ошибки
        if "chat not found" in error_msg.lower() or "user not found" in error_msg.lower():
            error_type = "invalid_user"
        elif "deleted" in error_msg.lower():
            error_type = "deleted"
        elif "privacy" in error_msg.lower() or "can't write" in error_msg.lower():
            error_type = "privacy"
        elif "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
            error_type = "rate_limit"
        else:
            error_type = "unknown"
        
        logger.warning(f"Ошибка отправки {recipient_identifier}: {error_type} - {error_msg}")
        return {
            "success": False,
            "error_type": error_type,
            "error_details": error_msg,
            "telegram_message_id": None
        }
    
    except TelegramAPIError as e:
        error_msg = str(e)
        logger.error(f"Техническая ошибка при отправке {recipient_identifier}: {error_msg}")
        return {
            "success": False,
            "error_type": "technical",
            "error_details": error_msg,
            "telegram_message_id": None
        }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Неизвестная ошибка при отправке {recipient_identifier}: {error_msg}")
        return {
            "success": False,
            "error_type": "unknown",
            "error_details": error_msg,
            "telegram_message_id": None
        }


async def process_mailing(
    bot: Bot,
    campaign: MailingCampaign,
    template: Template,
    recipients: List[Recipient]
) -> Dict:
    """
    Обрабатывает рассылку: проверяет дубли, отправляет сообщения, формирует отчеты
    
    Возвращает статистику рассылки
    """
    logger.info(f"Начало обработки рассылки {campaign.campaign_id}")
    
    # Обновляем статус
    await crud.update_campaign_status(
        campaign.id,
        "processing",
        started_at=datetime.now()
    )
    
    # Шаг 1: Разделение на "новых" и "дубли"
    new_recipients = []
    duplicate_recipients = []
    
    for recipient in recipients:
        duplicate_info = await crud.check_duplicate(
            template.id,
            recipient.normalized_identifier
        )
        
        if duplicate_info and duplicate_info.get("is_duplicate"):
            duplicate_recipients.append({
                "recipient": recipient,
                "previous_campaign": duplicate_info.get("campaign_id"),
                "previous_time": duplicate_info.get("previous_time")
            })
            # Помечаем как дубль
            await crud.mark_recipient_as_duplicate(
                recipient.id,
                duplicate_info.get("previous_campaign_id")
            )
        else:
            new_recipients.append(recipient)
    
    logger.info(f"Найдено новых получателей: {len(new_recipients)}, дублей: {len(duplicate_recipients)}")
    
    # Шаг 2: Отправка новым получателям
    sent_count = 0
    failed_count = 0
    
    for recipient in new_recipients:
        result = await send_with_error_handling(
            bot,
            recipient.recipient_identifier,
            template.text
        )
        
        # Сохраняем в историю
        await crud.add_sending_history(
            campaign.id,
            recipient.recipient_identifier,
            result["success"],
            result["error_type"],
            result["error_details"],
            result["telegram_message_id"]
        )
        
        if result["success"]:
            sent_count += 1
        else:
            failed_count += 1
        
        # Задержка между отправками
        if recipient != new_recipients[-1]:  # Не ждем после последнего
            delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            logger.debug(f"Задержка {delay} секунд перед следующей отправкой")
            await asyncio.sleep(delay)
    
    # Обновляем статистику
    await crud.update_campaign_stats(
        campaign.id,
        total=len(recipients),
        sent=sent_count,
        failed=failed_count,
        duplicates=len(duplicate_recipients)
    )
    
    # Обновляем статус
    await crud.update_campaign_status(
        campaign.id,
        "completed",
        completed_at=datetime.now()
    )
    
    logger.info(f"Рассылка {campaign.campaign_id} завершена. Отправлено: {sent_count}, Ошибок: {failed_count}, Дублей: {len(duplicate_recipients)}")
    
    # Если есть дубли, отправляем уведомление владельцу
    if duplicate_recipients:
        from keyboards.inline import get_duplicates_keyboard
        dup_list = ", ".join([d["recipient"].recipient_identifier for d in duplicate_recipients[:10]])
        if len(duplicate_recipients) > 10:
            dup_list += f", ... и еще {len(duplicate_recipients) - 10}"
        
        try:
            await bot.send_message(
                chat_id=campaign.owner_id,
                text=f"🔄 Обнаружено дублей: {len(duplicate_recipients)}\n\n"
                     f"Дубли не были отправлены:\n{dup_list}\n\n"
                     f"Хотите отправить их сейчас?",
                reply_markup=get_duplicates_keyboard(campaign.id)
            )
            logger.info(f"Уведомление о дублях отправлено владельцу {campaign.owner_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о дублях: {e}")
    
    # Отправляем персональный отчет владельцу
    try:
        from services.report_service import generate_personal_report
        report = await generate_personal_report(campaign.id)
        if report:
            await bot.send_message(
                chat_id=campaign.owner_id,
                text=report,
                parse_mode="Markdown"
            )
            logger.info(f"Персональный отчет отправлен владельцу {campaign.owner_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке персонального отчета: {e}")
    
    return {
        "sent": sent_count,
        "failed": failed_count,
        "duplicates": len(duplicate_recipients),
        "duplicate_list": [d["recipient"].recipient_identifier for d in duplicate_recipients],
        "duplicate_recipients": duplicate_recipients
    }


async def send_duplicates(
    bot: Bot,
    campaign: MailingCampaign,
    template: Template,
    duplicate_recipients: List[Recipient]
) -> Dict:
    """Отправляет сообщения дублям по запросу пользователя"""
    logger.info(f"Отправка дублей для рассылки {campaign.campaign_id}")
    
    sent_count = 0
    failed_count = 0
    
    for recipient in duplicate_recipients:
        result = await send_with_error_handling(
            bot,
            recipient.recipient_identifier,
            template.text
        )
        
        await crud.add_sending_history(
            campaign.id,
            recipient.recipient_identifier,
            result["success"],
            result["error_type"],
            result["error_details"],
            result["telegram_message_id"]
        )
        
        if result["success"]:
            sent_count += 1
            # Убираем пометку о дубле
            recipient.is_duplicate = False
        else:
            failed_count += 1
        
        if recipient != duplicate_recipients[-1]:
            delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            await asyncio.sleep(delay)
    
    # Обновляем статистику
    updated_campaign = await crud.get_campaign(campaign.id)
    if updated_campaign:
        await crud.update_campaign_stats(
            updated_campaign.id,
            total=updated_campaign.total_recipients,
            sent=updated_campaign.sent_successfully + sent_count,
            failed=updated_campaign.sent_failed + failed_count,
            duplicates=max(0, updated_campaign.duplicates_count - sent_count)
        )
    
    return {
        "sent": sent_count,
        "failed": failed_count
    }
