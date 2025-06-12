# models/assistant.py
from minerva.core.models.utils import PyObjectId
from minerva.core.services.vectorstore.pinecone.query import QueryConfig
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from bson import ObjectId
from datetime import datetime

class Tool(BaseModel):
    type: str
    config: Optional[Dict] = None

class Assistant(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    description: Optional[str]
    system_prompt: Optional[str]
    icon: Optional[str]
    owner_id: str 
    org_id: Optional[str] = None
    shared_with: Optional[List[dict]] = []
    openai_assistant_id: Optional[str]
    openai_vectorstore_id: Optional[str]
    tender_pinecone_id: Optional[str] = None
    uploaded_files_pinecone_id: Optional[str] = None
    pinecone_config: Optional[QueryConfig] = None
    tools: List[Tool] = []
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True