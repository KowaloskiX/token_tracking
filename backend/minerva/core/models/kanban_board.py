from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId


class KanbanBoardTenderItemModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default_factory=PyObjectId)
    board_id: PyObjectId
    column_id: PyObjectId
    tender_analysis_result_id: PyObjectId
    order: int
    created_at: Optional[datetime] = datetime.now()
    updated_at: Optional[datetime] = datetime.now()

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class KanbanColumnModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default_factory=PyObjectId)
    name: str
    order: Optional[int] = None
    color: Optional[str] = None
    limit: Optional[int] = None
    tender_items: List[KanbanBoardTenderItemModel] = []
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class KanbanBoardModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default_factory=PyObjectId)
    user_id: str
    org_id: Optional[str] = None  # <-- new field for organization ID
    name: str
    shared_with: List[str] = []  # List of user IDs who have access to this board
    created_at: Optional[datetime] = datetime.now()
    updated_at: Optional[datetime] = datetime.now()
    columns: List[KanbanColumnModel] = []
    assigned_users: List[str] = Field(default_factory=list)  # Add this field
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class KanbanBoardModelUpdate(BaseModel):
    user_id: Optional[str] = None
    org_id: Optional[str] = None  # <-- new field for updating org_id if needed
    name: Optional[str] = None
    shared_with: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    columns: Optional[List[KanbanColumnModel]] = None
    assigned_users: Optional[List[str]] = None

class KanbanColumnModelUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None
    color: Optional[str] = None
    limit: Optional[int] = None
    tender_items: Optional[List[KanbanBoardTenderItemModel]] = None

class KanbanBoardTenderItemModelUpdate(BaseModel):
    board_id: Optional[PyObjectId] = None
    column_id: Optional[PyObjectId] = None
    tender_analysis_result_id: Optional[PyObjectId] = None
    order: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class MoveTenderRequest(BaseModel):
    source_column_id: PyObjectId
    target_column_id: PyObjectId