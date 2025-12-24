"""
CRUD операции для работы с базой данных
"""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User, Template, MailingCampaign, Recipient, 
    SendingHistory, ReportReceiver, ReportReceiverList, BotGroup, async_session_maker
)
import uuid


# ========== USER OPERATIONS ==========

async def get_or_create_user(telegram_id: int, username: Optional[str] = None, 
                             first_name: Optional[str] = None, 
                             last_name: Optional[str] = None) -> User:
    """Получить или создать пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Обновляем данные пользователя
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.updated_at = datetime.now()
            await session.commit()
            await session.refresh(user)
        
        return user


async def update_user_client_auth(telegram_id: int, api_id: Optional[int] = None,
                                  api_hash: Optional[str] = None, 
                                  phone_number: Optional[str] = None,
                                  has_auth: bool = True) -> User:
    """Обновить настройки Client API для пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"Пользователь {telegram_id} не найден")
        
        if api_id is not None:
            user.api_id = api_id
        if api_hash is not None:
            user.api_hash = api_hash
        if phone_number is not None:
            user.phone_number = phone_number
        user.has_client_auth = has_auth
        user.updated_at = datetime.now()
        
        await session.commit()
        await session.refresh(user)
        return user


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


# ========== TEMPLATE OPERATIONS ==========

async def create_template(name: str, text: str, created_by: int, 
                         media_type: Optional[str] = None,
                         media_file_id: Optional[str] = None,
                         media_file_unique_id: Optional[str] = None) -> Template:
    """Создать шаблон"""
    async with async_session_maker() as session:
        template = Template(
            name=name,
            text=text,
            created_by=created_by,
            media_type=media_type,
            media_file_id=media_file_id,
            media_file_unique_id=media_file_unique_id
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return template


async def get_template(template_id: int) -> Optional[Template]:
    """Получить шаблон по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Template).where(Template.id == template_id)
        )
        return result.scalar_one_or_none()


async def get_all_active_templates() -> List[Template]:
    """Получить все активные шаблоны"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Template).where(Template.is_active == True).order_by(Template.created_at.desc())
        )
        return list(result.scalars().all())


async def update_template(template_id: int, name: Optional[str] = None, text: Optional[str] = None,
                         media_type: Optional[str] = None, media_file_id: Optional[str] = None,
                         media_file_unique_id: Optional[str] = None) -> Optional[Template]:
    """Обновить шаблон"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            return None
        
        if name is not None:
            template.name = name
        if text is not None:
            template.text = text
        if media_type is not None:
            template.media_type = media_type
        if media_file_id is not None:
            template.media_file_id = media_file_id
        if media_file_unique_id is not None:
            template.media_file_unique_id = media_file_unique_id
        
        await session.commit()
        await session.refresh(template)
        return template


async def delete_template(template_id: int) -> bool:
    """Удалить шаблон (пометить как неактивный)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            return False
        
        template.is_active = False
        await session.commit()
        return True


# ========== CAMPAIGN OPERATIONS ==========

async def create_campaign(owner_id: int, template_id: int, delay_seconds: int = 5, max_recipients: Optional[int] = None) -> MailingCampaign:
    """Создать новую рассылку
    
    Args:
        owner_id: ID владельца рассылки
        template_id: ID шаблона
        delay_seconds: Интервал между сообщениями в секундах (по умолчанию 5)
        max_recipients: Максимальное количество получателей (10, 50, 100, 300, 500)
    """
    async with async_session_maker() as session:
        # Генерируем уникальный ID рассылки
        campaign_id = f"MAIL-{uuid.uuid4().hex[:8].upper()}"
        
        campaign = MailingCampaign(
            campaign_id=campaign_id,
            owner_id=owner_id,
            template_id=template_id,
            status="pending",
            delay_seconds=delay_seconds,
            max_recipients=max_recipients
        )
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)
        return campaign


