"""Conversations router (composed by responsibility)."""

from fastapi import APIRouter

from . import counts, crud, plan, sidebar, wdk_import

router = APIRouter()
router.include_router(crud.router)
router.include_router(counts.router)
router.include_router(plan.router)
router.include_router(wdk_import.router)
router.include_router(sidebar.router)
