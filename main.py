import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command, StateFilter
from database import Database
import re
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any
from handlers import (
    commands_router,
    callbacks_router,
    ai_advice_router,
    session_router,
    general_router,
)
from handlers.states import SessionStates

# Версия 1.0.1, базовые исправления времени. Добавлена функция get_user_sessions, добавлена функция расчета статистики,
# времени и дохода в час calculate_user_statistics.

# 1 PART OF BOT (Initialization)
# Logging settings.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot initialization (lol)
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Register routers
dp.include_router(commands_router)
dp.include_router(callbacks_router)
dp.include_router(ai_advice_router)
dp.include_router(general_router)
dp.include_router(session_router)


# FSM states
class SessionStates(StatesGroup):
    waiting_for_session_data = State()
    waiting_for_advice_topic = State()  # Новое состояние
    waiting_for_advice_question = State()  # Новое состояние


async def main():
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
