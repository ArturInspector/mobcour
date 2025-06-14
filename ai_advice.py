import requests
import logging
from dotenv import load_dotenv
import os
import random

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIAdviceHandler:
    def __init__(self):
        # Шаблоны промптов
        self.prompts = [
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Помоги юзеру в том, что он просит и задай вопрос, позволяющий оптимизировать заработок и дай статистику. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Prompt:",
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Ты юрист, позволяющий разобраться в правах и возможностях, ПДД КР, патенте КР и прочем. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Prompt:",
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Ты помощник по здоровью, питанию, сначала напиши факт о здоровье и курьерке. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Вопрос юзера:",
            "Ты - встроен в тг бота для помощи курьерам в Бишкеке. Ты механик во всех видах транспорта. Помоги по максимуму оптимизировать юзеру транспорт для курьерки - дай все нужные советы и тонкости. Если вопрос не о курьерстве, верни: 'Этот вопрос не касается курьерства.' Вопрос юзера:"
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
        # Проверка ограничений
        if self.questions_today >= self.max_questions_per_day:
            return "Превышено количество вопросов на сегодня. 6 в сутки."

        if len(user_question) > self.max_characters_per_prompt:
            return "Вопрос превышает максимальное количество символов (120)."

        # Выбор шаблона в зависимости от топика
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
                'https://api.gemini.com/advice',
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={'prompt': full_prompt}
            )
            response.raise_for_status()  # Проверка на ошибки HTTP
            self.questions_today += 1  # Увеличиваем счетчик вопросов
            advice = response.json().get('advice')
            
            if advice is None:
                logger.warning("Ответ не содержит ключ 'advice'.")
                return 'Совет не найден'
            
            logger.info(f"Ответ от нейронной сети: {advice}")
            return advice
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP ошибка: {http_err}")
            return "Произошла ошибка при запросе к API."
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return "Произошла ошибка при получении совета."