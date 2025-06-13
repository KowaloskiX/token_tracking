from fastapi import APIRouter
from . import results_routes

router = APIRouter()
router.include_router(results_routes.router, prefix="/results", tags=["api-results"])