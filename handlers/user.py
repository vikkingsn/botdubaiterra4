"""
Handlers для пользователей
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from database import crud
from utils.parsers import parse_recipients_list, validate_recipients_list, format_recipient_list
from utils.logger import logger
from config import MAIN_ADMIN_ID
from keyboards.reply import get_main_keyboard, get_cancel_keyboard, get_recipients_keyboard
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from keyboards.inline import (
    get_templates_keyboard, get_confirm_mailing_keyboard,
    get_campaigns_keyboard, get_delay_keyboard, get_max_recipients_keyboard
)
from services.report_service import generate_personal_report

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == MAIN_ADMIN_ID


class MailingStates(StatesGroup):
    waiting_for_template = State()
    waiting_for_recipients = State()
    waiting_for_group_selection = State()  # Выбор группы для рассылки
    waiting_for_delay = State()
    waiting_for_max_recipients = State()  # Выбор максимального количества получателей
    confirm_mailing = State()


class GroupStates(StatesGroup):
    waiting_for_group_link = State()  # Ввод ссылки на группу для добавления


def get_cancel_keyboard_for_groups() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены для добавления группы"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


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
    
    # Добавляем информацию о добавлении бота в группы
    try:
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username
        if bot_username:
            welcome_text += f"\n\n🤖 Чтобы добавить бота в группу/канал, используйте команду /invite"
    except:
        pass
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(is_admin=is_admin_user)
    )
    logger.info(f"Пользователь {message.from_user.id} зарегистрирован/вошел в бота")


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message, bot: Bot):
    """Справка по использованию бота"""
    is_admin_user = is_admin(message.from_user.id)
    
    # Получаем информацию о боте для ссылок
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        if bot_username:
            add_to_group_link = f"https://t.me/{bot_username}?startgroup"
            add_to_channel_link = f"https://t.me/{bot_username}?startchannel"
            invite_text = f"""
🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:

📱 Добавить в группу:
{add_to_group_link}

📢 Добавить в канал:
{add_to_channel_link}

💡 ИНСТРУКЦИЯ:
1. Откройте ссылку выше
2. Выберите группу/канал
3. Нажмите "Добавить" или "Пригласить"
4. Бот будет добавлен в группу/канал

⚠️ ВАЖНО:
• Бот должен быть администратором группы/канала для работы некоторых функций
• После добавления бот автоматически появится в меню "👥 Группы"
"""
        else:
            invite_text = """
🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:

⚠️ У бота нет username. Для добавления бота:
1. Откройте настройки группы/канала
2. Перейдите в "Участники" → "Добавить участников"
3. Найдите бота по его ID или попросите администратора добавить его

Или настройте username для бота через @BotFather
"""
    except Exception as e:
        logger.error(f"Ошибка при получении информации о боте: {e}")
        invite_text = "\n\n⚠️ Не удалось получить ссылки для добавления бота"
    
    help_text = """ℹ️ СПРАВКА ПО ИСПОЛЬЗОВАНИЮ БОТА

📋 ОСНОВНЫЕ ФУНКЦИИ:

📧 Новая рассылка
   Создайте новую рассылку по вашим получателям
   • Выберите шаблон
   • Введите список получателей
   • Подтвердите запуск

📊 Мои рассылки
   Просмотрите историю ваших рассылок
   • Список всех ваших рассылок
   • Просмотр детальных отчетов
   • Статистика по каждой рассылке

📝 Команды:
   /start - регистрация и главное меню
   /help - эта справка
   /invite - получить ссылки для добавления бота в группы/каналы
   /report <ID> - просмотр отчета по ID рассылки
   Пример: /report 123

📝 ФОРМАТ СПИСКА ПОЛУЧАТЕЛЕЙ:
   • @username (пользователи)
   • user_id (число, например: 123456789)
   • Ссылки: https://t.me/user или t.me/user
   • Группы/каналы: @groupname или https://t.me/groupname
   • Разделители: запятая, пробел, новая строка
   
   Пример:
   @user1, 123456789, @user2
   https://t.me/user3"""
    
    if is_admin_user:
        help_text += "\n\n🔑 АДМИН-ФУНКЦИИ:\n\n"
        help_text += "📝 Шаблоны\n"
        help_text += "   Создание шаблонов сообщений для рассылок\n"
        help_text += "   • Введите название шаблона\n"
        help_text += "   • Введите текст (поддерживается Markdown)\n\n"
        help_text += "⚙️ Настройки\n"
        help_text += "   Настройка получателей сводных отчетов\n"
        help_text += "   • Введите список @username или user_id\n\n"
        help_text += "📝 АДМИН-КОМАНДЫ:\n"
        help_text += "   /add_template - создать шаблон\n"
        help_text += "   /set_report_receivers - настройка получателей отчетов\n"
        help_text += "   /templates_list - список всех шаблонов"
    else:
        help_text += "\n\n💡 СОВЕТ:\n"
        help_text += "Если у вас нет шаблонов для рассылок,\n"
        help_text += "обратитесь к администратору.\n\n"
        help_text += "📱 ОТПРАВКА ОТ ВАШЕГО ИМЕНИ:\n"
        help_text += "/setup_my_client - настроить отправку от вашего имени\n"
        help_text += "/my_client_status - проверить статус"
    
    # Получаем информацию о боте для ссылок
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        if bot_username:
            add_to_group_link = f"https://t.me/{bot_username}?startgroup"
            add_to_channel_link = f"https://t.me/{bot_username}?startchannel"
            invite_text = f"""

🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:

📱 Добавить в группу:
{add_to_group_link}

📢 Добавить в канал:
{add_to_channel_link}

💡 ИНСТРУКЦИЯ:
1. Нажмите на ссылку выше (для группы или канала)
2. Выберите группу/канал из списка
3. Нажмите "Добавить" или "Пригласить"
4. Бот будет добавлен в группу/канал

⚠️ ВАЖНО:
• После добавления бот автоматически появится в меню "👥 Группы"
• Для некоторых функций бот должен быть администратором
• Если ссылки не работают, попробуйте добавить бота через настройки группы:
  Настройки → Участники → Добавить участников → Найдите @{bot_username}

💬 Или используйте команду /invite для получения ссылок"""
        else:
            invite_text = """

🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ:

⚠️ У бота нет username. Для добавления бота:
1. Откройте настройки группы/канала
2. Перейдите в "Участники" → "Добавить участников"
3. Найдите бота по его ID или попросите администратора добавить его

💡 Чтобы настроить username для бота:
1. Откройте @BotFather в Telegram
2. Отправьте /mybots
3. Выберите вашего бота
4. Выберите "Edit Bot" → "Edit Username"
5. Установите username (например: my_mailing_bot)

После настройки username вы сможете использовать ссылки для добавления бота."""
    except Exception as e:
        logger.error(f"Ошибка при получении информации о боте: {e}")
        invite_text = "\n\n⚠️ Не удалось получить ссылки для добавления бота"
    
    await message.answer(help_text + invite_text, reply_markup=get_main_keyboard(is_admin=is_admin_user), parse_mode=None)


