import logging
from aiogram import Router, F
from aiogram.types import Update, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import Database
from keyboards.inline import get_main_menu_keyboard, get_back_keyboard

# Messages without states, or not handled messages are here.
logger = logging.getLogger(__name__)
db = Database()

# Создаем роутер для общих обработчиков
router = Router()

# Обработчик ошибок
@router.errors()
async def error_handler(update: Update, exception: Exception):
    """
    Глобальный обработчик ошибок
    """
    try:
        error_message = f"❌ Произошла ошибка: {str(exception)}"
        logger.error(f"Ошибка в обработке: {exception}", exc_info=True)
        
        # Создаем клавиатуру для возврата в главное меню
        keyboard = get_back_keyboard()
        
        if update.message:
            await update.message.answer(error_message, reply_markup=keyboard)
        elif update.callback_query:
            await update.callback_query.message.edit_text(error_message, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}", exc_info=True)
    return True

# Обработчик текстовых сообщений вне состояний
@router.message()
async def handle_text(message: Message):
    """
    Обработчик текстовых сообщений
    """
    await message.answer(
        "Я понимаю только команды и специальные сообщения.\n"
        "Используйте меню для навигации."
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Обработчик команды /start
    """
    await message.answer(
        "👋 Привет! Я бот для курьеров.\n"
        "Я помогу тебе вести учет смен и получать советы.",
        reply_markup=get_main_menu_keyboard()
    )
