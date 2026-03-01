"""Experiment Lab endpoints -- split into sub-routers for maintainability."""

from __future__ import annotations

from fastapi import APIRouter

from .analysis import router as analysis_router
from .crud import router as crud_router
from .execution import router as execution_router
from .results import router as results_router

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])

# Include order matters: non-parametric paths (/batch, /benchmark, /overlap,
# /enrichment-compare, /ai-assist, /importable-strategies) must be registered
# before /{experiment_id} to avoid route shadowing.
router.include_router(execution_router)
router.include_router(analysis_router)
router.include_router(crud_router)
router.include_router(results_router)
