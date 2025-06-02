from fastapi import APIRouter
from . import results

router = APIRouter()
router.include_router(results.router, prefix="/results", tags=["api-results"])