from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from minerva.config.constants import UserRole
from datetime import datetime
from bson import ObjectId
from minerva.core.models.utils import PyObjectId  # Adjust import if needed

class Invitation(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr
    org_id: str
    invited_by: PyObjectId
    token: str
    role: UserRole = UserRole.MEMBER
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    accepted: bool = False

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True