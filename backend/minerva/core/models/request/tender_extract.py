from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class Tender(BaseModel):
    name: str
    submission_deadline: str
    organization: str
    location: str
    details_url: str
    initiation_date: str
    content_type: str = "tender"
    source_type: str = "ezamowienia"

class ExtractorMetadata(BaseModel):
    total_tenders: int
    pages_scraped: int

class ExtractionRequest(BaseModel):
    max_pages: Optional[int] = 50
    start_date: Optional[str] = None
    
class ExtractionResponse(BaseModel):
    tenders: List[Tender]
    metadata: ExtractorMetadata