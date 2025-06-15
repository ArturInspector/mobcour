from aiogram.fsm.state import State, StatesGroup
# States registration and using file.

class SessionStates(StatesGroup):
    waiting_for_session_data = State()

class AIAdviceStates(StatesGroup):
    waiting_for_advice_topic = State()
    waiting_for_advice_question = State() 