@router.message(Command("invite"))
async def cmd_invite(message: Message, bot: Bot):
    """Получить ссылки для добавления бота в группы/каналы"""
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        bot_id = bot_info.id
        
        if bot_username:
            add_to_group_link = f"https://t.me/{bot_username}?startgroup"
            add_to_channel_link = f"https://t.me/{bot_username}?startchannel"
            
            # Пытаемся получить список групп пользователя через Client API
            user_groups_text = ""
            try:
                from services.telegram_client import get_user_groups
                user_groups = await get_user_groups(message.from_user.id)
                
                if user_groups:
                    user_groups_text = f"\n\n📋 ВАШИ ГРУППЫ (через Client API):\n"
                    user_groups_text += "Вы можете добавить бота в эти группы:\n\n"
                    
                    for i, group in enumerate(user_groups[:10], 1):  # Показываем первые 10
                        group_title = group.get('title', 'Без названия')
                        group_id = group.get('id')
                        group_type = group.get('type', 'group')
                        
                        # Создаем ссылку с параметром startgroup и chat_id
                        # К сожалению, Telegram не поддерживает прямой параметр chat_id в startgroup
                        # Но можем показать инструкцию
                        user_groups_text += f"{i}. {group_title} ({group_type})\n"
                        user_groups_text += f"   ID: {group_id}\n"
                        user_groups_text += f"   → Откройте группу → Настройки → Участники → Добавить → @{bot_username}\n\n"
                    
                    if len(user_groups) > 10:
                        user_groups_text += f"... и еще {len(user_groups) - 10} групп\n"
            except Exception as e:
                logger.warning(f"Не удалось получить группы пользователя через Client API: {e}")
            
            invite_text = f"""🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ

📱 СПОСОБ 1: Через ссылку (рекомендуется)
Добавить в группу:
{add_to_group_link}

Добавить в канал:
{add_to_channel_link}

💡 ИНСТРУКЦИЯ для ссылок:
1. Нажмите на ссылку выше
2. Выберите группу/канал из списка
3. Нажмите "Добавить" или "Пригласить"

📱 СПОСОБ 2: Через настройки группы
1. Откройте группу/канал
2. Настройки → Участники → Добавить участников
3. Введите: @{bot_username}
4. Или найдите бота в списке и добавьте

📱 СПОСОБ 3: Через поиск по ID
1. Откройте группу/канал
2. Настройки → Участники → Добавить участников
3. Введите ID бота: {bot_id}
4. Добавьте бота

⚠️ ВАЖНО:
• После добавления бот автоматически появится в меню "👥 Группы"
• Для некоторых функций бот должен быть администратором
• Если вы администратор группы, вы можете добавить бота напрямую
• Если вы не администратор, попросите администратора добавить бота{user_groups_text}"""
        else:
            invite_text = f"""🤖 ДОБАВЛЕНИЕ БОТА В ГРУППУ/КАНАЛ

⚠️ У бота нет username. Для добавления бота:

📱 СПОСОБ 1: Через ID бота
1. Откройте настройки группы/канала
2. Перейдите в "Участники" → "Добавить участников"
3. Введите ID бота: {bot_id}
4. Добавьте бота

📱 СПОСОБ 2: Через @BotFather
1. Откройте @BotFather в Telegram
2. Отправьте /mybots
3. Выберите вашего бота
4. Выберите "Edit Bot" → "Edit Username"
5. Установите username (например: my_mailing_bot)
6. После настройки username используйте команду /invite для получения ссылок

💡 РЕКОМЕНДАЦИЯ:
Настройте username для бота - это самый простой способ добавления в группы."""
        
        # Добавляем дополнительную информацию о проблемах
        additional_info = """

🔧 ЕСЛИ НЕ ПОЛУЧАЕТСЯ ДОБАВИТЬ:

1. Проверьте права:
   • Вы должны быть администратором группы/канала
   • Или попросите администратора добавить бота

2. Попробуйте разные способы:
   • Через ссылку (если есть username)
   • Через поиск @username
   • Через ID бота

3. Если ничего не помогает:
   • Убедитесь, что бот активен
   • Проверьте, что группа/канал не заблокированы
   • Попробуйте добавить бота через веб-версию Telegram

4. После добавления:
   • Бот автоматически появится в меню "👥 Группы"
   • Для работы некоторых функций бот должен быть администратором"""
        
        await message.answer(
            invite_text + additional_info,
            reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
            parse_mode=None
        )
        logger.info(f"Пользователь {message.from_user.id} запросил ссылки для добавления бота")
    except Exception as e:
        logger.error(f"Ошибка при получении ссылок для добавления бота: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при получении ссылок. Попробуйте позже.",
            reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
            parse_mode=None
        )


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
    try:
        if callback.data == "cancel":
            await state.clear()
            await callback.message.edit_text("Отменено.")
            await callback.answer()
            return
        
        template_id = int(callback.data.split("_")[1])
        template = await crud.get_template(template_id)
        
        if not template:
            await callback.answer("Шаблон не найден", show_alert=True)
            logger.warning(f"Шаблон #{template_id} не найден для пользователя {callback.from_user.id}")
            return
    except ValueError as e:
        logger.error(f"Ошибка парсинга template_id из {callback.data}: {e}")
        await callback.answer("Ошибка при выборе шаблона", show_alert=True)
        return
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора шаблона: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)
        return
    
    # Сохраняем template_id в state
    await state.update_data(template_id=template_id)
    logger.info(f"Шаг 1: template_id {template_id} сохранен в state для пользователя {callback.from_user.id}")
    
    # Устанавливаем состояние СРАЗУ
    await state.set_state(MailingStates.waiting_for_recipients)
    logger.info(f"Шаг 2: Состояние установлено в waiting_for_recipients для пользователя {callback.from_user.id}")
    
    # Отвечаем на callback ПЕРВЫМ
    await callback.answer(f"✅ Выбран: {template.name}")
    
    # Отправляем новое сообщение с инструкциями (без Markdown для надежности)
    recipients_text = (
        f"✅ Выбран шаблон: {template.name}\n\n"
        "📝 Введите список получателей:\n\n"
        "Формат:\n"
        "• @username (пользователи)\n"
        "• user_id (число)\n"
        "• Ссылки: https://t.me/user или t.me/user\n"
        "• Группы/каналы: @groupname или https://t.me/groupname\n"
        "• Приватные группы: https://t.me/joinchat/HASH или t.me/+HASH\n\n"
        "⚠️ Для приватных групп: бот автоматически присоединится по invite-ссылке\n\n"
        "Разделители: запятая, пробел, новая строка\n\n"
        "Пример:\n"
        "@user1, 123456789, @user2, @mygroup\n"
        "https://t.me/joinchat/ABC123 (приватная группа)"
    )
    
    try:
        # Всегда отправляем новое сообщение (без Markdown для избежания ошибок)
        sent_message = await callback.message.answer(
            recipients_text,
            parse_mode=None,  # Без Markdown
            reply_markup=get_recipients_keyboard()  # Клавиатура с кнопкой "В группе"
        )
        logger.info(f"Шаг 3: Сообщение с инструкциями отправлено пользователю {callback.from_user.id}, message_id: {sent_message.message_id}")
        
        # Проверяем состояние еще раз
        current_state = await state.get_state()
        logger.info(f"Шаг 4: Текущее состояние: {current_state}")
        
        if current_state != MailingStates.waiting_for_recipients:
            logger.error(f"ОШИБКА: Состояние не совпадает! Ожидалось: {MailingStates.waiting_for_recipients}, получено: {current_state}")
            # Пытаемся установить еще раз
            await state.set_state(MailingStates.waiting_for_recipients)
            logger.info("Состояние переустановлено")
        
    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при отправке сообщения: {e}", exc_info=True)
        await callback.message.answer(
            f"✅ Выбран шаблон: {template.name}\n\n"
            "Введите список получателей (через запятую или пробел):\n"
            "Пример: @user1, 123456789, @user2",
            reply_markup=get_cancel_keyboard()
        )
    
    logger.info(f"Пользователь {callback.from_user.id} выбрал шаблон #{template_id} '{template.name}', готов к вводу получателей")


