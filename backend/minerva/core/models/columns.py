from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from minerva.core.models.utils import PyObjectId
from bson import ObjectId

class ColumnConfiguration(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    analysis_id: PyObjectId
    column_id: str
    column_type: str
    column_key: str
    label: str
    width: int
    visible: bool
    order: int
    criteria_id: Optional[str] = None  # For criteria columns
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class ColumnConfigurationRequest(BaseModel):
    column_id: str
    column_type: str
    column_key: str
    label: str
    width: int
    visible: bool
    order: int
    criteria_id: Optional[str] = None

class ColumnConfigurationUpdate(BaseModel):
    columns: List[ColumnConfigurationRequest]

class ColumnConfigurationResponse(BaseModel):
    columns: List[ColumnConfiguration]
    total_count: int