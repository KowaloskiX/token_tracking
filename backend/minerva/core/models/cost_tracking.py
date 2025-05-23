from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from minerva.core.models.utils import PyObjectId

class LLMModelPricing(BaseModel):
    """Pricing information for LLM models (per 1M tokens)"""
    model_name: str
    input_cost_per_million: float  # Cost per 1M input tokens
    output_cost_per_million: float  # Cost per 1M output tokens
    
class OperationCost(BaseModel):
    """Cost breakdown for a specific operation"""
    operation_type: str  # e.g., "criteria_analysis", "ai_filtering", "description_generation"
    operation_id: Optional[str] = None  # Specific ID if applicable
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = None  # Additional context

class TenderAnalysisCost(BaseModel):
    """Comprehensive cost tracking for a tender analysis"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    tender_analysis_id: PyObjectId
    tender_id: str  # The specific tender being analyzed
    analysis_session_id: str  # Unique ID for this analysis session
    
    # Operation costs breakdown
    search_costs: List[OperationCost] = []
    ai_filtering_costs: List[OperationCost] = []
    file_extraction_costs: List[OperationCost] = []
    criteria_analysis_costs: List[OperationCost] = []
    description_generation_costs: List[OperationCost] = []
    description_filtering_costs: List[OperationCost] = []
    
    # Summary totals
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Status
    status: str = "in_progress"  # in_progress, completed, failed
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class UserCostSummary(BaseModel):
    """Summary of costs for a user over a time period"""
    user_id: PyObjectId
    period_start: datetime
    period_end: datetime
    
    # Cost breakdown by operation type
    search_cost: float = 0.0
    ai_filtering_cost: float = 0.0
    file_extraction_cost: float = 0.0
    criteria_analysis_cost: float = 0.0
    description_generation_cost: float = 0.0
    description_filtering_cost: float = 0.0
    
    # Totals
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_analyses: int = 0
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }