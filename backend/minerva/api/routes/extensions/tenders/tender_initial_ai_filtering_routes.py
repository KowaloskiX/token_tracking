import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis
from minerva.core.models.user import User
from minerva.tasks.services.search_service import get_saved_search_results
from minerva.tasks.services.tender_initial_ai_filtering_service import get_saved_initial_ai_filter_results, perform_ai_filtering
from pydantic import BaseModel
from minerva.core.database.database import db
from datetime import datetime


router = APIRouter()
logger = logging.getLogger(__name__)

class TenderFilterRequest(BaseModel):
    analysis_id: Optional[str] = None
    search_id: Optional[str] = None
    tender_matches: Optional[List[Dict[str, Any]]] = None
    combined_search_matches: Optional[Dict[str, Any]] = None
    ai_batch_size: Optional[int] = 20
    save_results: Optional[bool] = False
    tender_ids_to_compare: Optional[List[str]] = None

    company_description: Optional[str] = None
    search_phrase: Optional[str] = None

class ComparisonResult(BaseModel):
    total_extra_filtered: int
    extra_filtered: List[Dict[str, Any]]
    total_covered: int
    covered: List[Dict[str, Any]]
    total_missing: int
    missing_ids: List[str]

class TenderFilterResponse(BaseModel):
    initial_ai_filter_id: Optional[str] = None
    search_id: Optional[str] = None
    total_filtered: int
    total_filtered_out: int
    filtered_tenders: Optional[List[Any]] = None
    comparison: Optional[ComparisonResult] = None

