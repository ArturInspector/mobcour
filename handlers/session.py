from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from datetime import datetime
import logging
import re
from database import Database
from .states import SessionStates
from keyboards.inline import get_main_menu_keyboard, get_back_keyboard

# Courier session handler.
router = Router()
logger = logging.getLogger(__name__)
db = Database()

# Services dictionary
service_names = {
    "yandex_express": "Яндекс Экспресс",
    "yandex_food": "Яндекс Еда",
    "glovo": "Глово"
}

@router.message(SessionStates.waiting_for_session_data)
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
        current_service_key = db.get_user_service(user_id)

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
        keyboard = get_main_menu_keyboard()
        
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
        back_keyboard = get_back_keyboard()
        
        error_text = f"❌ Ошибка: {str(e)}\nПожалуйста, проверьте формат данных и попробуйте снова."
        await message.answer(error_text, reply_markup=back_keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке данных смены: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # В случае неизвестной ошибки создаем клавиатуру с кнопкой назад в меню
        back_keyboard = get_back_keyboard()
        
        await message.answer("❌ Произошла ошибка при обработке данных. Пожалуйста, попробуйте позже.", 
                             reply_markup=back_keyboard)