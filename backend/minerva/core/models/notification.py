from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from minerva.core.models.utils import PyObjectId
from bson import ObjectId

class Notification(BaseModel):
    """Notification model representing a user's notification in the system."""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    org_id: Optional[str] = None
    title: str
    content: str
    type: str = "info"  # info, warning, success, error, update, outcome
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Configuration for the Notification model."""
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda dt: dt.isoformat()}
        populate_by_name = True