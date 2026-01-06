import asyncio
from datetime import datetime, time
from typing import List, Dict, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import UserNotParticipant, ChatWriteForbidden, FloodWait, PeerIdInvalid, UsernameNotOccupied, UsernameInvalid, UserPrivacyRestricted, UserDeactivated, ChannelPrivate, ChatAdminRequired, InviteHashExpired, InviteHashInvalid, UserAlreadyParticipant, PeerFlood
import database as crud
from database import MailingCampaign, Template, Recipient, User, SendingHistory, async_session_maker
from utils import normalize_identifier, logger, format_personal_report, format_summary_report
from config import API_ID, API_HASH, PHONE_NUMBER

def is_within_allowed_time() -> bool:
    current_time = datetime.now().time()
    start_time = time(9, 0)
    end_time = time(22, 0)
    return start_time <= current_time <= end_time

async def send_with_error_handling(bot: Bot, recipient_identifier: str, text: str) -> Dict:
    try:
        if recipient_identifier.isdigit():
            chat_id = int(recipient_identifier)
        else:
            username = recipient_identifier.lstrip('@')
            try:
                chat = await bot.get_chat(f'@{username}')
                chat_id = chat.id
            except Exception:
                chat_id = f'@{username}'
        try:
            message = await bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
        except TelegramBadRequest as markdown_error:
            if "can't parse" in str(markdown_error).lower() or 'parse entities' in str(markdown_error).lower():
                logger.warning(f'Ошибка парсинга Markdown для {recipient_identifier}, отправляем без форматирования')
                message = await bot.send_message(chat_id=chat_id, text=text, parse_mode=None)
            else:
                raise
        return {'success': True, 'error_type': None, 'error_details': None, 'telegram_message_id': message.message_id}
    except TelegramForbiddenError as e:
        error_msg = str(e)
        if 'blocked' in error_msg.lower() or 'bot was blocked' in error_msg.lower():
            error_type = 'blocked'
        else:
            error_type = 'privacy'
        logger.warning(f'Ошибка отправки {recipient_identifier}: {error_type} - {error_msg}')
        return {'success': False, 'error_type': error_type, 'error_details': error_msg, 'telegram_message_id': None}
    except TelegramBadRequest as e:
        error_msg = str(e)
        if 'chat not found' in error_msg.lower() or 'user not found' in error_msg.lower():
            error_type = 'invalid_user'
        elif 'deleted' in error_msg.lower():
            error_type = 'deleted'
        elif 'privacy' in error_msg.lower() or "can't write" in error_msg.lower():
            error_type = 'privacy'
        elif 'rate limit' in error_msg.lower() or 'too many requests' in error_msg.lower():
            error_type = 'rate_limit'
        else:
            error_type = 'unknown'
        logger.warning(f'Ошибка отправки {recipient_identifier}: {error_type} - {error_msg}')
        return {'success': False, 'error_type': error_type, 'error_details': error_msg, 'telegram_message_id': None}
    except TelegramAPIError as e:
        error_msg = str(e)
        logger.error(f'Техническая ошибка при отправке {recipient_identifier}: {error_msg}')
        return {'success': False, 'error_type': 'technical', 'error_details': error_msg, 'telegram_message_id': None}
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Неизвестная ошибка при отправке {recipient_identifier}: {error_msg}')
        return {'success': False, 'error_type': 'unknown', 'error_details': error_msg, 'telegram_message_id': None}

