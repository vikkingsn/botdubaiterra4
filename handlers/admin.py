"""
Handlers для администратора
"""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import crud
from database.models import async_session_maker
from utils.validation import validate_template_name, validate_template_text
from utils.logger import logger
from config import MAIN_ADMIN_ID
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from keyboards.inline import get_templates_keyboard
from keyboards.reply import get_cancel_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == MAIN_ADMIN_ID


class TemplateStates(StatesGroup):
    waiting_for_name = State()  # Для нового шаблона
    waiting_for_text = State()  # Для нового шаблона
    waiting_for_media = State()  # Ожидание медиа файла (опционально)
    editing_name = State()
    editing_text = State()
    editing_media = State()  # Редактирование медиа


class ReportReceiversStates(StatesGroup):
    waiting_for_list_name = State()  # Ожидание названия нового списка
    waiting_for_receivers = State()  # Ожидание получателей для списка
    editing_list_name = State()  # Редактирование названия списка


@router.message(Command("add_template"))
@router.message(F.text == "📝 Шаблоны")
async def cmd_add_template(message: Message, state: FSMContext):
    """Показ списка шаблонов с кнопкой 'Новый шаблон'"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем все активные шаблоны
    templates = await crud.get_all_active_templates()
    
    # Формируем сообщение со списком шаблонов
    text = "📝 УПРАВЛЕНИЕ ШАБЛОНАМИ\n\n"
    
    if templates:
        text += "📋 Существующие шаблоны:\n"
        for i, template in enumerate(templates, 1):
            text += f"{i}. {template.name}\n"
        text += "\n"
    else:
        text += "📋 Шаблонов пока нет.\n\n"
    
    text += "💡 Выберите шаблон из списка или создайте новый:"
    
    # Создаем клавиатуру с существующими шаблонами и кнопкой "Новый шаблон"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = []
    
    for template in templates:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📝 {template.name}",
                callback_data=f"select_template_{template.id}"
            )
        ])
    
    # Добавляем кнопку "Новый шаблон"
    keyboard.append([
        InlineKeyboardButton(
            text="➕ Новый шаблон",
            callback_data="new_template"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_templates")
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        text,
        reply_markup=reply_markup
    )
    await state.clear()


@router.callback_query(F.data == "save_template_with_media")
async def save_template_with_media_handler(callback: CallbackQuery, state: FSMContext):
    """Сохранение шаблона с медиа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    data = await state.get_data()
    template_name = data.get("template_name")
    template_text = data.get("template_text", "")
    media_type = data.get("media_type")
    media_file_id = data.get("media_file_id")
    media_file_unique_id = data.get("media_file_unique_id")
    
    # Создаем шаблон с медиа
    template = await crud.create_template(
        name=template_name,
        text=template_text,
        created_by=callback.from_user.id,
        media_type=media_type,
        media_file_id=media_file_id,
        media_file_unique_id=media_file_unique_id
    )
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ Шаблон '{template_name}' сохранен с медиа. ID: #{template.id}",
        reply_markup=None
    )
    await callback.answer("Шаблон сохранен!")
    logger.info(f"Создан шаблон #{template.id} '{template_name}' с медиа {media_type} пользователем {callback.from_user.id}")


@router.callback_query(F.data == "save_template_no_media")
async def save_template_no_media_handler(callback: CallbackQuery, state: FSMContext):
    """Сохранение шаблона без медиа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    data = await state.get_data()
    template_name = data.get("template_name")
    template_text = data.get("template_text")
    
    # Создаем шаблон без медиа
    template = await crud.create_template(
        name=template_name,
        text=template_text,
        created_by=callback.from_user.id
    )
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ Шаблон '{template_name}' сохранен. ID: #{template.id}",
        reply_markup=None
    )
    await callback.answer("Шаблон сохранен!")
    logger.info(f"Создан шаблон #{template.id} '{template_name}' пользователем {callback.from_user.id}")


@router.callback_query(F.data == "add_media_to_template")
async def add_media_to_template_handler(callback: CallbackQuery, state: FSMContext):
    """Добавление медиа к шаблону"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📎 Отправьте медиа файл (фото, видео, документ и т.д.):\n\n"
        "Поддерживаемые типы:\n"
        "• 📷 Фото\n"
        "• 🎥 Видео\n"
        "• 📄 Документ\n"
        "• 🎵 Аудио\n"
        "• 🎤 Голосовое сообщение\n"
        "• 📹 Видео-кружок\n"
        "• 🎬 GIF/Анимация\n\n"
        "Текст подписи можно добавить к медиа.",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(TemplateStates.waiting_for_media)
    await callback.answer()


@router.callback_query(F.data == "add_more_media")
async def add_more_media_handler(callback: CallbackQuery, state: FSMContext):
    """Добавление еще одного медиа (пока поддерживаем только одно медиа)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    await callback.answer("⚠️ Пока поддерживается только одно медиа на шаблон. Используйте существующее или замените его.", show_alert=True)


@router.callback_query(F.data == "cancel_template")
async def cancel_template_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена создания шаблона"""
    await state.clear()
    await callback.message.edit_text("❌ Создание шаблона отменено.", reply_markup=None)
    await callback.answer("Отменено")


