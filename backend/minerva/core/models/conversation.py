from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

class Citation(BaseModel):
    content: str
    filename: str
    file_id: Optional[str] = None  # Add file_id field

class Message(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    role: str
    content: str
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    citations: Optional[list[Citation]] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class Conversation(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    assistant_id: str
    user_id: str
    messages: List[Message]
    org_id: Optional[str] = None
    thread_id: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    title: str = Field(default="New conversation")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        populate_by_name = True
        
    def __init__(self, **data):
        if 'last_updated' not in data:
            data['last_updated'] = datetime.utcnow()
        if 'title' not in data:
            data['title'] = "New conversation"
        super().__init__(**data)