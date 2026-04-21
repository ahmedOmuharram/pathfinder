"""Conversations router (composed by responsibility)."""

from fastapi import APIRouter

from . import (
    counts,
    crud,
    revert,
    scratchpad,
    sidebar,
    strategy_ast,
    wdk_import,
)

router = APIRouter()
router.include_router(crud.router)
router.include_router(counts.router)
router.include_router(strategy_ast.router)
router.include_router(wdk_import.router)
router.include_router(sidebar.router)
router.include_router(scratchpad.router)
router.include_router(revert.router)
