"""Site sub-routers (catalog, params, genes)."""

from fastapi import APIRouter

from veupath_chatbot.transport.http.routers.sites import catalog, genes, params

router = APIRouter()
router.include_router(catalog.router)
router.include_router(params.router)
router.include_router(genes.router)