async def get_campaign(campaign_id: int) -> Optional[MailingCampaign]:
    """Получить рассылку по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MailingCampaign).where(MailingCampaign.id == campaign_id)
        )
        return result.scalar_one_or_none()


async def get_campaign_by_campaign_id(campaign_id: str) -> Optional[MailingCampaign]:
    """Получить рассылку по campaign_id (MAIL-XXX-XXXX)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MailingCampaign).where(MailingCampaign.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()


async def get_user_campaigns(owner_id: int, limit: int = 20) -> List[MailingCampaign]:
    """Получить рассылки пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MailingCampaign)
            .where(MailingCampaign.owner_id == owner_id)
            .order_by(MailingCampaign.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def update_campaign_status(campaign_id: int, status: str, 
                                 started_at: Optional[datetime] = None,
                                 completed_at: Optional[datetime] = None):
    """Обновить статус рассылки"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MailingCampaign).where(MailingCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.status = status
            if started_at:
                campaign.started_at = started_at
            if completed_at:
                campaign.completed_at = completed_at
            await session.commit()


async def update_campaign_stats(campaign_id: int, total: int, sent: int, 
                                failed: int, duplicates: int):
    """Обновить статистику рассылки"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MailingCampaign).where(MailingCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.total_recipients = total
            campaign.sent_successfully = sent
            campaign.sent_failed = failed
            campaign.duplicates_count = duplicates
            await session.commit()


# ========== RECIPIENT OPERATIONS ==========

async def add_recipients(campaign_id: int, recipients: List[Dict]) -> List[Recipient]:
    """Добавить получателей к рассылке"""
    async with async_session_maker() as session:
        recipient_objects = []
        for rec in recipients:
            recipient = Recipient(
                campaign_id=campaign_id,
                recipient_identifier=rec["original"],
                normalized_identifier=rec["normalized"]
            )
            recipient_objects.append(recipient)
            session.add(recipient)
        
        await session.commit()
        return recipient_objects


async def check_duplicate(template_id: int, normalized_identifier: str) -> Optional[Dict]:
    """Проверить, отправлялось ли уже сообщение этому получателю"""
    async with async_session_maker() as session:
        # Ищем в истории отправок успешные отправки с таким же шаблоном
        result = await session.execute(
            select(SendingHistory, MailingCampaign)
            .join(MailingCampaign, SendingHistory.campaign_id == MailingCampaign.id)
            .where(
                and_(
                    MailingCampaign.template_id == template_id,
                    SendingHistory.recipient_identifier == normalized_identifier,
                    SendingHistory.success == True
                )
            )
            .order_by(SendingHistory.sent_at.desc())
            .limit(1)
        )
        
        row = result.first()
        if row:
            history, campaign = row
            return {
                "is_duplicate": True,
                "previous_campaign_id": campaign.id,
                "previous_time": history.sent_at,
                "campaign_id": campaign.campaign_id
            }
        
        return {"is_duplicate": False}


async def mark_recipient_as_duplicate(recipient_id: int, previous_campaign_id: int):
    """Пометить получателя как дубль"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        recipient = result.scalar_one_or_none()
        if recipient:
            recipient.is_duplicate = True
            recipient.previous_campaign_id = previous_campaign_id
            await session.commit()


# ========== SENDING HISTORY OPERATIONS ==========

async def add_sending_history(campaign_id: int, recipient_identifier: str, 
                             success: bool, error_type: Optional[str] = None,
                             error_details: Optional[str] = None,
                             telegram_message_id: Optional[int] = None):
    """Добавить запись в историю отправок"""
    async with async_session_maker() as session:
        history = SendingHistory(
            campaign_id=campaign_id,
            recipient_identifier=recipient_identifier,
            success=success,
            error_type=error_type,
            error_details=error_details,
            telegram_message_id=telegram_message_id
        )
        session.add(history)
        await session.commit()
        return history


async def get_campaign_sending_history(campaign_id: int) -> List[SendingHistory]:
    """Получить историю отправок для рассылки"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(SendingHistory)
            .where(SendingHistory.campaign_id == campaign_id)
            .order_by(SendingHistory.sent_at)
        )
        return list(result.scalars().all())


# ========== REPORT RECEIVER OPERATIONS ==========

# ========== REPORT RECEIVER LIST OPERATIONS ==========

async def create_report_receiver_list(name: str) -> ReportReceiverList:
    """Создать новый список получателей отчетов"""
    async with async_session_maker() as session:
        receiver_list = ReportReceiverList(
            name=name,
            is_active=True
        )
        session.add(receiver_list)
        await session.commit()
        await session.refresh(receiver_list)
        return receiver_list


async def get_all_report_receiver_lists() -> List[ReportReceiverList]:
    """Получить все активные списки получателей отчетов"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiverList)
            .where(ReportReceiverList.is_active == True)
            .order_by(ReportReceiverList.created_at.desc())
        )
        return list(result.scalars().all())


