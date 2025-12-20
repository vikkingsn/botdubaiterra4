"""
Handlers для администратора
"""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from database import crud
from database.models import async_session_maker
from utils.validation import validate_template_name, validate_template_text
from utils.logger import logger
from config import MAIN_ADMIN_ID
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from keyboards.inline import get_templates_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == MAIN_ADMIN_ID


class TemplateStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_text = State()


class ReportReceiversStates(StatesGroup):
    waiting_for_receivers = State()


@router.message(Command("add_template"))
@router.message(F.text == "📝 Шаблоны")
async def cmd_add_template(message: Message, state: FSMContext):
    """Начало создания шаблона"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    await message.answer(
        "Введите название шаблона:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(TemplateStates.waiting_for_name)


@router.message(StateFilter(TemplateStates.waiting_for_name))
async def process_template_name(message: Message, state: FSMContext):
    """Обработка названия шаблона"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    is_valid, error = validate_template_name(message.text)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте еще раз:")
        return
    
    await state.update_data(template_name=message.text)
    await message.answer(
        "Введите текст сообщения для рассылки (поддерживается Markdown):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(TemplateStates.waiting_for_text)


@router.message(StateFilter(TemplateStates.waiting_for_text))
async def process_template_text(message: Message, state: FSMContext):
    """Обработка текста шаблона"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    is_valid, error = validate_template_text(message.text)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте еще раз:")
        return
    
    data = await state.get_data()
    template_name = data.get("template_name")
    
    # Создаем шаблон
    template = await crud.create_template(
        name=template_name,
        text=message.text,
        created_by=message.from_user.id
    )
    
    await state.clear()
    await message.answer(
        f"✅ Шаблон '{template_name}' сохранен. ID: #{template.id}",
        reply_markup=get_main_keyboard(is_admin=True)
    )
    logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {message.from_user.id}")


@router.message(Command("set_report_receivers"))
async def cmd_set_report_receivers(message: Message, state: FSMContext):
    """Начало настройки получателей отчетов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    await message.answer(
        "Введите список получателей сводных отчетов.\n"
        "Формат: @username или user_id через запятую/пробел\n"
        "Пример: @user1 @user2 123456789",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ReportReceiversStates.waiting_for_receivers)


@router.message(StateFilter(ReportReceiversStates.waiting_for_receivers))
async def process_report_receivers(message: Message, state: FSMContext):
    """Обработка списка получателей отчетов"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    # Парсим список
    identifiers = message.text.replace(",", " ").split()
    
    if not identifiers:
        await message.answer("❌ Список пуст. Попробуйте еще раз:")
        return
    
    # Добавляем получателей
    receivers = await crud.add_report_receivers(identifiers)
    
    await state.clear()
    await message.answer(
        f"✅ Добавлено получателей сводных отчетов: {len(receivers)}",
        reply_markup=get_main_keyboard(is_admin=True)
    )
    logger.info(f"Добавлено {len(receivers)} получателей отчетов пользователем {message.from_user.id}")


@router.message(Command("templates_list"))
async def cmd_templates_list(message: Message):
    """Список всех шаблонов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    templates = await crud.get_all_active_templates()
    
    if not templates:
        await message.answer("📝 Шаблонов пока нет.")
        return
    
    text = "📝 Список шаблонов:\n\n"
    for template in templates:
        text += f"#{template.id} - {template.name}\n"
    
    await message.answer(text)