@router.message(StateFilter(TemplateStates.waiting_for_media))
async def process_template_media(message: Message, state: FSMContext):
    """Обработка медиа для шаблона"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    # Определяем тип медиа
    media_type = None
    media_file_id = None
    media_file_unique_id = None
    caption = message.caption or ""
    
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        media_file_unique_id = message.photo[-1].file_unique_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
        media_file_unique_id = message.video.file_unique_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
        media_file_unique_id = message.document.file_unique_id
    elif message.audio:
        media_type = "audio"
        media_file_id = message.audio.file_id
        media_file_unique_id = message.audio.file_unique_id
    elif message.voice:
        media_type = "voice"
        media_file_id = message.voice.file_id
        media_file_unique_id = message.voice.file_unique_id
    elif message.video_note:
        media_type = "video_note"
        media_file_id = message.video_note.file_id
        media_file_unique_id = message.video_note.file_unique_id
    elif message.animation:
        media_type = "animation"
        media_file_id = message.animation.file_id
        media_file_unique_id = message.animation.file_unique_id
    else:
        await message.answer("❌ Отправьте медиа файл (фото, видео, документ и т.д.):")
        return
    
    # Обновляем текст, если есть подпись
    data = await state.get_data()
    template_text = data.get("template_text", "")
    if caption:
        template_text = caption
    
    await state.update_data(
        template_text=template_text,
        media_type=media_type,
        media_file_id=media_file_id,
        media_file_unique_id=media_file_unique_id
    )
    
    # Показываем превью и предлагаем сохранить
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить шаблон", callback_data="save_template_with_media")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_template")]
    ])
    
    media_names = {
        "photo": "📷 Фото",
        "video": "🎥 Видео",
        "document": "📄 Документ",
        "audio": "🎵 Аудио",
        "voice": "🎤 Голосовое сообщение",
        "video_note": "📹 Видео-кружок",
        "animation": "🎬 GIF/Анимация"
    }
    
    await message.answer(
        f"✅ Медиа получено: {media_names.get(media_type, media_type)}\n\n"
        f"Текст подписи: {template_text if template_text else '(без подписи)'}\n\n"
        f"Готово к сохранению!",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("select_template_"))
async def select_template_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора существующего шаблона"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        template_id = int(callback.data.split("_")[2])
        template = await crud.get_template(template_id)
        
        if not template:
            await callback.answer("Шаблон не найден", show_alert=True)
            return
        
        # Показываем шаблон и даем выбор действий
        template_text = template.text[:500] + "..." if len(template.text) > 500 else (template.text if template.text else "(без текста)")
        
        # Формируем текст с информацией о медиа
        display_text = f"📝 ШАБЛОН: **{template.name}**\n\n"
        
        if template.media_type:
            media_names = {
                "photo": "📷 Фото",
                "video": "🎥 Видео",
                "document": "📄 Документ",
                "audio": "🎵 Аудио",
                "voice": "🎤 Голосовое сообщение",
                "video_note": "📹 Видео-кружок",
                "animation": "🎬 GIF/Анимация"
            }
            display_text += f"Медиа: {media_names.get(template.media_type, template.media_type)}\n\n"
        
        display_text += f"📄 Текст:\n━━━━━━━━━━━━━━━━━━━━\n{template_text}\n━━━━━━━━━━━━━━━━━━━━\n\n"
        display_text += "Выберите действие:"
        
        await callback.message.edit_text(
            display_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_template_{template_id}"),
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_template_{template_id}")
                ],
                [
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_templates")
                ]
            ])
        )
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при выборе шаблона: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "new_template")
async def new_template_handler(callback: CallbackQuery, state: FSMContext):
    """Начало создания нового шаблона"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "➕ СОЗДАНИЕ НОВОГО ШАБЛОНА\n\n"
        "Введите название шаблона:",
        reply_markup=None
    )
    await callback.message.answer(
        "Введите название нового шаблона:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()
    await state.set_state(TemplateStates.waiting_for_name)


@router.message(StateFilter(TemplateStates.waiting_for_name))
async def process_template_name(message: Message, state: FSMContext):
    """Обработка названия нового шаблона"""
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
    
    # Текст может быть пустым, если есть медиа с подписью
    text_content = message.text or message.caption or ""
    
    # Если есть медиа в сообщении, сохраняем его
    media_type = None
    media_file_id = None
    media_file_unique_id = None
    
    if message.photo:
        media_type = "photo"
        # Берем фото наибольшего размера (последнее в списке)
        media_file_id = message.photo[-1].file_id
        media_file_unique_id = message.photo[-1].file_unique_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
        media_file_unique_id = message.video.file_unique_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
        media_file_unique_id = message.document.file_unique_id
    elif message.audio:
        media_type = "audio"
        media_file_id = message.audio.file_id
        media_file_unique_id = message.audio.file_unique_id
    elif message.voice:
        media_type = "voice"
        media_file_id = message.voice.file_id
        media_file_unique_id = message.voice.file_unique_id
    elif message.video_note:
        media_type = "video_note"
        media_file_id = message.video_note.file_id
        media_file_unique_id = message.video_note.file_unique_id
    elif message.animation:
        media_type = "animation"
        media_file_id = message.animation.file_id
        media_file_unique_id = message.animation.file_unique_id
    
    # Если есть медиа, сохраняем текст как подпись
    if media_type:
        if not text_content:
            text_content = ""  # Медиа может быть без подписи
        await state.update_data(
            template_text=text_content,
            media_type=media_type,
            media_file_id=media_file_id,
            media_file_unique_id=media_file_unique_id
        )
        
        # Спрашиваем, нужно ли добавить еще медиа или завершить
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить шаблон", callback_data="save_template_with_media")],
            [InlineKeyboardButton(text="➕ Добавить еще медиа", callback_data="add_more_media")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_template")]
        ])
        
        media_names = {
            "photo": "📷 Фото",
            "video": "🎥 Видео",
            "document": "📄 Документ",
            "audio": "🎵 Аудио",
            "voice": "🎤 Голосовое сообщение",
            "video_note": "📹 Видео-кружок",
            "animation": "🎬 GIF/Анимация"
        }
        
        await message.answer(
            f"✅ Медиа получено: {media_names.get(media_type, media_type)}\n\n"
            f"Текст подписи: {text_content if text_content else '(без подписи)'}\n\n"
            f"Выберите действие:",
            reply_markup=keyboard
        )
        return
    
    # Если нет медиа, проверяем текст
    if not text_content:
        await message.answer("❌ Введите текст сообщения или отправьте медиа с подписью:")
        return
    
    is_valid, error = validate_template_text(text_content)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте еще раз:")
        return
    
    # Сохраняем текст и спрашиваем про медиа
    await state.update_data(template_text=text_content)
    
    # Спрашиваем, нужно ли добавить медиа
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить без медиа", callback_data="save_template_no_media")],
        [InlineKeyboardButton(text="➕ Добавить медиа", callback_data="add_media_to_template")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_template")]
    ])
    
    await message.answer(
        f"✅ Текст сохранен:\n\n{text_content[:200]}{'...' if len(text_content) > 200 else ''}\n\n"
        f"Хотите добавить медиа (фото, видео и т.д.) к шаблону?",
        reply_markup=keyboard
    )


