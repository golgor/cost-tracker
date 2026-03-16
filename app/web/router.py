from fastapi import APIRouter

from app.web.auth import router as auth_router
from app.web.dashboard import router as dashboard_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(dashboard_router)
