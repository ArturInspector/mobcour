import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import Database

logger = logging.getLogger(__name__)
db = Database()

# Обработчик ошибок
async def error_handler(update: types.Update, exception: Exception):
    """
    Обработчик ошибок бота
    """
    try:
        error_message = f"❌ Произошла ошибка: {str(exception)}"
        logger.error(f"Ошибка в обработке: {exception}", exc_info=True)
        
        # Создаем клавиатуру для возврата в главное меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ])
        
        if update.message:
            await update.message.answer(error_message, reply_markup=keyboard)
        elif update.callback_query:
            await update.callback_query.message.edit_text(error_message, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}", exc_info=True)
    return True

# Обработчик неизвестных команд
async def unknown_command(message: Message):
    """
    Обработчик неизвестных команд
    """
    try:
        # Создаем клавиатуру для возврата в главное меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ])
        
        await message.answer(
            "❓ Неизвестная команда.\n"
            "Используйте /start для начала работы с ботом.\nИли /help для получения функционала.",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка в обработчике неизвестных команд: {e}", exc_info=True)

# Обработчик текстовых сообщений вне состояний
async def handle_text(message: Message):
    """
    Обработчик текстовых сообщений вне состояний
    """
    try:
        # Создаем клавиатуру для возврата в главное меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ])
        
        await message.answer(
            "ℹ️ Пожалуйста, используйте кнопки меню для навигации.\n"
            "Для начала работы используйте /start\n",
            "Или /help для получения функционала.",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка в обработчике текстовых сообщений: {e}", exc_info=True)