@router.message(Command("set_report_receivers"))
async def cmd_set_report_receivers(message: Message, state: FSMContext):
    """Начало настройки получателей отчетов (через команду)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    await message.answer(
        "Введите список получателей сводных отчетов.\n\n"
        "Поддерживаемые форматы:\n"
        "• @username (пользователи)\n"
        "• user_id (число)\n"
        "• Ссылки: https://t.me/user\n"
        "• Группы/каналы: @groupname или https://t.me/groupname\n\n"
        "Пример: @user1 @user2 123456789 @mygroup",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ReportReceiversStates.waiting_for_receivers)


@router.callback_query(F.data == "report_receivers_menu")
async def report_receivers_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Меню списков получателей отчетов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    # Получаем все списки получателей
    lists = await crud.get_all_report_receiver_lists()
    
    text = "📋 ПОЛУЧАТЕЛИ ОТЧЕТОВ\n\n"
    
    if lists:
        text += "📝 Существующие списки:\n"
        for i, receiver_list in enumerate(lists, 1):
            # Подсчитываем количество получателей в списке
            receivers = await crud.get_receivers_by_list(receiver_list.id)
            text += f"{i}. {receiver_list.name} ({len(receivers)} получателей)\n"
        text += "\n"
    else:
        text += "📝 Списков пока нет.\n\n"
    
    text += "💡 Выберите список или создайте новый:"
    
    # Создаем клавиатуру со списками и кнопкой "Новый список"
    keyboard = []
    
    for receiver_list in lists:
        receivers = await crud.get_receivers_by_list(receiver_list.id)
        keyboard.append([
            InlineKeyboardButton(
                text=f"📋 {receiver_list.name} ({len(receivers)})",
                callback_data=f"select_receiver_list_{receiver_list.id}"
            )
        ])
    
    # Добавляем кнопку "Новый список"
    keyboard.append([
        InlineKeyboardButton(
            text="➕ Новый список",
            callback_data="new_receiver_list"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_receiver_lists")
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup
    )
    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "new_receiver_list")
async def new_receiver_list_handler(callback: CallbackQuery, state: FSMContext):
    """Создание нового списка получателей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "➕ СОЗДАНИЕ НОВОГО СПИСКА ПОЛУЧАТЕЛЕЙ\n\n"
        "Введите название списка:",
        reply_markup=None
    )
    await callback.message.answer(
        "Введите название нового списка:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()
    await state.set_state(ReportReceiversStates.waiting_for_list_name)


@router.message(StateFilter(ReportReceiversStates.waiting_for_list_name))
async def process_list_name(message: Message, state: FSMContext):
    """Обработка названия нового списка"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return
    
    list_name = message.text.strip()
    
    # Создаем список
    receiver_list = await crud.create_report_receiver_list(list_name)
    
    # Сохраняем list_id в state для добавления получателей
    await state.update_data(list_id=receiver_list.id, list_name=list_name)
    
    await message.answer(
        f"✅ Список '{list_name}' создан.\n\n"
        "Теперь добавьте получателей в этот список.\n\n"
        "Поддерживаемые форматы:\n"
        "• @username (пользователи)\n"
        "• user_id (число)\n"
        "• Ссылки: https://t.me/user\n"
        "• Группы/каналы: @groupname или https://t.me/groupname\n\n"
        "Введите список получателей:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ReportReceiversStates.waiting_for_receivers)
    logger.info(f"Создан список получателей '{list_name}' пользователем {message.from_user.id}")


@router.callback_query(F.data.startswith("select_receiver_list_"))
async def select_receiver_list_handler(callback: CallbackQuery, state: FSMContext):
    """Просмотр списка получателей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        list_id = int(callback.data.split("_")[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        
        if not receiver_list:
            await callback.answer("Список не найден", show_alert=True)
            return
        
        # Получаем получателей из списка
        receivers = await crud.get_receivers_by_list(list_id)
        
        # Формируем текст со списком получателей (без Markdown для избежания ошибок парсинга)
        text = f"📋 СПИСОК: {receiver_list.name}\n\n"
        
        if receivers:
            text += f"📝 Получатели ({len(receivers)}):\n"
            for i, receiver in enumerate(receivers[:20], 1):  # Показываем первые 20
                text += f"{i}. {receiver.identifier}\n"
            if len(receivers) > 20:
                text += f"\n... и еще {len(receivers) - 20} получателей\n"
        else:
            text += "📝 Получателей пока нет.\n"
        
        text += "\nВыберите действие:"
        
        # Создаем клавиатуру с кнопками действий
        keyboard_buttons = [
            [
                InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"edit_receiver_list_{list_id}"),
                InlineKeyboardButton(text="➕ Добавить получателей", callback_data=f"add_to_list_{list_id}")
            ],
            [
                InlineKeyboardButton(text="🗑️ Удалить список", callback_data=f"delete_receiver_list_{list_id}")
            ]
        ]
        
        # Добавляем кнопки для удаления отдельных получателей (если есть получатели)
        if receivers:
            keyboard_buttons.append([
                InlineKeyboardButton(text="📝 Управление получателями", callback_data=f"manage_receivers_{list_id}")
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_receiver_lists")
        ])
        
        await callback.message.edit_text(
            text,
            parse_mode=None,  # Без Markdown для избежания ошибок парсинга
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при выборе списка получателей: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("add_to_list_"))
async def add_to_list_handler(callback: CallbackQuery, state: FSMContext):
    """Добавление получателей в список"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        list_id = int(callback.data.split("_")[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        
        if not receiver_list:
            await callback.answer("Список не найден", show_alert=True)
            return
        
        await state.update_data(list_id=list_id, list_name=receiver_list.name)
        
        await callback.message.edit_text(
            f"➕ ДОБАВЛЕНИЕ ПОЛУЧАТЕЛЕЙ В СПИСОК\n\n"
            f"Список: {receiver_list.name}\n\n"
            "Введите список получателей.\n\n"
            "Поддерживаемые форматы:\n"
            "• @username (пользователи)\n"
            "• user_id (число)\n"
            "• Ссылки: https://t.me/user\n"
            "• Группы/каналы: @groupname или https://t.me/groupname\n"
            "• Приватные группы: https://t.me/joinchat/HASH\n\n"
            "Пример: @user1 @user2 123456789 @mygroup\n"
            "https://t.me/joinchat/ABC123",
            parse_mode=None,  # Без Markdown для избежания ошибок парсинга
            reply_markup=None
        )
        await callback.message.answer(
            "Введите список получателей (через запятую или пробел):",
            reply_markup=get_cancel_keyboard()
        )
        await callback.answer()
        await state.set_state(ReportReceiversStates.waiting_for_receivers)
    except Exception as e:
        logger.error(f"Ошибка при добавлении получателей в список: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(StateFilter(ReportReceiversStates.waiting_for_receivers))
async def process_report_receivers(message: Message, state: FSMContext):
    """Обработка списка получателей отчетов"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    # Получаем list_id из state
    data = await state.get_data()
    list_id = data.get("list_id")
    list_name = data.get("list_name", "список")
    
    if not list_id:
        await message.answer("❌ Ошибка: список не найден. Начните заново.", reply_markup=get_main_keyboard(is_admin=True))
        await state.clear()
        return
    
    # Используем тот же парсер, что и для рассылок
    from utils.parsers import parse_recipients_list, validate_recipients_list
    
    try:
        recipients = parse_recipients_list(message.text)
        logger.info(f"Парсинг получателей отчетов: найдено {len(recipients)} получателей для списка {list_id}")
        
        if not recipients:
            await message.answer(
                "❌ Не удалось распознать получателей в вашем сообщении.\n\n"
                "Проверьте формат:\n"
                "• @username\n"
                "• user_id (только цифры)\n"
                "• Ссылки: https://t.me/user\n"
                "• Группы: @groupname или https://t.me/groupname\n\n"
                "Попробуйте еще раз:",
                reply_markup=get_cancel_keyboard()
            )
            return
    except Exception as e:
        logger.error(f"Ошибка при парсинге получателей отчетов: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при обработке списка получателей.\n\n"
            "Попробуйте еще раз или нажмите '❌ Отмена':",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    is_valid, error = validate_recipients_list(recipients)
    if not is_valid:
        await message.answer(
            f"❌ {error}\n\nПопробуйте еще раз. Введите список получателей:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Извлекаем оригинальные идентификаторы
    identifiers = [r["original"] for r in recipients]
    
    # Добавляем получателей в список
    receivers = await crud.add_report_receivers_to_list(list_id, identifiers)
    
    await state.clear()
    
    # Показываем обновленный список
    receiver_list = await crud.get_report_receiver_list(list_id)
    updated_receivers = await crud.get_receivers_by_list(list_id)
    
    text = f"✅ Добавлено получателей в список '{list_name}': {len(receivers)}\n\n"
    text += f"📋 СПИСОК: {receiver_list.name}\n\n"
    
    if updated_receivers:
        text += f"📝 Получатели ({len(updated_receivers)}):\n"
        for i, receiver in enumerate(updated_receivers[:10], 1):
            text += f"{i}. {receiver.identifier}\n"
        if len(updated_receivers) > 10:
            text += f"\n... и еще {len(updated_receivers) - 10} получателей\n"
    
    text += "\nВыберите действие:"
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"edit_receiver_list_{list_id}"),
            InlineKeyboardButton(text="➕ Добавить получателей", callback_data=f"add_to_list_{list_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ Удалить список", callback_data=f"delete_receiver_list_{list_id}")
        ]
    ]
    
    if updated_receivers:
        keyboard_buttons.append([
            InlineKeyboardButton(text="📝 Управление получателями", callback_data=f"manage_receivers_{list_id}")
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel_receiver_lists")
    ])
    
    await message.answer(
        text,
        parse_mode=None,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    logger.info(f"Добавлено {len(receivers)} получателей в список {list_id} пользователем {message.from_user.id}")


@router.message(Command("templates_list"))
async def cmd_templates_list(message: Message):
    """Список всех шаблонов с возможностью редактирования"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    templates = await crud.get_all_active_templates()
    
    if not templates:
        await message.answer("📝 Шаблонов пока нет.")
        return
    
    await message.answer(
        "📝 Управление шаблонами:\n\nВыберите шаблон для редактирования или удаления:",
        reply_markup=get_templates_keyboard(templates, for_selection=False)
    )


@router.callback_query(F.data.startswith("edit_template_name_"))
async def edit_template_name_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование названия шаблона"""
    template_id = int(callback.data.split("_")[3])
    template = await crud.get_template(template_id)
    
    await state.update_data(template_id=template_id, editing_field="name")
    await state.set_state(TemplateStates.editing_name)
    
    await callback.message.edit_text(
        f"✏️ Редактирование названия шаблона\n\n"
        f"Текущее название: **{template.name}**\n\n"
        "Введите новое название:",
        parse_mode="Markdown",
        reply_markup=None
    )
    await callback.message.answer("Введите новое название:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_template_text_"))
async def edit_template_text_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование текста шаблона"""
    template_id = int(callback.data.split("_")[3])
    template = await crud.get_template(template_id)
    
    await state.update_data(template_id=template_id, editing_field="text")
    await state.set_state(TemplateStates.editing_text)
    
    await callback.message.edit_text(
        f"✏️ Редактирование текста шаблона\n\n"
        f"Текущий текст:\n━━━━━━━━━━━━━━━━━━━━\n{template.text}\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите новый текст:",
        parse_mode="Markdown",
        reply_markup=None
    )
    await callback.message.answer("Введите новый текст (поддерживается Markdown):", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_template_both_"))
async def edit_template_both_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование и названия, и текста"""
    template_id = int(callback.data.split("_")[3])
    template = await crud.get_template(template_id)
    
    await state.update_data(template_id=template_id, editing_field="both")
    await state.set_state(TemplateStates.editing_name)
    
    await callback.message.edit_text(
        f"✏️ Редактирование шаблона: **{template.name}**\n\n"
        "Введите новое название:",
        parse_mode="Markdown",
        reply_markup=None
    )
    await callback.message.answer("Введите новое название:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_template_"))
