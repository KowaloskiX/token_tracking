# CURRENTLY NOT USED!!!
# CURRENTLY NOT USED!!!
# CURRENTLY NOT USED!!!

from fastapi import APIRouter, Depends, status, HTTPException
from typing import List
from datetime import datetime

from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.core.models.observability_history import ObservabilityHistoryItem
from minerva.core.database.database import db

router = APIRouter(
    prefix="/observability",
    tags=["observability"]
)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_history_item(
    item: ObservabilityHistoryItem,
    current_user: User = Depends(get_current_user)
):
    # attach user_id
    doc = item.dict()
    doc["user_id"] = str(current_user.id)

    # persist
    try:
        await db.observability_history.insert_one(doc)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save observability history"
        ) from e

    return {"ok": True}

@router.get("/", response_model=List[ObservabilityHistoryItem])
async def list_history(
    current_user: User = Depends(get_current_user)
):
    try:
        docs = await db.observability_history \
            .find({"user_id": str(current_user.id)}) \
            .sort("timestamp", -1) \
            .to_list(50)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load observability history"
        ) from e

    return docs