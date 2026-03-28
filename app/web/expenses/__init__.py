"""Expense routes sub-package."""

from fastapi import APIRouter

from app.web.expenses.crud import router as crud_router
from app.web.expenses.detail import router as detail_router
from app.web.expenses.list import router as list_router
from app.web.expenses.notes import router as notes_router
from app.web.expenses.preview import router as preview_router

router = APIRouter(tags=["expenses"])
router.include_router(preview_router)
router.include_router(crud_router)
router.include_router(list_router)
router.include_router(detail_router)
router.include_router(notes_router)
