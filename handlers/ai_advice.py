import requests
import logging
from dotenv import load_dotenv
import os
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.inline import get_ai_advice_topics_keyboard, get_back_keyboard
from database import Database

# Full AI advice callbacks and functional (request in class)
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = Router()
db = Database()

class AIAdviceStates(StatesGroup):
    waiting_for_advice_question = State()

# Main prompt and answer.
class AIAdviceHandler:
    def __init__(self):
        # Шаблоны промптов
        self.prompts = [
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Помоги юзеру в том, что он просит и задай вопрос, позволяющий оптимизировать заработок и дай статистику. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Отвечай НЕ БОЛЕЕ 1000-1200 символов! Prompt:",
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Ты юрист, позволяющий разобраться в правах и возможностях, ПДД КР, патенте КР и прочем. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Отвечай НЕ БОЛЕЕ 1000-1200 символов! Prompt:",
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Ты помощник по здоровью, питанию, сначала напиши факт о здоровье и курьерке. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Отвечай НЕ БОЛЕЕ 1000-1200 символов! Вопрос юзера:",
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Ты механик во всех видах транспорта. Помоги по максимуму оптимизировать юзеру транспорт для курьерки - дай все нужные советы и тонкости. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Отвечай НЕ БОЛЕЕ 1000-1200 символов! Вопрос юзера:"
        ]
        
        # Ограничения
        self.max_questions_per_day = 6
        self.max_characters_per_prompt = 120
        self.questions_today = 0

        # Инициализация API-ключа
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("API ключ не найден. Убедитесь, что он указан в .env файле.")
            raise ValueError("API ключ не найден.")

    async def get_advice(self, user_question, selected_topic):
        if self.questions_today >= self.max_questions_per_day:
            return "Превышено количество вопросов на сегодня. 6 в сутки."

        if len(user_question) > self.max_characters_per_prompt:
            return "Вопрос превышает максимальное количество символов (120)."

        # Выбор шаблона в зависимости от топика.
        if selected_topic == "legal":
            prompt_template = self.prompts[1]  # Первый шаблон
        elif selected_topic == "nutrition":
            prompt_template = self.prompts[2]  # Второй шаблон
        elif selected_topic == "vehicle":
            prompt_template = self.prompts[3]  # Третий шаблон
        elif selected_topic == "optimization":
            prompt_template = self.prompts[0]  # Нулевой шаблон
        else:
            return "Неизвестный топик."

        # Формирование полного промпта
        full_prompt = f"{prompt_template}\nВопрос: {user_question}"

        # Здесь будет логика для получения совета от Gemini
        try:
            response = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                headers={
                    'Content-Type': 'application/json',
                    'x-goog-api-key': self.api_key
                },
                json={
                    "contents": [{
                        "parts": [{
                            "text": full_prompt
                        }]
                    }]
                }
            )
            response.raise_for_status()  # Проверка на ошибки HTTP
            self.questions_today += 1  # Увеличиваем счетчик вопросов
            
            response_data = response.json()
            if 'candidates' not in response_data or not response_data['candidates']:
                logger.warning("Ответ не содержит candidates")
                return 'Совет не найден'
                
            advice = response_data['candidates'][0]['content']['parts'][0]['text']
            
            if not advice:
                logger.warning("Пустой ответ от нейронной сети")
                return 'Совет не найден'
            
            logger.info(f"Ответ от нейронной сети: {advice}")
            return advice
            
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP ошибка: {http_err}")
            return "Произошла ошибка при запросе к API."
        except Exception as e:
            logger.error(f"Ошибка при получении совета: {e}")
            return "Произошла ошибка при получении совета."
        
# Callbacks, waiting for advice question state.
@router.callback_query(F.data == "ai_advice")
async def process_ai_advice(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку ИИ советы
    """
    try:
        await callback.message.edit_text(
            "🤖 Выберите тему, по которой хотите получить совет:",
            reply_markup=get_ai_advice_topics_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_ai_advice: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.in_(["legal", "nutrition", "vehicle", "optimization"]))
async def process_topic_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора темы для ИИ совета
    """
    try:
        topic = callback.data
        topic_names = {
            "legal": "юридические вопросы",
            "nutrition": "питание и здоровье",
            "vehicle": "транспорт",
            "optimization": "оптимизация заработка"
        }
        
        await state.update_data(selected_topic=topic)
        await state.set_state(AIAdviceStates.waiting_for_advice_question)
        
        await callback.message.edit_text(
            f"📝 Задайте ваш вопрос по теме '{topic_names[topic]}':",
            reply_markup=get_back_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_topic_selection: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.message(AIAdviceStates.waiting_for_advice_question)
async def process_advice_question(message: Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        selected_topic = user_data.get('selected_topic')
        
        if not selected_topic:
            await message.answer("Пожалуйста, выберите тему перед тем, как задавать вопрос.")
            return
        
        advice_handler = AIAdviceHandler()
        advice = await advice_handler.get_advice(message.text, selected_topic)
        
        if not advice:
            await message.answer("Не удалось получить ответ. Попробуйте позже.")
            await state.clear()
            return
            
        await message.answer(advice)
        await state.clear()
        
        await message.answer(
            "🤖 Хотите задать еще один вопрос? Выберите тему:",
            reply_markup=get_ai_advice_topics_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в process_advice_question: {e}")
        await message.answer("❌ Произошла ошибка при обработке вашего вопроса. Попробуйте позже.")
        await state.clear()