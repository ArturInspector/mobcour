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
from handlers import error_handler, unknown_command, handle_text
from ai_advice import AIAdviceHandler

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

# Global errors handler registration. Alright
dp.errors.register(error_handler)

# FSM states
class SessionStates(StatesGroup):
    waiting_for_session_data = State()
    waiting_for_advice_topic = State()  # Новое состояние
    waiting_for_advice_question = State()  # Новое состояние

# AI Advice Handler class in this file.
advice_handler = AIAdviceHandler()

# Services dictionary.
service_names = {
    "yandex_express": "Яндекс Экспресс",
    "yandex_food": "Яндекс Еда",
    "glovo": "Глово"
}


# 2 PART OF BOT (Handlers)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext = None):
    try:
        # Получаем или создаем пользователя
        user = db.get_or_create_user(message.from_user.id, message.from_user.username)
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
                InlineKeyboardButton(text="📝 Добавить смену", callback_data="add_session"),
                InlineKeyboardButton(text="💡 ИИ советы", callback_data="ai_advice")
            ]
        ])
        
        sent_message = await message.answer(
            "👋 Привет! Я бот для учета доставки.\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
        
        # Сохраняем ID сообщения в состоянии, если state предоставлен
        if state:
            await state.update_data(menu_message_id=sent_message.message_id)
            
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

# Обработчик нажатия на кнопку профиля
@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        stats = db.get_user_statistics(user_id)

        # Проверка на наличие статистики
        if not stats:
            await callback.message.edit_text(
                "👤 *Профиль курьера*\n\n"
                "У вас пока нет данных о сменах.\n"
                "Добавьте информацию о первой смене, чтобы увидеть статистику.",
                parse_mode="Markdown"
            )
            return
            
        # Безопасное получение значений с проверкой на None
        def safe_get(key: str, default: Any = 0) -> Any:
            value = stats.get(key)
            return default if value is None else value
        
        # Получаем все значения безопасно
        total_shifts = safe_get('total_shifts')
        total_earnings = safe_get('total_earnings')
        total_orders = safe_get('total_orders')
        avg_earnings = safe_get('avg_earnings')
        avg_orders = safe_get('avg_orders')
        max_earnings = safe_get('max_earnings')
        min_earnings = safe_get('min_earnings')
        total_hours = safe_get('total_hours')
        avg_shift_duration = safe_get('avg_shift_duration')
        
        # Вычисление earnings_per_hour с проверкой на ноль
        earnings_per_hour = 0
        if total_hours > 0:
            earnings_per_hour = total_earnings / total_hours
        
        # Формирование текста профиля
        profile_text = (
            f"👤 *Профиль курьера {callback.from_user.first_name}*\n\n"
        )
        
        # Добавление статистики только если есть смены
        if total_shifts > 0:
            profile_text += (
                f"📊 *Основная статистика:*\n"
                f"• 🔢 Всего смен: {total_shifts}\n"
                f"• 💰 Общий заработок: {total_earnings}С\n"
                f"• 📦 Всего заказов: {total_orders}\n\n"
                
                f"⏱ *Временные показатели:*\n"
                f"• 🕒 Общее время работы: {total_hours:.1f} ч\n"
                f"• ⏳ Средняя длительность смены: {avg_shift_duration:.1f} ч\n"
                f"• 💸 Средний доход в час: {earnings_per_hour:.0f}с\n\n"
                
                f"📈 *Результативность:*\n"
                f"• 📊 Средний заработок за смену: {avg_earnings:.0f}с\n"
                f"• 📊 Среднее число заказов за смену: {avg_orders:.1f}\n"
                f"• 🔝 Максимальный заработок: {max_earnings}с\n"
                f"• 🔻 Минимальный заработок: {min_earnings}с\n"
            )
        else:
            profile_text += (
                "У вас пока нет данных о сменах.\n"
                "Добавьте информацию о первой смене, чтобы увидеть статистику."
            )
        
        # Добавляем кнопку "Назад"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
            ]
        ])
        
        await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка при показе профиля: {e}")
        # Более подробный вывод ошибки для диагностики
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await callback.message.edit_text("❌ Произошла ошибка при загрузке профиля")

