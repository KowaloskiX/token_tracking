from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId
from datetime import datetime


class Folder(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str
    assistant_id: str  # Add assistant_id field
    shared_with: Optional[List[dict]] = []
    parent_folder_id: Optional[str] = None
    files: List[str] = []  # List of file IDs
    subfolders: List[str] = []  # List of subfolder IDs
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True