@router.callback_query(StateFilter(MailingStates.waiting_for_template), F.data.startswith("templates_page_"))
async def process_templates_pagination(callback: CallbackQuery, state: FSMContext):
    """Обработка пагинации шаблонов"""
    try:
        parts = callback.data.split("_")
        page = int(parts[2])
        templates = await crud.get_all_active_templates()
        
        await callback.message.edit_reply_markup(
            reply_markup=get_templates_keyboard(templates, page=page, for_selection=True)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при пагинации шаблонов: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.message(StateFilter(MailingStates.waiting_for_recipients))
async def process_recipients(message: Message, state: FSMContext):
    """Обработка списка получателей"""
    from services.telegram_client import get_chat_info_by_link, join_chat_by_link
    
    logger.info(f"Получено сообщение от {message.from_user.id} в состоянии waiting_for_recipients. Текст: {message.text[:50]}")
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        logger.info(f"Пользователь {message.from_user.id} отменил создание рассылки")
        return
    
    if message.text == "👥 В группе":
        # Переходим к выбору группы
        await show_groups_selection(message, state)
        return
    
    # Парсим список получателей
    try:
        recipients = parse_recipients_list(message.text)
        logger.info(f"Пользователь {message.from_user.id} ввел список получателей: {len(recipients)} получателей")
        
        if not recipients:
            await message.answer(
                "❌ Не удалось распознать получателей в вашем сообщении.\n\n"
                "Проверьте формат:\n"
                "• @username\n"
                "• user_id (только цифры)\n"
                "• Ссылки: https://t.me/user\n"
                "• Группы: https://t.me/groupname (сообщения отправятся участникам)\n\n"
                "Попробуйте еще раз или нажмите '👥 В группе' для выбора группы:",
                reply_markup=get_recipients_keyboard()
            )
            return
    except Exception as e:
        logger.error(f"Ошибка при парсинге получателей: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при обработке списка получателей.\n\n"
            "Попробуйте еще раз или нажмите '👥 В группе' для выбора группы:",
            reply_markup=get_recipients_keyboard()
        )
        return
    
    # Обрабатываем получателей - если это ссылка на группу, получаем участников
    final_recipients = []
    
    for recipient in recipients:
        # Проверяем, является ли получатель ссылкой на группу
        if recipient["type"] in ("link", "invite_link") or "t.me" in recipient["original"].lower():
            # Это может быть группа - проверяем
            await message.answer(f"⏳ Обрабатываю группу: {recipient['original']}...", parse_mode=None)
            
            # Если это invite-ссылка, сначала присоединяемся
            if "joinchat" in recipient["original"].lower() or "/+" in recipient["original"]:
                join_result = await join_chat_by_link(message.from_user.id, recipient["original"])
                if not join_result["success"]:
                    await message.answer(
                        f"❌ Не удалось присоединиться к чату:\n{join_result['error']}\n\n"
                        f"Пропускаю этот чат.",
                        parse_mode=None
                    )
                    continue
                
                # После присоединения получаем участников (только для групп/супергрупп)
                chat_type = join_result.get('chat_type', '')
                if chat_type in ("group", "supergroup"):
                    from services.telegram_client import get_group_members
                    # Пробуем получить участников через Pyrogram, затем Telethon
                    members = await get_group_members(message.from_user.id, join_result["chat_id"])
                    if not members:
                        try:
                            members = await get_group_members(message.from_user.id, join_result["chat_id"], use_telethon=True)
                        except:
                            pass
                    if members:
                        for member_id in members:
                            final_recipients.append({
                                "original": str(member_id),
                                "normalized": str(member_id),
                                "type": "chat_id"
                            })
                        await message.answer(
                            f"✅ Чат обработан: {join_result.get('title', 'Чат')}\n"
                            f"📝 Участников: {len(members)}",
                            parse_mode=None
                        )
                    else:
                        await message.answer(
                            f"⚠️ Чат обработан, но не удалось получить участников: {join_result.get('title', 'Чат')}",
                            parse_mode=None
                        )
                elif chat_type == "channel":
                    await message.answer(
                        f"⚠️ Канал обработан: {join_result.get('title', 'Канал')}\n"
                        f"Для каналов рассылка участникам недоступна.",
                        parse_mode=None
                    )
                continue
            else:
                # Обычная ссылка на чат/группу/канал - получаем информацию
                chat_info = await get_chat_info_by_link(message.from_user.id, recipient["original"])
                if not chat_info["success"]:
                    # Если не удалось получить информацию, возможно это не чат
                    # Добавляем как обычного получателя
                    final_recipients.append(recipient)
                    continue
                
                # Если это группа или супергруппа, добавляем участников
                chat_type = chat_info.get('chat_type', '')
                if chat_type in ("group", "supergroup") and chat_info.get("members"):
                    for member_id in chat_info["members"]:
                        final_recipients.append({
                            "original": str(member_id),
                            "normalized": str(member_id),
                            "type": "chat_id"
                        })
                    await message.answer(
                        f"✅ Чат обработан: {chat_info.get('title', 'Чат')}\n"
                        f"📝 Участников: {len(chat_info['members'])}",
                        parse_mode=None
                    )
                elif chat_type == "channel":
                    # Для каналов участники не получаются, но канал можно добавить в список для отслеживания
                    await message.answer(
                        f"✅ Канал обработан: {chat_info.get('title', 'Канал')}\n"
                        f"ID: {chat_info.get('chat_id')}\n\n"
                        f"ℹ️ Для каналов рассылка участникам недоступна, но канал добавлен в список.",
                        parse_mode=None
                    )
                    # Каналы не добавляем в получатели, так как рассылка по участникам канала невозможна
                else:
                    # Не группа/канал или не удалось получить участников - добавляем как обычного получателя
                    final_recipients.append(recipient)
        else:
            # Обычный получатель (пользователь)
            final_recipients.append(recipient)
    
    if not final_recipients:
        await message.answer(
            "❌ Не удалось получить получателей.\n\n"
            "Попробуйте еще раз или нажмите '👥 В группе' для выбора группы:",
            reply_markup=get_recipients_keyboard()
        )
        return
    
    is_valid, error = validate_recipients_list(final_recipients)
    if not is_valid:
        await message.answer(
            f"❌ {error}\n\nПопробуйте еще раз. Введите список получателей или нажмите '👥 В группе':",
            reply_markup=get_recipients_keyboard()
        )
        return
    
    data = await state.get_data()
    template_id = data.get("template_id")
    
    # Сохраняем получателей в state для использования после выбора интервала
    await state.update_data(
        recipients=final_recipients,
        template_id=template_id,
        group_id=None,  # Не из группы
        group_title=None
    )
    
    # Запрашиваем интервал между сообщениями
    await message.answer(
        f"✅ Получено {len(final_recipients)} получателей.\n\n"
        "⏱️ Выберите интервал между сообщениями:\n\n"
        "⭐ РЕКОМЕНДУЕТСЯ: 15-30 секунд (безопасно)\n"
        "⚠️ МИНИМУМ: 10 секунд (риск ограничения)\n"
        "❌ НЕ РЕКОМЕНДУЕТСЯ: менее 10 секунд (высокий риск PEER_FLOOD)\n\n"
        "💡 Поддерживаются пользователи, группы и каналы",
        reply_markup=get_delay_keyboard()
    )
    await state.set_state(MailingStates.waiting_for_delay)
    logger.info(f"Пользователь {message.from_user.id} ввел {len(final_recipients)} получателей (включая участников групп), ожидается выбор интервала")


@router.callback_query(StateFilter(MailingStates.waiting_for_delay), F.data.startswith("delay_"))
async def process_delay_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора интервала между сообщениями"""
    if callback.data == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Создание рассылки отменено.")
        await callback.answer()
        return
    
    # Извлекаем интервал из callback_data (delay_5 -> 5)
    try:
        delay_seconds = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный интервал", show_alert=True)
        return
    
    # Предупреждение о риске ограничения для малых интервалов
    if delay_seconds < 10:
        await callback.answer(
            "⚠️ ВНИМАНИЕ: Интервал менее 10 секунд может привести к ограничению аккаунта Telegram (PEER_FLOOD). Рекомендуется использовать минимум 15 секунд.",
            show_alert=True
        )
    
    # Получаем сохраненные данные
    data = await state.get_data()
    recipients = data.get("recipients")
    template_id = data.get("template_id")
    group_id = data.get("group_id")
    group_title = data.get("group_title")
    
    if not recipients or not template_id:
        await callback.answer("❌ Ошибка: данные не найдены. Начните заново.", show_alert=True)
        await state.clear()
        return
    
    template = await crud.get_template(template_id)
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        await state.clear()
        return
    
    # Создаем рассылку с выбранным интервалом
    campaign = await crud.create_campaign(
        owner_id=callback.from_user.id,
        template_id=template_id,
        delay_seconds=delay_seconds
    )
    
    # Добавляем получателей
    recipient_data = [
        {"original": r["original"], "normalized": r["normalized"]}
        for r in recipients
    ]
    await crud.add_recipients(campaign.id, recipient_data)
    
    # Сохраняем campaign_id в state для подтверждения
    await state.update_data(campaign_id=campaign.id)
    
    # Форматируем интервал для отображения
    if delay_seconds < 60:
        delay_text = f"{delay_seconds} сек"
    else:
        minutes = delay_seconds // 60
        seconds = delay_seconds % 60
        if seconds > 0:
            delay_text = f"{minutes} мин {seconds} сек"
        else:
            delay_text = f"{minutes} мин"
    
    # Предупреждение для малых интервалов
    warning_text = ""
    if delay_seconds < 10:
        warning_text = "\n\n⚠️ ВНИМАНИЕ: Интервал менее 10 секунд может привести к ограничению аккаунта Telegram (PEER_FLOOD). Рекомендуется использовать минимум 15 секунд."
    elif delay_seconds < 15:
        warning_text = "\n\n💡 РЕКОМЕНДАЦИЯ: Для большей безопасности используйте интервал 15-30 секунд."
    
    # Сохраняем delay_seconds в state и переходим к выбору количества получателей
    await state.update_data(delay_seconds=delay_seconds)
    
    # Запрашиваем выбор максимального количества получателей
    await callback.message.edit_text(
        f"✅ Интервал выбран: {delay_text}{warning_text}\n\n"
        f"📊 Всего получателей: {len(recipients)}\n\n"
        f"🔢 Выберите максимальное количество получателей для рассылки:\n\n"
        f"💡 Рассылка будет ограничена выбранным количеством",
        reply_markup=get_max_recipients_keyboard(),
        parse_mode=None
    )
    await callback.answer()
    await state.set_state(MailingStates.waiting_for_max_recipients)
    logger.info(f"Пользователь {callback.from_user.id} выбрал интервал {delay_seconds} сек, ожидается выбор количества получателей")


@router.callback_query(StateFilter(MailingStates.waiting_for_max_recipients), F.data.startswith("max_recipients_"))
async def process_max_recipients_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора максимального количества получателей"""
    if callback.data == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Создание рассылки отменено.")
        await callback.answer()
        return
    
    # Извлекаем количество из callback_data (max_recipients_100 -> 100)
    try:
        max_recipients = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверное количество", show_alert=True)
        return
    
    # Получаем сохраненные данные
    data = await state.get_data()
    recipients = data.get("recipients")
    template_id = data.get("template_id")
    delay_seconds = data.get("delay_seconds")
    group_id = data.get("group_id")
    group_title = data.get("group_title")
    
    if not recipients or not template_id or not delay_seconds:
        await callback.answer("❌ Ошибка: данные не найдены. Начните заново.", show_alert=True)
        await state.clear()
        return
    
    template = await crud.get_template(template_id)
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        await state.clear()
        return
    
    # Ограничиваем список получателей выбранным количеством
    limited_recipients = recipients[:max_recipients]
    
    # Создаем рассылку с выбранными параметрами
    campaign = await crud.create_campaign(
        owner_id=callback.from_user.id,
        template_id=template_id,
        delay_seconds=delay_seconds,
        max_recipients=max_recipients
    )
    
    # Добавляем получателей (ограниченное количество)
    recipient_data = [
        {"original": r["original"], "normalized": r["normalized"]}
        for r in limited_recipients
    ]
    await crud.add_recipients(campaign.id, recipient_data)
    
    # Сохраняем campaign_id в state для подтверждения
    await state.update_data(campaign_id=campaign.id)
    
    # Форматируем интервал для отображения
    if delay_seconds < 60:
        delay_text = f"{delay_seconds} сек"
    else:
        minutes = delay_seconds // 60
        seconds = delay_seconds % 60
        if seconds > 0:
            delay_text = f"{minutes} мин {seconds} сек"
        else:
            delay_text = f"{minutes} мин"
    
    # Предупреждение для малых интервалов в превью
    delay_warning = ""
    if delay_seconds < 10:
        delay_warning = " ⚠️ (риск PEER_FLOOD)"
    elif delay_seconds < 15:
        delay_warning = " 💡 (рекомендуется больше)"
    
    # Показываем превью
    from utils.formatters import format_campaign_preview
    preview = format_campaign_preview(campaign, template, len(limited_recipients))
    preview += f"\n\n⏱️ Интервал между сообщениями: {delay_text}{delay_warning}"
    preview += f"\n\n🔢 Максимум получателей: {max_recipients}"
    
    if len(recipients) > max_recipients:
        preview += f"\n⚠️ Ограничено до {max_recipients} из {len(recipients)} получателей"
    
    if group_title:
        preview += f"\n\n👥 Группа: {group_title}"
    
    await callback.message.edit_text(
        preview,
        reply_markup=get_confirm_mailing_keyboard(campaign.id),
        parse_mode=None  # Без Markdown для избежания ошибок парсинга
    )
    await callback.answer()
    await state.set_state(MailingStates.confirm_mailing)
    logger.info(f"Создана рассылка #{campaign.id} пользователем {callback.from_user.id}, получателей: {len(limited_recipients)}/{len(recipients)}, интервал: {delay_seconds} сек, максимум: {max_recipients}, группа: {group_title or 'нет'}")


@router.callback_query(StateFilter(MailingStates.confirm_mailing), F.data.startswith("confirm_mailing_"))
async def confirm_mailing(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и запуск рассылки"""
    from services.mailing_service import is_within_allowed_time
    from datetime import datetime
    
    campaign_id = int(callback.data.split("_")[2])
    
    campaign = await crud.get_campaign(campaign_id)
    if not campaign:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return
    
    # Проверяем права
    if campaign.owner_id != callback.from_user.id:
        await callback.answer("У вас нет прав на эту рассылку", show_alert=True)
        return
    
    # Проверяем время отправки (09:00 - 22:00)
    if not is_within_allowed_time():
        current_time = datetime.now().time().strftime("%H:%M")
        await callback.message.edit_text(
            f"❌ Рассылка не может быть запущена вне разрешенного времени.\n\n"
            f"⏰ Текущее время: {current_time}\n"
            f"✅ Разрешенное время: с 09:00 до 22:00\n\n"
            f"Попробуйте запустить рассылку позже.",
            parse_mode=None
        )
        await callback.answer("Рассылка разрешена только с 09:00 до 22:00", show_alert=True)
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


@router.callback_query(StateFilter(MailingStates.waiting_for_max_recipients), F.data == "cancel")
async def cancel_max_recipients(callback: CallbackQuery, state: FSMContext):
    """Отмена выбора количества получателей"""
    await state.clear()
    await callback.message.edit_text("❌ Создание рассылки отменено.")
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


async def show_groups_selection(message: Message, state: FSMContext):
    """Показ списка групп для выбора"""
    from services.telegram_client import get_user_groups
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Получаем список групп пользователя через Client API
    user_groups = await get_user_groups(message.from_user.id)
    
    # Получаем группы бота из БД
    bot_groups = await crud.get_all_bot_groups(active_only=True)
    
    # Фильтруем только группы (не каналы) для рассылки
    user_groups_filtered = [g for g in user_groups if g["type"] in ("group", "supergroup")]
    bot_groups_filtered = [g for g in bot_groups if g.chat_type in ("group", "supergroup")]
    
    if not user_groups_filtered and not bot_groups_filtered:
        await message.answer(
            "👥 Группы не найдены.\n\n"
            "Для групп пользователя:\n"
            "• Настройте Client API через /setup_my_client\n"
            "• Убедитесь, что вы являетесь участником групп\n\n"
            "Для групп бота:\n"
            "• Добавьте бота в группу",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    text = f"👥 ВЫБОР ГРУППЫ\n\n"
    
    # Подсчитываем общее количество групп
    total_groups = len(user_groups_filtered) + len(bot_groups_filtered)
    text += f"Найдено групп: {total_groups}\n\n"
    text += "Выберите группу для рассылки всем участникам:"
    
    # Создаем клавиатуру с группами
    keyboard = []
    
    # Сначала показываем группы бота
    if bot_groups_filtered:
        for group in bot_groups_filtered[:10]:
            members_text = f"({group.members_count} участн.)" if group.members_count else ""
            username_text = f" @{group.username}" if group.username else ""
            button_text = f"🤖 {group.title or 'Без названия'}{username_text} {members_text}"
            button_text = button_text[:60]  # Ограничиваем длину
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_bot_group_{group.chat_id}"
                )
            ])
    
    # Затем показываем группы пользователя
    if user_groups_filtered:
        for group in user_groups_filtered[:10]:
            group_type_emoji = "👥"
            members_text = f"({group['members_count']} участн.)" if group['members_count'] > 0 else ""
            button_text = f"{group_type_emoji} {group['title'][:40]} {members_text}"
            button_text = button_text[:60]  # Ограничиваем длину
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_group_{group['id']}"
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_group_selection")
    ])
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(MailingStates.waiting_for_group_selection)


@router.callback_query(StateFilter(MailingStates.waiting_for_group_selection), F.data.startswith("select_bot_group_"))
async def process_bot_group_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора группы бота"""
    from services.telegram_client import get_group_members
    
    try:
        group_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о группе из БД
        bot_group = await crud.get_bot_group(group_id)
        
        if not bot_group or not bot_group.is_active:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"👥 ГРУППА БОТА ВЫБРАНА\n\n"
            f"Название: {bot_group.title or 'Без названия'}\n"
            f"Тип: {bot_group.chat_type}\n"
            f"Участников: {bot_group.members_count or 'неизвестно'}\n\n"
            f"⏳ Получаю список участников...",
            reply_markup=None
        )
        await callback.answer()
        
        # Получаем участников группы через Client API пользователя (пробуем Pyrogram, затем Telethon)
        members = await get_group_members(callback.from_user.id, group_id)
        
        # Если не получилось через Pyrogram, пробуем Telethon
        if not members:
            logger.info(f"Пробуем получить участников через Telethon для группы {group_id}")
            try:
                members = await get_group_members(callback.from_user.id, group_id, use_telethon=True)
            except Exception as e:
                logger.warning(f"Не удалось использовать Telethon: {e}")
        
        if not members:
            await callback.message.edit_text(
                f"❌ Не удалось получить участников группы\n\n"
                f"Возможные причины:\n"
                f"• Нет прав на просмотр участников\n"
                f"• Группа пуста\n"
                f"• Ошибка доступа\n\n"
                f"Убедитесь, что вы настроили Client API и являетесь участником группы",
                reply_markup=None
            )
            await state.clear()
            return
        
        # Сохраняем данные в state
        data = await state.get_data()
        template_id = data.get("template_id")
        
        # Создаем список получателей из участников группы
        recipients = [
            {"original": str(member_id), "normalized": str(member_id), "type": "chat_id"}
            for member_id in members
        ]
        
        # Сохраняем получателей в state
        await state.update_data(
            recipients=recipients,
            group_id=group_id,
            group_title=bot_group.title or "Без названия"
        )
        
        # Переходим к выбору интервала
        await callback.message.edit_text(
            f"✅ Группа бота: {bot_group.title or 'Без названия'}\n"
            f"📝 Участников: {len(members)}\n\n"
            f"⏱️ Выберите интервал между сообщениями:\n\n"
            f"💡 РЕКОМЕНДАЦИЯ: Используйте минимум 15 секунд для избежания ограничений Telegram",
            reply_markup=get_delay_keyboard(),
            parse_mode=None
        )
        await state.set_state(MailingStates.waiting_for_delay)
        logger.info(f"Пользователь {callback.from_user.id} выбрал группу бота {group_id} с {len(members)} участниками")
        
    except Exception as e:
        logger.error(f"Ошибка при выборе группы бота: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)
        await state.clear()


@router.callback_query(StateFilter(MailingStates.waiting_for_group_selection), F.data.startswith("select_group_"))
async def process_group_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора группы"""
    from services.telegram_client import get_group_members, get_user_groups
    
    try:
        group_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о группе
        groups = await get_user_groups(callback.from_user.id)
        selected_group = None
        for group in groups:
            if group["id"] == group_id:
                selected_group = group
                break
        
        if not selected_group:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"👥 ГРУППА ВЫБРАНА\n\n"
            f"Название: {selected_group['title']}\n"
            f"Тип: {selected_group['type']}\n"
            f"Участников: {selected_group['members_count']}\n\n"
            f"⏳ Получаю список участников...",
            reply_markup=None
        )
        await callback.answer()
        
        # Получаем участников группы (пробуем сначала Pyrogram, затем Telethon если нужно)
        members = await get_group_members(callback.from_user.id, group_id)
        
        # Если не получилось через Pyrogram, пробуем Telethon
        if not members:
            logger.info(f"Пробуем получить участников через Telethon для группы {group_id}")
            members = await get_group_members(callback.from_user.id, group_id, use_telethon=True)
        
        if not members:
            await callback.message.edit_text(
                f"❌ Не удалось получить участников группы\n\n"
                f"Возможные причины:\n"
                f"• Нет прав на просмотр участников\n"
                f"• Группа пуста\n"
                f"• Ошибка доступа",
                reply_markup=None
            )
            await state.clear()
            return
        
        # Сохраняем данные в state
        data = await state.get_data()
        template_id = data.get("template_id")
        
        # Создаем список получателей из участников группы
        recipients = [
            {"original": str(member_id), "normalized": str(member_id), "type": "chat_id"}
            for member_id in members
        ]
        
        # Сохраняем получателей в state
        await state.update_data(
            recipients=recipients,
            group_id=group_id,
            group_title=selected_group['title']
        )
        
        # Переходим к выбору интервала
        await callback.message.edit_text(
            f"✅ Группа: {selected_group['title']}\n"
            f"📝 Участников: {len(members)}\n\n"
            f"⏱️ Выберите интервал между сообщениями:\n\n"
            f"💡 РЕКОМЕНДАЦИЯ: Используйте минимум 15 секунд для избежания ограничений Telegram",
            reply_markup=get_delay_keyboard(),
            parse_mode=None
        )
        await state.set_state(MailingStates.waiting_for_delay)
        logger.info(f"Пользователь {callback.from_user.id} выбрал группу {group_id} с {len(members)} участниками")
        
    except Exception as e:
        logger.error(f"Ошибка при выборе группы: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)
        await state.clear()


@router.callback_query(StateFilter(MailingStates.waiting_for_group_selection), F.data == "cancel_group_selection")
async def cancel_group_selection(callback: CallbackQuery, state: FSMContext):
    """Отмена выбора группы"""
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_keyboard(is_admin=is_admin(callback.from_user.id))
    )


@router.my_chat_member()
async def handle_bot_chat_member(event: ChatMemberUpdated, bot: Bot):
    """Обработка событий добавления/удаления бота из групп"""
    try:
        chat = event.chat
        new_status = event.new_chat_member.status
        old_status = event.old_chat_member.status if event.old_chat_member else None
        
        logger.info(f"my_chat_member event: chat_id={chat.id}, type={chat.type}, new_status={new_status}, old_status={old_status}")
        
        # Проверяем, что это группа или канал
        if chat.type not in ("group", "supergroup", "channel"):
            logger.debug(f"Пропускаем чат типа {chat.type}")
            return
        
        # Определяем тип чата
        chat_type = chat.type
        
        # Если бот был добавлен
        if new_status in ("member", "administrator"):
            # Получаем информацию о количестве участников
            members_count = None
            try:
                if chat_type in ("group", "supergroup"):
                    # Пытаемся получить количество участников
                    chat_info = await bot.get_chat(chat.id)
                    if hasattr(chat_info, 'members_count') and chat_info.members_count:
                        members_count = chat_info.members_count
            except Exception as e:
                logger.debug(f"Не удалось получить количество участников для {chat.id}: {e}")
            
            # Сохраняем/обновляем группу в БД
            bot_group = await crud.add_or_update_bot_group(
                chat_id=chat.id,
                title=chat.title,
                username=chat.username,
                chat_type=chat_type,
                members_count=members_count,
                is_active=True
            )
            logger.info(f"✅ Бот добавлен в {chat_type} {chat.id} ({chat.title}), сохранено в БД: {bot_group.id}")
        
        # Если бот был удален
        elif new_status in ("left", "kicked"):
            await crud.remove_bot_group(chat.id)
            logger.info(f"❌ Бот удален из {chat_type} {chat.id} ({chat.title})")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке события my_chat_member: {e}", exc_info=True)


async def sync_bot_groups(bot: Bot):
    """Синхронизация групп бота через Bot API (получение текущих групп)"""
    try:
        # К сожалению, Bot API не предоставляет прямой метод для получения списка всех групп бота
        # Но мы можем попробовать получить информацию о группах, в которых бот точно есть
        # через getUpdates или другие методы
        
        # Пока что просто логируем, что синхронизация невозможна через Bot API
        logger.info("Синхронизация групп бота: группы отслеживаются через события my_chat_member")
        return []
    except Exception as e:
        logger.error(f"Ошибка при синхронизации групп бота: {e}", exc_info=True)
        return []


@router.message(Command("groups"))
@router.message(F.text == "👥 Группы")
async def cmd_groups(message: Message, bot: Bot, state: FSMContext):
    """Список групп пользователя и групп бота"""
    from services.telegram_client import get_user_groups
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Получаем группы пользователя через Client API
    user_groups = await get_user_groups(message.from_user.id)
    
    # Получаем группы бота из БД
    bot_groups = await crud.get_all_bot_groups(active_only=True)
    
    # Кнопка для добавления группы по ссылке
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить чат/группу/канал по ссылке", callback_data="add_group_by_link")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_groups")]
    ])
    
    # Если нет ни групп пользователя, ни групп бота
    if not user_groups and not bot_groups:
        await message.answer(
            "👥 Группы не найдены.\n\n"
            "Для групп пользователя:\n"
            "• Настройте Client API через /setup_my_client\n"
            "• Убедитесь, что вы являетесь участником групп\n\n"
            "Для групп бота:\n"
            "• Добавьте бота в группу или канал\n"
            "• Группы сохраняются автоматически при добавлении бота\n\n"
            "Или добавьте чат/группу/канал по ссылке:",
            reply_markup=keyboard,
            parse_mode=None
        )
        return
    
    text = "👥 ГРУППЫ И КАНАЛЫ\n\n"
    
    # Показываем группы бота
    if bot_groups:
        text += f"🤖 ГРУППЫ БОТА ({len(bot_groups)}):\n\n"
        
        groups_list = [g for g in bot_groups if g.chat_type in ("group", "supergroup")]
        channels_list = [g for g in bot_groups if g.chat_type == "channel"]
        
        if groups_list:
            text += f"👥 Группы ({len(groups_list)}):\n"
            for group in groups_list[:10]:
                members_text = f" ({group.members_count} участн.)" if group.members_count else ""
                username_text = f" (@{group.username})" if group.username else ""
                # Экранируем специальные символы для избежания ошибок парсинга
                title = (group.title or "Без названия").replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
                text += f"• {title}{username_text}{members_text}\n"
            if len(groups_list) > 10:
                text += f"... и еще {len(groups_list) - 10} групп\n"
            text += "\n"
        
        if channels_list:
            text += f"📢 Каналы ({len(channels_list)}):\n"
            for channel in channels_list[:10]:
                members_text = f" ({channel.members_count} подписч.)" if channel.members_count else ""
                username_text = f" (@{channel.username})" if channel.username else ""
                # Экранируем специальные символы
                title = (channel.title or "Без названия").replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
                text += f"• {title}{username_text}{members_text}\n"
            if len(channels_list) > 10:
                text += f"... и еще {len(channels_list) - 10} каналов\n"
            text += "\n"
    
    # Показываем группы пользователя (если есть Client API)
    if user_groups:
        text += f"👤 ВАШИ ГРУППЫ (через Client API) ({len(user_groups)}):\n\n"
        
        user_groups_list = [g for g in user_groups if g["type"] in ("group", "supergroup")]
        user_channels_list = [g for g in user_groups if g["type"] == "channel"]
        
        if user_groups_list:
            text += f"👥 Группы ({len(user_groups_list)}):\n"
            for group in user_groups_list[:5]:
                members_text = f" ({group['members_count']} участн.)" if group['members_count'] > 0 else ""
                # Экранируем специальные символы
                title = group['title'].replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
                text += f"• {title}{members_text}\n"
            if len(user_groups_list) > 5:
                text += f"... и еще {len(user_groups_list) - 5} групп\n"
            text += "\n"
        
        if user_channels_list:
            text += f"📢 Каналы ({len(user_channels_list)}):\n"
            for channel in user_channels_list[:5]:
                members_text = f" ({channel['members_count']} подписч.)" if channel['members_count'] > 0 else ""
                # Экранируем специальные символы
                title = channel['title'].replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
                text += f"• {title}{members_text}\n"
            if len(user_channels_list) > 5:
                text += f"... и еще {len(user_channels_list) - 5} каналов\n"
    
    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode=None  # Отключаем Markdown для избежания ошибок парсинга
    )


# Обработчики для работы с группами - регистрируем перед общими обработчиками
@router.callback_query(F.data == "add_group_by_link")
async def add_group_by_link_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик для добавления группы по ссылке"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    try:
        logger.info(f"Обработчик add_group_by_link вызван для пользователя {callback.from_user.id}")
        
        # Создаем inline-клавиатуру с кнопкой отмены
        cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_group")]
        ])
        
        await callback.message.edit_text(
            "➕ ДОБАВЛЕНИЕ ЧАТА/ГРУППЫ/КАНАЛА ПО ССЫЛКЕ\n\n"
            "Отправьте ссылку на чат, группу или канал:\n\n"
            "• Публичная группа/канал: https://t.me/groupname или @groupname\n"
            "• Приватная группа/канал: https://t.me/joinchat/HASH или t.me/+HASH\n"
            "• Канал: https://t.me/channelname или @channelname\n\n"
            "Бот присоединится к чату и добавит его в список.",
            reply_markup=cancel_keyboard,
            parse_mode=None
        )
        await callback.answer("Введите ссылку на группу")
        await state.set_state(GroupStates.waiting_for_group_link)
        logger.info(f"Пользователь {callback.from_user.id} начал добавление чата/группы/канала по ссылке, состояние установлено")
    except Exception as e:
        logger.error(f"Ошибка при обработке add_group_by_link: {e}", exc_info=True)
        try:
            await callback.answer("Произошла ошибка", show_alert=True)
        except:
            pass


@router.callback_query(F.data == "cancel_add_group")
async def cancel_add_group_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления группы"""
    await state.clear()
    await callback.message.edit_text("❌ Добавление чата отменено.", reply_markup=None)
    await callback.answer()


@router.message(StateFilter(GroupStates.waiting_for_group_link))
async def process_group_link(message: Message, state: FSMContext, bot: Bot):
    """Обработка ссылки на чат/группу/канал для добавления"""
    from services.telegram_client import join_chat_by_link, get_chat_info_by_link
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    
    chat_link = message.text.strip()
    
    # Отправляем сообщение о обработке
    processing_msg = await message.answer("⏳ Обрабатываю ссылку на чат...", reply_markup=get_cancel_keyboard(), parse_mode=None)
    
    # Проверяем, это invite-ссылка или обычная ссылка
    if "joinchat" in chat_link.lower() or "/+" in chat_link or chat_link.startswith("+"):
        # Invite-ссылка - присоединяемся
        result = await join_chat_by_link(message.from_user.id, chat_link)
        
        if result["success"]:
            # Сохраняем чат в БД бота (если бот тоже должен быть в чате)
            # Для пользователя чат будет в его списке диалогов
            try:
                await processing_msg.delete()
            except:
                pass
            
            # Проверяем, есть ли специальное сообщение (например, "уже участник")
            if result.get("message"):
                await message.answer(
                    f"✅ {result.get('message')}\n\n"
                    f"Чат доступен для использования в рассылках.",
                    reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
                    parse_mode=None
                )
                logger.info(f"Пользователь {message.from_user.id} уже участник чата по ссылке {chat_link}")
            else:
                # Обычный успешный результат
                chat_type_emoji = {
                    "group": "👥",
                    "supergroup": "👥",
                    "channel": "📢"
                }.get(result.get('chat_type', ''), "💬")
                
                chat_type_name = {
                    "group": "группа",
                    "supergroup": "супергруппа",
                    "channel": "канал"
                }.get(result.get('chat_type', ''), "чат")
                
                await message.answer(
                    f"✅ Успешно присоединились к {chat_type_name}!\n\n"
                    f"{chat_type_emoji} Название: {result.get('title', 'Без названия')}\n"
                    f"ID: {result.get('chat_id')}\n"
                    f"Тип: {chat_type_name}\n\n"
                    f"Чат добавлен в ваш список.",
                    reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
                    parse_mode=None
                )
                logger.info(f"Пользователь {message.from_user.id} присоединился к {chat_type_name} {result.get('chat_id')} по ссылке")
        else:
            try:
                await processing_msg.delete()
            except:
                pass
            await message.answer(
                f"❌ Не удалось присоединиться к чату:\n{result.get('error', 'Неизвестная ошибка')}\n\n"
                f"Проверьте ссылку и попробуйте еще раз.",
                reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
                parse_mode=None
            )
    else:
        # Обычная ссылка - получаем информацию
        result = await get_chat_info_by_link(message.from_user.id, chat_link)
        
        if result["success"]:
            try:
                await processing_msg.delete()
            except:
                pass
            
            chat_type_emoji = {
                "group": "👥",
                "supergroup": "👥",
                "channel": "📢"
            }.get(result.get('chat_type', ''), "💬")
            
            chat_type_name = {
                "group": "группа",
                "supergroup": "супергруппа",
                "channel": "канал"
            }.get(result.get('chat_type', ''), "чат")
            
            members_text = ""
            if result.get('members'):
                members_text = f"\nУчастников: {len(result.get('members', []))}"
            elif result.get('chat_type') == "channel":
                members_text = "\n(Для каналов участники не отображаются)"
            
            await message.answer(
                f"✅ {chat_type_name.capitalize()} найдена!\n\n"
                f"{chat_type_emoji} Название: {result.get('title', 'Без названия')}\n"
                f"ID: {result.get('chat_id')}\n"
                f"Тип: {chat_type_name}{members_text}\n\n"
                f"Чат доступен для рассылок.",
                reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
                parse_mode=None
            )
            logger.info(f"Пользователь {message.from_user.id} добавил {chat_type_name} {result.get('chat_id')} по ссылке")
        else:
            try:
                await processing_msg.delete()
            except:
                pass
            error_msg = result.get('error', 'Неизвестная ошибка')
            
            # Более детальное сообщение об ошибке
            if "не группа" in error_msg.lower() or "не супергруппа" in error_msg.lower() or "не канал" in error_msg.lower():
                await message.answer(
                    f"❌ Не удалось добавить чат:\n\n"
                    f"{error_msg}\n\n"
                    f"💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:\n"
                    f"• Это личный чат (не группа/канал)\n"
                    f"• Это бот (боты нельзя добавить в список групп)\n"
                    f"• Неверный формат ссылки\n\n"
                    f"✅ ЧТО ПРОВЕРИТЬ:\n"
                    f"• Убедитесь, что ссылка ведет на группу или канал\n"
                    f"• Попробуйте использовать invite-ссылку для приватных групп\n"
                    f"• Для публичных групп используйте формат: @groupname или https://t.me/groupname",
                    reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
                    parse_mode=None
                )
            else:
                await message.answer(
                    f"❌ Не удалось получить информацию о чате:\n{error_msg}\n\n"
                    f"Проверьте ссылку и убедитесь, что:\n"
                    f"• Чат существует\n"
                    f"• Вы являетесь участником чата\n"
                    f"• Ссылка правильная",
                    reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)),
                    parse_mode=None
                )
    
    await state.clear()


