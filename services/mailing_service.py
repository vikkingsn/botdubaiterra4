"""
Сервис для обработки рассылок
"""
import asyncio
from datetime import datetime, time
from typing import List, Dict, Optional
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
)
from database import crud
from database.models import MailingCampaign, Template, Recipient
from utils.parsers import normalize_identifier
from utils.logger import logger
# MIN_DELAY_SECONDS и MAX_DELAY_SECONDS больше не используются
# Интервал теперь выбирается пользователем при создании рассылки
from services.telegram_client import send_message_as_user, check_account_status


def is_within_allowed_time() -> bool:
    """
    Проверяет, находится ли текущее время в разрешенном диапазоне для рассылок
    Разрешенное время: с 09:00 до 22:00
    """
    current_time = datetime.now().time()
    start_time = time(9, 0)  # 09:00
    end_time = time(22, 0)   # 22:00
    
    return start_time <= current_time <= end_time


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
        
        # Пытаемся отправить с Markdown, если ошибка - без форматирования
        try:
            message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown"
            )
        except TelegramBadRequest as markdown_error:
            # Если ошибка парсинга Markdown, пробуем без форматирования
            if "can't parse" in str(markdown_error).lower() or "parse entities" in str(markdown_error).lower():
                logger.warning(f"Ошибка парсинга Markdown для {recipient_identifier}, отправляем без форматирования")
                message = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None
                )
            else:
                raise  # Если другая ошибка - пробрасываем дальше
        
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
    
    # Проверяем время отправки (09:00 - 22:00)
    if not is_within_allowed_time():
        current_time = datetime.now().time()
        logger.warning(f"Попытка запуска рассылки вне разрешенного времени. Текущее время: {current_time}")
        await crud.update_campaign_status(
            campaign.id,
            "failed",
            completed_at=datetime.now()
        )
        return {
            "success": False,
            "error": "Рассылка разрешена только с 09:00 до 22:00",
            "sent_count": 0,
            "failed_count": len(recipients),
            "duplicates_count": 0
        }
    
    # Ограничиваем количество получателей, если указано max_recipients
    if campaign.max_recipients and len(recipients) > campaign.max_recipients:
        logger.info(f"Ограничиваем рассылку до {campaign.max_recipients} получателей (было {len(recipients)})")
        recipients = recipients[:campaign.max_recipients]
    
    # Проверяем статус аккаунта перед началом рассылки
    logger.info(f"Проверка статуса аккаунта перед началом рассылки {campaign.campaign_id}")
    account_status = await check_account_status(campaign.owner_id)
    
    if not account_status["success"]:
        # Если аккаунт ограничен - останавливаем рассылку
        if account_status["error_type"] == "peer_flood":
            logger.error(f"⚠️ PEER_FLOOD обнаружен при проверке статуса! Останавливаем рассылку {campaign.campaign_id}")
            
            # Обновляем статус рассылки
            await crud.update_campaign_status(
                campaign.id,
                "failed",
                completed_at=datetime.now()
            )
            
            # Отправляем уведомление владельцу
            try:
                await bot.send_message(
                    chat_id=campaign.owner_id,
                    text=f"⚠️ РАССЫЛКА ОТМЕНЕНА\n\n"
                         f"Кампания: {campaign.campaign_id}\n"
                         f"Причина: Аккаунт все еще ограничен Telegram (PEER_FLOOD)\n\n"
                         f"💡 ВАЖНО:\n"
                         f"• Ограничение может быть снято для Bot API, но еще активно для Client API\n"
                         f"• Подождите еще 1-2 часа после снятия ограничения\n"
                         f"• Проверьте статус через @SpamBot и убедитесь, что ограничение полностью снято\n"
                         f"• После снятия ограничения попробуйте запустить рассылку снова\n\n"
                         f"📝 Детали: {account_status.get('error_details', 'Неизвестная ошибка')}",
                    parse_mode=None
                )
                logger.info(f"Уведомление о PEER_FLOOD отправлено владельцу {campaign.owner_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления о PEER_FLOOD: {e}")
            
            return {
                "success": False,
                "error": account_status.get("error_details", "Аккаунт ограничен"),
                "sent_count": 0,
                "failed_count": len(recipients),
                "duplicates_count": 0
            }
        else:
            # Другие ошибки при проверке - логируем, но продолжаем
            logger.warning(f"Предупреждение при проверке статуса аккаунта: {account_status.get('error_details')}")
    
    # Обновляем статус
    await crud.update_campaign_status(
        campaign.id,
        "processing",
        started_at=datetime.now()
    )
    
    # Шаг 1: Разделение на "новых" и "дубли"
    # Дубли НЕ отправляются - они пропускаются без паузы
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
            # Сохраняем в историю как пропущенный дубль
            await crud.add_sending_history(
                campaign.id,
                recipient.recipient_identifier,
                False,  # Не отправлено
                "duplicate",
                f"Пропущен дубль (уже отправлялось в {duplicate_info.get('campaign_id')})",
                None
            )
        else:
            new_recipients.append(recipient)
    
    logger.info(f"Найдено новых получателей: {len(new_recipients)}, дублей (пропущено): {len(duplicate_recipients)}")
    
    # Шаг 2: Отправка только новым получателям (от имени пользователя через Client API)
    # Пауза только между новыми получателями (кому сообщение еще не отправлялось)
    # При переходе от дубля к новому получателю пауза НЕ применяется
    sent_count = 0
    failed_count = 0
    last_was_new = False  # Флаг, был ли предыдущий получатель новым
    
    for recipient in recipients:
        # Проверяем, является ли получатель дублем
        duplicate_info = await crud.check_duplicate(
            template.id,
            recipient.normalized_identifier
        )
        
        if duplicate_info and duplicate_info.get("is_duplicate"):
            # Дубль - пропускаем без отправки и без паузы
            logger.debug(f"Пропущен дубль: {recipient.recipient_identifier} (уже отправлялось ранее)")
            last_was_new = False  # Предыдущий был дублем, пауза не нужна
            continue
        
        # Это новый получатель - отправляем
        # Пауза ПЕРЕД отправкой только если предыдущий получатель тоже был новым
        if last_was_new:  # Если предыдущий был новым, делаем паузу
            delay = campaign.delay_seconds or 5  # По умолчанию 5 секунд, если не указано
            logger.debug(f"Задержка {delay} секунд перед отправкой новому получателю (выбранный интервал)")
            await asyncio.sleep(delay)
        
        # Используем Client API для отправки от имени создателя рассылки
        # Сообщения будут отправляться от имени campaign.owner_id
        result = await send_message_as_user(
            recipient.recipient_identifier,
            template.text,
            sender_user_id=campaign.owner_id,
            media_type=template.media_type,
            media_file_id=template.media_file_id
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
            last_was_new = True  # Отметили, что этот получатель был новым
        else:
            failed_count += 1
            
            # Если получили PeerFlood - останавливаем рассылку
            if result["error_type"] == "peer_flood":
                logger.error(f"⚠️ PEER_FLOOD обнаружен! Останавливаем рассылку {campaign.campaign_id}")
                
                # Обновляем статус рассылки
                await crud.update_campaign_status(
                    campaign.id,
                    "failed",
                    completed_at=datetime.now()
                )
                
                # Обновляем статистику до текущего момента
                await crud.update_campaign_stats(
                    campaign.id,
                    total=len(recipients),
                    sent=sent_count,
                    failed=failed_count,
                    duplicates=len(duplicate_recipients)
                )
                
                # Отправляем уведомление владельцу
                try:
                    await bot.send_message(
                        chat_id=campaign.owner_id,
                        text=f"⚠️ РАССЫЛКА ПРЕРВАНА\n\n"
                             f"Кампания: {campaign.campaign_id}\n"
                             f"Причина: Аккаунт ограничен Telegram (PEER_FLOOD)\n\n"
                             f"Отправлено до ограничения: {sent_count}\n"
                             f"Ошибок: {failed_count}\n\n"
                             f"💡 РЕКОМЕНДАЦИИ:\n"
                             f"• Увеличьте интервал между сообщениями (минимум 15-30 секунд)\n"
                             f"• Уменьшите количество получателей за раз (используйте ограничение 10, 50, 100)\n"
                             f"• Подождите 1-2 часа перед следующей рассылкой\n"
                             f"• Избегайте интервалов менее 10 секунд",
                        parse_mode=None
                    )
                    logger.info(f"Уведомление о PEER_FLOOD отправлено владельцу {campaign.owner_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления о PEER_FLOOD: {e}")
                
                # Прерываем цикл рассылки
                break
            
            # Для других ошибок продолжаем
            last_was_new = True
    
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
    # Дубли НЕ отправляются - они пропущены, так как сообщение уже отправлялось этим пользователям ранее
    if duplicate_recipients:
        dup_list = ", ".join([d["recipient"].recipient_identifier for d in duplicate_recipients[:10]])
        if len(duplicate_recipients) > 10:
            dup_list += f", ... и еще {len(duplicate_recipients) - 10}"
        
        try:
            await bot.send_message(
                chat_id=campaign.owner_id,
                text=f"ℹ️ Обнаружено дублей: {len(duplicate_recipients)}\n\n"
                     f"Дубли пропущены (сообщение уже отправлялось этим пользователям ранее):\n{dup_list}\n\n"
                     f"Пауза при переходе от дубля к новому получателю не применялась.",
                parse_mode=None
            )
            logger.info(f"Уведомление о дублях отправлено владельцу {campaign.owner_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о дублях: {e}")
    
    # Отправляем персональный отчет владельцу
    try:
        from services.report_service import generate_personal_report
        report = await generate_personal_report(campaign.id)
        if report:
            # Отправляем без форматирования для надежности
            await bot.send_message(
                chat_id=campaign.owner_id,
                text=report,
                parse_mode=None  # Без форматирования - избегаем ошибок парсинга
            )
            logger.info(f"Персональный отчет отправлен владельцу {campaign.owner_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке персонального отчета: {e}", exc_info=True)
    
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
    """Отправляет сообщения дублям по запросу пользователя (от имени пользователя)
    
    ВАЖНО: Дубли НЕ должны отправляться, так как сообщение уже отправлялось этим пользователям.
    Эта функция оставлена для обратной совместимости, но теперь дубли просто пропускаются.
    """
    logger.warning(f"Попытка отправить дубли для рассылки {campaign.campaign_id} - дубли не отправляются, так как сообщение уже отправлялось")
    
    # Дубли не отправляются - сообщение уже было отправлено этим пользователям ранее
    return {
        "sent": 0,
        "failed": len(duplicate_recipients)
    }
    
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
