from fastapi import APIRouter

from app.api.routes_tasks import router as tasks_router
from app.api.routes_memory import router as memory_router
from app.api.routes_datapool import router as datapool_router
from app.api.routes_eval import router as eval_router
from app.api.routes_health import router as health_router
from app.api.routes_notes import router as notes_router
from app.api.routes_todos import router as todos_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(tasks_router)
api_router.include_router(notes_router)
api_router.include_router(todos_router)
api_router.include_router(memory_router)
api_router.include_router(datapool_router)
api_router.include_router(eval_router)