# Обработчик нажатия на кнопку добавления смены
@dp.callback_query(F.data == "add_session")
async def add_session(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.set_state(SessionStates.waiting_for_session_data)
        
        # Сохраняем ID сообщения меню
        await state.update_data(menu_message_id=callback.message.message_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
            ]
        ])
        
        await callback.message.edit_text(
            "📝 Отправьте данные смены в формате:\n"
            "05.02.2007 (дата)\n"
            "16:40 (время начала)\n"
            "18:21 (время завершения)\n"
            "2 (количество заказов)\n"
            "454 (заработок)",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении смены: {e}")
        await callback.message.edit_text("❌ Произошла ошибка")

# Обработчик ввода данных смены
@dp.message(SessionStates.waiting_for_session_data)
async def process_session_data(message: Message, state: FSMContext):
    try:
        # Получаем сохраненные данные о меню
        state_data = await state.get_data()
        menu_message_id = state_data.get('menu_message_id')
        
        # Отправляем временное сообщение о начале обработки и удаляем его потом
        processing_msg = await message.answer("⌛ Обрабатываю данные...")
        
        # Разбиваем сообщение на строки
        lines = message.text.strip().split('\n')
        if len(lines) != 5:
            raise ValueError("Неверный формат данных")
        
        # Парсим данные
        date_str = lines[0].strip()
        start_time_str = lines[1].strip()
        end_time_str = lines[2].strip()
        orders = int(lines[3].strip())
        earnings = float(lines[4].strip())
        
        # Проверяем формат даты
        if not re.match(r'\d{2}\.\d{2}\.\d{4}', date_str):
            raise ValueError("Неверный формат даты")
        
        # Проверяем формат времени
        if not re.match(r'\d{2}:\d{2}', start_time_str) or not re.match(r'\d{2}:\d{2}', end_time_str):
            raise ValueError("Неверный формат времени")
        
        # Проверяем количество заказов и заработок
        if orders <= 0 or orders > 25:
            raise ValueError("Количество заказов должно быть положительным числом и меньше 25.")
        
        # Проверяем количество заказов за смену
        if orders > 25 or earnings >= 6000:
            raise ValueError("Заработок не соответствует реальности! Введите меньшее число.")

        # Проверяем корректность времени
        try:
            # Преобразуем строки в объекты datetime
            start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%d.%m.%Y %H:%M")
            end_dt = datetime.strptime(f"{date_str} {end_time_str}", "%d.%m.%Y %H:%M")
            
            # Получаем текущую дату и время
            current_dt = datetime.now()
            
            # Проверка года (должен быть не раньше 2022)
            if start_dt.year < 2022:
                raise ValueError("Год не может быть раньше 2022")
            
            # Проверка месяца (должен быть от 1 до 12)
            if not 1 <= start_dt.month <= 12:
                raise ValueError("Месяц должен быть от 1 до 12")
            
            # Проверка, что дата не в будущем
            if start_dt > current_dt or end_dt > current_dt:
                raise ValueError("Дата и время не могут быть в будущем")
            
            # Проверяем, что время окончания позже времени начала
            if end_dt <= start_dt:
                raise ValueError("Время окончания должно быть позже времени начала")
            
            # Вычисляем общее время работы в часах
            total_hours = (end_dt - start_dt).total_seconds() / 3600
            if total_hours <= 0:
                raise ValueError("Время работы должно быть положительным")
                
        except ValueError as e:
            raise ValueError(f"Некорректная дата или время: {str(e)}")
        
        # Получаем текущий сервис пользователя из базы данных
        user_id = message.from_user.id
        current_service_key = db.get_user_service(user_id)  # Предполагается, что эта функция существует

        # Если сервис не найден, устанавливаем по умолчанию
        if not current_service_key:
            current_service_key = "yandex_food"

        # Получаем название сервиса на русском
        current_service = service_names.get(current_service_key, "Неизвестный сервис")

        # Сохраняем смену с полной датой и временем
        session_id = db.add_session(
            message.from_user.id,
            "delivery",
            start_dt.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        await state.clear()
        
        # Создаем клавиатуру для главного меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
                InlineKeyboardButton(text="📝 Добавить смену", callback_data="add_session"),
                InlineKeyboardButton(text="💡 ИИ советы", callback_data="ai_advice")
            ]
        ])
        
        # Обновляем основное сообщение с результатом
        if session_id:
            # Обновляем сессию с добавлением текущего сервиса
            db.update_session(
                session_id, 
                earnings=earnings, 
                order_count=orders, 
                start_time=start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_dt.strftime('%Y-%m-%d %H:%M:%S'),
                service=current_service_key
            )
            
            success_text = (
                "✅ Смена успешно добавлена!\n\n"
                f"📅 Дата: {date_str}\n"
                f"🕒 Время: {start_time_str} - {end_time_str}\n"
                f"📦 Заказов: {orders}\n"
                f"💰 Заработок: {earnings}с\n\n"
                f"🕒 Общее время работы: {total_hours:.1f} ч\n\n"
                f"🚚 Текущий сервис: {current_service}\n\n"
                "👋 Выберите действие:"
            )
            
            await message.answer(success_text, reply_markup=keyboard)
        else:
            await message.answer("❌ Ошибка при сохранении смены.\n\nВыберите действие:", reply_markup=keyboard)
        
        # Удаляем сообщение о процессе обработки
        await processing_msg.delete()
        
    except ValueError as e:
        # В случае ошибки валидации создаем клавиатуру с кнопкой назад
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="add_session")]
        ])
        
        error_text = f"❌ Ошибка: {str(e)}\nПожалуйста, проверьте формат данных и попробуйте снова."
        await message.answer(error_text, reply_markup=back_keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке данных смены: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # В случае неизвестной ошибки создаем клавиатуру с кнопкой назад в меню
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ])
        
        await message.answer("❌ Произошла ошибка при обработке данных. Пожалуйста, попробуйте позже.", 
                             reply_markup=back_keyboard)