async def edit_template_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования шаблона (общий обработчик для edit_template_ID)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        template_id = int(callback.data.split("_")[2])
        template = await crud.get_template(template_id)
        
        if not template:
            await callback.answer("Шаблон не найден", show_alert=True)
            return
        
        await state.update_data(template_id=template_id, template_name=template.name, template_text=template.text)
        
        await callback.message.edit_text(
            f"✏️ Редактирование шаблона: **{template.name}**\n\n"
            "Что вы хотите изменить?\n"
            "1️⃣ Название\n"
            "2️⃣ Текст\n"
            "3️⃣ И то, и другое",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="1️⃣ Название", callback_data=f"edit_template_name_{template_id}"),
                    InlineKeyboardButton(text="2️⃣ Текст", callback_data=f"edit_template_text_{template_id}")
                ],
                [
                    InlineKeyboardButton(text="3️⃣ Оба", callback_data=f"edit_template_both_{template_id}")
                ],
                [
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_templates")
                ]
            ])
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования шаблона: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(StateFilter(TemplateStates.editing_name))
async def process_editing_name(message: Message, state: FSMContext):
    """Обработка нового названия"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    is_valid, error = validate_template_name(message.text)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте еще раз:")
        return
    
    data = await state.get_data()
    template_id = data.get("template_id")
    editing_field = data.get("editing_field", "name")
    
    if editing_field == "both":
        # Сохраняем название и переходим к тексту
        await state.update_data(template_name=message.text)
        await state.set_state(TemplateStates.editing_text)
        template = await crud.get_template(template_id)
        await message.answer(
            f"✅ Название сохранено: **{message.text}**\n\n"
            f"Текущий текст:\n━━━━━━━━━━━━━━━━━━━━\n{template.text}\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Теперь введите новый текст:",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
    else:
        # Только название
        template = await crud.update_template(template_id, name=message.text)
        await state.clear()
        await message.answer(
            f"✅ Название шаблона обновлено!\n\n"
            f"Новое название: **{template.name}**",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin=True)
        )
        logger.info(f"Шаблон #{template_id} обновлен пользователем {message.from_user.id}: новое название")


@router.message(StateFilter(TemplateStates.editing_text))
async def process_editing_text(message: Message, state: FSMContext):
    """Обработка нового текста"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    is_valid, error = validate_template_text(message.text)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте еще раз:")
        return
    
    data = await state.get_data()
    template_id = data.get("template_id")
    editing_field = data.get("editing_field", "text")
    template_name = data.get("template_name")
    
    if editing_field == "both" and template_name:
        # Обновляем и название, и текст
        template = await crud.update_template(template_id, name=template_name, text=message.text)
        await state.clear()
        await message.answer(
            f"✅ Шаблон полностью обновлен!\n\n"
            f"Название: **{template.name}**\n"
            f"Текст обновлен",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin=True)
        )
        logger.info(f"Шаблон #{template_id} полностью обновлен пользователем {message.from_user.id}")
    else:
        # Только текст
        template = await crud.update_template(template_id, text=message.text)
        await state.clear()
        await message.answer(
            f"✅ Текст шаблона обновлен!\n\n"
            f"Шаблон: **{template.name}**",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(is_admin=True)
        )
        logger.info(f"Текст шаблона #{template_id} обновлен пользователем {message.from_user.id}")