async def process_mailing(bot: Bot, campaign: MailingCampaign, template: Template, recipients: List[Recipient]) -> Dict:
    logger.info(f'Начало обработки рассылки {campaign.campaign_id}')
    if not is_within_allowed_time():
        current_time = datetime.now().time()
        logger.warning(f'Попытка запуска рассылки вне разрешенного времени. Текущее время: {current_time}')
        await crud.update_campaign_status(campaign.id, 'failed', completed_at=datetime.now())
        return {'success': False, 'error': 'Рассылка разрешена только с 09:00 до 22:00', 'sent_count': 0, 'failed_count': len(recipients), 'duplicates_count': 0}
    if campaign.max_recipients and len(recipients) > campaign.max_recipients:
        logger.info(f'Ограничиваем рассылку до {campaign.max_recipients} получателей (было {len(recipients)})')
        recipients = recipients[:campaign.max_recipients]
    logger.info(f'Проверка статуса аккаунта перед началом рассылки {campaign.campaign_id}')
    account_status = await check_account_status(campaign.owner_id)
    if not account_status['success']:
        if account_status['error_type'] == 'peer_flood':
            logger.error(f'⚠️ PEER_FLOOD обнаружен при проверке статуса! Останавливаем рассылку {campaign.campaign_id}')
            await crud.update_campaign_status(campaign.id, 'failed', completed_at=datetime.now())
            try:
                await bot.send_message(chat_id=campaign.owner_id, text=f'⚠️ РАССЫЛКА ОТМЕНЕНА\n\nКампания: {campaign.campaign_id}\nПричина: Аккаунт все еще ограничен Telegram (PEER_FLOOD)\n\n💡 ВАЖНО:\n• Ограничение может быть снято для Bot API, но еще активно для Client API\n• Подождите еще 1-2 часа после снятия ограничения\n• Проверьте статус через @SpamBot и убедитесь, что ограничение полностью снято\n• После снятия ограничения попробуйте запустить рассылку снова\n\n📝 Детали: {account_status.get('error_details', 'Неизвестная ошибка')}', parse_mode=None)
                logger.info(f'Уведомление о PEER_FLOOD отправлено владельцу {campaign.owner_id}')
            except Exception as e:
                logger.error(f'Ошибка при отправке уведомления о PEER_FLOOD: {e}')
            return {'success': False, 'error': account_status.get('error_details', 'Аккаунт ограничен'), 'sent_count': 0, 'failed_count': len(recipients), 'duplicates_count': 0}
        else:
            logger.warning(f'Предупреждение при проверке статуса аккаунта: {account_status.get('error_details')}')
    await crud.update_campaign_status(campaign.id, 'processing', started_at=datetime.now())
    new_recipients = []
    duplicate_recipients = []
    for recipient in recipients:
        duplicate_info = await crud.check_duplicate(template.id, recipient.normalized_identifier)
        if duplicate_info and duplicate_info.get('is_duplicate'):
            duplicate_recipients.append({'recipient': recipient, 'previous_campaign': duplicate_info.get('campaign_id'), 'previous_time': duplicate_info.get('previous_time')})
            await crud.mark_recipient_as_duplicate(recipient.id, duplicate_info.get('previous_campaign_id'))
            await crud.add_sending_history(campaign.id, recipient.recipient_identifier, False, 'duplicate', f'Пропущен дубль (уже отправлялось в {duplicate_info.get('campaign_id')})', None)
        else:
            new_recipients.append(recipient)
    logger.info(f'Найдено новых получателей: {len(new_recipients)}, дублей (пропущено): {len(duplicate_recipients)}')
    sent_count = 0
    failed_count = 0
    last_was_new = False
    for recipient in recipients:
        duplicate_info = await crud.check_duplicate(template.id, recipient.normalized_identifier)
        if duplicate_info and duplicate_info.get('is_duplicate'):
            logger.debug(f'Пропущен дубль: {recipient.recipient_identifier} (уже отправлялось ранее)')
            last_was_new = False
            continue
        if last_was_new:
            delay = campaign.delay_seconds or 5
            logger.debug(f'Задержка {delay} секунд перед отправкой новому получателю (выбранный интервал)')
            await asyncio.sleep(delay)
        result = await send_message_as_user(recipient.recipient_identifier, template.text, sender_user_id=campaign.owner_id, media_type=template.media_type, media_file_id=template.media_file_id)
        await crud.add_sending_history(campaign.id, recipient.recipient_identifier, result['success'], result['error_type'], result['error_details'], result['telegram_message_id'])
        if result['success']:
            sent_count += 1
            last_was_new = True
        else:
            failed_count += 1
            if result['error_type'] == 'peer_flood':
                logger.error(f'⚠️ PEER_FLOOD обнаружен! Останавливаем рассылку {campaign.campaign_id}')
                await crud.update_campaign_status(campaign.id, 'failed', completed_at=datetime.now())
                await crud.update_campaign_stats(campaign.id, total=len(recipients), sent=sent_count, failed=failed_count, duplicates=len(duplicate_recipients))
                try:
                    await bot.send_message(chat_id=campaign.owner_id, text=f'⚠️ РАССЫЛКА ПРЕРВАНА\n\nКампания: {campaign.campaign_id}\nПричина: Аккаунт ограничен Telegram (PEER_FLOOD)\n\nОтправлено до ограничения: {sent_count}\nОшибок: {failed_count}\n\n💡 РЕКОМЕНДАЦИИ:\n• Увеличьте интервал между сообщениями (минимум 15-30 секунд)\n• Уменьшите количество получателей за раз (используйте ограничение 10, 50, 100)\n• Подождите 1-2 часа перед следующей рассылкой\n• Избегайте интервалов менее 10 секунд', parse_mode=None)
                    logger.info(f'Уведомление о PEER_FLOOD отправлено владельцу {campaign.owner_id}')
                except Exception as e:
                    logger.error(f'Ошибка при отправке уведомления о PEER_FLOOD: {e}')
                break
            last_was_new = True
    await crud.update_campaign_stats(campaign.id, total=len(recipients), sent=sent_count, failed=failed_count, duplicates=len(duplicate_recipients))
    await crud.update_campaign_status(campaign.id, 'completed', completed_at=datetime.now())
    logger.info(f'Рассылка {campaign.campaign_id} завершена. Отправлено: {sent_count}, Ошибок: {failed_count}, Дублей: {len(duplicate_recipients)}')
    if duplicate_recipients:
        dup_list = ', '.join([d['recipient'].recipient_identifier for d in duplicate_recipients[:10]])
        if len(duplicate_recipients) > 10:
            dup_list += f', ... и еще {len(duplicate_recipients) - 10}'
        try:
            await bot.send_message(chat_id=campaign.owner_id, text=f'ℹ️ Обнаружено дублей: {len(duplicate_recipients)}\n\nДубли пропущены (сообщение уже отправлялось этим пользователям ранее):\n{dup_list}\n\nПауза при переходе от дубля к новому получателю не применялась.', parse_mode=None)
            logger.info(f'Уведомление о дублях отправлено владельцу {campaign.owner_id}')
        except Exception as e:
            logger.error(f'Ошибка при отправке уведомления о дублях: {e}')
    try:
        report = await generate_personal_report(campaign.id)
        if report:
            await bot.send_message(chat_id=campaign.owner_id, text=report, parse_mode=None)
            logger.info(f'Персональный отчет отправлен владельцу {campaign.owner_id}')
    except Exception as e:
        logger.error(f'Ошибка при отправке персонального отчета: {e}', exc_info=True)
    return {'sent': sent_count, 'failed': failed_count, 'duplicates': len(duplicate_recipients), 'duplicate_list': [d['recipient'].recipient_identifier for d in duplicate_recipients], 'duplicate_recipients': duplicate_recipients}