# Обработчик кнопки "Назад"
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    try:
        if state is not None:
            await state.clear()
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
                InlineKeyboardButton(text="📝 Добавить смену", callback_data="add_session"),
                InlineKeyboardButton(text="💡 ИИ советы", callback_data="ai_advice")
            ]
        ])
        
        # Редактируем текущее сообщение вместо создания нового
        await callback.message.edit_text(
            "👋 Привет! Я бот для учета доставки.\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при возврате в главное меню")

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "👋! Вот список доступных команд:\n"
        "/start - Запустить бота (потому что кто-то должен это делать)\n"
        "/help - Показать это сообщение (если вы не знаете, что делать дальше)\n"
        "/service - Изменить сервис доставки (по умолчанию - Яндекс Экспресс, но кто знает, может, вам повезет больше)\n"
        "И другие функции, доступные через кнопки в меню (потому что текст слишком скучен для вас).\n\n"
        "🤖 Этот бот поможет вам эффективно управлять работой и отслеживать статистику, пока вы не станете цифровым рабом.\n"
        "💡 Используйте ИИ советы для оптимизации работы и повышения заработка! Или просто будьте нормисом.\n"
        "Скажем нет цифровому рабству Яндекса! (или да) Теперь у нас тоже есть бот."
    )
    await message.answer(help_text)

# Обработчик команды /service
@dp.message(Command("service"))
async def cmd_service(message: Message):
    # Создаем клавиатуру с сервисами
    service_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Яндекс Экспресс", callback_data="service_yandex_express"),
            InlineKeyboardButton(text="Яндекс Еда", callback_data="service_yandex_food")
        ],
        [
            InlineKeyboardButton(text="Глово", callback_data="service_glovo"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
        ]
    ])
    
    await message.answer(
        "🚚 Выберите сервис доставки:",
        reply_markup=service_keyboard
    )

