"""Strategies router (composed by responsibility).

This package keeps `router` as the public import used by `veupath_chatbot.main`.
Individual endpoints live in smaller modules.
"""

from fastapi import APIRouter

from . import counts, crud, plan, wdk_import

router = APIRouter()
router.include_router(crud.router)
router.include_router(counts.router)
router.include_router(plan.router)
router.include_router(wdk_import.router)