async def send_duplicates(bot: Bot, campaign: MailingCampaign, template: Template, duplicate_recipients: List[Recipient]) -> Dict:
    logger.warning(f'Попытка отправить дубли для рассылки {campaign.campaign_id} - дубли не отправляются, так как сообщение уже отправлялось')
    return {'sent': 0, 'failed': len(duplicate_recipients)}
    updated_campaign = await crud.get_campaign(campaign.id)
    if updated_campaign:
        await crud.update_campaign_stats(updated_campaign.id, total=updated_campaign.total_recipients, sent=updated_campaign.sent_successfully + sent_count, failed=updated_campaign.sent_failed + failed_count, duplicates=max(0, updated_campaign.duplicates_count - sent_count))
    return {'sent': sent_count, 'failed': failed_count}

async def generate_personal_report(campaign_id: int) -> Optional[str]:
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        return None
    template = await crud.get_template(campaign.template_id)
    if not template:
        return None
    owner = await crud.get_user_by_telegram_id(campaign.owner_id)
    if not owner:
        return None
    history = await crud.get_campaign_sending_history(campaign_id)
    from database import Recipient
    from sqlalchemy import select
    from database import async_session_maker
    duplicates = []
    async with async_session_maker() as session:
        result = await session.execute(select(Recipient).where(Recipient.campaign_id == campaign_id, Recipient.is_duplicate == True))
        duplicate_recipients = list(result.scalars().all())
        duplicates = [r.recipient_identifier for r in duplicate_recipients]
    report = format_personal_report(campaign, template, owner, history, duplicates)
    return report

async def generate_summary_report(date: Optional[datetime]=None) -> str:
    if not date:
        date = datetime.now()
    campaigns = await crud.get_daily_campaigns(date)
    if not campaigns:
        return f'📈 СВОДНЫЙ ОТЧЕТ ПО РАССЫЛКАМ\n\nПериод: {date.strftime('%d.%m.%Y')}\n\nРассылок за день не было.'
    template_ids = list(set((c.template_id for c in campaigns)))
    owner_ids = list(set((c.owner_id for c in campaigns)))
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
    start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
    error_stats = await crud.get_error_statistics(start_date, end_date)
    report = format_summary_report(campaigns, templates, owners, error_stats, date)
    return report

async def send_summary_reports_to_receivers(bot, date: Optional[datetime]=None):
    if not date:
        date = datetime.now()
    report = await generate_summary_report(date)
    receivers = await crud.get_all_report_receivers()
    if not receivers:
        logger.info('Нет получателей сводных отчетов')
        return
    for receiver in receivers:
        try:
            if receiver.telegram_id:
                await bot.send_message(chat_id=receiver.telegram_id, text=report, parse_mode='Markdown')
                logger.info(f'Сводный отчет отправлен получателю {receiver.identifier}')
            elif receiver.identifier_type == 'username':
                try:
                    await bot.send_message(chat_id=f'@{receiver.identifier.lstrip('@')}', text=report, parse_mode='Markdown')
                    logger.info(f'Сводный отчет отправлен получателю {receiver.identifier}')
                except Exception as e:
                    logger.warning(f'Не удалось отправить отчет {receiver.identifier}: {e}')
        except Exception as e:
            logger.error(f'Ошибка при отправке сводного отчета {receiver.identifier}: {e}')
_clients: Dict[int, Client] = {}

