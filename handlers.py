from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as crud
from database import async_session_maker
from utils import validate_template_name, validate_template_text
from utils import logger
from config import MAIN_ADMIN_ID
from keyboards import get_main_keyboard, get_cancel_keyboard
from keyboards import get_templates_keyboard
from keyboards import get_cancel_keyboard
router = Router()

def is_admin(user_id: int) -> bool:
    return user_id == MAIN_ADMIN_ID

class TemplateStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_text = State()
    waiting_for_media = State()
    editing_name = State()
    editing_text = State()
    editing_media = State()

class ReportReceiversStates(StatesGroup):
    waiting_for_list_name = State()
    waiting_for_receivers = State()
    editing_list_name = State()

@router.message(Command('add_template'))
@router.message(F.text == '📝 Шаблоны')
async def cmd_add_template(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer('❌ У вас нет прав для выполнения этой команды.')
        return
    templates = await crud.get_all_active_templates()
    text = '📝 УПРАВЛЕНИЕ ШАБЛОНАМИ\n\n'
    if templates:
        text += '📋 Существующие шаблоны:\n'
        for i, template in enumerate(templates, 1):
            text += f'{i}. {template.name}\n'
        text += '\n'
    else:
        text += '📋 Шаблонов пока нет.\n\n'
    text += '💡 Выберите шаблон из списка или создайте новый:'
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = []
    for template in templates:
        keyboard.append([InlineKeyboardButton(text=f'📝 {template.name}', callback_data=f'select_template_{template.id}')])
    keyboard.append([InlineKeyboardButton(text='➕ Новый шаблон', callback_data='new_template')])
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_templates')])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(text, reply_markup=reply_markup)
    await state.clear()

@router.callback_query(F.data == 'save_template_with_media')
async def save_template_with_media_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    data = await state.get_data()
    template_name = data.get('template_name')
    template_text = data.get('template_text', '')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    media_file_unique_id = data.get('media_file_unique_id')
    template = await crud.create_template(name=template_name, text=template_text, created_by=callback.from_user.id, media_type=media_type, media_file_id=media_file_id, media_file_unique_id=media_file_unique_id)
    await callback.message.edit_text(
        f"✅ Шаблон '{template_name}' сохранен с медиа. ID: #{template.id}",
        reply_markup=None
    )
    await callback.answer('Шаблон сохранен!')
    logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {callback.from_user.id}")

@router.callback_query(F.data == 'save_template_no_media')
async def save_template_no_media_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    data = await state.get_data()
    template_name = data.get('template_name')
    template_text = data.get('template_text')
    template = await crud.create_template(name=template_name, text=template_text, created_by=callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(
        f"✅ Шаблон '{template_name}' сохранен. ID: #{template.id}",
        reply_markup=None
    )
    await callback.answer('Шаблон сохранен!')
    logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {callback.from_user.id}")

@router.callback_query(F.data == 'add_media_to_template')
async def add_media_to_template_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    await callback.message.edit_text('📎 Отправьте медиа файл (фото, видео, документ и т.д.):\n\nПоддерживаемые типы:\n• 📷 Фото\n• 🎥 Видео\n• 📄 Документ\n• 🎵 Аудио\n• 🎤 Голосовое сообщение\n• 📹 Видео-кружок\n• 🎬 GIF/Анимация\n\nТекст подписи можно добавить к медиа.', reply_markup=get_cancel_keyboard())
    await state.set_state(TemplateStates.waiting_for_media)
    await callback.answer()

@router.callback_query(F.data == 'add_more_media')
async def add_more_media_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    await callback.answer('⚠️ Пока поддерживается только одно медиа на шаблон. Используйте существующее или замените его.', show_alert=True)

@router.callback_query(F.data == 'cancel_template')
async def cancel_template_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Создание шаблона отменено.', reply_markup=None)
    await callback.answer('Отменено')

@router.message(StateFilter(TemplateStates.waiting_for_media))
async def process_template_media(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    media_type = None
    media_file_id = None
    media_file_unique_id = None
    caption = message.caption or ''
    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
        media_file_unique_id = message.photo[-1].file_unique_id
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
        media_file_unique_id = message.video.file_unique_id
    elif message.document:
        media_type = 'document'
        media_file_id = message.document.file_id
        media_file_unique_id = message.document.file_unique_id
    elif message.audio:
        media_type = 'audio'
        media_file_id = message.audio.file_id
        media_file_unique_id = message.audio.file_unique_id
    elif message.voice:
        media_type = 'voice'
        media_file_id = message.voice.file_id
        media_file_unique_id = message.voice.file_unique_id
    elif message.video_note:
        media_type = 'video_note'
        media_file_id = message.video_note.file_id
        media_file_unique_id = message.video_note.file_unique_id
    elif message.animation:
        media_type = 'animation'
        media_file_id = message.animation.file_id
        media_file_unique_id = message.animation.file_unique_id
    else:
        await message.answer('❌ Отправьте медиа файл (фото, видео, документ и т.д.):')
        return
    data = await state.get_data()
    template_text = data.get('template_text', '')
    if caption:
        template_text = caption
    await state.update_data(template_text=template_text, media_type=media_type, media_file_id=media_file_id, media_file_unique_id=media_file_unique_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Сохранить шаблон', callback_data='save_template_with_media')], [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_template')]])
    media_names = {'photo': '📷 Фото', 'video': '🎥 Видео', 'document': '📄 Документ', 'audio': '🎵 Аудио', 'voice': '🎤 Голосовое сообщение', 'video_note': '📹 Видео-кружок', 'animation': '🎬 GIF/Анимация'}
    await message.answer(f'✅ Медиа получено: {media_names.get(media_type, media_type)}\n\nТекст подписи: {(template_text if template_text else '(без подписи)')}\n\nГотово к сохранению!', reply_markup=keyboard)

@router.callback_query(F.data.startswith('select_template_'))
async def select_template_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        template_id = int(callback.data.split('_')[2])
        template = await crud.get_template(template_id)
        if not template:
            await callback.answer('Шаблон не найден', show_alert=True)
            return
        template_text = template.text[:500] + '...' if len(template.text) > 500 else template.text if template.text else '(без текста)'
        display_text = f'📝 ШАБЛОН: **{template.name}**\n\n'
        if template.media_type:
            media_names = {'photo': '📷 Фото', 'video': '🎥 Видео', 'document': '📄 Документ', 'audio': '🎵 Аудио', 'voice': '🎤 Голосовое сообщение', 'video_note': '📹 Видео-кружок', 'animation': '🎬 GIF/Анимация'}
            display_text += f'Медиа: {media_names.get(template.media_type, template.media_type)}\n\n'
        display_text += f'📄 Текст:\n━━━━━━━━━━━━━━━━━━━━\n{template_text}\n━━━━━━━━━━━━━━━━━━━━\n\n'
        display_text += 'Выберите действие:'
        await callback.message.edit_text(display_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✏️ Редактировать', callback_data=f'edit_template_{template_id}'), InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'delete_template_{template_id}')], [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_templates')]]))
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error(f'Ошибка при выборе шаблона: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.callback_query(F.data == 'new_template')
async def new_template_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    await callback.message.edit_text('➕ СОЗДАНИЕ НОВОГО ШАБЛОНА\n\nВведите название шаблона:', reply_markup=None)
    await callback.message.answer('Введите название нового шаблона:', reply_markup=get_cancel_keyboard())
    await callback.answer()
    await state.set_state(TemplateStates.waiting_for_name)

@router.message(StateFilter(TemplateStates.waiting_for_name))
async def process_template_name(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    is_valid, error = validate_template_name(message.text)
    if not is_valid:
        await message.answer(f'❌ {error}\nПопробуйте еще раз:')
        return
    await state.update_data(template_name=message.text)
    await message.answer('Введите текст сообщения для рассылки (поддерживается Markdown):', reply_markup=get_cancel_keyboard())
    await state.set_state(TemplateStates.waiting_for_text)

@router.message(StateFilter(TemplateStates.waiting_for_text))
async def process_template_text(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    text_content = message.text or message.caption or ''
    media_type = None
    media_file_id = None
    media_file_unique_id = None
    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
        media_file_unique_id = message.photo[-1].file_unique_id
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
        media_file_unique_id = message.video.file_unique_id
    elif message.document:
        media_type = 'document'
        media_file_id = message.document.file_id
        media_file_unique_id = message.document.file_unique_id
    elif message.audio:
        media_type = 'audio'
        media_file_id = message.audio.file_id
        media_file_unique_id = message.audio.file_unique_id
    elif message.voice:
        media_type = 'voice'
        media_file_id = message.voice.file_id
        media_file_unique_id = message.voice.file_unique_id
    elif message.video_note:
        media_type = 'video_note'
        media_file_id = message.video_note.file_id
        media_file_unique_id = message.video_note.file_unique_id
    elif message.animation:
        media_type = 'animation'
        media_file_id = message.animation.file_id
        media_file_unique_id = message.animation.file_unique_id
    if media_type:
        if not text_content:
            text_content = ''
        await state.update_data(template_text=text_content, media_type=media_type, media_file_id=media_file_id, media_file_unique_id=media_file_unique_id)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Сохранить шаблон', callback_data='save_template_with_media')], [InlineKeyboardButton(text='➕ Добавить еще медиа', callback_data='add_more_media')], [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_template')]])
        media_names = {'photo': '📷 Фото', 'video': '🎥 Видео', 'document': '📄 Документ', 'audio': '🎵 Аудио', 'voice': '🎤 Голосовое сообщение', 'video_note': '📹 Видео-кружок', 'animation': '🎬 GIF/Анимация'}
        await message.answer(f'✅ Медиа получено: {media_names.get(media_type, media_type)}\n\nТекст подписи: {(text_content if text_content else '(без подписи)')}\n\nВыберите действие:', reply_markup=keyboard)
        return
    if not text_content:
        await message.answer('❌ Введите текст сообщения или отправьте медиа с подписью:')
        return
    is_valid, error = validate_template_text(text_content)
    if not is_valid:
        await message.answer(f'❌ {error}\nПопробуйте еще раз:')
        return
    await state.update_data(template_text=text_content)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Сохранить без медиа', callback_data='save_template_no_media')], [InlineKeyboardButton(text='➕ Добавить медиа', callback_data='add_media_to_template')], [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_template')]])
    await message.answer(f'✅ Текст сохранен:\n\n{text_content[:200]}{('...' if len(text_content) > 200 else '')}\n\nХотите добавить медиа (фото, видео и т.д.) к шаблону?', reply_markup=keyboard)

