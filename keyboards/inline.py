from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру главного меню.
    Возвращает InlineKeyboardMarkup с кнопками профиля, добавления смены и ИИ советов.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
            InlineKeyboardButton(text="📝 Добавить смену", callback_data="add_session"),
            InlineKeyboardButton(text="💡 ИИ советы", callback_data="ai_advice")
        ]
    ])

def get_service_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора сервиса доставки.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Яндекс Экспресс", callback_data="service_yandex_express"),
            InlineKeyboardButton(text="Яндекс Еда", callback_data="service_yandex_food")
        ],
        [
            InlineKeyboardButton(text="Глово", callback_data="service_glovo"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
        ]
    ])

def get_back_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой "Назад".
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
        ]
    ])

def get_ai_advice_topics_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с темами для ИИ советов.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
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