async def get_user_client(user_id: int) -> Optional[Client]:
    if user_id in _clients:
        client = _clients[user_id]
        try:
            if hasattr(client, 'is_connected') and client.is_connected:
                return client
        except Exception:
            pass
    user = await crud.get_user_by_telegram_id(user_id)
    if user and user.has_client_auth and user.api_id and user.api_hash:
        api_id = user.api_id
        api_hash = user.api_hash
        phone = user.phone_number
        session_name = f'client_{user_id}'
        logger.info(f'Используем персональный Client API для пользователя {user_id}')
    else:
        if not API_ID or not API_HASH:
            logger.warning(f'У пользователя {user_id} нет Client API и общие данные не настроены')
            return None
        api_id = API_ID
        api_hash = API_HASH
        phone = PHONE_NUMBER
        session_name = 'mailing_client'
        logger.info(f'Используем общий Client API для пользователя {user_id}')
    client = Client(session_name, api_id=api_id, api_hash=api_hash, phone_number=phone)
    try:
        logger.info(f'🔐 Авторизация Client API для пользователя {user_id}...')
        logger.info(f'   Session: {session_name}, API_ID: {api_id}, Phone: {phone}')
        await client.start()
        logger.info(f'✅ Client API авторизован для пользователя {user_id}')
        if user and (not user.has_client_auth):
            try:
                await crud.update_user_client_auth(telegram_id=user_id, has_auth=True)
            except Exception as e:
                logger.warning(f'Не удалось обновить статус авторизации в БД: {e}')
        _clients[user_id] = client
        return client
    except TypeError as e:
        if "can't be used in 'await' expression" in str(e):
            logger.error(f'❌ Ошибка: client.start() вернул None для {user_id}')
            logger.error(f'   Это может означать, что клиент уже запущен или сессия повреждена')
            try:
                _clients[user_id] = client
                return client
            except Exception as e2:
                logger.error(f'❌ Не удалось использовать клиент: {e2}')
                return None
        else:
            raise
    except Exception as e:
        logger.error(f'❌ Ошибка авторизации Client API для {user_id}: {e}', exc_info=True)
        return None

async def check_account_status(user_id: int) -> Dict:
    try:
        client = await get_user_client(user_id)
        if client is None:
            return {'success': False, 'error_type': 'no_client', 'error_details': 'Client API не настроен'}
        try:
            await client.send_message('me', 'test')
            logger.info(f'✅ Проверка статуса аккаунта для {user_id}: аккаунт не ограничен')
            return {'success': True, 'error_type': None, 'error_details': None}
        except PeerFlood as e:
            logger.error(f'⚠️ PEER_FLOOD при проверке статуса аккаунта для {user_id}: {e}')
            return {'success': False, 'error_type': 'peer_flood', 'error_details': 'Аккаунт все еще ограничен Telegram (PEER_FLOOD). Ограничение может быть снято для Bot API, но еще активно для Client API. Подождите еще 1-2 часа.'}
        except Exception as e:
            logger.warning(f'Предупреждение при проверке статуса аккаунта для {user_id}: {e}')
            return {'success': True, 'error_type': None, 'error_details': None}
    except Exception as e:
        logger.error(f'Ошибка при проверке статуса аккаунта для {user_id}: {e}', exc_info=True)
        return {'success': False, 'error_type': 'unknown', 'error_details': f'Ошибка при проверке статуса: {str(e)}'}

