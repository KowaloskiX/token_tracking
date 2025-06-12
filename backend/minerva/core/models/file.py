from minerva.core.models.utils import PyObjectId
from minerva.core.services.vectorstore.pinecone.query import QueryConfig
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

class FilePineconeConfig(BaseModel):
    query_config: QueryConfig
    pinecone_unique_id_prefix: str
    elasticsearch_indexed: Optional[bool] = None

class File(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    filename: str
    openai_file_id: Optional[str] = None
    type: str  #file, website etc
    url: Optional[str] = None
    bytes: Optional[int] = None
    blob_url: Optional[str] = None
    file_pinecone_config: Optional[FilePineconeConfig] = None
    owner_id: str
    shared_with: Optional[List[dict]] = []
    parent_folder_id: Optional[str] = None
    preview_chars: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    user_file: Optional[bool] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True