@router.callback_query(F.data == "close_groups")
async def close_groups_handler(callback: CallbackQuery, state: FSMContext):
    """Закрытие меню групп"""
    await state.clear()
    await callback.message.edit_text("❌ Закрыто.", reply_markup=None)
    await callback.answer()


@router.message(Command("my_mailings"))
@router.message(F.text == "📊 Мои рассылки")
async def cmd_my_mailings(message: Message):
    """Список рассылок пользователя"""
    campaigns = await crud.get_user_campaigns(message.from_user.id)
    
    if not campaigns:
        await message.answer(
            "📊 У вас пока нет рассылок.\n\n"
            "Создайте первую рассылку через кнопку '📧 Новая рассылка'",
            reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id))
        )
        return
    
    # Формируем текст со статистикой
    status_emoji = {
        "pending": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "failed": "❌"
    }
    
    text = f"📊 ВАШИ РАССЫЛКИ\n\nВсего: {len(campaigns)}\n\n"
    text += "Нажмите на рассылку для просмотра деталей:\n\n"
    
    # Показываем краткую информацию о первых 5 рассылках
    for campaign in campaigns[:5]:
        emoji = status_emoji.get(campaign.status, "❓")
        text += f"{emoji} #{campaign.id} - {campaign.campaign_id}\n"
        if campaign.status == "completed":
            text += f"   ✅ {campaign.sent_successfully}/{campaign.total_recipients}\n"
    
    if len(campaigns) > 5:
        text += f"\n... и еще {len(campaigns) - 5} рассылок"
    
    await message.answer(
        text,
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
            # Пытаемся отредактировать без форматирования (надежнее)
            await callback.message.edit_text(report, parse_mode=None)
        except Exception as e:
            # Если сообщение слишком длинное или ошибка, отправляем новое
            logger.warning(f"Не удалось отредактировать сообщение: {e}")
            await callback.message.answer(report, parse_mode=None)
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
        try:
            await message.answer(report, parse_mode=None)  # Без форматирования для надежности
        except Exception as e:
            logger.error(f"Ошибка при отправке отчета: {e}")
            await message.answer("❌ Не удалось отправить отчет. Попробуйте позже.")
    else:
        await message.answer("❌ Не удалось сгенерировать отчет.")