async def send_message_as_user(recipient_identifier: str, text: str, sender_user_id: int, media_type: Optional[str]=None, media_file_id: Optional[str]=None) -> dict:
    try:
        client = await get_user_client(sender_user_id)
        if client is None:
            return {'success': False, 'error_type': 'no_client', 'error_details': 'Client API не настроен. Настройте через /setup_my_client или используйте общие настройки в .env', 'telegram_message_id': None}
        chat_id = None
        if recipient_identifier.isdigit() or (recipient_identifier.startswith('-') and recipient_identifier[1:].isdigit()):
            chat_id = int(recipient_identifier)
        else:
            original_identifier = recipient_identifier
            identifier = recipient_identifier.lstrip('@')
            if 't.me/' in identifier or 'telegram.me/' in identifier:
                import re
                invite_match = re.search('(?:t\\.me/|telegram\\.me/)(?:joinchat/|\\+)([a-zA-Z0-9_-]+)', identifier)
                if invite_match:
                    invite_hash = invite_match.group(1)
                    try:
                        chat = await client.join_chat(f'https://t.me/joinchat/{invite_hash}')
                        chat_id = chat.id
                        logger.info(f'Присоединились к приватной группе по invite-ссылке: {chat_id}')
                    except (InviteHashExpired, InviteHashInvalid) as e:
                        logger.warning(f'Недействительная invite-ссылка для {original_identifier}: {e}')
                        return {'success': False, 'error_type': 'invalid_invite', 'error_details': f'Недействительная или истекшая invite-ссылка: {str(e)}', 'telegram_message_id': None}
                    except Exception as e:
                        logger.warning(f'Не удалось присоединиться к группе по invite-ссылке {original_identifier}: {e}')
                        return {'success': False, 'error_type': 'join_failed', 'error_details': f'Не удалось присоединиться к группе: {str(e)}', 'telegram_message_id': None}
                else:
                    match = re.search('(?:t\\.me/|telegram\\.me/)(?:c/)?([a-zA-Z0-9_]+)', identifier)
                    if match:
                        chat_id = match.group(1)
                    else:
                        chat_id = identifier
            else:
                chat_id = identifier
        if isinstance(chat_id, str):
            try:
                chat = await client.get_chat(chat_id)
                chat_id = chat.id
                logger.debug(f'Получен chat_id {chat_id} для {recipient_identifier}')
            except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid, ChannelPrivate) as e:
                logger.warning(f'Не удалось получить информацию о чате {chat_id}: {e}')
                return {'success': False, 'error_type': 'invalid_user', 'error_details': f'Чат не найден или недоступен: {str(e)}', 'telegram_message_id': None}
            except Exception as e:
                logger.warning(f'Ошибка при получении информации о чате {chat_id}: {e}')
                pass
        if isinstance(chat_id, int) and chat_id < 0:
            try:
                chat_member = await client.get_chat_member(chat_id, 'me')
                if chat_member.status not in ['member', 'administrator', 'creator']:
                    logger.warning(f'Пользователь не является участником группы {chat_id}')
                    return {'success': False, 'error_type': 'not_participant', 'error_details': 'Вы не являетесь участником этой группы. Присоединитесь к группе перед отправкой сообщений.', 'telegram_message_id': None}
            except UserNotParticipant:
                logger.warning(f'Пользователь не является участником группы {chat_id}')
                return {'success': False, 'error_type': 'not_participant', 'error_details': 'Вы не являетесь участником этой группы. Присоединитесь к группе перед отправкой сообщений.', 'telegram_message_id': None}
            except Exception as e:
                logger.warning(f'Ошибка при проверке участника группы {chat_id}: {e}')
        if media_type and media_file_id:
            if media_type == 'photo':
                message = await client.send_photo(chat_id=chat_id, photo=media_file_id, caption=text if text else None)
            elif media_type == 'video':
                message = await client.send_video(chat_id=chat_id, video=media_file_id, caption=text if text else None)
            elif media_type == 'document':
                message = await client.send_document(chat_id=chat_id, document=media_file_id, caption=text if text else None)
            elif media_type == 'audio':
                message = await client.send_audio(chat_id=chat_id, audio=media_file_id, caption=text if text else None)
            elif media_type == 'voice':
                message = await client.send_voice(chat_id=chat_id, voice=media_file_id, caption=text if text else None)
            elif media_type == 'video_note':
                message = await client.send_video_note(chat_id=chat_id, video_note=media_file_id)
                if text:
                    await client.send_message(chat_id=chat_id, text=text)
            elif media_type == 'animation':
                message = await client.send_animation(chat_id=chat_id, animation=media_file_id, caption=text if text else None)
            else:
                message = await client.send_document(chat_id=chat_id, document=media_file_id, caption=text if text else None)
        else:
            message = await client.send_message(chat_id=chat_id, text=text)
        logger.info(f'Сообщение отправлено от имени пользователя получателю {recipient_identifier}, message_id: {message.id}')
        return {'success': True, 'error_type': None, 'error_details': None, 'telegram_message_id': message.id}
    except FloodWait as e:
        wait_time = e.value
        logger.warning(f'FloodWait для {recipient_identifier}: нужно подождать {wait_time} секунд')
        await asyncio.sleep(wait_time)
        return await send_message_as_user(recipient_identifier, text, sender_user_id, media_type, media_file_id)
    except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid) as e:
        logger.warning(f'Неверный получатель {recipient_identifier}: {e}')
        return {'success': False, 'error_type': 'invalid_user', 'error_details': f'Пользователь не найден: {str(e)}', 'telegram_message_id': None}
    except ChatWriteForbidden:
        logger.warning(f'Нельзя писать получателю {recipient_identifier}: запрещено')
        return {'success': False, 'error_type': 'privacy', 'error_details': 'Нельзя отправить сообщение этому пользователю', 'telegram_message_id': None}
    except UserPrivacyRestricted:
        logger.warning(f'Ограничения приватности для {recipient_identifier}')
        return {'success': False, 'error_type': 'privacy', 'error_details': 'Ограничения приватности пользователя', 'telegram_message_id': None}
    except UserDeactivated:
        logger.warning(f'Аккаунт {recipient_identifier} деактивирован')
        return {'success': False, 'error_type': 'deleted', 'error_details': 'Аккаунт деактивирован', 'telegram_message_id': None}
    except UserNotParticipant:
        logger.warning(f'Пользователь {recipient_identifier} не является участником группы/канала')
        return {'success': False, 'error_type': 'not_participant', 'error_details': 'Вы не являетесь участником этой группы/канала. Присоединитесь к группе перед отправкой сообщений.', 'telegram_message_id': None}
    except ChatAdminRequired:
        logger.warning(f'Требуются права администратора для отправки в {recipient_identifier}')
        return {'success': False, 'error_type': 'admin_required', 'error_details': 'Требуются права администратора для отправки сообщений в эту группу/канал', 'telegram_message_id': None}
    except ChannelPrivate:
        logger.warning(f'Приватный канал/группа {recipient_identifier} недоступен')
        return {'success': False, 'error_type': 'private_chat', 'error_details': 'Это приватная группа/канал. Используйте invite-ссылку для присоединения или убедитесь, что вы являетесь участником.', 'telegram_message_id': None}
    except PeerFlood as e:
        logger.error(f'⚠️ PEER_FLOOD: Аккаунт ограничен из-за слишком частых отправок для {recipient_identifier}: {e}')
        return {'success': False, 'error_type': 'peer_flood', 'error_details': 'Аккаунт временно ограничен Telegram из-за слишком частых отправок. Увеличьте интервал между сообщениями (минимум 15-30 секунд) или подождите 1-2 часа перед следующей рассылкой.', 'telegram_message_id': None}
    except Exception as e:
        logger.error(f'Неизвестная ошибка при отправке {recipient_identifier}: {e}', exc_info=True)
        return {'success': False, 'error_type': 'unknown', 'error_details': str(e), 'telegram_message_id': None}

