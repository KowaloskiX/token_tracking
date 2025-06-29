from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
from datetime import datetime

class ObservabilityHistoryItem(BaseModel):
    """
    A single observability history record as stored in MongoDB.
    """
    id: str = Field(..., description="Search or filter operation identifier")
    timestamp: datetime = Field(..., description="When the operation ran")
    endpoint: Literal["search", "filter"] = Field(..., description="Type of operation")
    status: Literal["success", "warning", "error"] = Field(..., description="Outcome status")
    params: Dict[str, Any] = Field(..., description="Original request parameters")
    results: Optional[Dict[str, Any]] = Field(None, description="Full results object")
    user_id: str = Field(..., description="ID of the user who ran this operation")