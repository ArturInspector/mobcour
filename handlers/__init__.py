from .commands import router as commands_router
from .calllbacks import router as callbacks_router
from .general import router as general_router
from .ai_advice import router as ai_advice_router
from .session import router as session_router

__all__ = [
    'commands_router',
    'callbacks_router',
    'general_router',
    'ai_advice_router',
    'session_router'
]