async def get_user_groups(user_id: int) -> List[Dict]:
    try:
        client = await get_user_client(user_id)
        if client is None:
            logger.warning(f'Client API не настроен для пользователя {user_id}')
            return []
        groups = []
        async for dialog in client.get_dialogs():
            if dialog.chat.type in ('group', 'supergroup', 'channel'):
                try:
                    members_count = 0
                    try:
                        chat_info = await client.get_chat(dialog.chat.id)
                        if hasattr(chat_info, 'members_count') and chat_info.members_count:
                            members_count = chat_info.members_count
                        elif hasattr(dialog.chat, 'members_count') and dialog.chat.members_count:
                            members_count = dialog.chat.members_count
                    except Exception as e:
                        logger.debug(f'Не удалось получить количество участников для {dialog.chat.id}: {e}')
                        members_count = 0
                    groups.append({'id': dialog.chat.id, 'title': dialog.chat.title or 'Без названия', 'type': dialog.chat.type, 'username': dialog.chat.username, 'members_count': members_count})
                except Exception as e:
                    logger.warning(f'Ошибка при обработке группы {dialog.chat.id}: {e}')
                    continue
        logger.info(f'Найдено {len(groups)} групп/каналов для пользователя {user_id}')
        return groups
    except Exception as e:
        logger.error(f'Ошибка при получении списка групп для пользователя {user_id}: {e}', exc_info=True)
        return []

async def join_chat_by_link(user_id: int, invite_link: str) -> Dict:
    try:
        client = await get_user_client(user_id)
        if client is None:
            return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'error': 'Client API не настроен'}
        if not invite_link.startswith('http'):
            if invite_link.startswith('t.me/'):
                invite_link = f'https://{invite_link}'
            elif invite_link.startswith('+'):
                invite_link = f'https://t.me/joinchat/{invite_link.lstrip('+')}'
            else:
                invite_link = f'https://t.me/joinchat/{invite_link}'
        try:
            chat = await client.join_chat(invite_link)
            logger.info(f'Успешно присоединились к {chat.type} {chat.id} ({chat.title}) по ссылке')
            return {'success': True, 'chat_id': chat.id, 'title': chat.title, 'chat_type': chat.type, 'error': None}
        except UserAlreadyParticipant:
            try:
                logger.info(f'Пользователь уже участник чата по ссылке {invite_link}')
                try:
                    import re
                    hash_match = re.search('joinchat/([a-zA-Z0-9_-]+)', invite_link)
                    if hash_match:
                        return {'success': True, 'chat_id': None, 'title': None, 'chat_type': None, 'error': None, 'message': 'Вы уже являетесь участником этого чата. Чат доступен для использования в рассылках.'}
                    else:
                        return {'success': True, 'chat_id': None, 'title': None, 'chat_type': None, 'error': None, 'message': 'Вы уже являетесь участником этого чата'}
                except Exception as e:
                    logger.warning(f'Не удалось обработать ссылку после UserAlreadyParticipant: {e}')
                    return {'success': True, 'chat_id': None, 'title': None, 'chat_type': None, 'error': None, 'message': 'Вы уже являетесь участником этого чата. Чат доступен для использования в рассылках.'}
            except Exception as e:
                logger.warning(f'Ошибка при обработке UserAlreadyParticipant: {e}')
                return {'success': True, 'chat_id': None, 'title': None, 'chat_type': None, 'error': None, 'message': 'Вы уже являетесь участником этого чата. Чат доступен для использования в рассылках.'}
        except InviteHashExpired:
            return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'error': 'Ссылка истекла или недействительна'}
        except InviteHashInvalid:
            return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'error': 'Неверная ссылка на чат'}
        except Exception as e:
            logger.error(f'Ошибка при присоединении к чату по ссылке {invite_link}: {e}', exc_info=True)
            return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'error': f'Не удалось присоединиться: {str(e)}'}
    except Exception as e:
        logger.error(f'Ошибка при присоединении к чату: {e}', exc_info=True)
        return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'error': str(e)}

