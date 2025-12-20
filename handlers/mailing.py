"""
Handlers для обработки дублей в рассылках
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import crud
from database.models import Recipient, async_session_maker
from sqlalchemy import select
from services.mailing_service import send_duplicates
from keyboards.inline import get_duplicates_keyboard
from utils.logger import logger

router = Router()


@router.callback_query(F.data.startswith("send_duplicates_"))
async def handle_send_duplicates(callback: CallbackQuery):
    """Обработка запроса на отправку дублей"""
    campaign_id = int(callback.data.split("_")[2])
    
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return
    
    # Проверяем права
    if campaign.owner_id != callback.from_user.id:
        await callback.answer("У вас нет прав на эту рассылку", show_alert=True)
        return
    
    # Получаем дубли
    async with async_session_maker() as session:
        result = await session.execute(
            select(Recipient).where(
                Recipient.campaign_id == campaign_id,
                Recipient.is_duplicate == True
            )
        )
        duplicate_recipients = list(result.scalars().all())
    
    if not duplicate_recipients:
        await callback.answer("Нет дублей для отправки", show_alert=True)
        return
    
    await callback.message.edit_text("✅ Отправка дублей начата...")
    await callback.answer()
    
    # Получаем шаблон
    template = await crud.get_template(campaign.template_id)
    
    # Отправляем дубли
    result = await send_duplicates(
        callback.bot,
        campaign,
        template,
        duplicate_recipients
    )
    
    await callback.message.answer(
        f"✅ Дубли отправлены!\n"
        f"Успешно: {result['sent']}\n"
        f"Ошибок: {result['failed']}"
    )
    logger.info(f"Дубли отправлены для рассылки {campaign.campaign_id}")


@router.callback_query(F.data.startswith("skip_duplicates_"))
async def handle_skip_duplicates(callback: CallbackQuery):
    """Пропуск дублей"""
    campaign_id = int(callback.data.split("_")[2])
    
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return
    
    await callback.message.edit_text("✅ Дубли пропущены.")
    await callback.answer()
    logger.info(f"Дубли пропущены для рассылки {campaign.campaign_id}")