async def get_report_receiver_list(list_id: int) -> Optional[ReportReceiverList]:
    """Получить список получателей по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiverList).where(ReportReceiverList.id == list_id)
        )
        return result.scalar_one_or_none()


async def update_report_receiver_list(list_id: int, name: Optional[str] = None) -> Optional[ReportReceiverList]:
    """Обновить список получателей"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiverList).where(ReportReceiverList.id == list_id)
        )
        receiver_list = result.scalar_one_or_none()
        
        if not receiver_list:
            return None
        
        if name is not None:
            receiver_list.name = name
        receiver_list.updated_at = datetime.now()
        
        await session.commit()
        await session.refresh(receiver_list)
        return receiver_list


async def delete_report_receiver_list(list_id: int) -> bool:
    """Удалить список получателей (пометить как неактивный)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiverList).where(ReportReceiverList.id == list_id)
        )
        receiver_list = result.scalar_one_or_none()
        
        if not receiver_list:
            return False
        
        receiver_list.is_active = False
        await session.commit()
        return True


async def get_receivers_by_list(list_id: int) -> List[ReportReceiver]:
    """Получить всех получателей из списка"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiver)
            .where(
                and_(
                    ReportReceiver.list_id == list_id,
                    ReportReceiver.is_active == True
                )
            )
            .order_by(ReportReceiver.created_at.desc())
        )
        return list(result.scalars().all())


async def add_report_receivers_to_list(list_id: int, identifiers: List[str]) -> List[ReportReceiver]:
    """Добавить получателей в список
    
    Поддерживает пользователей, группы и каналы
    """
    from utils.parsers import normalize_identifier
    
    async with async_session_maker() as session:
        receivers = []
        for identifier in identifiers:
            identifier = identifier.strip()
            if not identifier:
                continue
            
            # Нормализуем идентификатор (поддерживает пользователей, группы, каналы)
            normalized = normalize_identifier(identifier)
            if not normalized:
                continue
            
            # Определяем тип идентификатора
            if identifier.isdigit():
                identifier_type = "user_id"
            elif identifier.startswith("@"):
                identifier_type = "username"  # Может быть пользователь или группа
            elif "t.me" in identifier or "telegram.me" in identifier:
                identifier_type = "link"  # Может быть ссылка на пользователя или группу
            else:
                identifier_type = "username"
            
            # Проверяем, существует ли уже в этом списке
            result = await session.execute(
                select(ReportReceiver).where(
                    and_(
                        ReportReceiver.list_id == list_id,
                        ReportReceiver.identifier == normalized
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                receiver = ReportReceiver(
                    list_id=list_id,
                    identifier=normalized,
                    identifier_type=identifier_type
                )
                session.add(receiver)
                receivers.append(receiver)
        
        await session.commit()
        return receivers


async def delete_report_receiver(receiver_id: int) -> bool:
    """Удалить получателя из списка (пометить как неактивный)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiver).where(ReportReceiver.id == receiver_id)
        )
        receiver = result.scalar_one_or_none()
        
        if not receiver:
            return False
        
        receiver.is_active = False
        await session.commit()
        return True


async def get_all_report_receivers() -> List[ReportReceiver]:
    """Получить всех активных получателей отчетов (из всех списков)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiver).where(ReportReceiver.is_active == True)
        )
        return list(result.scalars().all())


async def update_report_receiver_telegram_id(identifier: str, telegram_id: int):
    """Обновить Telegram ID получателя отчетов"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReportReceiver).where(ReportReceiver.identifier == identifier)
        )
        receiver = result.scalar_one_or_none()
        if receiver:
            receiver.telegram_id = telegram_id
            await session.commit()


# ========== STATISTICS OPERATIONS ==========

async def get_daily_campaigns(date: datetime) -> List[MailingCampaign]:
    """Получить все рассылки за день"""
    async with async_session_maker() as session:
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        result = await session.execute(
            select(MailingCampaign)
            .where(
                and_(
                    MailingCampaign.created_at >= start_date,
                    MailingCampaign.created_at <= end_date
                )
            )
            .order_by(MailingCampaign.created_at.desc())
        )
        return list(result.scalars().all())


async def get_error_statistics(start_date: datetime, end_date: datetime) -> Dict:
    """Получить статистику ошибок за период"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(
                SendingHistory.error_type,
                func.count(SendingHistory.id).label("count")
            )
            .join(MailingCampaign, SendingHistory.campaign_id == MailingCampaign.id)
            .where(
                and_(
                    SendingHistory.success == False,
                    MailingCampaign.created_at >= start_date,
                    MailingCampaign.created_at <= end_date
                )
            )
            .group_by(SendingHistory.error_type)
            .order_by(func.count(SendingHistory.id).desc())
        )
        
        error_stats = {}
        for row in result.all():
            error_stats[row.error_type or "unknown"] = row.count
        
        return error_stats