async def get_chat_info_by_link(user_id: int, chat_link: str) -> Dict:
    try:
        client = await get_user_client(user_id)
        if client is None:
            return {'success': False, 'chat_id': None, 'title': None, 'members': None, 'error': 'Client API не настроен'}
        if chat_link.startswith('http'):
            import re
            match = re.search('(?:t\\.me/|telegram\\.me/)(?:c/)?([a-zA-Z0-9_]+)', chat_link)
            if match:
                chat_username = match.group(1)
            else:
                return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'members': None, 'error': 'Неверный формат ссылки'}
        elif chat_link.startswith('@'):
            chat_username = chat_link[1:]
        else:
            chat_username = chat_link
        try:
            chat = await client.get_chat(chat_username)
            logger.info(f'Получена информация о чате: ID={chat.id}, Type={chat.type}, Title={chat.title}, Username={getattr(chat, 'username', None)}')
            chat_attrs = {'type': chat.type, 'is_broadcast': getattr(chat, 'is_broadcast', None), 'is_group': getattr(chat, 'is_group', None), 'is_supergroup': getattr(chat, 'is_supergroup', None), 'is_channel': getattr(chat, 'is_channel', None)}
            logger.info(f'Атрибуты чата: {chat_attrs}')
            chat_type_raw = chat.type
            if isinstance(chat_type_raw, ChatType):
                chat_type = chat_type_raw.value if hasattr(chat_type_raw, 'value') else str(chat_type_raw).split('.')[-1].lower()
            elif hasattr(chat_type_raw, 'name'):
                chat_type = chat_type_raw.name.lower()
            else:
                chat_type = str(chat_type_raw).lower()
            logger.info(f'Тип чата (исходный): {chat_type_raw}, (обработанный): {chat_type}')
            if chat_type == 'channel' or (isinstance(chat_type_raw, ChatType) and chat_type_raw == ChatType.CHANNEL):
                chat_type = 'channel'
                logger.info(f'✅ Определен как канал: {chat.id}')
            elif chat_type in ('group', 'supergroup') or (isinstance(chat_type_raw, ChatType) and chat_type_raw in (ChatType.GROUP, ChatType.SUPERGROUP)):
                logger.info(f'✅ Определен как {chat_type}: {chat.id}')
            else:
                logger.warning(f'Неожиданный тип чата: {chat_type} для {chat_username}, проверяем атрибуты...')
                if getattr(chat, 'is_broadcast', False) or getattr(chat, 'is_channel', False):
                    chat_type = 'channel'
                    logger.info(f'Определен как канал по атрибутам is_broadcast/is_channel')
                elif getattr(chat, 'is_supergroup', False):
                    chat_type = 'supergroup'
                    logger.info(f'Определен как супергруппа по атрибуту is_supergroup')
                elif getattr(chat, 'is_group', False):
                    chat_type = 'group'
                    logger.info(f'Определен как группа по атрибуту is_group')
                else:
                    logger.warning(f'Не удалось точно определить тип, но чат существует. Пробуем обработать как канал/группу')
                    if hasattr(chat, 'title') and chat.title:
                        if chat.id < 0:
                            if abs(chat.id) >= 1000000000000:
                                chat_type = 'channel'
                                logger.info(f'Определен как канал по ID: {chat.id}')
                            else:
                                chat_type = 'supergroup'
                                logger.info(f'Определен как супергруппа по ID: {chat.id}')
                        else:
                            chat_type = 'group'
                            logger.info(f'Определен как группа по ID: {chat.id}')
                    else:
                        logger.error(f'Чат не имеет названия, вероятно это личный чат или бот. Тип: {chat_type}')
                        return {'success': False, 'chat_id': chat.id, 'title': None, 'chat_type': chat_type, 'members': None, 'error': f'Это не группа, супергруппа или канал. Тип: {chat_type}. Возможно, это личный чат или бот.'}
            members = None
            if chat_type in ('group', 'supergroup'):
                logger.info(f'Пытаемся получить участников для {chat_type} {chat.id}')
                members = await get_group_members(user_id, chat.id)
                if not members:
                    try:
                        logger.info(f'Пробуем получить участников через Telethon для {chat.id}')
                        members = await get_group_members(user_id, chat.id, use_telethon=True)
                    except Exception as e:
                        logger.warning(f'Не удалось использовать Telethon: {e}')
                if members:
                    logger.info(f'✅ Получено {len(members)} участников для {chat_type} {chat.id}')
                else:
                    logger.warning(f'⚠️ Не удалось получить участников для {chat_type} {chat.id}')
            elif chat_type == 'channel':
                logger.info(f'Канал {chat.id} - участники не получаются (это канал, не группа)')
            return {'success': True, 'chat_id': chat.id, 'title': chat.title, 'chat_type': chat_type, 'members': members, 'error': None}
        except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid, ChannelPrivate) as e:
            return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'members': None, 'error': f'Чат не найден или недоступен: {str(e)}'}
        except Exception as e:
            logger.error(f'Ошибка при получении информации о чате {chat_username}: {e}', exc_info=True)
            return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'members': None, 'error': str(e)}
    except Exception as e:
        logger.error(f'Ошибка при получении информации о чате: {e}', exc_info=True)
        return {'success': False, 'chat_id': None, 'title': None, 'chat_type': None, 'members': None, 'error': str(e)}