@router.callback_query(F.data.startswith("delete_template_"))
async def delete_template_handler(callback: CallbackQuery):
    """Удаление шаблона"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        template_id = int(callback.data.split("_")[2])
        template = await crud.get_template(template_id)
        
        if not template:
            await callback.answer("Шаблон не найден", show_alert=True)
            return
        
        # Подтверждение удаления
        await callback.message.edit_text(
            f"🗑️ Удаление шаблона\n\n"
            f"Название: **{template.name}**\n\n"
            f"⚠️ Вы уверены? Шаблон будет помечен как неактивный.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{template_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_templates")
                ]
            ])
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при удалении шаблона: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


# Обработчик для удаления списков должен быть ПЕРЕД обработчиком для шаблонов
# (более специфичный фильтр должен быть первым)


@router.callback_query(F.data == "cancel_templates")
async def cancel_templates_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена работы с шаблонами"""
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_keyboard(is_admin=True)
    )


@router.callback_query(F.data == "open_templates")
async def open_templates_handler(callback: CallbackQuery, state: FSMContext):
    """Открытие меню шаблонов из настроек"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    # Получаем все активные шаблоны
    templates = await crud.get_all_active_templates()
    
    # Формируем сообщение со списком шаблонов
    text = "📝 УПРАВЛЕНИЕ ШАБЛОНАМИ\n\n"
    
    if templates:
        text += "📋 Существующие шаблоны:\n"
        for i, template in enumerate(templates, 1):
            text += f"{i}. {template.name}\n"
        text += "\n"
    else:
        text += "📋 Шаблонов пока нет.\n\n"
    
    text += "💡 Выберите шаблон из списка или создайте новый:"
    
    # Создаем клавиатуру с существующими шаблонами и кнопкой "Новый шаблон"
    keyboard = []
    
    for template in templates:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📝 {template.name}",
                callback_data=f"select_template_{template.id}"
            )
        ])
    
    # Добавляем кнопку "Новый шаблон"
    keyboard.append([
        InlineKeyboardButton(
            text="➕ Новый шаблон",
            callback_data="new_template"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_templates")
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_receiver_list_"))
async def edit_receiver_list_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование списка получателей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        list_id = int(callback.data.split("_")[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        
        if not receiver_list:
            await callback.answer("Список не найден", show_alert=True)
            return
        
        await state.update_data(list_id=list_id)
        await state.set_state(ReportReceiversStates.editing_list_name)
        
        await callback.message.edit_text(
            f"✏️ РЕДАКТИРОВАНИЕ СПИСКА\n\n"
            f"Текущее название: {receiver_list.name}\n\n"
            "Введите новое название:",
            parse_mode=None,  # Без Markdown для избежания ошибок парсинга
            reply_markup=None
        )
        await callback.message.answer(
            "Введите новое название списка:",
            reply_markup=get_cancel_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при редактировании списка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(StateFilter(ReportReceiversStates.editing_list_name))
async def process_editing_list_name(message: Message, state: FSMContext):
    """Обработка нового названия списка"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=True))
        return
    
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return
    
    data = await state.get_data()
    list_id = data.get("list_id")
    
    if not list_id:
        await message.answer("❌ Ошибка: список не найден.", reply_markup=get_main_keyboard(is_admin=True))
        await state.clear()
        return
    
    receiver_list = await crud.update_report_receiver_list(list_id, name=message.text.strip())
    
    if receiver_list:
        await state.clear()
        
        # Показываем обновленный список
        receivers = await crud.get_receivers_by_list(list_id)
        
        text = f"✅ Название списка обновлено!\n\n"
        text += f"📋 СПИСОК: {receiver_list.name}\n\n"
        
        if receivers:
            text += f"📝 Получатели ({len(receivers)}):\n"
            for i, receiver in enumerate(receivers[:10], 1):
                text += f"{i}. {receiver.identifier}\n"
            if len(receivers) > 10:
                text += f"\n... и еще {len(receivers) - 10} получателей\n"
        else:
            text += "📝 Получателей пока нет.\n"
        
        text += "\nВыберите действие:"
        
        keyboard_buttons = [
            [
                InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"edit_receiver_list_{list_id}"),
                InlineKeyboardButton(text="➕ Добавить получателей", callback_data=f"add_to_list_{list_id}")
            ],
            [
                InlineKeyboardButton(text="🗑️ Удалить список", callback_data=f"delete_receiver_list_{list_id}")
            ]
        ]
        
        if receivers:
            keyboard_buttons.append([
                InlineKeyboardButton(text="📝 Управление получателями", callback_data=f"manage_receivers_{list_id}")
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel_receiver_lists")
        ])
        
        await message.answer(
            text,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        logger.info(f"Список получателей #{list_id} обновлен пользователем {message.from_user.id}")
    else:
        await message.answer("❌ Не удалось обновить список", reply_markup=get_main_keyboard(is_admin=True))
        await state.clear()


@router.callback_query(F.data.startswith("delete_receiver_list_"))
async def delete_receiver_list_handler(callback: CallbackQuery):
    """Удаление списка получателей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        list_id = int(callback.data.split("_")[3])
        receiver_list = await crud.get_report_receiver_list(list_id)
        
        if not receiver_list:
            await callback.answer("Список не найден", show_alert=True)
            return
        
        # Подтверждение удаления
        receivers = await crud.get_receivers_by_list(list_id)
        await callback.message.edit_text(
            f"🗑️ УДАЛЕНИЕ СПИСКА\n\n"
            f"Название: {receiver_list.name}\n"
            f"Получателей: {len(receivers)}\n\n"
            f"⚠️ Вы уверены? Список будет помечен как неактивный.",
            parse_mode=None,  # Без Markdown для избежания ошибок парсинга
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_list_{list_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_receiver_lists")
                ]
            ])
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при удалении списка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete_list_"))
async def confirm_delete_list_handler(callback: CallbackQuery):
    """Подтверждение удаления списка"""
    list_id = int(callback.data.split("_")[3])
    
    success = await crud.delete_report_receiver_list(list_id)
    
    if success:
        await callback.message.edit_text("✅ Список удален (помечен как неактивный)")
        await callback.answer("Список удален")
        logger.info(f"Список получателей #{list_id} удален пользователем {callback.from_user.id}")
    else:
        await callback.message.edit_text("❌ Не удалось удалить список")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_template(callback: CallbackQuery):
    """Подтверждение удаления шаблона"""
    template_id = int(callback.data.split("_")[2])
    
    success = await crud.delete_template(template_id)
    
    if success:
        await callback.message.edit_text("✅ Шаблон удален (помечен как неактивный)")
        await callback.answer("Шаблон удален")
        logger.info(f"Шаблон #{template_id} удален пользователем {callback.from_user.id}")
    else:
        await callback.message.edit_text("❌ Не удалось удалить шаблон")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("manage_receivers_"))
async def manage_receivers_handler(callback: CallbackQuery, state: FSMContext):
    """Управление получателями в списке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        list_id = int(callback.data.split("_")[2])
        receiver_list = await crud.get_report_receiver_list(list_id)
        
        if not receiver_list:
            await callback.answer("Список не найден", show_alert=True)
            return
        
        receivers = await crud.get_receivers_by_list(list_id)
        
        if not receivers:
            await callback.answer("В списке нет получателей", show_alert=True)
            return
        
        text = f"📝 УПРАВЛЕНИЕ ПОЛУЧАТЕЛЯМИ\n\n"
        text += f"Список: {receiver_list.name}\n\n"
        text += "Выберите получателя для удаления:\n\n"
        
        # Создаем клавиатуру с получателями (по 2 в ряд)
        keyboard = []
        for i in range(0, len(receivers), 2):
            row = []
            row.append(
                InlineKeyboardButton(
                    text=f"🗑️ {receivers[i].identifier[:20]}",
                    callback_data=f"delete_receiver_{receivers[i].id}"
                )
            )
            if i + 1 < len(receivers):
                row.append(
                    InlineKeyboardButton(
                        text=f"🗑️ {receivers[i+1].identifier[:20]}",
                        callback_data=f"delete_receiver_{receivers[i+1].id}"
                    )
                )
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"select_receiver_list_{list_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_receiver_lists")
        ])
        
        await callback.message.edit_text(
            text,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при управлении получателями: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("delete_receiver_"))