@router.post("/test-tender-filter", response_model=TenderFilterResponse)
async def filter_tenders(
    request: TenderFilterRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Filter tenders using AI based on relevance.
    Optionally compares the results against a provided list of tender IDs.
    """
    try:
        # Variable to store the tender analysis
        tender_analysis = None
        
        # Check which mode we're operating in - existing analysis or direct creation
        if request.analysis_id:
            # Get tender analysis configuration from database
            tender_analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(request.analysis_id)})
            if not tender_analysis_doc:
                raise HTTPException(status_code=404, detail="Tender analysis configuration not found")
            tender_analysis = TenderAnalysis(**tender_analysis_doc)
        elif request.company_description and request.search_phrase:
            # Create a temporary analysis object
            tender_analysis = TenderAnalysis(
                user_id=current_user.id,
                org_id=None,
                name="Temporary Analysis",
                company_description=request.company_description,
                search_phrase=request.search_phrase,
                sources=[],
                # Use provided criteria or create an empty list
                criteria=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                active=True
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail="Either analysis_id or both company_description and search_phrase must be provided"
            )
        
        # Get search results - either from saved search or from request
        if request.search_id:
            search_results = await get_saved_search_results(request.search_id)
            if not search_results:
                raise HTTPException(status_code=404, detail=f"Search results with ID {request.search_id} not found")
                
            all_tender_matches = search_results["all_tender_matches"]
            combined_search_matches = search_results["combined_search_matches"]
        else:
            if not request.tender_matches or not request.combined_search_matches:
                raise HTTPException(
                    status_code=400, 
                    detail="Either search_id or tender_matches with combined_search_matches must be provided"
                )
                
            all_tender_matches = request.tender_matches
            combined_search_matches = request.combined_search_matches
        
        # Perform AI filtering
        filter_results = await perform_ai_filtering(
            tender_analysis=tender_analysis,
            all_tender_matches=all_tender_matches,
            combined_search_matches=combined_search_matches,
            analysis_id="" if not request.analysis_id else request.analysis_id,
            current_user=current_user,
            ai_batch_size=request.ai_batch_size,
            search_id=request.search_id,
            save_results=request.save_results
        )
        
        # Prepare base response data
        ai_filtered_tenders = filter_results.get("filtered_tenders", [])
        filtered_out_tenders = filter_results.get("filtered_out_tenders", [])

        response_data = {
            "initial_ai_filter_id": filter_results.get('initial_ai_filter_id'),
            "search_id": request.search_id,
            "total_filtered": len(ai_filtered_tenders),
            "total_filtered_out": len(filtered_out_tenders),
            "filtered_tenders": ai_filtered_tenders,
            "comparison": None
        }

        # Comparison Logic
        if request.tender_ids_to_compare is not None:
            try:
                # Correctly access the 'id' attribute of the TenderProfileMatch objects
                ai_filtered_ids = {str(tender.id) for tender in ai_filtered_tenders if tender.id}

                comparison_ids_set = set(request.tender_ids_to_compare)

                extra_filtered_ids = ai_filtered_ids - comparison_ids_set
                covered_ids = ai_filtered_ids.intersection(comparison_ids_set)
                missing_ids = comparison_ids_set - ai_filtered_ids

                # Correctly access the 'id' attribute for filtering
                extra_filtered_tenders = [t for t in ai_filtered_tenders if str(t.id) in extra_filtered_ids]
                covered_tenders = [t for t in ai_filtered_tenders if str(t.id) in covered_ids]

                # Convert model instances to dictionaries for JSON serializable response
                def to_dict(item):
                    if hasattr(item, "model_dump"):
                        return item.model_dump()
                    if hasattr(item, "dict"):
                        return item.dict()
                    if isinstance(item, dict):
                        return item
                    # Fallback: build basic dict using attributes
                    return {
                        "id": getattr(item, "id", None),
                        "name": getattr(item, "name", None),
                        "organization": getattr(item, "organization", None),
                        "location": getattr(item, "location", None),
                        "relevancy_score": getattr(item, "relevancy_score", None),
                    }

                extra_filtered_dicts = [to_dict(t) for t in extra_filtered_tenders]
                covered_dicts = [to_dict(t) for t in covered_tenders]

                comparison_data = ComparisonResult(
                    total_extra_filtered=len(extra_filtered_dicts),
                    extra_filtered=extra_filtered_dicts,
                    total_covered=len(covered_dicts),
                    covered=covered_dicts,
                    total_missing=len(missing_ids),
                    missing_ids=sorted(list(missing_ids))
                )
                response_data["comparison"] = comparison_data

            except Exception as comp_err:
                 logger.error(f"Error during tender comparison: {str(comp_err)}", exc_info=True)
                 response_data["comparison"] = None
                 response_data["filtered_tenders"] = ai_filtered_tenders

        return TenderFilterResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in tender filtering: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in tender filtering: {str(e)}"
        )

class InitialAIFilterResponse(BaseModel):
    """Detailed response model for initial AI filter results"""
    initial_ai_filter_id: str
    search_id: Optional[str] = None
    query: str
    total_filtered: int
    total_filtered_out: int
    filtered_tenders: List[Dict[str, Any]]
    filtered_out_tenders: Optional[List[Dict[str, Any]]] = None
    
@router.get("/tender-filter/{initial_ai_filter_id}")
async def get_initial_ai_filter(
    initial_ai_filter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve previously saved initial AI filter results.
    """
    try:
        filter_results = await get_saved_initial_ai_filter_results(initial_ai_filter_id)
        
        if not filter_results:
            raise HTTPException(
                status_code=404,
                detail=f"Initial AI filter results with ID {initial_ai_filter_id} not found"
            )
    
        return   {
            "initial_ai_filter_id": str(filter_results["initial_ai_filter_id"]),
            "search_id": filter_results.get("search_id"),
            "analysis_id": filter_results.get("analysis_id"),
            "created_at": filter_results.get("created_at"),
            "filtered_tenders_count": filter_results.get("filtered_tenders_count", 0),
            "filtered_out_count": filter_results.get("filtered_out_count", 0),
            "filtered_tenders_ids": filter_results.get("filtered_tenders_ids", []),
            "filtered_out_ids": filter_results.get("filtered_out_ids", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving initial AI filter results: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving initial AI filter results: {str(e)}"
        )