from fastapi import APIRouter

from app.web.admin import router as admin_router
from app.web.auth import router as auth_router
from app.web.dashboard import router as dashboard_router
from app.web.setup import router as setup_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(setup_router)
router.include_router(admin_router)

