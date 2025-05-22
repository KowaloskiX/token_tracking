from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from minerva.core.models.utils import PyObjectId
from bson import ObjectId

class Comment(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tender_id: PyObjectId  # The tender the comment belongs to.
    user_id: PyObjectId    # The user who made the comment.
    org_id: str            # Organization id to restrict view to org members.
    text: str              # The comment content.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None  # For edited comments.

    # If you want threaded comments in the future, you can add:
    # reply_to: Optional[PyObjectId] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True