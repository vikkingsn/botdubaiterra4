"""
Модели базы данных
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, 
    Index, func
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import DATABASE_URL

Base = declarative_base()


class User(Base):
    """Пользователи бота"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Client API настройки (для отправки от имени пользователя)
    api_id = Column(Integer, nullable=True)
    api_hash = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    has_client_auth = Column(Boolean, default=False)  # Авторизован ли Client API
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    campaigns = relationship("MailingCampaign", back_populates="owner", cascade="all, delete-orphan")


class Template(Base):
    """Шаблоны сообщений для рассылок"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Медиа файлы (file_id из Telegram)
    media_type = Column(String(50), nullable=True)  # photo, video, document, audio, voice, video_note, animation
    media_file_id = Column(String(255), nullable=True)  # file_id медиа файла
    media_file_unique_id = Column(String(255), nullable=True)  # file_unique_id для проверки уникальности
    
    # Связи
    campaigns = relationship("MailingCampaign", back_populates="template")


class MailingCampaign(Base):
    """Информация о рассылках"""
    __tablename__ = "mailing_campaigns"
    
    id = Column(Integer, primary_key=True)
    campaign_id = Column(String(50), unique=True, nullable=False, index=True)  # MAIL-789-ABCD
    owner_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    total_recipients = Column(Integer, default=0)
    sent_successfully = Column(Integer, default=0)
    sent_failed = Column(Integer, default=0)
    duplicates_count = Column(Integer, default=0)
    delay_seconds = Column(Integer, default=5)  # Интервал между сообщениями в секундах
    max_recipients = Column(Integer, nullable=True)  # Максимальное количество получателей для рассылки (10, 50, 100, 300, 500)
    created_at = Column(DateTime, default=func.now())
    
    # Связи
    owner = relationship("User", back_populates="campaigns")
    template = relationship("Template", back_populates="campaigns")
    recipients = relationship("Recipient", back_populates="campaign", cascade="all, delete-orphan")
    sending_history = relationship("SendingHistory", back_populates="campaign", cascade="all, delete-orphan")


class Recipient(Base):
    """Получатели рассылок"""
    __tablename__ = "recipients"
    
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("mailing_campaigns.id"), nullable=False)
    recipient_identifier = Column(String(255), nullable=False)  # username, user_id, или ссылка
    normalized_identifier = Column(String(255), nullable=False, index=True)  # нормализованный формат
    is_duplicate = Column(Boolean, default=False)
    previous_campaign_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Связи
    campaign = relationship("MailingCampaign", back_populates="recipients")
    
    # Индекс для быстрого поиска дублей
    __table_args__ = (
        Index('idx_template_recipient', 'normalized_identifier'),
    )


class SendingHistory(Base):
    """Детальная история отправок"""
    __tablename__ = "sending_history"
    
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("mailing_campaigns.id"), nullable=False)
    recipient_identifier = Column(String(255), nullable=False)
    success = Column(Boolean, nullable=False)
    error_type = Column(String(100), nullable=True)  # blocked, invalid_user, deleted, privacy, rate_limit, technical, unknown
    error_details = Column(Text, nullable=True)
    telegram_message_id = Column(Integer, nullable=True)
    sent_at = Column(DateTime, default=func.now())
    
    # Связи
    campaign = relationship("MailingCampaign", back_populates="sending_history")


class ReportReceiverList(Base):
    """Списки получателей сводных отчетов"""
    __tablename__ = "report_receiver_lists"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)  # Название списка
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    receivers = relationship("ReportReceiver", back_populates="list", cascade="all, delete-orphan")


class ReportReceiver(Base):
    """Получатели сводных отчетов"""
    __tablename__ = "report_receivers"
    
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey("report_receiver_lists.id"), nullable=False)  # Связь со списком
    identifier = Column(String(255), nullable=False)  # username или user_id
    identifier_type = Column(String(20), nullable=False)  # username или user_id
    telegram_id = Column(Integer, nullable=True)  # заполняется при первом отчете
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    # Связи
    list = relationship("ReportReceiverList", back_populates="receivers")


class BotGroup(Base):
    """Группы и каналы, в которых находится бот"""
    __tablename__ = "bot_groups"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False, index=True)  # ID чата (может быть отрицательным для групп)
    title = Column(String(255), nullable=True)  # Название группы/канала
    username = Column(String(255), nullable=True)  # Username группы/канала (если есть)
    chat_type = Column(String(50), nullable=False)  # group, supergroup, channel
    is_active = Column(Boolean, default=True)  # Активна ли группа (бот не удален)
    members_count = Column(Integer, nullable=True)  # Количество участников (если доступно)
    added_at = Column(DateTime, default=func.now())  # Когда бот был добавлен
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# Создание движка и сессии
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Инициализация базы данных (создание таблиц)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Закрытие соединения с БД"""
    await engine.dispose()
