from enum import Enum
from minerva.core.models.file import File
from minerva.core.services.vectorstore.pinecone.query import QueryConfig
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Literal, Dict
from datetime import datetime
from minerva.core.models.utils import PyObjectId
from bson import ObjectId

class TenderMetadata(BaseModel):
    name: str
    organization: str
    submission_deadline: str
    procedure_type: Optional[str] = None
    initiation_date: Optional[str] = None


class TenderLocation(BaseModel):
    country: str 
    voivodeship: str
    city: str 


class CriteriaAnalysis(BaseModel):
    summary: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    criteria_met: Optional[bool] = False  # Default to False if nothing is returned
    weight: int = Field(default=3)

class Citation(BaseModel):
    """A citation snippet extracted from tender documentation referencing the source file."""
    text: str
    source: Optional[str] = None  # original filename or other identifier
    keyword: Optional[str] = None  # keyword that triggered this citation
    file_id: Optional[str] = None  # unique file identifier for better matching
    sanitized_filename: Optional[str] = None  # normalized filename for fallback matching

class CriteriaAnalysisResult(BaseModel):
    criteria: str
    analysis: CriteriaAnalysis
    exclude_from_score: Optional[bool] = False
    is_disqualifying: Optional[bool] = False
    citations: Optional[List[Citation]] = None  # Snippets supporting the analysis
    class Config:
        extra = "allow"

class CriteriaAnalysisUpdate(BaseModel):
    # Both fields are optional so that a client may update just one of them.
    summary: Optional[str] = None
    confidence: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = None

class CriteriaAnalysisResultUpdate(BaseModel):
    # The outer model also becomes optional.
    criteria: Optional[str] = None
    analysis: Optional[CriteriaAnalysisUpdate] = None

class FileExtractionStatus(BaseModel):
    user_id: str
    files_processed: int
    files_uploaded: int
    status: str

class ColumnConfiguration(BaseModel):
    column_id: str
    width: int
    visible: bool
    order: int
    criteria_id: Optional[str] = None  # Only for criteria columns

class TableLayout(BaseModel):
    """Table layout configuration per user for this analysis"""
    user_id: str
    columns: List[ColumnConfiguration]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TenderAnalysisResult(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    tender_analysis_id: PyObjectId
    tender_url: str 
    source: Optional[str] = ""
    location: Optional[TenderLocation] = None
    tender_score: Optional[float] = None
    tender_metadata: TenderMetadata
    tender_description: Optional[str] = None 
    file_extraction_status: FileExtractionStatus  
    criteria_analysis: List[CriteriaAnalysisResult]
    criteria_analysis_archive: Optional[List[CriteriaAnalysisResult]]=None
    criteria_analysis_edited: bool = False
    company_match_explanation: str
    assistant_id: Optional[str] = None
    pinecone_config: Optional[QueryConfig] = None
    tender_pinecone_id: Optional[str] = None
    uploaded_files: List[File]
    updates: List[PyObjectId] = []
    status: Literal["inactive", "active", "archived"] = "inactive"
    updated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    opened_at: Optional[datetime] = None
    order_number: Optional[int] = None
    language: Optional[str] = None
    finished_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat(),
            HttpUrl: str
        }
        populate_by_name = True

class AnalysisCriteria(BaseModel):
    name: str
    description: str
    weight: Optional[int] = None
    is_disqualifying: Optional[bool] = None
    exclude_from_score: Optional[bool] = None
    instruction: Optional[str] = None  # New field for optional LLM instruction
    subcriteria: Optional[list[str]] = None
    keywords: Optional[str] = None

class TenderAnalysis(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    org_id: Optional[str] = None
    name: str
    company_description: str
    search_phrase: str
    sources: List[str] = []
    criteria: List[AnalysisCriteria]
    filtering_rules: Optional[str] = None
    last_run: Optional[datetime] = None
    language: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = Field(default=True)
    assigned_users: List[str] = Field(default_factory=list)  # Add this field
    email_recipients: List[str] = Field(default_factory=list)  # NEW: Users who receive email notifications
    
    # NEW: Table layout configurations per user
    table_layouts: Optional[List[TableLayout]] = Field(default_factory=list)
    
    def get_email_recipients(self) -> List[str]:
        """Get users who should receive email notifications.
        
        Returns:
            List[str]: User IDs who should receive emails. 
                      Defaults to assigned_users if email_recipients is empty.
        """
        # Default to all assigned users if email_recipients is empty
        if not self.email_recipients:
            return self.assigned_users
        return self.email_recipients
    
    def get_user_table_layout(self, user_id: str) -> Optional[TableLayout]:
        """Get table layout for a specific user"""
        if not self.table_layouts:
            return None
        return next((layout for layout in self.table_layouts if layout.user_id == user_id), None)
    
    def set_user_table_layout(self, user_id: str, columns: List[ColumnConfiguration]) -> None:
        """Set or update table layout for a specific user"""
        if not self.table_layouts:
            self.table_layouts = []
        
        # Remove existing layout for this user
        self.table_layouts = [layout for layout in self.table_layouts if layout.user_id != user_id]
        
        # Add new layout
        new_layout = TableLayout(
            user_id=user_id,
            columns=columns,
            updated_at=datetime.utcnow()
        )
        self.table_layouts.append(new_layout)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class FileUpdateSummaries(BaseModel):
    filename: str
    summary: str


class TenderAnalysisUpdate(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tender_analysis_result_id: PyObjectId
    updated_files: List[File] = []
    update_date: datetime = Field(default_factory=datetime.utcnow)
    update_link: Optional[str] = None 
    file_summaries: Optional[FileUpdateSummaries] = None
    overall_summary: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True


class TenderProfileMatch(BaseModel):
    id: str
    name: str
    organization: str
    location: Optional[str] = None

class TenderProfileMatches(BaseModel):
    matches: List[TenderProfileMatch]


class TenderDecriptionProfileMatch(BaseModel):
    id: str
    tender_score: Optional[float] = None

class TenderDecriptionProfileMatches(BaseModel):
    matches: List[TenderDecriptionProfileMatch]

class FilterStage(str, Enum):
    AI_INITIAL_FILTER = "ai_initial_filter"
    FILE_EXTRACTION = "file_extraction" 
    AI_DESCRIPTION_FILTER = "ai_description_filter"
    CRITERIA_NOT_MET = 'criteria_not_met'

class FilteredTenderAnalysisResult(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tender_id: str
    tender_name: str
    organization: Optional[str] = None
    location: Optional[str] = None

    analysis_id: str

    # Filtering information
    filter_stage: FilterStage
    filter_reason: Optional[str] = None
    filter_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Original search details
    search_phrase: Optional[str] = None
    source: Optional[str] = None
    original_match: Optional[dict] = None
    tender_description: Optional[str] = None
    details_url: Optional[str] = None
    processed_files: Optional[dict] = None
    extraction_error: Optional[str] = None
    description_filter_score: Optional[float] = None
    user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }



class TenderToAnalyseDescription(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tender_score: Optional[float] = None
    tender_metadata: TenderMetadata
    tender_description: Optional[str] = None 

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat(),
            HttpUrl: str
        }
        populate_by_name = True

class TenderAnalysisResultSummary(BaseModel):
    id: PyObjectId = Field(alias="_id")
    tender_name: Optional[str] = Field(alias="tender_metadata.name", default=None)
    organization: Optional[str] = Field(alias="tender_metadata.organization", default=None)
    tender_description: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ColumnConfigurationRequest(BaseModel):
    column_id: str
    width: int
    visible: bool
    order: int
    criteria_id: Optional[str] = None

class TableLayoutUpdate(BaseModel):
    columns: List[ColumnConfigurationRequest]

class TableLayoutResponse(BaseModel):
    columns: List[ColumnConfiguration]
    total_count: int