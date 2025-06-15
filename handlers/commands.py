import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.inline import get_main_menu_keyboard, get_service_keyboard
from database import Database

# Main commands handler right here.

logger = logging.getLogger(__name__)

# Создаем роутер для команд
router = Router()
db = Database()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext = None):
    """
    Обработчик команды /start.
    Создает или получает пользователя и показывает главное меню.
    """
    try:
        # Получаем или создаем пользователя
        user = db.get_or_create_user(message.from_user.id, message.from_user.username)
        
        # Отправляем приветственное сообщение с клавиатурой
        sent_message = await message.answer(
            "👋 Привет! Я бот для учета доставки.\n"
            "Выберите действие:",
            reply_markup=get_main_menu_keyboard()
        )
        
        # Сохраняем ID сообщения в состоянии, если state предоставлен
        if state:
            await state.update_data(menu_message_id=sent_message.message_id)
            
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """
    Обработчик команды /help.
    Показывает список доступных команд и их описание.
    """
    help_text = (
        "👋! Вот список доступных команд:\n"
        "/start - Запустить бота\n"
        "/help - Показать это сообщение\n"
        "/service - Изменить сервис доставки (По умолчанию - Яндекс Еда)\n"
        "И другие функции, доступные через кнопки в меню.\n\n"
        "🤖 Этот бот поможет вам эффективно управлять работой и отслеживать статистику.\n"
        "💡 Используйте ИИ советы для оптимизации работы и повышения заработка!\n"
        "Курьеры не рабы! (Ну немного)"
    )
    await message.answer(help_text)

@router.message(Command("service"))
async def cmd_service(message: types.Message):
    """
    Обработчик команды /service.
    Показывает меню выбора сервиса доставки.
    """
    await message.answer(
        "🚚 Выберите сервис доставки:",
        reply_markup=get_service_keyboard()
    )
