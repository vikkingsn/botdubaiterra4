"""
Handlers для авторизации Client API пользователями
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from database import crud
from utils.logger import logger
from config import MAIN_ADMIN_ID
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from services.telegram_client import get_user_client

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == MAIN_ADMIN_ID


class ClientAuthStates(StatesGroup):
    waiting_for_api_id = State()
    waiting_for_api_hash = State()
    waiting_for_phone = State()


@router.message(Command("setup_my_client"))
@router.message(Command("setup_client"))
async def cmd_setup_client(message: Message, state: FSMContext):
    """Начало настройки Client API для пользователя"""
    await message.answer(
        "🔐 Настройка отправки сообщений от ВАШЕГО имени\n\n"
        "После настройки все ваши рассылки будут отправляться от вашего имени.\n\n"
        "📋 Инструкция:\n"
        "1. Зайдите на https://my.telegram.org\n"
        "2. Войдите с вашим номером телефона\n"
        "3. Перейдите в 'API development tools'\n"
        "4. Создайте приложение (любое название)\n"
        "5. Скопируйте api_id и api_hash\n\n"
        "Введите ваш API_ID (число):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ClientAuthStates.waiting_for_api_id)


@router.message(ClientAuthStates.waiting_for_api_id)
async def process_api_id(message: Message, state: FSMContext):
    """Обработка API_ID"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    
    try:
        api_id = int(message.text)
        await state.update_data(api_id=api_id)
        await message.answer(
            "✅ API_ID сохранен\n\n"
            "Теперь введите ваш API_HASH (длинная строка):",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ClientAuthStates.waiting_for_api_hash)
    except ValueError:
        await message.answer("❌ API_ID должен быть числом. Попробуйте еще раз:")


@router.message(ClientAuthStates.waiting_for_api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    """Обработка API_HASH"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    
    api_hash = message.text.strip()
    if len(api_hash) < 10:
        await message.answer("❌ API_HASH слишком короткий. Попробуйте еще раз:")
        return
    
    await state.update_data(api_hash=api_hash)
    await message.answer(
        "✅ API_HASH сохранен\n\n"
        "Введите ваш номер телефона в международном формате:\n"
        "Пример: +79991234567",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ClientAuthStates.waiting_for_phone)


@router.message(ClientAuthStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка номера телефона"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))
        return
    
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Номер должен начинаться с +. Пример: +79991234567")
        return
    
    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    
    # Сохраняем в БД
    try:
        await crud.update_user_client_auth(
            telegram_id=message.from_user.id,
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone,
            has_auth=False  # Пока не авторизован
        )
        
        await message.answer(
            "✅ Данные сохранены\n\n"
            "🔐 Запускаю авторизацию...\n\n"
            "Вам придет код подтверждения в Telegram на номер " + phone + "\n\n"
            "Введите код когда получите:"
        )
        
        await state.set_state(ClientAuthStates.waiting_for_code)
        
        # Инициализируем клиент (но не авторизуемся пока)
        from services.telegram_client import get_user_client
        try:
            # Сохраняем данные в БД
            await crud.update_user_client_auth(
                telegram_id=message.from_user.id,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=phone,
                has_auth=False  # Пока не авторизован
            )
            
            # Пытаемся авторизоваться (автоматически при первом использовании)
            # Авторизация произойдет при создании первой рассылки
            await state.clear()
            await message.answer(
                "✅ Данные сохранены!\n\n"
                "🔐 Авторизация произойдет автоматически при создании первой рассылки.\n\n"
                "Или перезапустите бота для авторизации сейчас.\n\n"
                "После авторизации все ваши рассылки будут отправляться от ВАШЕГО имени! 🎉",
                reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id))
            )
            logger.info(f"Пользователь {message.from_user.id} настроил Client API, авторизация при первой рассылке")
            
            if client:
                # Авторизация прошла успешно
                await crud.update_user_client_auth(
                    telegram_id=message.from_user.id,
                    has_auth=True
                )
                await state.clear()
                await message.answer(
                    "✅ Авторизация успешна!\n\n"
                    "Теперь все ваши рассылки будут отправляться от вашего имени! 🎉",
                    reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id))
                )
                logger.info(f"Пользователь {message.from_user.id} успешно авторизовал Client API")
            else:
                await message.answer(
                    "❌ Не удалось авторизоваться. Проверьте данные и попробуйте еще раз через /setup_my_client"
                )
                await state.clear()
        except Exception as e:
            logger.error(f"Ошибка авторизации Client API для {message.from_user.id}: {e}", exc_info=True)
            await message.answer(
                f"❌ Ошибка авторизации: {str(e)}\n\n"
                "Проверьте данные и попробуйте еще раз через /setup_my_client"
            )
            await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении Client API данных: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при сохранении данных. Попробуйте еще раз."
        )


@router.message(Command("my_client_status"))
async def cmd_my_client_status(message: Message):
    """Проверка статуса Client API пользователя"""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    if user.has_client_auth and user.api_id:
        status_text = (
            "✅ Ваш Client API настроен и авторизован\n\n"
            f"📱 Номер: {user.phone_number or 'не указан'}\n"
            f"🔑 API_ID: {user.api_id}\n\n"
            "✅ Все ваши рассылки будут отправляться от ВАШЕГО имени!"
        )
    elif user.api_id:
        status_text = (
            "⚠️ Client API настроен, но не авторизован\n\n"
            f"📱 Номер: {user.phone_number}\n"
            f"🔑 API_ID: {user.api_id}\n\n"
            "Авторизация произойдет автоматически при первой рассылке.\n"
            "Или перезапустите бота для авторизации."
        )
    else:
        # Проверяем есть ли общие настройки в .env
        from config import API_ID, API_HASH
        if API_ID and API_HASH:
            status_text = (
                "ℹ️ Ваш персональный Client API не настроен\n\n"
                "Ваши рассылки будут отправляться от имени владельца бота (общий Client API).\n\n"
                "Чтобы отправлять от ВАШЕГО имени:\n"
                "1. Отправьте /setup_my_client\n"
                "2. Введите ваши API_ID и API_HASH\n"
                "3. Авторизуйтесь\n\n"
                "После этого все ваши рассылки будут от вашего имени!"
            )
        else:
            status_text = (
                "❌ Client API не настроен\n\n"
                "Рассылки будут работать только для пользователей, которые писали боту.\n\n"
                "Для отправки от вашего имени:\n"
                "Отправьте /setup_my_client"
            )
    
    await message.answer(status_text, reply_markup=get_main_keyboard(is_admin=is_admin(message.from_user.id)))