async def get_group_members(user_id: int, group_id: int, use_telethon: bool=False) -> List[int]:
    if use_telethon:
        try:
            return await get_group_members_telethon(user_id, group_id)
        except ImportError:
            logger.warning('Telethon не установлен, используем Pyrogram')
        except Exception as e:
            logger.warning(f'Ошибка при использовании Telethon, переключаемся на Pyrogram: {e}')
    try:
        client = await get_user_client(user_id)
        if client is None:
            logger.warning(f'Client API не настроен для пользователя {user_id}')
            return []
        members = []
        try:
            logger.info(f'Начинаем получение участников группы {group_id} через Pyrogram...')
            count = 0
            async for member in client.get_chat_members(group_id):
                count += 1
                if member.user.is_bot or member.user.is_self:
                    continue
                if member.user.id:
                    members.append(member.user.id)
                if count % 100 == 0:
                    logger.info(f'Обработано {count} участников, уникальных пользователей: {len(members)}')
            logger.info(f'Найдено {len(members)} уникальных участников из {count} всего в группе {group_id}')
        except ChatAdminRequired:
            logger.warning(f'Нет прав администратора для получения участников группы {group_id}')
            return []
        except Exception as e:
            logger.warning(f'Ошибка при получении участников группы {group_id} через Pyrogram: {e}')
            if not use_telethon:
                try:
                    logger.info('Пробуем использовать Telethon как альтернативу...')
                    return await get_group_members(user_id, group_id, use_telethon=True)
                except:
                    pass
            return []
        return members
    except Exception as e:
        logger.error(f'Ошибка при получении участников группы {group_id}: {e}', exc_info=True)
        return []

async def get_group_members_telethon(user_id: int, group_id: int) -> List[int]:
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsSearch
        from telethon.errors import ChatAdminRequiredError, UserNotParticipantError
        import os
        user = await crud.get_user_by_telegram_id(user_id)
        if not user:
            raise ValueError(f'Пользователь {user_id} не найден в БД')
        api_id = user.api_id if user.api_id else API_ID
        api_hash = user.api_hash if user.api_hash else API_HASH
        phone = user.phone_number if user.phone_number else PHONE_NUMBER
        if not api_id or not api_hash or (not phone):
            raise ValueError('API_ID, API_HASH или PHONE_NUMBER не настроены')
        session_dir = 'telethon_sessions'
        os.makedirs(session_dir, exist_ok=True)
        session_name = os.path.join(session_dir, f'telethon_{user_id}')
        client = TelegramClient(session_name, api_id, api_hash)
        members = []
        try:
            if not client.is_connected():
                await client.start(phone=phone)
            logger.info(f'Начинаем получение участников группы {group_id} через Telethon...')
            try:
                entity = await client.get_entity(group_id)
            except Exception as e:
                logger.warning(f'Не удалось получить entity для {group_id}, пробуем альтернативный способ: {e}')
                if isinstance(group_id, int):
                    entity = await client.get_entity(int(f'-100{group_id}'))
                else:
                    raise
            offset = 0
            limit = 200
            total = 0
            unique_members = set()
            while True:
                try:
                    participants = await client(GetParticipantsRequest(entity, ChannelParticipantsSearch(''), offset, limit, hash=0))
                except ChatAdminRequiredError:
                    logger.warning(f'Нет прав администратора для получения участников группы {group_id} через Telethon')
                    break
                except UserNotParticipantError:
                    logger.warning(f'Пользователь не является участником группы {group_id}')
                    break
                if not participants.users:
                    break
                for user_obj in participants.users:
                    if user_obj.bot:
                        continue
                    if user_obj.id and user_obj.id not in unique_members:
                        unique_members.add(user_obj.id)
                        members.append(user_obj.id)
                total += len(participants.users)
                offset += len(participants.users)
                logger.info(f'Обработано {total} участников, уникальных пользователей: {len(members)}')
                if len(participants.users) < limit:
                    break
            logger.info(f'Найдено {len(members)} уникальных участников из {total} всего в группе {group_id} через Telethon')
        except ChatAdminRequiredError:
            logger.warning(f'Нет прав администратора для получения участников группы {group_id} через Telethon')
            return []
        except UserNotParticipantError:
            logger.warning(f'Пользователь не является участником группы {group_id}')
            return []
        except Exception as e:
            logger.error(f'Ошибка при получении участников через Telethon: {e}', exc_info=True)
            return []
        finally:
            try:
                if client.is_connected():
                    await client.disconnect()
            except:
                pass
        return members
    except ImportError:
        raise ImportError('Telethon не установлен. Установите: pip install telethon')
    except Exception as e:
        logger.error(f'Ошибка при использовании Telethon: {e}', exc_info=True)
        raise

async def close_client():
    global _clients
    for user_id, client in _clients.items():
        try:
            if client.is_connected:
                await client.stop()
        except Exception as e:
            logger.warning(f'Ошибка при закрытии Client для {user_id}: {e}')
    _clients.clear()
    logger.info('Все Telegram Clients закрыты')