# Обработчик выбора сервиса
@dp.callback_query(F.data.startswith("service_"))
async def handle_service_selection(callback: types.CallbackQuery):
    try:
        # Получаем выбранный сервис из callback_data
        service_map = {
            "service_yandex_express": ("Яндекс Экспресс", "yandex_express"),
            "service_yandex_food": ("Яндекс Еда", "yandex_food"),
            "service_glovo": ("Глово", "glovo")
        }
        
        # Получаем название сервиса на русском и его английский идентификатор
        selected_service_info = service_map.get(callback.data)
        if not selected_service_info:
            raise ValueError("Неизвестный сервис")
        
        selected_service_name, selected_service_key = selected_service_info
        
        # Обновляем сервис в базе данных
        user_id = callback.from_user.id
        db.update_user_service(user_id, selected_service_key)  # Отправляем английский идентификатор
        
        # Отправляем сообщение об успешном обновлении
        await callback.message.edit_text(
            f"✅ Сервис успешно изменен на: {selected_service_name}"  # Показываем название на русском
        )
        
        # Вызываем существующий обработчик для возврата в главное меню
        await back_to_main(callback, None)
        
    except Exception as e:
        logger.error(f"Ошибка при выборе сервиса: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при выборе сервиса. Попробуйте позже."
        )
        await back_to_main(callback, None)

# Обработчик неизвестных команд
@dp.message(Command("settings"))
async def unknown_cmd_handler(message: Message):
    await unknown_command(message)

# Обработчик текстовых сообщений вне состояний
@dp.message()
async def text_message_handler(message: Message):
    await handle_text(message)

# Обработчик кнопки "ИИ советы"
@dp.callback_query(F.data == "ai_advice")
async def ai_advice_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SessionStates.waiting_for_advice_topic)
    
    # Предложение тем
    topics_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚖ Юридические вопросы", callback_data="legal"),
            InlineKeyboardButton(text="🍎 Питание, здоровье", callback_data="nutrition"),
            InlineKeyboardButton(text="🚲 Транспорт", callback_data="vehicle"),
            InlineKeyboardButton(text="💡 Оптимизация заработка", callback_data="optimization")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
        ]
    ])
    
    await callback.message.edit_text("Выберите тему для ИИ советов:", reply_markup=topics_keyboard)

@dp.callback_query(F.data.in_({"legal", "nutrition", "vehicle", "optimization"}))
async def handle_advice_topic(callback: types.CallbackQuery, state: FSMContext):
    selected_topic = callback.data
    await state.update_data(selected_topic=selected_topic)  # Сохраняем выбранную тему
    
    await state.set_state(SessionStates.waiting_for_advice_question)
    
    await callback.message.edit_text("Введите ваш вопрос по выбранной теме:")

@dp.message(SessionStates.waiting_for_advice_question)
async def process_advice_question(message: Message, state: FSMContext):
    user_data = await state.get_data()
    selected_topic = user_data.get('selected_topic')

    if selected_topic is None:
        await message.answer("Пожалуйста, выберите тему перед тем, как задавать вопрос.")
        return

    # Логируем выбранную тему
    logger.info(f"Выбранная тема: {selected_topic}")

    # Вызываем функцию из ai_advice.py для обработки вопроса
    response = await advice_handler.get_advice(message.text, selected_topic)

    # Логируем ответ от AI
    logger.info(f"Ответ от AI: {response}")

    await message.answer(response)
    await state.clear()  # Очистка состояния после обработки

def calculate_user_statistics(user_id):
    sessions = db.get_user_sessions(user_id)  # Получаем все смены пользователя
    total_hours = 0
    total_earnings = 0
    total_orders = 0

    for session in sessions:
        if session['start_time'] and session['end_time']:
            start_dt = datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S')
            session_hours = (end_dt - start_dt).total_seconds() / 3600
            total_hours += session_hours
        total_earnings += session['earnings']
        total_orders += session['order_count']

    avg_shift_duration = total_hours / len(sessions) if sessions else 0
    avg_earnings_per_hour = total_earnings / total_hours if total_hours > 0 else 0

    return {
        'total_shifts': len(sessions),
        'total_hours': round(total_hours, 2),
        'total_earnings': total_earnings,
        'total_orders': total_orders,
        'avg_shift_duration': round(avg_shift_duration, 2),
        'avg_earnings_per_hour': round(avg_earnings_per_hour, 2)
    }

async def main():
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