# ========== BOT GROUP OPERATIONS ==========

async def add_or_update_bot_group(
    chat_id: int,
    title: Optional[str] = None,
    username: Optional[str] = None,
    chat_type: str = "group",
    members_count: Optional[int] = None,
    is_active: bool = True
) -> BotGroup:
    """Добавить или обновить группу бота"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotGroup).where(BotGroup.chat_id == chat_id)
        )
        bot_group = result.scalar_one_or_none()
        
        if not bot_group:
            bot_group = BotGroup(
                chat_id=chat_id,
                title=title,
                username=username,
                chat_type=chat_type,
                members_count=members_count,
                is_active=is_active
            )
            session.add(bot_group)
        else:
            # Обновляем существующую запись
            bot_group.title = title or bot_group.title
            bot_group.username = username or bot_group.username
            bot_group.chat_type = chat_type
            bot_group.members_count = members_count or bot_group.members_count
            bot_group.is_active = is_active
            bot_group.updated_at = datetime.now()
        
        await session.commit()
        await session.refresh(bot_group)
        return bot_group


async def get_bot_group(chat_id: int) -> Optional[BotGroup]:
    """Получить группу бота по chat_id"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotGroup).where(BotGroup.chat_id == chat_id)
        )
        return result.scalar_one_or_none()


async def get_all_bot_groups(active_only: bool = True) -> List[BotGroup]:
    """Получить все группы бота"""
    async with async_session_maker() as session:
        query = select(BotGroup)
        if active_only:
            query = query.where(BotGroup.is_active == True)
        query = query.order_by(BotGroup.title)
        result = await session.execute(query)
        return list(result.scalars().all())


async def remove_bot_group(chat_id: int) -> bool:
    """Удалить группу бота (пометить как неактивную)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotGroup).where(BotGroup.chat_id == chat_id)
        )
        bot_group = result.scalar_one_or_none()
        
        if bot_group:
            bot_group.is_active = False
            bot_group.updated_at = datetime.now()
            await session.commit()
            return True
        return False


async def update_bot_group_members_count(chat_id: int, members_count: int):
    """Обновить количество участников группы"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotGroup).where(BotGroup.chat_id == chat_id)
        )
        bot_group = result.scalar_one_or_none()
        
        if bot_group:
            bot_group.members_count = members_count
            bot_group.updated_at = datetime.now()
            await session.commit()
