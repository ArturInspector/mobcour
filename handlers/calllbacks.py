import logging
from typing import Any
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from keyboards.inline import (
    get_main_menu_keyboard,
    get_service_keyboard,
    get_back_keyboard,
    get_ai_advice_topics_keyboard
)
from database import Database
from .states import SessionStates, AIAdviceStates

# Main buttons handler right here.
logger = logging.getLogger(__name__)

# Router and database.
router = Router()
db = Database()


@router.callback_query(F.data == "ai_advice")
async def ai_advice_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки "ИИ советы".
    Показывает меню с темами для советов.
    """
    try:
        await state.set_state(AIAdviceStates.waiting_for_advice_topic)
        
        await callback.message.edit_text(
            "Выберите тему для ИИ советов:",
            reply_markup=get_ai_advice_topics_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при показе тем ИИ советов: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data.in_({"legal", "nutrition", "vehicle", "optimization"}))
async def handle_advice_topic(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора темы для ИИ советов.
    Сохраняет выбранную тему и запрашивает вопрос.
    """
    try:
        selected_topic = callback.data
        await state.update_data(selected_topic=selected_topic)
        await state.set_state(AIAdviceStates.waiting_for_advice_question)
        
        await callback.message.edit_text(
            "Введите ваш вопрос по выбранной теме:",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при выборе темы: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data == "add_session")
async def add_session(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки добавления смены.
    Устанавливает состояние ожидания данных смены.
    """
    try:
        await state.set_state(SessionStates.waiting_for_session_data)
        await state.update_data(menu_message_id=callback.message.message_id)
        
        await callback.message.edit_text(
            "📝 Отправьте данные смены в формате:\n"
            "05.02.2007 (дата)\n"
            "16:40 (время начала)\n"
            "18:21 (время завершения)\n"
            "2 (количество заказов)\n"
            "454 (заработок)",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при добавлении смены: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data.startswith("service_"))
async def handle_service_selection(callback: types.CallbackQuery):
    """
    Обработчик выбора сервиса доставки.
    Обновляет сервис пользователя в базе данных.
    """
    try:
        service_map = {
            "service_yandex_express": ("Яндекс Экспресс", "yandex_express"),
            "service_yandex_food": ("Яндекс Еда", "yandex_food"),
            "service_glovo": ("Глово", "glovo")
        }
        
        selected_service_info = service_map.get(callback.data)
        if not selected_service_info:
            raise ValueError("Неизвестный сервис")
        
        selected_service_name, selected_service_key = selected_service_info
        
        user_id = callback.from_user.id
        username = callback.from_user.username
        user = db.get_or_create_user(user_id, username=username)
        db.update_user_service(user_id, selected_service_key)
        
        await callback.message.edit_text(
            f"✅ Сервис успешно изменен на: {selected_service_name}",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе сервиса: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при выборе сервиса",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()

# Обработчик нажатия на кнопку профиля
@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        username = callback.from_user.username
        user = db.get_or_create_user(user_id, username=username)
        
        if not user:
            await callback.message.edit_text(
                "❌ Пользователь не найден в базе данных.\n"
                "Пожалуйста, используйте /start для регистрации.",
                reply_markup=get_back_keyboard()
            )
            return
            
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
        keyboard = get_back_keyboard()
        
        await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка при показе профиля: {e}")
        # Более подробный вывод ошибки для диагностики
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await callback.message.edit_text("❌ Произошла ошибка при загрузке профиля")


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    try:
        if state is not None:
            await state.clear()
        
        # Создаем клавиатуру
        keyboard = get_main_menu_keyboard()
        
        # Редактируем текущее сообщение вместо создания нового
        await callback.message.edit_text(
            "👋 Привет! Я бот для учета доставки.\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при возврате в главное меню")
        await callback.answer()
