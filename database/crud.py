"""
CRUD операции для работы с базой данных
"""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User, Template, MailingCampaign, Recipient, 
    SendingHistory, ReportReceiver, async_session_maker
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


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


# ========== TEMPLATE OPERATIONS ==========

async def create_template(name: str, text: str, created_by: int) -> Template:
    """Создать шаблон"""
    async with async_session_maker() as session:
        template = Template(
            name=name,
            text=text,
            created_by=created_by
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


# ========== CAMPAIGN OPERATIONS ==========

async def create_campaign(owner_id: int, template_id: int) -> MailingCampaign:
    """Создать новую рассылку"""
    async with async_session_maker() as session:
        # Генерируем уникальный ID рассылки
        campaign_id = f"MAIL-{uuid.uuid4().hex[:8].upper()}"
        
        campaign = MailingCampaign(
            campaign_id=campaign_id,
            owner_id=owner_id,
            template_id=template_id,
            status="pending"
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

async def add_report_receivers(identifiers: List[str]) -> List[ReportReceiver]:
    """Добавить получателей сводных отчетов"""
    async with async_session_maker() as session:
        receivers = []
        for identifier in identifiers:
            identifier = identifier.strip()
            if not identifier:
                continue
            
            # Определяем тип идентификатора
            if identifier.startswith("@"):
                identifier_type = "username"
                normalized = identifier.lower()
            else:
                try:
                    telegram_id = int(identifier)
                    identifier_type = "user_id"
                    normalized = str(telegram_id)
                except ValueError:
                    continue
            
            # Проверяем, существует ли уже
            result = await session.execute(
                select(ReportReceiver).where(ReportReceiver.identifier == normalized)
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                receiver = ReportReceiver(
                    identifier=normalized,
                    identifier_type=identifier_type
                )
                session.add(receiver)
                receivers.append(receiver)
        
        await session.commit()
        return receivers


async def get_all_report_receivers() -> List[ReportReceiver]:
    """Получить всех активных получателей отчетов"""
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
