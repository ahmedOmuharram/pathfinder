"""Conversations router (composed by responsibility)."""

from fastapi import APIRouter

from . import (
    cancel,
    counts,
    crud,
    events,
    insert_saved,
    operations,
    revert,
    save_substrategy,
    scratchpad,
    sidebar,
    strategy_ast,
    wdk_import,
)

router = APIRouter()
router.include_router(crud.router)
router.include_router(counts.router)
router.include_router(events.router)
router.include_router(strategy_ast.router)
router.include_router(operations.router)
router.include_router(wdk_import.router)
router.include_router(sidebar.router)
router.include_router(scratchpad.router)
router.include_router(revert.router)
router.include_router(save_substrategy.router)
router.include_router(insert_saved.router)
router.include_router(cancel.router)
