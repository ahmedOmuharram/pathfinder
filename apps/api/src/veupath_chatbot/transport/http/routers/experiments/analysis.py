"""Analysis endpoints: cross-validate, enrich, re-evaluate, threshold-sweep, etc.

Mounts sub-routers for each analysis domain. Non-parametric routes (overlap,
enrichment-compare, ai-assist) are included first so they don't get shadowed
by /{experiment_id} parametric routes.
"""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.transport.http.routers.experiments.ai_assist import (
    router as ai_assist_router,
)
from veupath_chatbot.transport.http.routers.experiments.comparison import (
    router as comparison_router,
)
from veupath_chatbot.transport.http.routers.experiments.cross_validation import (
    router as cv_router,
)
from veupath_chatbot.transport.http.routers.experiments.enrichment import (
    router as enrichment_router,
)
from veupath_chatbot.transport.http.routers.experiments.evaluation import (
    router as evaluation_router,
)

router = APIRouter()

# Non-parametric routes first (avoid /{experiment_id} shadowing).
router.include_router(comparison_router)
router.include_router(ai_assist_router)

# Parametric routes (/{experiment_id}/...).
router.include_router(cv_router)
router.include_router(enrichment_router)
router.include_router(evaluation_router)
