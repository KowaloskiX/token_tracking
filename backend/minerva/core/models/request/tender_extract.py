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

class HistoricalTender(BaseModel):
    """Extended tender model for historical/completed tenders"""
    name: str
    organization: str
    location: str
    announcement_date: str
    details_url: str
    content_type: str = "historical_tender"
    source_type: str = "ezamowienia_historical"
    
    completion_status: Optional[str] = None
    total_offers: Optional[int] = None
    sme_offers: Optional[int] = None
    lowest_price: Optional[str] = None
    highest_price: Optional[str] = None
    winning_price: Optional[str] = None
    winner_name: Optional[str] = None
    winner_location: Optional[str] = None
    winner_size: Optional[str] = None
    contract_date: Optional[str] = None
    contract_value: Optional[str] = None
    realization_period: Optional[str] = None
    full_content: Optional[str] = None

class HistoricalExtractionRequest(BaseModel):
    start_date: str
    end_date: str
    max_pages: Optional[int] = 10

class HistoricalExtractionResponse(BaseModel):
    tenders: List[HistoricalTender]
    metadata: ExtractorMetadata