async def delete_receiver_handler(callback: CallbackQuery):
    """Удаление получателя из списка"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    try:
        receiver_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о получателе для определения list_id
        from database.models import ReportReceiver, async_session_maker
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(ReportReceiver).where(ReportReceiver.id == receiver_id)
            )
            receiver = result.scalar_one_or_none()
            
            if not receiver:
                await callback.answer("Получатель не найден", show_alert=True)
                return
            
            list_id = receiver.list_id
            identifier = receiver.identifier
        
        success = await crud.delete_report_receiver(receiver_id)
        
        if success:
            await callback.answer(f"✅ Получатель {identifier} удален")
            
            # Возвращаемся к списку
            receiver_list = await crud.get_report_receiver_list(list_id)
            receivers = await crud.get_receivers_by_list(list_id)
            
            text = f"📋 СПИСОК: {receiver_list.name}\n\n"
            
            if receivers:
                text += f"📝 Получатели ({len(receivers)}):\n"
                for i, rec in enumerate(receivers[:20], 1):
                    text += f"{i}. {rec.identifier}\n"
                if len(receivers) > 20:
                    text += f"\n... и еще {len(receivers) - 20} получателей\n"
            else:
                text += "📝 Получателей пока нет.\n"
            
            text += "\nВыберите действие:"
            
            keyboard_buttons = [
                [
                    InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"edit_receiver_list_{list_id}"),
                    InlineKeyboardButton(text="➕ Добавить получателей", callback_data=f"add_to_list_{list_id}")
                ],
                [
                    InlineKeyboardButton(text="🗑️ Удалить список", callback_data=f"delete_receiver_list_{list_id}")
                ]
            ]
            
            if receivers:
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📝 Управление получателями", callback_data=f"manage_receivers_{list_id}")
                ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_receiver_lists")
            ])
            
            await callback.message.edit_text(
                text,
                parse_mode=None,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            )
            
            logger.info(f"Получатель #{receiver_id} удален из списка {list_id} пользователем {callback.from_user.id}")
        else:
            await callback.answer("❌ Не удалось удалить получателя", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при удалении получателя: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "cancel_receiver_lists")
async def cancel_receiver_lists_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена работы со списками получателей"""
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_keyboard(is_admin=True)
    )


@router.callback_query(F.data == "close_settings")
async def close_settings_handler(callback: CallbackQuery):
    """Закрытие меню настроек"""
    await callback.message.edit_text("⚙️ Настройки закрыты")
    await callback.answer()


@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message):
    """Меню настроек для администратора"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем списки получателей отчетов
    receiver_lists = await crud.get_all_report_receiver_lists()
    
    settings_text = "⚙️ НАСТРОЙКИ БОТА\n\n"
    settings_text += "📝 Выберите действие:"
    
    # Создаем inline-клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Получатели отчетов", callback_data="report_receivers_menu")
        ],
        [
            InlineKeyboardButton(text="📝 Шаблоны", callback_data="open_templates")
        ],
        [
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close_settings")
        ]
    ])
    
    await message.answer(
        settings_text,
        reply_markup=keyboard
    )
