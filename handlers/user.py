"""
Handlers для пользователей
"""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from database import crud
from utils.parsers import parse_recipients_list, validate_recipients_list, format_recipient_list
from utils.logger import logger
from config import MAIN_ADMIN_ID
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from keyboards.inline import (
    get_templates_keyboard, get_confirm_mailing_keyboard,
    get_campaigns_keyboard
)
from services.report_service import generate_personal_report

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == MAIN_ADMIN_ID


class MailingStates(StatesGroup):
    waiting_for_template = State()
    waiting_for_recipients = State()
    confirm_mailing = State()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Регистрация пользователя и приветствие"""
    user = await crud.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    is_admin_user = is_admin(message.from_user.id)
    
    welcome_text = f"""👋 Добро пожаловать в бота для рассылок!

Вы можете:
📧 Создавать новые рассылки
📊 Просматривать свои рассылки и отчеты
ℹ️ Получать помощь

Используйте меню или команды для навигации."""
    
    if is_admin_user:
        welcome_text += "\n\n🔑 Вы являетесь администратором и имеете доступ к дополнительным функциям."
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(is_admin=is_admin_user)
    )
    logger.info(f"Пользователь {message.from_user.id} зарегистрирован/вошел в бота")


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """Справка по использованию бота"""
    is_admin_user = is_admin(message.from_user.id)
    
    help_text = """ℹ️ СПРАВКА

📧 Новая рассылка - создайте новую рассылку по вашим получателям
📊 Мои рассылки - просмотрите историю ваших рассылок
/report_<ID> - просмотр конкретного отчета (например, /report_123)