@router.message(Command('set_report_receivers'))
async def cmd_set_report_receivers(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer('❌ У вас нет прав для выполнения этой команды.')
        return
    await message.answer('Введите список получателей сводных отчетов.\n\nПоддерживаемые форматы:\n• @username (пользователи)\n• user_id (число)\n• Ссылки: https://t.me/user\n• Группы/каналы: @groupname или https://t.me/groupname\n\nПример: @user1 @user2 123456789 @mygroup', reply_markup=get_cancel_keyboard())
    await state.set_state(ReportReceiversStates.waiting_for_receivers)

@router.callback_query(F.data == 'report_receivers_menu')
async def report_receivers_menu_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    lists = await crud.get_all_report_receiver_lists()
    text = '📋 ПОЛУЧАТЕЛИ ОТЧЕТОВ\n\n'
    if lists:
        text += '📝 Существующие списки:\n'
        for i, receiver_list in enumerate(lists, 1):
            receivers = await crud.get_receivers_by_list(receiver_list.id)
            text += f'{i}. {receiver_list.name} ({len(receivers)} получателей)\n'
        text += '\n'
    else:
        text += '📝 Списков пока нет.\n\n'
    text += '💡 Выберите список или создайте новый:'
    keyboard = []
    for receiver_list in lists:
        receivers = await crud.get_receivers_by_list(receiver_list.id)
        keyboard.append([InlineKeyboardButton(text=f'📋 {receiver_list.name} ({len(receivers)})', callback_data=f'select_receiver_list_{receiver_list.id}')])
    keyboard.append([InlineKeyboardButton(text='➕ Новый список', callback_data='new_receiver_list')])
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_receiver_lists')])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == 'new_receiver_list')
async def new_receiver_list_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    await callback.message.edit_text('➕ СОЗДАНИЕ НОВОГО СПИСКА ПОЛУЧАТЕЛЕЙ\n\nВведите название списка:', reply_markup=None)
    await callback.message.answer('Введите название нового списка:', reply_markup=get_cancel_keyboard())
    await callback.answer()
    await state.set_state(ReportReceiversStates.waiting_for_list_name)

@router.message(StateFilter(ReportReceiversStates.waiting_for_list_name))
async def process_list_name(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    if not message.text or len(message.text.strip()) < 1:
        await message.answer('❌ Название не может быть пустым. Попробуйте еще раз:')
        return
    list_name = message.text.strip()
    receiver_list = await crud.create_report_receiver_list(list_name)
    await state.update_data(list_id=receiver_list.id, list_name=list_name)
    await message.answer(f"✅ Список '{list_name}' создан.\n\nТеперь добавьте получателей в этот список.\n\nПоддерживаемые форматы:\n• @username (пользователи)\n• user_id (число)\n• Ссылки: https://t.me/user\n• Группы/каналы: @groupname или https://t.me/groupname\n\nВведите список получателей:", reply_markup=get_cancel_keyboard())
    await state.set_state(ReportReceiversStates.waiting_for_receivers)
    logger.info(f"Создан список получателей '{list_name}' пользователем {message.from_user.id}")

@router.callback_query(F.data.startswith('select_receiver_list_'))
async def select_receiver_list_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        list_id = int(callback.data.split('_')[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        if not receiver_list:
            await callback.answer('Список не найден', show_alert=True)
            return
        receivers = await crud.get_receivers_by_list(list_id)
        text = f'📋 СПИСОК: {receiver_list.name}\n\n'
        if receivers:
            text += f'📝 Получатели ({len(receivers)}):\n'
            for i, receiver in enumerate(receivers[:20], 1):
                text += f'{i}. {receiver.identifier}\n'
            if len(receivers) > 20:
                text += f'\n... и еще {len(receivers) - 20} получателей\n'
        else:
            text += '📝 Получателей пока нет.\n'
        text += '\nВыберите действие:'
        keyboard_buttons = [[InlineKeyboardButton(text='✏️ Редактировать название', callback_data=f'edit_receiver_list_{list_id}'), InlineKeyboardButton(text='➕ Добавить получателей', callback_data=f'add_to_list_{list_id}')], [InlineKeyboardButton(text='🗑️ Удалить список', callback_data=f'delete_receiver_list_{list_id}')]]
        if receivers:
            keyboard_buttons.append([InlineKeyboardButton(text='📝 Управление получателями', callback_data=f'manage_receivers_{list_id}')])
        keyboard_buttons.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_receiver_lists')])
        await callback.message.edit_text(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error(f'Ошибка при выборе списка получателей: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.callback_query(F.data.startswith('add_to_list_'))
async def add_to_list_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        list_id = int(callback.data.split('_')[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        if not receiver_list:
            await callback.answer('Список не найден', show_alert=True)
            return
        await state.update_data(list_id=list_id, list_name=receiver_list.name)
        await callback.message.edit_text(f'➕ ДОБАВЛЕНИЕ ПОЛУЧАТЕЛЕЙ В СПИСОК\n\nСписок: {receiver_list.name}\n\nВведите список получателей.\n\nПоддерживаемые форматы:\n• @username (пользователи)\n• user_id (число)\n• Ссылки: https://t.me/user\n• Группы/каналы: @groupname или https://t.me/groupname\n• Приватные группы: https://t.me/joinchat/HASH\n\nПример: @user1 @user2 123456789 @mygroup\nhttps://t.me/joinchat/ABC123', parse_mode=None, reply_markup=None)
        await callback.message.answer('Введите список получателей (через запятую или пробел):', reply_markup=get_cancel_keyboard())
        await callback.answer()
        await state.set_state(ReportReceiversStates.waiting_for_receivers)
    except Exception as e:
        logger.error(f'Ошибка при добавлении получателей в список: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.message(StateFilter(ReportReceiversStates.waiting_for_receivers))
async def process_report_receivers(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    data = await state.get_data()
    list_id = data.get('list_id')
    list_name = data.get('list_name', 'список')
    if not list_id:
        await message.answer('❌ Ошибка: список не найден. Начните заново.', reply_markup=get_main_keyboard(is_admin=True))
        await state.clear()
        return
    from utils import parse_recipients_list, validate_recipients_list
    try:
        recipients = parse_recipients_list(message.text)
        logger.info(f'Парсинг получателей отчетов: найдено {len(recipients)} получателей для списка {list_id}')
        if not recipients:
            await message.answer('❌ Не удалось распознать получателей в вашем сообщении.\n\nПроверьте формат:\n• @username\n• user_id (только цифры)\n• Ссылки: https://t.me/user\n• Группы: @groupname или https://t.me/groupname\n\nПопробуйте еще раз:', reply_markup=get_cancel_keyboard())
            return
    except Exception as e:
        logger.error(f'Ошибка при парсинге получателей отчетов: {e}', exc_info=True)
        await message.answer("❌ Ошибка при обработке списка получателей.\n\nПопробуйте еще раз или нажмите '❌ Отмена':", reply_markup=get_cancel_keyboard())
        return
    is_valid, error = validate_recipients_list(recipients)
    if not is_valid:
        await message.answer(f'❌ {error}\n\nПопробуйте еще раз. Введите список получателей:', reply_markup=get_cancel_keyboard())
        return
    identifiers = [r['original'] for r in recipients]
    receivers = await crud.add_report_receivers_to_list(list_id, identifiers)
    await state.clear()
    receiver_list = await crud.get_report_receiver_list(list_id)
    updated_receivers = await crud.get_receivers_by_list(list_id)
    text = f"✅ Добавлено получателей в список '{list_name}': {len(receivers)}\n\n"
    text += f'📋 СПИСОК: {receiver_list.name}\n\n'
    if updated_receivers:
        text += f'📝 Получатели ({len(updated_receivers)}):\n'
        for i, receiver in enumerate(updated_receivers[:10], 1):
            text += f'{i}. {receiver.identifier}\n'
        if len(updated_receivers) > 10:
            text += f'\n... и еще {len(updated_receivers) - 10} получателей\n'
    text += '\nВыберите действие:'
    keyboard_buttons = [[InlineKeyboardButton(text='✏️ Редактировать название', callback_data=f'edit_receiver_list_{list_id}'), InlineKeyboardButton(text='➕ Добавить получателей', callback_data=f'add_to_list_{list_id}')], [InlineKeyboardButton(text='🗑️ Удалить список', callback_data=f'delete_receiver_list_{list_id}')]]
    if updated_receivers:
        keyboard_buttons.append([InlineKeyboardButton(text='📝 Управление получателями', callback_data=f'manage_receivers_{list_id}')])
    keyboard_buttons.append([InlineKeyboardButton(text='❌ Закрыть', callback_data='cancel_receiver_lists')])
    await message.answer(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    logger.info(f'Добавлено {len(receivers)} получателей в список {list_id} пользователем {message.from_user.id}')

@router.message(Command('templates_list'))
async def cmd_templates_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('❌ У вас нет прав для выполнения этой команды.')
        return
    templates = await crud.get_all_active_templates()
    if not templates:
        await message.answer('📝 Шаблонов пока нет.')
        return
    await message.answer('📝 Управление шаблонами:\n\nВыберите шаблон для редактирования или удаления:', reply_markup=get_templates_keyboard(templates, for_selection=False))

@router.callback_query(F.data.startswith('edit_template_name_'))
async def edit_template_name_handler(callback: CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split('_')[3])
    template = await crud.get_template(template_id)
    await state.update_data(template_id=template_id, editing_field='name')
    await state.set_state(TemplateStates.editing_name)
    await callback.message.edit_text(f'✏️ Редактирование названия шаблона\n\nТекущее название: **{template.name}**\n\nВведите новое название:', parse_mode='Markdown', reply_markup=None)
    await callback.message.answer('Введите новое название:', reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith('edit_template_text_'))
async def edit_template_text_handler(callback: CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split('_')[3])
    template = await crud.get_template(template_id)
    await state.update_data(template_id=template_id, editing_field='text')
    await state.set_state(TemplateStates.editing_text)
    await callback.message.edit_text(f'✏️ Редактирование текста шаблона\n\nТекущий текст:\n━━━━━━━━━━━━━━━━━━━━\n{template.text}\n━━━━━━━━━━━━━━━━━━━━\n\nВведите новый текст:', parse_mode='Markdown', reply_markup=None)
    await callback.message.answer('Введите новый текст (поддерживается Markdown):', reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith('edit_template_both_'))
async def edit_template_both_handler(callback: CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split('_')[3])
    template = await crud.get_template(template_id)
    await state.update_data(template_id=template_id, editing_field='both')
    await state.set_state(TemplateStates.editing_name)
    await callback.message.edit_text(f'✏️ Редактирование шаблона: **{template.name}**\n\nВведите новое название:', parse_mode='Markdown', reply_markup=None)
    await callback.message.answer('Введите новое название:', reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith('edit_template_'))
async def edit_template_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        template_id = int(callback.data.split('_')[2])
        template = await crud.get_template(template_id)
        if not template:
            await callback.answer('Шаблон не найден', show_alert=True)
            return
        await state.update_data(template_id=template_id, template_name=template.name, template_text=template.text)
        await callback.message.edit_text(f'✏️ Редактирование шаблона: **{template.name}**\n\nЧто вы хотите изменить?\n1️⃣ Название\n2️⃣ Текст\n3️⃣ И то, и другое', parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='1️⃣ Название', callback_data=f'edit_template_name_{template_id}'), InlineKeyboardButton(text='2️⃣ Текст', callback_data=f'edit_template_text_{template_id}')], [InlineKeyboardButton(text='3️⃣ Оба', callback_data=f'edit_template_both_{template_id}')], [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_templates')]]))
        await callback.answer()
    except Exception as e:
        logger.error(f'Ошибка при начале редактирования шаблона: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.message(StateFilter(TemplateStates.editing_name))
async def process_editing_name(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    is_valid, error = validate_template_name(message.text)
    if not is_valid:
        await message.answer(f'❌ {error}\nПопробуйте еще раз:')
        return
    data = await state.get_data()
    template_id = data.get('template_id')
    editing_field = data.get('editing_field', 'name')
    if editing_field == 'both':
        await state.update_data(template_name=message.text)
        await state.set_state(TemplateStates.editing_text)
        template = await crud.get_template(template_id)
        await message.answer(f'✅ Название сохранено: **{message.text}**\n\nТекущий текст:\n━━━━━━━━━━━━━━━━━━━━\n{template.text}\n━━━━━━━━━━━━━━━━━━━━\n\nТеперь введите новый текст:', parse_mode='Markdown', reply_markup=get_cancel_keyboard())
    else:
        template = await crud.update_template(template_id, name=message.text)
        await state.clear()
        await message.answer(f'✅ Название шаблона обновлено!\n\nНовое название: **{template.name}**', parse_mode='Markdown', reply_markup=get_main_keyboard(is_admin=True))
        logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {callback.from_user.id}")
@router.message(StateFilter(TemplateStates.editing_text))
async def process_editing_text(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    is_valid, error = validate_template_text(message.text)
    if not is_valid:
        await message.answer(f'❌ {error}\nПопробуйте еще раз:')
        return
    data = await state.get_data()
    template_id = data.get('template_id')
    editing_field = data.get('editing_field', 'text')
    template_name = data.get('template_name')
    if editing_field == 'both' and template_name:
        template = await crud.update_template(template_id, name=template_name, text=message.text)
        await state.clear()
        await message.answer(f'✅ Шаблон полностью обновлен!\n\nНазвание: **{template.name}**\nТекст обновлен', parse_mode='Markdown', reply_markup=get_main_keyboard(is_admin=True))
        logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {callback.from_user.id}")
    else:
        template = await crud.update_template(template_id, text=message.text)
        await state.clear()
        await message.answer(f'✅ Текст шаблона обновлен!\n\nШаблон: **{template.name}**', parse_mode='Markdown', reply_markup=get_main_keyboard(is_admin=True))
        logger.info(f"Текст шаблона #{template_id} обновлен пользователем {message.from_user.id}")
@router.callback_query(F.data.startswith('delete_template_'))
async def delete_template_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        template_id = int(callback.data.split('_')[2])
        template = await crud.get_template(template_id)
        if not template:
            await callback.answer('Шаблон не найден', show_alert=True)
            return
        await callback.message.edit_text(f'🗑️ Удаление шаблона\n\nНазвание: **{template.name}**\n\n⚠️ Вы уверены? Шаблон будет помечен как неактивный.', parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Да, удалить', callback_data=f'confirm_delete_{template_id}'), InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_templates')]]))
        await callback.answer()
    except Exception as e:
        logger.error(f'Ошибка при удалении шаблона: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.callback_query(F.data == 'cancel_templates')
async def cancel_templates_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Отменено.')
    await callback.answer()
    await callback.message.answer('Выберите действие:', reply_markup=get_main_keyboard(is_admin=True))

@router.callback_query(F.data == 'open_templates')
async def open_templates_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    templates = await crud.get_all_active_templates()
    text = '📝 УПРАВЛЕНИЕ ШАБЛОНАМИ\n\n'
    if templates:
        text += '📋 Существующие шаблоны:\n'
        for i, template in enumerate(templates, 1):
            text += f'{i}. {template.name}\n'
        text += '\n'
    else:
        text += '📋 Шаблонов пока нет.\n\n'
    text += '💡 Выберите шаблон из списка или создайте новый:'
    keyboard = []
    for template in templates:
        keyboard.append([InlineKeyboardButton(text=f'📝 {template.name}', callback_data=f'select_template_{template.id}')])
    keyboard.append([InlineKeyboardButton(text='➕ Новый шаблон', callback_data='new_template')])
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_templates')])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()

@router.callback_query(F.data.startswith('edit_receiver_list_'))
async def edit_receiver_list_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        list_id = int(callback.data.split('_')[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        if not receiver_list:
            await callback.answer('Список не найден', show_alert=True)
            return
        await state.update_data(list_id=list_id)
        await state.set_state(ReportReceiversStates.editing_list_name)
        await callback.message.edit_text(f'✏️ РЕДАКТИРОВАНИЕ СПИСКА\n\nТекущее название: {receiver_list.name}\n\nВведите новое название:', parse_mode=None, reply_markup=None)
        await callback.message.answer('Введите новое название списка:', reply_markup=get_cancel_keyboard())
        await callback.answer()
    except Exception as e:
        logger.error(f'Ошибка при редактировании списка: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.message(StateFilter(ReportReceiversStates.editing_list_name))
async def process_editing_list_name(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=True))
        return
    if not message.text or len(message.text.strip()) < 1:
        await message.answer('❌ Название не может быть пустым. Попробуйте еще раз:')
        return
    data = await state.get_data()
    list_id = data.get('list_id')
    if not list_id:
        await message.answer('❌ Ошибка: список не найден.', reply_markup=get_main_keyboard(is_admin=True))
        await state.clear()
        return
    receiver_list = await crud.update_report_receiver_list(list_id, name=message.text.strip())
    if receiver_list:
        await state.clear()
        receivers = await crud.get_receivers_by_list(list_id)
        text = f'✅ Название списка обновлено!\n\n'
        text += f'📋 СПИСОК: {receiver_list.name}\n\n'
        if receivers:
            text += f'📝 Получатели ({len(receivers)}):\n'
            for i, receiver in enumerate(receivers[:10], 1):
                text += f'{i}. {receiver.identifier}\n'
            if len(receivers) > 10:
                text += f'\n... и еще {len(receivers) - 10} получателей\n'
        else:
            text += '📝 Получателей пока нет.\n'
        text += '\nВыберите действие:'
        keyboard_buttons = [[InlineKeyboardButton(text='✏️ Редактировать название', callback_data=f'edit_receiver_list_{list_id}'), InlineKeyboardButton(text='➕ Добавить получателей', callback_data=f'add_to_list_{list_id}')], [InlineKeyboardButton(text='🗑️ Удалить список', callback_data=f'delete_receiver_list_{list_id}')]]
        if receivers:
            keyboard_buttons.append([InlineKeyboardButton(text='📝 Управление получателями', callback_data=f'manage_receivers_{list_id}')])
        keyboard_buttons.append([InlineKeyboardButton(text='❌ Закрыть', callback_data='cancel_receiver_lists')])
        await message.answer(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
        await message.answer(
            text,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    else:
        await message.answer('❌ Не удалось обновить список', reply_markup=get_main_keyboard(is_admin=True))
        await state.clear()

@router.callback_query(F.data.startswith('delete_receiver_list_'))
async def delete_receiver_list_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        list_id = int(callback.data.split('_')[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        if not receiver_list:
            await callback.answer('Список не найден', show_alert=True)
            return
        receivers = await crud.get_receivers_by_list(list_id)
        await callback.message.edit_text(f'🗑️ УДАЛЕНИЕ СПИСКА\n\nНазвание: {receiver_list.name}\nПолучателей: {len(receivers)}\n\n⚠️ Вы уверены? Список будет помечен как неактивный.', parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Да, удалить', callback_data=f'confirm_delete_list_{list_id}'), InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_receiver_lists')]]))
        await callback.answer()
    except Exception as e:
        logger.error(f'Ошибка при удалении списка: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.callback_query(F.data.startswith('confirm_delete_list_'))
async def confirm_delete_list_handler(callback: CallbackQuery):
    list_id = int(callback.data.split('_')[3])
    success = await crud.delete_report_receiver_list(list_id)
    if success:
        await callback.message.edit_text('✅ Список удален (помечен как неактивный)')
        await callback.answer('Список удален')
        logger.info(f"Список получателей #{list_id} удален пользователем {callback.from_user.id}")
    else:
        await callback.message.edit_text('❌ Не удалось удалить список')
        await callback.answer('Ошибка', show_alert=True)

@router.callback_query(F.data.startswith('confirm_delete_'))
async def confirm_delete_template(callback: CallbackQuery):
    template_id = int(callback.data.split('_')[2])
    success = await crud.delete_template(template_id)
    if success:
        await callback.message.edit_text('✅ Шаблон удален (помечен как неактивный)')
        await callback.answer('Шаблон удален')
        logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {callback.from_user.id}")
    else:
        await callback.message.edit_text('❌ Не удалось удалить шаблон')
        await callback.answer('Ошибка', show_alert=True)

@router.callback_query(F.data.startswith('manage_receivers_'))
async def manage_receivers_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        list_id = int(callback.data.split('_')[2])
        receiver_list = await crud.get_report_receiver_list(list_id)
        if not receiver_list:
            await callback.answer('Список не найден', show_alert=True)
            return
        receivers = await crud.get_receivers_by_list(list_id)
        if not receivers:
            await callback.answer('В списке нет получателей', show_alert=True)
            return
        text = f'📝 УПРАВЛЕНИЕ ПОЛУЧАТЕЛЯМИ\n\n'
        text += f'Список: {receiver_list.name}\n\n'
        text += 'Выберите получателя для удаления:\n\n'
        keyboard = []
        for i in range(0, len(receivers), 2):
            row = []
            row.append(InlineKeyboardButton(text=f'🗑️ {receivers[i].identifier[:20]}', callback_data=f'delete_receiver_{receivers[i].id}'))
            if i + 1 < len(receivers):
                row.append(InlineKeyboardButton(text=f'🗑️ {receivers[i + 1].identifier[:20]}', callback_data=f'delete_receiver_{receivers[i + 1].id}'))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text='◀️ Назад к списку', callback_data=f'select_receiver_list_{list_id}')])
        keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_receiver_lists')])
        await callback.message.edit_text(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error(f'Ошибка при управлении получателями: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.callback_query(F.data.startswith('delete_receiver_'))
async def delete_receiver_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer('❌ У вас нет прав', show_alert=True)
        return
    try:
        receiver_id = int(callback.data.split('_')[2])
        from database import ReportReceiver, async_session_maker
        from sqlalchemy import select
        async with async_session_maker() as session:
            result = await session.execute(select(ReportReceiver).where(ReportReceiver.id == receiver_id))
            receiver = result.scalar_one_or_none()
            if not receiver:
                await callback.answer('Получатель не найден', show_alert=True)
                return
            list_id = receiver.list_id
            identifier = receiver.identifier
        success = await crud.delete_report_receiver(receiver_id)
        if success:
            await callback.answer(f'✅ Получатель {identifier} удален')
            receiver_list = await crud.get_report_receiver_list(list_id)
            receivers = await crud.get_receivers_by_list(list_id)
            text = f'📋 СПИСОК: {receiver_list.name}\n\n'
            if receivers:
                text += f'📝 Получатели ({len(receivers)}):\n'
                for i, rec in enumerate(receivers[:20], 1):
                    text += f'{i}. {rec.identifier}\n'
                if len(receivers) > 20:
                    text += f'\n... и еще {len(receivers) - 20} получателей\n'
            else:
                text += '📝 Получателей пока нет.\n'
            text += '\nВыберите действие:'
            keyboard_buttons = [[InlineKeyboardButton(text='✏️ Редактировать название', callback_data=f'edit_receiver_list_{list_id}'), InlineKeyboardButton(text='➕ Добавить получателей', callback_data=f'add_to_list_{list_id}')], [InlineKeyboardButton(text='🗑️ Удалить список', callback_data=f'delete_receiver_list_{list_id}')]]
            if receivers:
                keyboard_buttons.append([InlineKeyboardButton(text='📝 Управление получателями', callback_data=f'manage_receivers_{list_id}')])
            keyboard_buttons.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_receiver_lists')])
            await callback.message.edit_text(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
            logger.info(f"Получатель #{receiver_id} удален из списка {list_id} пользователем {callback.from_user.id}")
        else:
            await callback.answer('❌ Не удалось удалить получателя', show_alert=True)
    except Exception as e:
        logger.error(f'Ошибка при удалении получателя: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)

@router.callback_query(F.data == 'cancel_receiver_lists')
async def cancel_receiver_lists_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Отменено.')
    await callback.answer()
    await callback.message.answer('Выберите действие:', reply_markup=get_main_keyboard(is_admin=True))

@router.callback_query(F.data == 'close_settings')
async def close_settings_handler(callback: CallbackQuery):
    await callback.message.edit_text('⚙️ Настройки закрыты')
    await callback.answer()

@router.message(F.text == '⚙️ Настройки')
async def cmd_settings(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('❌ У вас нет прав для выполнения этой команды.')
        return
    receiver_lists = await crud.get_all_report_receiver_lists()
    settings_text = '⚙️ НАСТРОЙКИ БОТА\n\n'
    settings_text += '📝 Выберите действие:'
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📋 Получатели отчетов', callback_data='report_receivers_menu')], [InlineKeyboardButton(text='📝 Шаблоны', callback_data='open_templates')], [InlineKeyboardButton(text='❌ Закрыть', callback_data='close_settings')]])
    await message.answer(settings_text, reply_markup=keyboard)
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
import database as crud
from utils import parse_recipients_list, validate_recipients_list, format_recipient_list
from utils import logger
from config import MAIN_ADMIN_ID
from keyboards import get_main_keyboard, get_cancel_keyboard, get_recipients_keyboard
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from keyboards import get_templates_keyboard, get_confirm_mailing_keyboard, get_campaigns_keyboard, get_delay_keyboard, get_max_recipients_keyboard
from services import generate_personal_report

def is_admin(user_id: int) -> bool:
    return user_id == MAIN_ADMIN_ID

class MailingStates(StatesGroup):
    waiting_for_template = State()
    waiting_for_recipients = State()
    waiting_for_group_selection = State()
    waiting_for_delay = State()
    waiting_for_max_recipients = State()
    confirm_mailing = State()

class GroupStates(StatesGroup):
    waiting_for_group_link = State()

def get_cancel_keyboard_for_groups() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='❌ Отмена')]], resize_keyboard=True)

@router.message(Command('start'))
async def cmd_start(message: Message):
    user = await crud.get_or_create_user(telegram_id=message.from_user.id, username=message.from_user.username, first_name=message.from_user.first_name, last_name=message.from_user.last_name)
    is_admin_user = is_admin(message.from_user.id)
    welcome_text = f'👋 Добро пожаловать в бота для рассылок!\n\nВы можете:\n📧 Создавать новые рассылки\n📊 Просматривать свои рассылки и отчеты\nℹ️ Получать помощь\n\nИспользуйте меню или команды для навигации.'
    if is_admin_user:
        welcome_text += '\n\n🔑 Вы являетесь администратором и имеете доступ к дополнительным функциям.'
    try:
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username
        if bot_username:
            welcome_text += f'\n\n🤖 Чтобы добавить бота в группу/канал, используйте команду /invite'
    except:
        pass
    await message.answer(welcome_text, reply_markup=get_main_keyboard(is_admin=is_admin_user))
    logger.info(f'Пользователь {message.from_user.id} зарегистрирован/вошел в бота')

@router.message(Command('help'))
@router.message(F.text == 'ℹ️ Помощь')
async def cmd_help(message: Message, bot: Bot):
    is_admin_user = is_admin(message.from_user.id)
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        if bot_username:
            add_to_group_link = f'https://t.me/{bot_username}?startgroup'
            add_to_channel_link = f'https://t.me/{bot_username}?startchannel'
            invite_text = f'\n🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:\n\n📱 Добавить в группу:\n{add_to_group_link}\n\n📢 Добавить в канал:\n{add_to_channel_link}\n\n💡 ИНСТРУКЦИЯ:\n1. Откройте ссылку выше\n2. Выберите группу/канал\n3. Нажмите "Добавить" или "Пригласить"\n4. Бот будет добавлен в группу/канал\n\n⚠️ ВАЖНО:\n• Бот должен быть администратором группы/канала для работы некоторых функций\n• После добавления бот автоматически появится в меню "👥 Группы"\n'
        else:
            invite_text = '\n🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:\n\n⚠️ У бота нет username. Для добавления бота:\n1. Откройте настройки группы/канала\n2. Перейдите в "Участники" → "Добавить участников"\n3. Найдите бота по его ID или попросите администратора добавить его\n\nИли настройте username для бота через @BotFather\n'
    except Exception as e:
        logger.error(f'Ошибка при получении информации о боте: {e}')
        invite_text = '\n\n⚠️ Не удалось получить ссылки для добавления бота'
    help_text = 'ℹ️ СПРАВКА ПО ИСПОЛЬЗОВАНИЮ БОТА\n\n📋 ОСНОВНЫЕ ФУНКЦИИ:\n\n📧 Новая рассылка\n   Создайте новую рассылку по вашим получателям\n   • Выберите шаблон\n   • Введите список получателей\n   • Подтвердите запуск\n\n📊 Мои рассылки\n   Просмотрите историю ваших рассылок\n   • Список всех ваших рассылок\n   • Просмотр детальных отчетов\n   • Статистика по каждой рассылке\n\n📝 Команды:\n   /start - регистрация и главное меню\n   /help - эта справка\n   /invite - получить ссылки для добавления бота в группы/каналы\n   /report <ID> - просмотр отчета по ID рассылки\n   Пример: /report 123\n\n📝 ФОРМАТ СПИСКА ПОЛУЧАТЕЛЕЙ:\n   • @username (пользователи)\n   • user_id (число, например: 123456789)\n   • Ссылки: https://t.me/user или t.me/user\n   • Группы/каналы: @groupname или https://t.me/groupname\n   • Разделители: запятая, пробел, новая строка\n   \n   Пример:\n   @user1, 123456789, @user2\n   https://t.me/user3'
    if is_admin_user:
        help_text += '\n\n🔑 АДМИН-ФУНКЦИИ:\n\n'
        help_text += '📝 Шаблоны\n'
        help_text += '   Создание шаблонов сообщений для рассылок\n'
        help_text += '   • Введите название шаблона\n'
        help_text += '   • Введите текст (поддерживается Markdown)\n\n'
        help_text += '⚙️ Настройки\n'
        help_text += '   Настройка получателей сводных отчетов\n'
        help_text += '   • Введите список @username или user_id\n\n'
        help_text += '📝 АДМИН-КОМАНДЫ:\n'
        help_text += '   /add_template - создать шаблон\n'
        help_text += '   /set_report_receivers - настройка получателей отчетов\n'
        help_text += '   /templates_list - список всех шаблонов'
    else:
        help_text += '\n\n💡 СОВЕТ:\n'
        help_text += 'Если у вас нет шаблонов для рассылок,\n'
        help_text += 'обратитесь к администратору.\n\n'
        help_text += '📱 ОТПРАВКА ОТ ВАШЕГО ИМЕНИ:\n'
        help_text += '/setup_my_client - настроить отправку от вашего имени\n'
        help_text += '/my_client_status - проверить статус'
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        if bot_username:
            add_to_group_link = f'https://t.me/{bot_username}?startgroup'
            add_to_channel_link = f'https://t.me/{bot_username}?startchannel'
            invite_text = f'\n\n🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:\n\n📱 Добавить в группу:\n{add_to_group_link}\n\n📢 Добавить в канал:\n{add_to_channel_link}\n\n💡 ИНСТРУКЦИЯ:\n1. Нажмите на ссылку выше (для группы или канала)\n2. Выберите группу/канал из списка\n3. Нажмите "Добавить" или "Пригласить"\n4. Бот будет добавлен в группу/канал\n\n⚠️ ВАЖНО:\n• После добавления бот автоматически появится в меню "👥 Группы"\n• Для некоторых функций бот должен быть администратором\n• Если ссылки не работают, попробуйте добавить бота через настройки группы:\n  Настройки → Участники → Добавить участников → Найдите @{bot_username}\n\n💬 Или используйте команду /invite для получения ссылок'
        else:
            invite_text = '\n\n🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:\n\n⚠️ У бота нет username. Для добавления бота:\n1. Откройте настройки группы/канала\n2. Перейдите в "Участники" → "Добавить участников"\n3. Найдите бота по его ID или попросите администратора добавить его\n\n💡 Чтобы настроить username для бота:\n1. Откройте @BotFather в Telegram\n2. Отправьте /mybots\n3. Выберите вашего бота\n4. Выберите "Edit Bot" → "Edit Username"\n5. Установите username (например: my_mailing_bot)\n\nПосле настройки username вы сможете использовать ссылки для добавления бота.'
    except Exception as e:
        logger.error(f'Ошибка при получении информации о боте: {e}')
        invite_text = '\n\n⚠️ Не удалось получить ссылки для добавления бота'
    await message.answer(help_text + invite_text, reply_markup=get_main_keyboard(is_admin=is_admin_user), parse_mode=None)

@router.message(Command('invite'))
async def cmd_invite(message: Message, bot: Bot):
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        bot_id = bot_info.id
        if bot_username:
            add_to_group_link = f'https://t.me/{bot_username}?startgroup'
            add_to_channel_link = f'https://t.me/{bot_username}?startchannel'
            user_groups_text = ''
            try:
                from services import get_user_groups
                user_groups = await get_user_groups(message.from_user.id)
                if user_groups:
                    user_groups_text = f'\n\n📋 ВАШИ ГРУППЫ (через Client API):\n'
                    user_groups_text += 'Вы можете добавить бота в эти группы:\n\n'
                    for i, group in enumerate(user_groups[:10], 1):
                        group_title = group.get('title', 'Без названия')
                        group_id = group.get('id')
                        group_type = group.get('type', 'group')
                        user_groups_text += f'{i}. {group_title} ({group_type})\n'
                        user_groups_text += f'   ID: {group_id}\n'
                        user_groups_text += f'   → Откройте группу → Настройки → Участники → Добавить → @{bot_username}\n\n'
                    if len(user_groups) > 10:
                        user_groups_text += f'... и еще {len(user_groups) - 10} групп\n'
            except Exception as e:
                logger.warning(f'Не удалось получить группы пользователя через Client API: {e}')
            invite_text = f'🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ\n\n📱 СПОСОБ 1: Через ссылку (рекомендуется)\nДобавить в группу:\n{add_to_group_link}\n\nДобавить в канал:\n{add_to_channel_link}\n\n💡 ИНСТРУКЦИЯ для ссылок:\n1. Нажмите на ссылку выше\n2. Выберите группу/канал из списка\n3. Нажмите "Добавить" или "Пригласить"\n\n📱 СПОСОБ 2: Через настройки группы\n1. Откройте группу/канал\n2. Настройки → Участники → Добавить участников\n3. Введите: @{bot_username}\n4. Или найдите бота в списке и добавьте\n\n📱 СПОСОБ 3: Через поиск по ID\n1. Откройте группу/канал\n2. Настройки → Участники → Добавить участников\n3. Введите ID бота: {bot_id}\n4. Добавьте бота\n\n⚠️ ВАЖНО:\n• После добавления бот автоматически появится в меню "👥 Группы"\n• Для некоторых функций бот должен быть администратором\n• Если вы администратор группы, вы можете добавить бота напрямую\n• Если вы не администратор, попросите администратора добавить бота{user_groups_text}'
        else:
            invite_text = f'🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ\n\n⚠️ У бота нет username. Для добавления бота:\n\n📱 СПОСОБ 1: Через ID бота\n1. Откройте настройки группы/канала\n2. Перейдите в "Участники" → "Добавить участников"\n3. Введите ID бота: {bot_id}\n4. Добавьте бота\n\n📱 СПОСОБ 2: Через @BotFather\n1. Откройте @BotFather в Telegram\n2. Отправьте /mybots\n3. Выберите вашего бота\n4. Выберите "Edit Bot" → "Edit Username"\n5. Установите username (например: my_mailing_bot)\n6. После настройки username используйте команду /invite для получения ссылок\n\n💡 РЕКОМЕНДАЦИЯ:\nНастройте username для бота - это самый простой способ добавления в группы.'
        additional_info = '\n\n🔧 ЕСЛИ НЕ ПОЛУЧАЕТСЯ ДОБАВИТЬ:\n\n1. Проверьте права:\n   • Вы должны быть администратором группы/канала\n   • Или попросите администратора добавить бота\n\n2. Попробуйте разные способы:\n   • Через ссылку (если есть username)\n   • Через поиск @username\n   • Через ID бота\n\n3. Если ничего не помогает:\n   • Убедитесь, что бот активен\n   • Проверьте, что группа/канал не заблокированы\n   • Попробуйте добавить бота через веб-версию Telegram\n\n4. После добавления:\n   • Бот автоматически появится в меню "👥 Группы"\n   • Для работы некоторых функций бот должен быть администратором'
        await message.answer(invite_text + additional_info, reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
        logger.info(f'Пользователь {message.from_user.id} запросил ссылки для добавления бота')
    except Exception as e:
        logger.error(f'Ошибка при получении ссылок для добавления бота: {e}', exc_info=True)
        await message.answer('❌ Ошибка при получении ссылок. Попробуйте позже.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)

@router.message(Command('new_mailing'))
@router.message(F.text == '📧 Новая рассылка')
async def cmd_new_mailing(message: Message, state: FSMContext):
    templates = await crud.get_all_active_templates()
    if not templates:
        await message.answer('❌ Нет доступных шаблонов. Обратитесь к администратору.')
        return
    await message.answer('Выберите шаблон для рассылки:', reply_markup=get_templates_keyboard(templates))
    await state.set_state(MailingStates.waiting_for_template)

@router.callback_query(StateFilter(MailingStates.waiting_for_template), F.data.startswith('template_'))
async def process_template_selection(callback: CallbackQuery, state: FSMContext):
    try:
        if callback.data == 'cancel':
            await state.clear()
            await callback.message.edit_text('Отменено.')
            await callback.answer()
            return
        template_id = int(callback.data.split('_')[1])
        template = await crud.get_template(template_id)
        if not template:
            await callback.answer('Шаблон не найден', show_alert=True)
        logger.warning(f"Шаблон #{template_id} не найден для пользователя {callback.from_user.id}")
        logger.warning(f"Шаблон #{template_id} не найден для пользователя {callback.from_user.id}")
    except ValueError as e:
        logger.error(f'Ошибка парсинга template_id из {callback.data}: {e}')
        await callback.answer('Ошибка при выборе шаблона', show_alert=True)
        return
    except Exception as e:
        logger.error(f'Ошибка при обработке выбора шаблона: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)
        return
    await state.update_data(template_id=template_id)
    logger.info(f'Шаг 1: template_id {template_id} сохранен в state для пользователя {callback.from_user.id}')
    await state.set_state(MailingStates.waiting_for_recipients)
    logger.info(f'Шаг 2: Состояние установлено в waiting_for_recipients для пользователя {callback.from_user.id}')
    await callback.answer(f'✅ Выбран: {template.name}')
    recipients_text = f'✅ Выбран шаблон: {template.name}\n\n📝 Введите список получателей:\n\nФормат:\n• @username (пользователи)\n• user_id (число)\n• Ссылки: https://t.me/user или t.me/user\n• Группы/каналы: @groupname или https://t.me/groupname\n• Приватные группы: https://t.me/joinchat/HASH или t.me/+HASH\n\n⚠️ Для приватных групп: бот автоматически присоединится по invite-ссылке\n\nРазделители: запятая, пробел, новая строка\n\nПример:\n@user1, 123456789, @user2, @mygroup\nhttps://t.me/joinchat/ABC123 (приватная группа)'
    try:
        sent_message = await callback.message.answer(recipients_text, parse_mode=None, reply_markup=get_recipients_keyboard())
        logger.info(f'Шаг 3: Сообщение с инструкциями отправлено пользователю {callback.from_user.id}, message_id: {sent_message.message_id}')
        current_state = await state.get_state()
        logger.info(f'Шаг 4: Текущее состояние: {current_state}')
        if current_state != MailingStates.waiting_for_recipients:
            logger.error(f'ОШИБКА: Состояние не совпадает! Ожидалось: {MailingStates.waiting_for_recipients}, получено: {current_state}')
            await state.set_state(MailingStates.waiting_for_recipients)
            logger.info('Состояние переустановлено')
    except Exception as e:
        logger.error(f'КРИТИЧЕСКАЯ ОШИБКА при отправке сообщения: {e}', exc_info=True)
        await callback.message.answer(f'✅ Выбран шаблон: {template.name}\n\nВведите список получателей (через запятую или пробел):\nПример: @user1, 123456789, @user2', reply_markup=get_cancel_keyboard())
    
    logger.info(f"Пользователь {callback.from_user.id} выбрал шаблон #{template_id} '{template.name}', готов к вводу получателей")
    final_recipients = []
    for recipient in recipients:
        if recipient['type'] in ('link', 'invite_link') or 't.me' in recipient['original'].lower():
            await message.answer(f'⏳ Обрабатываю группу: {recipient['original']}...', parse_mode=None)
            if 'joinchat' in recipient['original'].lower() or '/+' in recipient['original']:
                join_result = await join_chat_by_link(message.from_user.id, recipient['original'])
                if not join_result['success']:
                    await message.answer(f'❌ Не удалось присоединиться к чату:\n{join_result['error']}\n\nПропускаю этот чат.', parse_mode=None)
                    continue
                chat_type = join_result.get('chat_type', '')
                if chat_type in ('group', 'supergroup'):
                    from services import get_group_members
                    members = await get_group_members(message.from_user.id, join_result['chat_id'])
                    if not members:
                        try:
                            members = await get_group_members(message.from_user.id, join_result['chat_id'], use_telethon=True)
                        except:
                            pass
                    if members:
                        for member_id in members:
                            final_recipients.append({'original': str(member_id), 'normalized': str(member_id), 'type': 'chat_id'})
                        await message.answer(f'✅ Чат обработан: {join_result.get('title', 'Чат')}\n📝 Участников: {len(members)}', parse_mode=None)
                    else:
                        await message.answer(f'⚠️ Чат обработан, но не удалось получить участников: {join_result.get('title', 'Чат')}', parse_mode=None)
                elif chat_type == 'channel':
                    await message.answer(f'⚠️ Канал обработан: {join_result.get('title', 'Канал')}\nДля каналов рассылка участникам недоступна.', parse_mode=None)
                continue
            else:
                chat_info = await get_chat_info_by_link(message.from_user.id, recipient['original'])
                if not chat_info['success']:
                    final_recipients.append(recipient)
                    continue
                chat_type = chat_info.get('chat_type', '')
                if chat_type in ('group', 'supergroup') and chat_info.get('members'):
                    for member_id in chat_info['members']:
                        final_recipients.append({'original': str(member_id), 'normalized': str(member_id), 'type': 'chat_id'})
                    await message.answer(f'✅ Чат обработан: {chat_info.get('title', 'Чат')}\n📝 Участников: {len(chat_info['members'])}', parse_mode=None)
                elif chat_type == 'channel':
                    await message.answer(f'✅ Канал обработан: {chat_info.get('title', 'Канал')}\nID: {chat_info.get('chat_id')}\n\nℹ️ Для каналов рассылка участникам недоступна, но канал добавлен в список.', parse_mode=None)
                else:
                    final_recipients.append(recipient)
        else:
            final_recipients.append(recipient)
    if not final_recipients:
        await message.answer("❌ Не удалось получить получателей.\n\nПопробуйте еще раз или нажмите '👥 В группе' для выбора группы:", reply_markup=get_recipients_keyboard())
        return
    is_valid, error = validate_recipients_list(final_recipients)
    if not is_valid:
        await message.answer(f"❌ {error}\n\nПопробуйте еще раз. Введите список получателей или нажмите '👥 В группе':", reply_markup=get_recipients_keyboard())
        return
    data = await state.get_data()
    template_id = data.get('template_id')
    await state.update_data(recipients=final_recipients, template_id=template_id, group_id=None, group_title=None)
    await message.answer(f'✅ Получено {len(final_recipients)} получателей.\n\n⏱️ Выберите интервал между сообщениями:\n\n⭐ РЕКОМЕНДУЕТСЯ: 15-30 секунд (безопасно)\n⚠️ МИНИМУМ: 10 секунд (риск ограничения)\n❌ НЕ РЕКОМЕНДУЕТСЯ: менее 10 секунд (высокий риск PEER_FLOOD)\n\n💡 Поддерживаются пользователи, группы и каналы', reply_markup=get_delay_keyboard())
    await state.set_state(MailingStates.waiting_for_delay)
    logger.info(f'Пользователь {message.from_user.id} ввел {len(final_recipients)} получателей (включая участников групп), ожидается выбор интервала')

@router.callback_query(StateFilter(MailingStates.waiting_for_delay), F.data.startswith('delay_'))
async def process_delay_selection(callback: CallbackQuery, state: FSMContext):
    if callback.data == 'cancel':
        await state.clear()
        await callback.message.edit_text('❌ Создание рассылки отменено.')
        await callback.answer()
        return
    try:
        delay_seconds = int(callback.data.split('_')[1])
    except (ValueError, IndexError):
        await callback.answer('❌ Ошибка: неверный интервал', show_alert=True)
        return
    if delay_seconds < 10:
        await callback.answer('⚠️ ВНИМАНИЕ: Интервал менее 10 секунд может привести к ограничению аккаунта Telegram (PEER_FLOOD). Рекомендуется использовать минимум 15 секунд.', show_alert=True)
    data = await state.get_data()
    recipients = data.get('recipients')
    template_id = data.get('template_id')
    group_id = data.get('group_id')
    group_title = data.get('group_title')
    if not recipients or not template_id:
        await callback.answer('❌ Ошибка: данные не найдены. Начните заново.', show_alert=True)
        await state.clear()
        return
    template = await crud.get_template(template_id)
    if not template:
        await callback.answer('❌ Шаблон не найден', show_alert=True)
        await state.clear()
        return
    campaign = await crud.create_campaign(owner_id=callback.from_user.id, template_id=template_id, delay_seconds=delay_seconds)
    recipient_data = [{'original': r['original'], 'normalized': r['normalized']} for r in recipients]
    await crud.add_recipients(campaign.id, recipient_data)
    await state.update_data(campaign_id=campaign.id)
    if delay_seconds < 60:
        delay_text = f'{delay_seconds} сек'
    else:
        minutes = delay_seconds // 60
        seconds = delay_seconds % 60
        if seconds > 0:
            delay_text = f'{minutes} мин {seconds} сек'
        else:
            delay_text = f'{minutes} мин'
    warning_text = ''
    if delay_seconds < 10:
        warning_text = '\n\n⚠️ ВНИМАНИЕ: Интервал менее 10 секунд может привести к ограничению аккаунта Telegram (PEER_FLOOD). Рекомендуется использовать минимум 15 секунд.'
    elif delay_seconds < 15:
        warning_text = '\n\n💡 РЕКОМЕНДАЦИЯ: Для большей безопасности используйте интервал 15-30 секунд.'
    await state.update_data(delay_seconds=delay_seconds)
    await callback.message.edit_text(f'✅ Интервал выбран: {delay_text}{warning_text}\n\n📊 Всего получателей: {len(recipients)}\n\n🔢 Выберите максимальное количество получателей для рассылки:\n\n💡 Рассылка будет ограничена выбранным количеством', reply_markup=get_max_recipients_keyboard(), parse_mode=None)
    await callback.answer()
    await state.set_state(MailingStates.waiting_for_max_recipients)
    logger.info(f'Пользователь {callback.from_user.id} выбрал интервал {delay_seconds} сек, ожидается выбор количества получателей')

@router.callback_query(StateFilter(MailingStates.waiting_for_max_recipients), F.data.startswith('max_recipients_'))
async def process_max_recipients_selection(callback: CallbackQuery, state: FSMContext):
    if callback.data == 'cancel':
        await state.clear()
        await callback.message.edit_text('❌ Создание рассылки отменено.')
        await callback.answer()
        return
    try:
        max_recipients = int(callback.data.split('_')[2])
    except (ValueError, IndexError):
        await callback.answer('❌ Ошибка: неверное количество', show_alert=True)
        return
    data = await state.get_data()
    recipients = data.get('recipients')
    template_id = data.get('template_id')
    delay_seconds = data.get('delay_seconds')
    group_id = data.get('group_id')
    group_title = data.get('group_title')
    if not recipients or not template_id or (not delay_seconds):
        await callback.answer('❌ Ошибка: данные не найдены. Начните заново.', show_alert=True)
        await state.clear()
        return
    template = await crud.get_template(template_id)
    if not template:
        await callback.answer('❌ Шаблон не найден', show_alert=True)
        await state.clear()
        return
    limited_recipients = recipients[:max_recipients]
    campaign = await crud.create_campaign(owner_id=callback.from_user.id, template_id=template_id, delay_seconds=delay_seconds, max_recipients=max_recipients)
    recipient_data = [{'original': r['original'], 'normalized': r['normalized']} for r in limited_recipients]
    await crud.add_recipients(campaign.id, recipient_data)
    await state.update_data(campaign_id=campaign.id)
    if delay_seconds < 60:
        delay_text = f'{delay_seconds} сек'
    else:
        minutes = delay_seconds // 60
        seconds = delay_seconds % 60
        if seconds > 0:
            delay_text = f'{minutes} мин {seconds} сек'
        else:
            delay_text = f'{minutes} мин'
    delay_warning = ''
    if delay_seconds < 10:
        delay_warning = ' ⚠️ (риск PEER_FLOOD)'
    elif delay_seconds < 15:
        delay_warning = ' 💡 (рекомендуется больше)'
    from utils import format_campaign_preview
    preview = format_campaign_preview(campaign, template, len(limited_recipients))
    preview += f'\n\n⏱️ Интервал между сообщениями: {delay_text}{delay_warning}'
    preview += f'\n\n🔢 Максимум получателей: {max_recipients}'
    if len(recipients) > max_recipients:
        preview += f'\n⚠️ Ограничено до {max_recipients} из {len(recipients)} получателей'
    if group_title:
        preview += f'\n\n👥 Группа: {group_title}'
    await callback.message.edit_text(preview, reply_markup=get_confirm_mailing_keyboard(campaign.id), parse_mode=None)
    await callback.answer()
    await state.set_state(MailingStates.confirm_mailing)
    logger.info(f'Создана рассылка #{campaign.id} пользователем {callback.from_user.id}')

@router.callback_query(StateFilter(MailingStates.confirm_mailing), F.data.startswith('confirm_mailing_'))
async def confirm_mailing(callback: CallbackQuery, state: FSMContext):
    from services import is_within_allowed_time
    from datetime import datetime
    campaign_id = int(callback.data.split('_')[2])
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer('Рассылка не найдена', show_alert=True)
        return
    if campaign.owner_id != callback.from_user.id:
        await callback.answer('У вас нет прав на эту рассылку', show_alert=True)
        return
    if not is_within_allowed_time():
        current_time = datetime.now().time().strftime('%H:%M')
        await callback.message.edit_text(f'❌ Рассылка не может быть запущена вне разрешенного времени.\n\n⏰ Текущее время: {current_time}\n✅ Разрешенное время: с 09:00 до 22:00\n\nПопробуйте запустить рассылку позже.', parse_mode=None)
        await callback.answer('Рассылка разрешена только с 09:00 до 22:00', show_alert=True)
        return
    await callback.message.edit_text('✅ Рассылка запущена! Обработка началась...')
    await callback.answer()
    await state.clear()
    from services import process_mailing
    from database import Recipient, async_session_maker
    from sqlalchemy import select
    bot = callback.bot
    template = await crud.get_template(campaign.template_id)
    async with async_session_maker() as session:
        result = await session.execute(select(Recipient).where(Recipient.campaign_id == campaign.id))
        recipients = list(result.scalars().all())
    import asyncio
    asyncio.create_task(process_mailing(bot, campaign, template, recipients))
    await callback.message.answer(
        f'📧 Рассылка #{campaign.id} запущена!\n'
        f'Идентификатор: {campaign.campaign_id}\n\n'
        f'Отчет будет отправлен после завершения.',
        reply_markup=get_main_keyboard(is_admin=is_admin(callback.from_user.id))
    )

@router.callback_query(StateFilter(MailingStates.waiting_for_max_recipients), F.data == 'cancel')
async def cancel_max_recipients(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Создание рассылки отменено.')
    await callback.answer()

@router.callback_query(F.data == 'cancel')
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('Отменено.')
    await callback.answer()

async def show_groups_selection(message: Message, state: FSMContext):
    from services import get_user_groups
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    user_groups = await get_user_groups(message.from_user.id)
    bot_groups = await crud.get_all_bot_groups(active_only=True)
    user_groups_filtered = [g for g in user_groups if g['type'] in ('group', 'supergroup')]
    bot_groups_filtered = [g for g in bot_groups if g.chat_type in ('group', 'supergroup')]
    if not user_groups_filtered and (not bot_groups_filtered):
        await message.answer('👥 Группы не найдены.\n\nДля групп пользователя:\n• Настройте Client API через /setup_my_client\n• Убедитесь, что вы являетесь участником групп\n\nДля групп бота:\n• Добавьте бота в группу', reply_markup=get_cancel_keyboard())
        return
    text = f'👥 ВЫБОР ГРУППЫ\n\n'
    total_groups = len(user_groups_filtered) + len(bot_groups_filtered)
    text += f'Найдено групп: {total_groups}\n\n'
    text += 'Выберите группу для рассылки всем участникам:'
    keyboard = []
    if bot_groups_filtered:
        for group in bot_groups_filtered[:10]:
            members_text = f'({group.members_count} участн.)' if group.members_count else ''
            username_text = f' @{group.username}' if group.username else ''
            button_text = f'🤖 {group.title or 'Без названия'}{username_text} {members_text}'
            button_text = button_text[:60]
            keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'select_bot_group_{group.chat_id}')])
    if user_groups_filtered:
        for group in user_groups_filtered[:10]:
            group_type_emoji = '👥'
            members_text = f'({group['members_count']} участн.)' if group['members_count'] > 0 else ''
            button_text = f'{group_type_emoji} {group['title'][:40]} {members_text}'
            button_text = button_text[:60]
            keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'select_group_{group['id']}')])
    keyboard.append([InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_group_selection')])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(MailingStates.waiting_for_group_selection)

@router.callback_query(StateFilter(MailingStates.waiting_for_group_selection), F.data.startswith('select_bot_group_'))
async def process_bot_group_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    from services import get_group_members
    try:
        group_id = int(callback.data.split('_')[3])
        bot_group = await crud.get_bot_group(group_id)
        if not bot_group or not bot_group.is_active:
            await callback.answer('Группа не найдена', show_alert=True)
            return
        await callback.message.edit_text(f'👥 ГРУППА БОТА ВЫБРАНА\n\nНазвание: {bot_group.title or 'Без названия'}\nТип: {bot_group.chat_type}\nУчастников: {bot_group.members_count or 'неизвестно'}\n\n⏳ Получаю список участников...', reply_markup=None)
        await callback.answer()
        members = await get_group_members(callback.from_user.id, group_id)
        if not members:
            logger.info(f'Пробуем получить участников через Telethon для группы {group_id}')
            try:
                members = await get_group_members(callback.from_user.id, group_id, use_telethon=True)
            except Exception as e:
                logger.warning(f'Не удалось использовать Telethon: {e}')
        if not members:
            await callback.message.edit_text(f'❌ Не удалось получить участников группы\n\nВозможные причины:\n• Нет прав на просмотр участников\n• Группа пуста\n• Ошибка доступа\n\nУбедитесь, что вы настроили Client API и являетесь участником группы', reply_markup=None)
            await state.clear()
            return
        data = await state.get_data()
        template_id = data.get('template_id')
        recipients = [{'original': str(member_id), 'normalized': str(member_id), 'type': 'chat_id'} for member_id in members]
        await state.update_data(recipients=recipients, group_id=group_id, group_title=bot_group.title or 'Без названия')
        await callback.message.edit_text(f'✅ Группа бота: {bot_group.title or 'Без названия'}\n📝 Участников: {len(members)}\n\n⏱️ Выберите интервал между сообщениями:\n\n💡 РЕКОМЕНДАЦИЯ: Используйте минимум 15 секунд для избежания ограничений Telegram', reply_markup=get_delay_keyboard(), parse_mode=None)
        await state.set_state(MailingStates.waiting_for_delay)
        logger.info(f'Пользователь {callback.from_user.id} выбрал группу бота {group_id} с {len(members)} участниками')
    except Exception as e:
        logger.error(f'Ошибка при выборе группы бота: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)
        await state.clear()

@router.callback_query(StateFilter(MailingStates.waiting_for_group_selection), F.data.startswith('select_group_'))
async def process_group_selection(callback: CallbackQuery, state: FSMContext):
    from services import get_group_members, get_user_groups
    try:
        group_id = int(callback.data.split('_')[2])
        groups = await get_user_groups(callback.from_user.id)
        selected_group = None
        for group in groups:
            if group['id'] == group_id:
                selected_group = group
                break
        if not selected_group:
            await callback.answer('Группа не найдена', show_alert=True)
            return
        await callback.message.edit_text(f'👥 ГРУППА ВЫБРАНА\n\nНазвание: {selected_group['title']}\nТип: {selected_group['type']}\nУчастников: {selected_group['members_count']}\n\n⏳ Получаю список участников...', reply_markup=None)
        await callback.answer()
        members = await get_group_members(callback.from_user.id, group_id)
        if not members:
            logger.info(f'Пробуем получить участников через Telethon для группы {group_id}')
            members = await get_group_members(callback.from_user.id, group_id, use_telethon=True)
        if not members:
            await callback.message.edit_text(f'❌ Не удалось получить участников группы\n\nВозможные причины:\n• Нет прав на просмотр участников\n• Группа пуста\n• Ошибка доступа', reply_markup=None)
            await state.clear()
            return
        data = await state.get_data()
        template_id = data.get('template_id')
        recipients = [{'original': str(member_id), 'normalized': str(member_id), 'type': 'chat_id'} for member_id in members]
        await state.update_data(recipients=recipients, group_id=group_id, group_title=selected_group['title'])
        await callback.message.edit_text(f'✅ Группа: {selected_group['title']}\n📝 Участников: {len(members)}\n\n⏱️ Выберите интервал между сообщениями:\n\n💡 РЕКОМЕНДАЦИЯ: Используйте минимум 15 секунд для избежания ограничений Telegram', reply_markup=get_delay_keyboard(), parse_mode=None)
        await state.set_state(MailingStates.waiting_for_delay)
        logger.info(f'Пользователь {callback.from_user.id} выбрал группу {group_id} с {len(members)} участниками')
    except Exception as e:
        logger.error(f'Ошибка при выборе группы: {e}', exc_info=True)
        await callback.answer('Произошла ошибка', show_alert=True)
        await state.clear()

@router.callback_query(StateFilter(MailingStates.waiting_for_group_selection), F.data == 'cancel_group_selection')
async def cancel_group_selection(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Отменено.')
    await callback.answer()
    await callback.message.answer('Выберите действие:', reply_markup=get_main_keyboard(is_admin=is_admin(callback.from_user.id)))

@router.my_chat_member()
async def handle_bot_chat_member(event: ChatMemberUpdated, bot: Bot):
    try:
        chat = event.chat
        new_status = event.new_chat_member.status
        old_status = event.old_chat_member.status if event.old_chat_member else None
        logger.info(f'my_chat_member event: chat_id={chat.id}, type={chat.type}, new_status={new_status}, old_status={old_status}')
        if chat.type not in ('group', 'supergroup', 'channel'):
            logger.debug(f'Пропускаем чат типа {chat.type}')
            return
        chat_type = chat.type
        if new_status in ('member', 'administrator'):
            members_count = None
            try:
                if chat_type in ('group', 'supergroup'):
                    chat_info = await bot.get_chat(chat.id)
                    if hasattr(chat_info, 'members_count') and chat_info.members_count:
                        members_count = chat_info.members_count
            except Exception as e:
                logger.debug(f'Не удалось получить количество участников для {chat.id}: {e}')
            bot_group = await crud.add_or_update_bot_group(chat_id=chat.id, title=chat.title, username=chat.username, chat_type=chat_type, members_count=members_count, is_active=True)
            logger.info(f'✅ Бот добавлен в {chat_type} {chat.id} ({chat.title}), сохранено в БД: {bot_group.id}')
        elif new_status in ('left', 'kicked'):
            await crud.remove_bot_group(chat.id)
            logger.info(f'❌ Бот удален из {chat_type} {chat.id} ({chat.title})')
    except Exception as e:
        logger.error(f'Ошибка при обработке события my_chat_member: {e}', exc_info=True)

async def sync_bot_groups(bot: Bot):
    try:
        logger.info('Синхронизация групп бота: группы отслеживаются через события my_chat_member')
        return []
    except Exception as e:
        logger.error(f'Ошибка при синхронизации групп бота: {e}', exc_info=True)
        return []

@router.message(Command('groups'))
@router.message(F.text == '👥 Группы')
async def cmd_groups(message: Message, bot: Bot, state: FSMContext):
    from services import get_user_groups
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    user_groups = await get_user_groups(message.from_user.id)
    bot_groups = await crud.get_all_bot_groups(active_only=True)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='➕ Добавить чат/группу/канал по ссылке', callback_data='add_group_by_link')], [InlineKeyboardButton(text='❌ Закрыть', callback_data='close_groups')]])
    if not user_groups and (not bot_groups):
        await message.answer('👥 Группы не найдены.\n\nДля групп пользователя:\n• Настройте Client API через /setup_my_client\n• Убедитесь, что вы являетесь участником групп\n\nДля групп бота:\n• Добавьте бота в группу или канал\n• Группы сохраняются автоматически при добавлении бота\n\nИли добавьте чат/группу/канал по ссылке:', reply_markup=keyboard, parse_mode=None)
        return
    text = '👥 ГРУППЫ И КАНАЛЫ\n\n'
    if bot_groups:
        text += f'🤖 ГРУППЫ БОТА ({len(bot_groups)}):\n\n'
        groups_list = [g for g in bot_groups if g.chat_type in ('group', 'supergroup')]
        channels_list = [g for g in bot_groups if g.chat_type == 'channel']
        if groups_list:
            text += f'👥 Группы ({len(groups_list)}):\n'
            for group in groups_list[:10]:
                members_text = f' ({group.members_count} участн.)' if group.members_count else ''
                username_text = f' (@{group.username})' if group.username else ''
                title = (group.title or 'Без названия').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                text += f'• {title}{username_text}{members_text}\n'
            if len(groups_list) > 10:
                text += f'... и еще {len(groups_list) - 10} групп\n'
            text += '\n'
        if channels_list:
            text += f'📢 Каналы ({len(channels_list)}):\n'
            for channel in channels_list[:10]:
                members_text = f' ({channel.members_count} подписч.)' if channel.members_count else ''
                username_text = f' (@{channel.username})' if channel.username else ''
                title = (channel.title or 'Без названия').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                text += f'• {title}{username_text}{members_text}\n'
            if len(channels_list) > 10:
                text += f'... и еще {len(channels_list) - 10} каналов\n'
            text += '\n'
    if user_groups:
        text += f'👤 ВАШИ ГРУППЫ (через Client API) ({len(user_groups)}):\n\n'
        user_groups_list = [g for g in user_groups if g['type'] in ('group', 'supergroup')]
        user_channels_list = [g for g in user_groups if g['type'] == 'channel']
        if user_groups_list:
            text += f'👥 Группы ({len(user_groups_list)}):\n'
            for group in user_groups_list[:5]:
                members_text = f' ({group['members_count']} участн.)' if group['members_count'] > 0 else ''
                title = group['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                text += f'• {title}{members_text}\n'
            if len(user_groups_list) > 5:
                text += f'... и еще {len(user_groups_list) - 5} групп\n'
            text += '\n'
        if user_channels_list:
            text += f'📢 Каналы ({len(user_channels_list)}):\n'
            for channel in user_channels_list[:5]:
                members_text = f' ({channel['members_count']} подписч.)' if channel['members_count'] > 0 else ''
                title = channel['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                text += f'• {title}{members_text}\n'
            if len(user_channels_list) > 5:
                text += f'... и еще {len(user_channels_list) - 5} каналов\n'
    await message.answer(text, reply_markup=keyboard, parse_mode=None)

@router.callback_query(F.data == 'add_group_by_link')
async def add_group_by_link_handler(callback: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    try:
        logger.info(f'Обработчик add_group_by_link вызван для пользователя {callback.from_user.id}')
        cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_add_group')]])
        await callback.message.edit_text('➕ ДОБАВЛЕНИЕ ЧАТА/ГРУППЫ/КАНАЛА ПО ССЫЛКЕ\n\nОтправьте ссылку на чат, группу или канал:\n\n• Публичная группа/канал: https://t.me/groupname или @groupname\n• Приватная группа/канал: https://t.me/joinchat/HASH или t.me/+HASH\n• Канал: https://t.me/channelname или @channelname\n\nБот присоединится к чату и добавит его в список.', reply_markup=cancel_keyboard, parse_mode=None)
        await callback.answer('Введите ссылку на группу')
        await state.set_state(GroupStates.waiting_for_group_link)
        logger.info(f'Пользователь {callback.from_user.id} начал добавление чата/группы/канала по ссылке, состояние установлено')
    except Exception as e:
        logger.error(f'Ошибка при обработке add_group_by_link: {e}', exc_info=True)
        try:
            await callback.answer('Произошла ошибка', show_alert=True)
        except:
            pass

@router.callback_query(F.data == 'cancel_add_group')
async def cancel_add_group_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Добавление чата отменено.', reply_markup=None)
    await callback.answer()

@router.message(StateFilter(GroupStates.waiting_for_group_link))
async def process_group_link(message: Message, state: FSMContext, bot: Bot):
    from services import join_chat_by_link, get_chat_info_by_link
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('❌ Отменено.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    chat_link = message.text.strip()
    processing_msg = await message.answer('⏳ Обрабатываю ссылку на чат...', reply_markup=get_cancel_keyboard(), parse_mode=None)
    if 'joinchat' in chat_link.lower() or '/+' in chat_link or chat_link.startswith('+'):
        result = await join_chat_by_link(message.from_user.id, chat_link)
        if result['success']:
            try:
                await processing_msg.delete()
            except:
                pass
            if result.get('message'):
                await message.answer(f'✅ {result.get('message')}\n\nЧат доступен для использования в рассылках.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
                logger.info(f'Пользователь {message.from_user.id} уже участник чата по ссылке {chat_link}')
            else:
                chat_type_emoji = {'group': '👥', 'supergroup': '👥', 'channel': '📢'}.get(result.get('chat_type', ''), '💬')
                chat_type_name = {'group': 'группа', 'supergroup': 'супергруппа', 'channel': 'канал'}.get(result.get('chat_type', ''), 'чат')
                await message.answer(f'✅ Успешно присоединились к {chat_type_name}!\n\n{chat_type_emoji} Название: {result.get('title', 'Без названия')}\nID: {result.get('chat_id')}\nТип: {chat_type_name}\n\nЧат добавлен в ваш список.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
                logger.info(f'Пользователь {message.from_user.id} присоединился к {chat_type_name} {result.get('chat_id')} по ссылке')
        else:
            try:
                await processing_msg.delete()
            except:
                pass
            await message.answer(f'❌ Не удалось присоединиться к чату:\n{result.get('error', 'Неизвестная ошибка')}\n\nПроверьте ссылку и попробуйте еще раз.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
    else:
        result = await get_chat_info_by_link(message.from_user.id, chat_link)
        if result['success']:
            try:
                await processing_msg.delete()
            except:
                pass
            chat_type_emoji = {'group': '👥', 'supergroup': '👥', 'channel': '📢'}.get(result.get('chat_type', ''), '💬')
            chat_type_name = {'group': 'группа', 'supergroup': 'супергруппа', 'channel': 'канал'}.get(result.get('chat_type', ''), 'чат')
            members_text = ''
            if result.get('members'):
                members_text = f'\nУчастников: {len(result.get('members', []))}'
            elif result.get('chat_type') == 'channel':
                members_text = '\n(Для каналов участники не отображаются)'
            await message.answer(f'✅ {chat_type_name.capitalize()} найдена!\n\n{chat_type_emoji} Название: {result.get('title', 'Без названия')}\nID: {result.get('chat_id')}\nТип: {chat_type_name}{members_text}\n\nЧат доступен для рассылок.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
            logger.info(f'Пользователь {message.from_user.id} добавил {chat_type_name} {result.get('chat_id')} по ссылке')
        else:
            try:
                await processing_msg.delete()
            except:
                pass
            error_msg = result.get('error', 'Неизвестная ошибка')
            if 'не группа' in error_msg.lower() or 'не супергруппа' in error_msg.lower() or 'не канал' in error_msg.lower():
                await message.answer(f'❌ Не удалось добавить чат:\n\n{error_msg}\n\n💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:\n• Это личный чат (не группа/канал)\n• Это бот (боты нельзя добавить в список групп)\n• Неверный формат ссылки\n\n✅ ЧТО ПРОВЕРИТЬ:\n• Убедитесь, что ссылка ведет на группу или канал\n• Попробуйте использовать invite-ссылку для приватных групп\n• Для публичных групп используйте формат: @groupname или https://t.me/groupname', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
            else:
                await message.answer(f'❌ Не удалось получить информацию о чате:\n{error_msg}\n\nПроверьте ссылку и убедитесь, что:\n• Чат существует\n• Вы являетесь участником чата\n• Ссылка правильная', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)), parse_mode=None)
    await state.clear()

@router.callback_query(F.data == 'close_groups')
async def close_groups_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Закрыто.', reply_markup=None)
    await callback.answer()

@router.message(Command('my_mailings'))
@router.message(F.text == '📊 Мои рассылки')
async def cmd_my_mailings(message: Message):
    campaigns = await crud.get_user_campaigns(message.from_user.id)
    if not campaigns:
        await message.answer("📊 У вас пока нет рассылок.\n\nСоздайте первую рассылку через кнопку '📧 Новая рассылка'", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    status_emoji = {'pending': '⏳', 'processing': '🔄', 'completed': '✅', 'failed': '❌'}
    text = f'📊 ВАШИ РАССЫЛКИ\n\nВсего: {len(campaigns)}\n\n'
    text += 'Нажмите на рассылку для просмотра деталей:\n\n'
    for campaign in campaigns[:5]:
        emoji = status_emoji.get(campaign.status, '❓')
        text += f'{emoji} #{campaign.id} - {campaign.campaign_id}\n'
        if campaign.status == 'completed':
            text += f'   ✅ {campaign.sent_successfully}/{campaign.total_recipients}\n'
    if len(campaigns) > 5:
        text += f'\n... и еще {len(campaigns) - 5} рассылок'
    await message.answer(text, reply_markup=get_campaigns_keyboard(campaigns))

@router.callback_query(F.data.startswith('campaign_'))
async def view_campaign(callback: CallbackQuery):
    campaign_id = int(callback.data.split('_')[1])
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer('Рассылка не найдена', show_alert=True)
        return
    if campaign.owner_id != callback.from_user.id and (not is_admin(callback.from_user.id)):
        await callback.answer('У вас нет прав на эту рассылку', show_alert=True)
        return
    report = await generate_personal_report(campaign_id)
    if report:
        try:
            await callback.message.edit_text(report, parse_mode=None)
        except Exception as e:
            logger.warning(f'Не удалось отредактировать сообщение: {e}')
            await callback.message.answer(report, parse_mode=None)
    else:
        await callback.message.edit_text('❌ Не удалось сгенерировать отчет.')
    await callback.answer()

@router.callback_query(F.data.startswith('campaigns_page_'))
async def process_campaigns_pagination(callback: CallbackQuery):
    page = int(callback.data.split('_')[2])
    campaigns = await crud.get_user_campaigns(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=get_campaigns_keyboard(campaigns, page=page))
    await callback.answer()

@router.message(Command('report'))
async def cmd_report(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /report <ID_рассылки>\nПример: /report 123')
        return
    try:
        campaign_id = int(parts[1])
    except ValueError:
        await message.answer('❌ Неверный формат ID. Используйте число.')
        return
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await message.answer('❌ Рассылка не найдена.')
        return
    if campaign.owner_id != message.from_user.id and (not is_admin(message.from_user.id)):
        await message.answer('❌ У вас нет прав на просмотр этого отчета.')
        return
    report = await generate_personal_report(campaign_id)
    if report:
        try:
            await message.answer(report, parse_mode=None)
        except Exception as e:
            logger.error(f'Ошибка при отправке отчета: {e}')
            await message.answer('❌ Не удалось отправить отчет. Попробуйте позже.')
    else:
        await message.answer('❌ Не удалось сгенерировать отчет.')
from aiogram import Router, F
from aiogram.types import CallbackQuery
import database as crud
from database import Recipient, async_session_maker
from sqlalchemy import select
from services import send_duplicates
from keyboards import get_duplicates_keyboard
from utils import logger

@router.callback_query(F.data.startswith('send_duplicates_'))
async def handle_send_duplicates(callback: CallbackQuery):
    campaign_id = int(callback.data.split('_')[2])
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer('Рассылка не найдена', show_alert=True)
        return
    if campaign.owner_id != callback.from_user.id:
        await callback.answer('У вас нет прав на эту рассылку', show_alert=True)
        return
    async with async_session_maker() as session:
        result = await session.execute(select(Recipient).where(Recipient.campaign_id == campaign_id, Recipient.is_duplicate == True))
        duplicate_recipients = list(result.scalars().all())
    if not duplicate_recipients:
        await callback.answer('Нет дублей для отправки', show_alert=True)
        return
    await callback.message.edit_text('ℹ️ Дубли не отправляются, так как сообщение уже было отправлено этим пользователям ранее.')
    await callback.answer()
    await callback.message.answer(f'ℹ️ Дубли не отправляются\n\nСообщение уже было отправлено этим пользователям в предыдущих рассылках.\nПовторная отправка не выполняется.')
    logger.info(f'Попытка отправить дубли для рассылки {campaign.campaign_id} - дубли не отправляются')

@router.callback_query(F.data.startswith('skip_duplicates_'))
async def handle_skip_duplicates(callback: CallbackQuery):
    campaign_id = int(callback.data.split('_')[2])
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer('Рассылка не найдена', show_alert=True)
        return
    await callback.message.edit_text('✅ Дубли пропущены.')
    await callback.answer()
    logger.info(f'Дубли пропущены для рассылки {campaign.campaign_id}')
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
import database as crud
from utils import logger
from config import MAIN_ADMIN_ID
from keyboards import get_main_keyboard, get_cancel_keyboard
from services import get_user_client

def is_admin(user_id: int) -> bool:
    return user_id == MAIN_ADMIN_ID

class ClientAuthStates(StatesGroup):
    waiting_for_api_id = State()
    waiting_for_api_hash = State()
    waiting_for_phone = State()

@router.message(Command('setup_my_client'))
@router.message(Command('setup_client'))
async def cmd_setup_client(message: Message, state: FSMContext):
    await message.answer("🔐 Настройка отправки сообщений от ВАШЕГО имени\n\nПосле настройки все ваши рассылки будут отправляться от вашего имени.\n\n📋 Инструкция:\n1. Зайдите на https://my.telegram.org\n2. Войдите с вашим номером телефона\n3. Перейдите в 'API development tools'\n4. Создайте приложение (любое название)\n5. Скопируйте api_id и api_hash\n\nВведите ваш API_ID (число):", reply_markup=get_cancel_keyboard())
    await state.set_state(ClientAuthStates.waiting_for_api_id)

@router.message(ClientAuthStates.waiting_for_api_id)
async def process_api_id(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    try:
        api_id = int(message.text)
        await state.update_data(api_id=api_id)
        await message.answer('✅ API_ID сохранен\n\nТеперь введите ваш API_HASH (длинная строка):', reply_markup=get_cancel_keyboard())
        await state.set_state(ClientAuthStates.waiting_for_api_hash)
    except ValueError:
        await message.answer('❌ API_ID должен быть числом. Попробуйте еще раз:')

@router.message(ClientAuthStates.waiting_for_api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    api_hash = message.text.strip()
    if len(api_hash) < 10:
        await message.answer('❌ API_HASH слишком короткий. Попробуйте еще раз:')
        return
    await state.update_data(api_hash=api_hash)
    await message.answer('✅ API_HASH сохранен\n\nВведите ваш номер телефона в международном формате:\nПример: +79991234567', reply_markup=get_cancel_keyboard())
    await state.set_state(ClientAuthStates.waiting_for_phone)

@router.message(ClientAuthStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.text == '❌ Отмена':
        await state.clear()
        await message.answer('Отменено.', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    phone = message.text.strip()
    if not phone.startswith('+'):
        await message.answer('❌ Номер должен начинаться с +. Пример: +79991234567')
        return
    data = await state.get_data()
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    try:
        await crud.update_user_client_auth(telegram_id=message.from_user.id, api_id=api_id, api_hash=api_hash, phone_number=phone, has_auth=False)
        await message.answer('✅ Данные сохранены\n\n🔐 Запускаю авторизацию...\n\nВам придет код подтверждения в Telegram на номер ' + phone + '\n\nВведите код когда получите:')
        await state.set_state(ClientAuthStates.waiting_for_code)
        from services import get_user_client
        try:
            await crud.update_user_client_auth(telegram_id=message.from_user.id, api_id=api_id, api_hash=api_hash, phone_number=phone, has_auth=False)
            await state.clear()
            await message.answer('✅ Данные сохранены!\n\n🔐 Авторизация произойдет автоматически при создании первой рассылки.\n\nИли перезапустите бота для авторизации сейчас.\n\nПосле авторизации все ваши рассылки будут отправляться от ВАШЕГО имени! 🎉', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
            logger.info(f'Пользователь {message.from_user.id} настроил Client API, авторизация при первой рассылке')
            if client:
                await crud.update_user_client_auth(telegram_id=message.from_user.id, has_auth=True)
                await state.clear()
                await message.answer('✅ Авторизация успешна!\n\nТеперь все ваши рассылки будут отправляться от вашего имени! 🎉', reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
                logger.info(f'Пользователь {message.from_user.id} успешно авторизовал Client API')
            else:
                await message.answer('❌ Не удалось авторизоваться. Проверьте данные и попробуйте еще раз через /setup_my_client')
                await state.clear()
        except Exception as e:
            logger.error(f'Ошибка авторизации Client API для {message.from_user.id}: {e}', exc_info=True)
            await message.answer(f'❌ Ошибка авторизации: {str(e)}\n\nПроверьте данные и попробуйте еще раз через /setup_my_client')
            await state.clear()
    except Exception as e:
        logger.error(f'Ошибка при сохранении Client API данных: {e}', exc_info=True)
        await message.answer('❌ Ошибка при сохранении данных. Попробуйте еще раз.')

@router.message(Command('my_client_status'))
async def cmd_my_client_status(message: Message):
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer('❌ Пользователь не найден')
        return
    if user.has_client_auth and user.api_id:
        status_text = f'✅ Ваш Client API настроен и авторизован\n\n📱 Номер: {user.phone_number or 'не указан'}\n🔑 API_ID: {user.api_id}\n\n✅ Все ваши рассылки будут отправляться от ВАШЕГО имени!'
    elif user.api_id:
        status_text = f'⚠️ Client API настроен, но не авторизован\n\n📱 Номер: {user.phone_number}\n🔑 API_ID: {user.api_id}\n\nАвторизация произойдет автоматически при первой рассылке.\nИли перезапустите бота для авторизации.'
    else:
        from config import API_ID, API_HASH
        if API_ID and API_HASH:
            status_text = 'ℹ️ Ваш персональный Client API не настроен\n\nВаши рассылки будут отправляться от имени владельца бота (общий Client API).\n\nЧтобы отправлять от ВАШЕГО имени:\n1. Отправьте /setup_my_client\n2. Введите ваши API_ID и API_HASH\n3. Авторизуйтесь\n\nПосле этого все ваши рассылки будут от вашего имени!'
        else:
            status_text = '❌ Client API не настроен\n\nРассылки будут работать только для пользователей, которые писали боту.\n\nДля отправки от вашего имени:\nОтправьте /setup_my_client'
    await message.answer(status_text, reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
