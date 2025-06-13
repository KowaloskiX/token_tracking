from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import AnalysisCriteria, TenderAnalysis
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.tasks.services.analysis_service import create_tender_analysis_result_v2
from minerva.tasks.services.tender_criteria_analysis_service import perform_criteria_analysis
from minerva.tasks.services.tender_description_generation_service import generate_tender_description
from pydantic import BaseModel
from minerva.core.services.vectorstore.pinecone.query import QueryConfig

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

class ReanalyzeTenderCriteriaRequest(BaseModel):
    existing_result_id: str
    language: Optional[str] = "polish"

class TenderCriteriaAnalysisResponse(BaseModel):
    status: str
    criteria_analysis_id: Optional[str] = None
    tender_pinecone_id: str
    criteria_analysis: Optional[Dict[str, Any]] = None
    vector_search_results: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

class ReanalyzeTenderCriteriaResponse(BaseModel):
    status: str
    criteria_analysis_id: Optional[str] = None
    tender_pinecone_id: str
    criteria_analysis: Optional[Dict[str, Any]] = None
    vector_search_results: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    new_result_id: Optional[str] = None


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


@router.post("/reanalyze-tender-criteria", response_model=ReanalyzeTenderCriteriaResponse)
async def reanalyze_tender_criteria(
    request: ReanalyzeTenderCriteriaRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Reanalyze criteria for an existing tender analysis result.
    Creates a new result with updated criteria analysis while preserving other data.
    """
    try:
        # Fetch existing result
        existing_result = await db.tender_analysis_results.find_one({"_id": ObjectId(request.existing_result_id)})
        if not existing_result:
            raise HTTPException(status_code=404, detail=f"Tender analysis result with ID {request.existing_result_id} not found")
        
        # Get analysis configuration
        analysis_id = str(existing_result.get("tender_analysis_id"))
        tender_analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(analysis_id)})
        if not tender_analysis_doc:
            raise HTTPException(status_code=404, detail="Tender analysis configuration not found")
        
        tender_analysis = TenderAnalysis(**tender_analysis_doc)
        criteria = tender_analysis.criteria
        criteria_definitions = tender_analysis.criteria

        tender_pinecone_id = existing_result.get("tender_pinecone_id", "")
        rag_index_name = existing_result.get("pinecone_config", {}).get("index_name", "")
        embedding_model = existing_result.get("pinecone_config", {}).get("embedding_model", "")
        language = existing_result.get("language", "")


        # Perform criteria analysis
        criteria_result = await perform_criteria_analysis(
            tender_pinecone_id=tender_pinecone_id,
            rag_index_name=rag_index_name,
            embedding_model=embedding_model,
            criteria=criteria,
            criteria_definitions=criteria_definitions,
            extraction_id=None,
            analysis_id=analysis_id,
            current_user=current_user,
            save_results=False,
            include_vector_results=False,
            use_elasticsearch=True,
            language=language
        )

        # Create new result using existing data but with new criteria analysis
        new_result = create_tender_analysis_result_v2(
            original_tender_metadata=existing_result.get("tender_metadata", {}),
            processed_files_data={
                "total_processed": existing_result.get("file_extraction_status", {}).get("files_processed", 0),
                "successful_count": existing_result.get("file_extraction_status", {}).get("files_uploaded", 0),
                "successful_files": existing_result.get("uploaded_files", [])
            },
            criteria_and_location_result=criteria_result['criteria_analysis'],
            analysis_id=analysis_id,
            current_user=current_user,
            tender_url=existing_result.get("tender_url", ""),
            pinecone_config=QueryConfig(
                index_name=rag_index_name,
                namespace="",
                embedding_model=embedding_model
            ),
            criteria_definitions=criteria_definitions,
            tender_pinecone_id=tender_pinecone_id,
            tender_description=existing_result.get("tender_description"),
            language=request.language
        )

        # Save new result to database
        new_result_dict = new_result.dict(by_alias=True)
        new_result_dict["created_at"] = datetime.utcnow()
        new_result_dict["updated_at"] = datetime.utcnow()
        insert_result = await db.tender_analysis_results.insert_one(new_result_dict)
        new_result_id = str(insert_result.inserted_id)

        return {
            "status": "success",
            "criteria_analysis_id": criteria_result.get("criteria_analysis_id"),
            "tender_pinecone_id": tender_pinecone_id,
            "criteria_analysis": criteria_result.get("criteria_analysis"),
            "vector_search_results": criteria_result.get("vector_search_results"),
            "created_at": datetime.utcnow(),
            "new_result_id": new_result_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reanalyzing criteria: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in reanalyzing criteria: {str(e)}"
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