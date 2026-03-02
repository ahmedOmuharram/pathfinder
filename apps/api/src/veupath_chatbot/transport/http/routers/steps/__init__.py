"""Step sub-routers (filters, analyses, reports)."""

from fastapi import APIRouter

from veupath_chatbot.transport.http.routers.steps import (
    analyses,
    crud,
    filters,
    reports,
)

router = APIRouter()
router.include_router(crud.router)
router.include_router(filters.router)
router.include_router(analyses.router)
router.include_router(reports.router)
