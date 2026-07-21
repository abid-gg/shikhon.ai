from .health import router as health_router
from .questions import router as questions_router
from .auth import router as auth_router
from .exams import router as exams_router
from .sessions import router as sessions_router
from .documents import router as documents_router
from .analytics import router as analytics_router

__all__ = [
    "health_router",
    "questions_router",
    "auth_router",
    "exams_router",
    "sessions_router",
    "documents_router",
    "analytics_router",
]
