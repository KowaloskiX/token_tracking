from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import AnalysisCriteria, TenderAnalysis
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.tasks.services.tender_criteria_analysis_service import perform_criteria_analysis
from minerva.tasks.services.tender_description_generation_service import generate_tender_description
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

class TenderCriteriaAnalysisRequest(BaseModel):
    tender_pinecone_id: str
    rag_index_name: str
    embedding_model: str
    analysis_id: Optional[str] = None
    extraction_id: Optional[str] = None
    criteria: Optional[List[AnalysisCriteria]] = None
    criteria_definitions: Optional[List[AnalysisCriteria]] = None
    save_results: Optional[bool] = False
    use_elasticsearch: Optional[bool] = False
    include_vector_results: Optional[bool] = False
    language: Optional[str] = "polish"

class TenderCriteriaAnalysisResponse(BaseModel):
    status: str
    criteria_analysis_id: Optional[str] = None
    tender_pinecone_id: str
    criteria_analysis: Optional[Dict[str, Any]] = None
    vector_search_results: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


@router.post("/tender-criteria-analysis", response_model=TenderCriteriaAnalysisResponse)
async def analyze_tender_criteria(
    request: TenderCriteriaAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Analyze tender against specified criteria.
    """
    try:
        if request.analysis_id:
            tender_analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(request.analysis_id)})
            if not tender_analysis_doc:
                raise HTTPException(status_code=404, detail="Tender analysis configuration not found")
                
            tender_analysis = TenderAnalysis(**tender_analysis_doc)
            criteria = tender_analysis.criteria
            criteria_definitions = tender_analysis.criteria
        elif request.criteria:
            criteria = request.criteria
            criteria_definitions = request.criteria_definitions if request.criteria_definitions else criteria
        else:
            raise HTTPException(status_code=400, detail="Either analysis_id or criteria must be provided")
        
        # Perform criteria analysis
        criteria_result = await perform_criteria_analysis(
            tender_pinecone_id=request.tender_pinecone_id,
            rag_index_name=request.rag_index_name,
            embedding_model=request.embedding_model,
            criteria=criteria,
            criteria_definitions=criteria_definitions,
            extraction_id=request.extraction_id,
            analysis_id=request.analysis_id,
            current_user=current_user,
            save_results=request.save_results,
            include_vector_results=request.include_vector_results,
            use_elasticsearch=request.use_elasticsearch,
            language=request.language
        )
        
        return criteria_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in criteria analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in criteria analysis: {str(e)}"
        )


@router.get("/tender-criteria-analysis/{criteria_analysis_id}", response_model=TenderCriteriaAnalysisResponse)
async def get_criteria_analysis_results(
    criteria_analysis_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        criteria_doc = await db.tender_criteria_analysis_results.find_one({"_id": ObjectId(criteria_analysis_id)})
        if not criteria_doc:
            raise HTTPException(status_code=404, detail=f"Criteria analysis results with ID {criteria_analysis_id} not found")
            
        return {
            "status": criteria_doc.get("status", "success"),
            "criteria_analysis_id": criteria_analysis_id,
            "tender_pinecone_id": criteria_doc.get("tender_pinecone_id"),
            "criteria_analysis": criteria_doc.get("criteria_analysis"),
            "vector_search_results": criteria_doc.get("vector_search_results"),
            "created_at": criteria_doc.get("created_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving criteria analysis results: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving criteria analysis results: {str(e)}"
        )