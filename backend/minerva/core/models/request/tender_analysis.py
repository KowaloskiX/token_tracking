from typing import List, Optional
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult, AnalysisCriteria
from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel

class TenderSearchRequest(BaseModel):
    analysis_id: PyObjectId
    top_k: int = 15
    score_threshold: float = 0.1

class TenderSearchResponse(BaseModel):
    query: str
    total_tenders_analyzed: int
    analysis_results: List[TenderAnalysisResult]
    initial_ai_filter_id: Optional[str] = None
    description_filter_id: Optional[str] = None
    analysis_stats: Optional[dict] = None


class BatchAnalysisResult(BaseModel):
    analysis_id: str
    total_tenders_analyzed: int
    query: str
    analysis_results: List[TenderAnalysisResult]
    initial_ai_filter_id: Optional[str] = None
    description_filter_id: Optional[str] = None

class TenderAnalysisResponse(BaseModel):
    total_analyses: int = 0
    successful_analyses: int = 0
    failed_analyses: int = 0
    analysis_results: List[BatchAnalysisResult] = []


class TenderAnalysisCreate(BaseModel):
    name: str
    company_description: str
    search_phrase: str
    sources: List[str] = []
    criteria: List[AnalysisCriteria]
    filtering_rules: Optional[str] = None

class TenderAnalysisUpdate(BaseModel):
    name: Optional[str] = None
    company_description: Optional[str] = None
    search_phrase: Optional[str] = None
    sources: List[str] = None
    criteria: Optional[List[AnalysisCriteria]] = None
    filtering_rules: Optional[str] = None
    org_id: Optional[str] = None
    assigned_users: Optional[List[str]] = None
    email_recipients: Optional[List[str]] = None

class TenderAnalysisResultUpdate(BaseModel):
    tender_url: Optional[str] = None
    source: Optional[str] = None
    tender_score: Optional[float] = None
    tender_metadata: Optional[dict] = None
    file_extraction_status: Optional[dict] = None
    criteria_analysis: Optional[List[dict]] = None
    company_match_explanation: Optional[str] = None
    assistant_id: Optional[str] = None
    uploaded_files: Optional[List[dict]] = None

class UserAnalysisTestRequest(BaseModel):
    top_k: int = 20
    score_threshold: float = 0.1
    target_date: Optional[str] = None
    specific_analysis_id: Optional[str] = None

class IncreaseRelevancyScoreRequest(BaseModel):
    analysis_id: str
    score_increase: float