Формат списка получателей:
• @username
• user_id (число)
• Ссылки (https://t.me/user, t.me/user)
• Разделители: запятая, пробел, новая строка"""
    
    if is_admin_user:
        help_text += "\n\n🔑 АДМИН-КОМАНДЫ:\n"
        help_text += "/add_template - создать шаблон\n"
        help_text += "/set_report_receivers - настроить получателей отчетов\n"
        help_text += "/templates_list - список шаблонов"
    
    await message.answer(help_text)


@router.message(Command("new_mailing"))
@router.message(F.text == "📧 Новая рассылка")
async def cmd_new_mailing(message: Message, state: FSMContext):
    """Начало создания новой рассылки"""
    templates = await crud.get_all_active_templates()
    
    if not templates:
        await message.answer(
            "❌ Нет доступных шаблонов. Обратитесь к администратору."
        )
        return
    
    await message.answer(
        "Выберите шаблон для рассылки:",
        reply_markup=get_templates_keyboard(templates)
    )
    await state.set_state(MailingStates.waiting_for_template)


@router.callback_query(StateFilter(MailingStates.waiting_for_template), F.data.startswith("template_"))
async def process_template_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора шаблона"""
    if callback.data == "cancel":
        await state.clear()
        await callback.message.edit_text("Отменено.")
        await callback.answer()
        return
    
    template_id = int(callback.data.split("_")[1])
    template = await crud.get_template(template_id)
    
    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    
    await state.update_data(template_id=template_id)
    await callback.message.edit_text(
        f"✅ Выбран шаблон: {template.name}\n\n"
        "Введите список получателей:\n"
        "• @username\n"
        "• user_id\n"
        "• Ссылки (https://t.me/user)\n"
        "• Разделители: запятая, пробел, новая строка",
        reply_markup=None
    )
    await callback.answer()
    await state.set_state(MailingStates.waiting_for_recipients)


@router.callback_query(StateFilter(MailingStates.waiting_for_template), F.data.startswith("templates_page_"))
async def process_templates_pagination(callback: CallbackQuery, state: FSMContext):
    """Обработка пагинации шаблонов"""
    page = int(callback.data.split("_")[2])
    templates = await crud.get_all_active_templates()
    
    await callback.message.edit_reply_markup(
        reply_markup=get_templates_keyboard(templates, page=page)
    )
    await callback.answer()


@router.message(StateFilter(MailingStates.waiting_for_recipients))
async def process_recipients(message: Message, state: FSMContext):
    """Обработка списка получателей"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    
    # Парсим список получателей
    recipients = parse_recipients_list(message.text)
    
    is_valid, error = validate_recipients_list(recipients)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте еще раз:")
        return
    
    data = await state.get_data()
    template_id = data.get("template_id")
    template = await crud.get_template(template_id)
    
    # Создаем рассылку
    campaign = await crud.create_campaign(
        owner_id=message.from_user.id,
        template_id=template_id
    )
    
    # Добавляем получателей
    recipient_data = [
        {"original": r["original"], "normalized": r["normalized"]}
        for r in recipients
    ]
    await crud.add_recipients(campaign.id, recipient_data)
    
    # Сохраняем campaign_id в state для подтверждения
    await state.update_data(campaign_id=campaign.id)
    
    # Показываем превью
    from utils.formatters import format_campaign_preview
    preview = format_campaign_preview(campaign, template, len(recipients))
    
    await message.answer(
        preview,
        reply_markup=get_confirm_mailing_keyboard(campaign.id),
        parse_mode="Markdown"
    )
    await state.set_state(MailingStates.confirm_mailing)


@router.callback_query(StateFilter(MailingStates.confirm_mailing), F.data.startswith("confirm_mailing_"))
async def confirm_mailing(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и запуск рассылки"""
    campaign_id = int(callback.data.split("_")[2])
    
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return
    
    # Проверяем права
    if campaign.owner_id != callback.from_user.id:
        await callback.answer("У вас нет прав на эту рассылку", show_alert=True)
        return
    
    await callback.message.edit_text("✅ Рассылка запущена! Обработка началась...")
    await callback.answer()
    await state.clear()
    
    # Запускаем рассылку в фоне
    from services.mailing_service import process_mailing
    from database.models import Recipient, async_session_maker
    from sqlalchemy import select
    
    bot = callback.bot
    template = await crud.get_template(campaign.template_id)
    
    # Получаем получателей
    async with async_session_maker() as session:
        result = await session.execute(
            select(Recipient).where(Recipient.campaign_id == campaign.id)
        )
        recipients = list(result.scalars().all())
    
    # Запускаем рассылку
    import asyncio
    asyncio.create_task(process_mailing(bot, campaign, template, recipients))
    
    # Отправляем уведомление
    await callback.message.answer(
        f"📧 Рассылка #{campaign.id} запущена!\n"
        f"Идентификатор: {campaign.campaign_id}\n\n"
        f"Отчет будет отправлен после завершения.",
        reply_markup=get_main_keyboard(is_admin=is_admin(callback.from_user.id))
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.message(Command("my_mailings"))
@router.message(F.text == "📊 Мои рассылки")
async def cmd_my_mailings(message: Message):
    """Список рассылок пользователя"""
    campaigns = await crud.get_user_campaigns(message.from_user.id)
    
    if not campaigns:
        await message.answer("📊 У вас пока нет рассылок.")
        return
    
    await message.answer(
        "📊 Ваши рассылки:",
        reply_markup=get_campaigns_keyboard(campaigns)
    )


@router.callback_query(F.data.startswith("campaign_"))
async def view_campaign(callback: CallbackQuery):
    """Просмотр конкретной рассылки"""
    campaign_id = int(callback.data.split("_")[1])
    campaign = await crud.get_campaign(campaign_id)
    
    if not campaign:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return
    
    # Проверяем права
    if campaign.owner_id != callback.from_user.id and not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав на эту рассылку", show_alert=True)
        return
    
    # Генерируем отчет
    report = await generate_personal_report(campaign_id)
    
    if report:
        try:
            await callback.message.edit_text(report, parse_mode="Markdown")
        except Exception as e:
            # Если сообщение слишком длинное, отправляем новое
            await callback.message.answer(report, parse_mode="Markdown")
    else:
        await callback.message.edit_text("❌ Не удалось сгенерировать отчет.")
    
    await callback.answer()


@router.callback_query(F.data.startswith("campaigns_page_"))
async def process_campaigns_pagination(callback: CallbackQuery):
    """Обработка пагинации рассылок"""
    page = int(callback.data.split("_")[2])
    campaigns = await crud.get_user_campaigns(callback.from_user.id)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_campaigns_keyboard(campaigns, page=page)
    )
    await callback.answer()


@router.message(Command("report"))
async def cmd_report(message: Message):
    """Просмотр отчета по ID рассылки"""
    # Парсим команду /report_123
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /report <ID_рассылки>\nПример: /report 123")
        return
    
    try:
        campaign_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный формат ID. Используйте число.")
        return
    
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await message.answer("❌ Рассылка не найдена.")
        return
    
    # Проверяем права
    if campaign.owner_id != message.from_user.id and not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав на просмотр этого отчета.")
        return
    
    report = await generate_personal_report(campaign_id)
    if report:
        await message.answer(report, parse_mode="Markdown")
    else:
        await message.answer("❌ Не удалось сгенерировать отчет.")
