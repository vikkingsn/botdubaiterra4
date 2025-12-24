"""
Обычные клавиатуры
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = [
        [KeyboardButton(text="📧 Новая рассылка")],
        [KeyboardButton(text="📊 Мои рассылки")],
        [KeyboardButton(text="👥 Группы")],
    ]
    
    if is_admin:
        keyboard.append([KeyboardButton(text="📝 Шаблоны")])
        keyboard.append([KeyboardButton(text="⚙️ Настройки")])
    
    keyboard.append([KeyboardButton(text="ℹ️ Помощь")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


def get_recipients_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для ввода получателей с кнопкой 'В группе'"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 В группе")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
