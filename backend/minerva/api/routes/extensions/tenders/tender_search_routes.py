import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.core.database.database import db
from bson import ObjectId
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis
from minerva.tasks.services.search_service import compare_tender_search_results, get_saved_search_results, perform_tender_search
from minerva.tasks.services.tender_initial_ai_filtering_service import perform_ai_filtering
from pydantic import BaseModel
from datetime import datetime


router = APIRouter()
logger = logging.getLogger(__name__)

class TenderSearchRequest(BaseModel):
    search_phrase: Optional[str] = None
    tender_names_index_name: Optional[str] = "tenders"
    elasticsearch_index_name: Optional[str] = "tenders"
    embedding_model: Optional[str] = "text-embedding-3-large"
    score_threshold: Optional[float] = 0.5
    top_k: Optional[int] = 30
    sources: Optional[List[str]] = None
    filter_conditions: Optional[List[Dict[str, Any]]] = None
    analysis_id: Optional[str] = None
    save_results: Optional[bool] = False
    search_id: Optional[str] = None
    tender_ids_to_compare: Optional[List[str]] = None

class TenderSearchResponse(BaseModel):
    query: str
    total_matches: int
    search_id: Optional[str] = None
    matches: List[Dict[str, Any]]
    detailed_results: Optional[Dict[str, Dict[str, List[Dict]]]] = None
    comparison_results: Optional['CompareSearchResponse'] = None

class CompareSearchRequest(BaseModel):
    tender_ids: List[str]

class CompareSearchResponse(BaseModel):
    found_in_search: List[str]
    missing_from_index: List[str]
    not_found_by_search: List[str]

# Forward reference resolution for comparison_results
TenderSearchResponse.model_rebuild()

@router.post("/test-tender-search", response_model=TenderSearchResponse)
async def search_tenders(
    request: TenderSearchRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        search_phrase_to_use = request.search_phrase
        analysis_id_to_use = request.analysis_id
        sources_to_use = request.sources

        if not search_phrase_to_use:
            if not analysis_id_to_use:
                raise HTTPException(
                    status_code=400,
                    detail="Either search_phrase or analysis_id must be provided."
                )
            try:
                analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(analysis_id_to_use)})
                if not analysis_doc:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Tender analysis with ID {analysis_id_to_use} not found."
                    )
                tender_analysis = TenderAnalysis(**analysis_doc)
                search_phrase_to_use = tender_analysis.search_phrase
                sources_to_use = tender_analysis.sources
                if not search_phrase_to_use:
                     raise HTTPException(
                        status_code=404,
                        detail=f"Search phrase not found in tender analysis with ID {analysis_id_to_use}."
                    )
            except Exception as db_err:
                logger.error(f"Error fetching tender analysis {analysis_id_to_use}: {db_err}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error retrieving tender analysis data.")

        compare_mode = request.tender_ids_to_compare is not None and len(request.tender_ids_to_compare) > 0

        # If we plan to compare, ensure results are saved by forcing save_results True
        save_results_flag = request.save_results or compare_mode

        # If compare_mode and analysis_id missing, raise error (needed to save results)
        if compare_mode and not analysis_id_to_use:
            raise HTTPException(
                status_code=400,
                detail="analysis_id is required when tender_ids_to_compare are provided."
            )

        search_results = await perform_tender_search(
            search_phrase=search_phrase_to_use,
            tender_names_index_name=request.tender_names_index_name,
            elasticsearch_index_name=request.elasticsearch_index_name,
            embedding_model=request.embedding_model,
            score_threshold=request.score_threshold,
            top_k=request.top_k,
            sources=sources_to_use,
            filter_conditions=request.filter_conditions,
            analysis_id=analysis_id_to_use,
            current_user_id=str(current_user.id),
            save_results=save_results_flag
        )
        
        response_payload = {
            "search_id": search_results.get("search_id"),
            "query": search_phrase_to_use,
            "total_matches": len(search_results["all_tender_matches"]),
            "matches": search_results["all_tender_matches"],
            "detailed_results": search_results.get("detailed_results", {})
        }

        # If compare_mode, perform comparison and add to response
        if compare_mode:
            search_id_for_compare = search_results.get("search_id")
            if not search_id_for_compare:
                # Should not happen because we forced save_results True and provided analysis_id
                raise HTTPException(status_code=500, detail="Failed to save search results for comparison.")

            comparison_result = await compare_tender_search_results(
                search_id=search_id_for_compare,
                tender_ids_to_compare=request.tender_ids_to_compare
            )

            response_payload["comparison_results"] = comparison_result

        return response_payload
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in tender search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in tender search: {str(e)}"
        )


@router.get("/tender-search/{search_id}", response_model=TenderSearchResponse)
async def get_saved_tender_search(
    search_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve previously saved search results.
    """
    try:
        search_results = await get_saved_search_results(search_id)
        
        if not search_results:
            raise HTTPException(
                status_code=404,
                detail=f"Search results with ID {search_id} not found"
            )
        
        return {
            "search_id": search_id,
            "query": search_results["search_phrase"],
            "total_matches": len(search_results["all_tender_matches"]),
            "matches": search_results["all_tender_matches"],
            "detailed_results": search_results.get("detailed_results", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving saved search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving saved search: {str(e)}"
        )

@router.post("/tender-search/{search_id}/compare", response_model=CompareSearchResponse)
async def compare_search(
    search_id: str,
    request: CompareSearchRequest
):
    """
    Compare a list of tender IDs against a saved search result and its source indices.
    """
    try:
        comparison_result = await compare_tender_search_results(
            search_id=search_id,
            tender_ids_to_compare=request.tender_ids
        )
        return comparison_result
    except ValueError as e:
        logger.warning(f"Comparison error for search {search_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except EnvironmentError as e:
         logger.error(f"Environment error during comparison for search {search_id}: {str(e)}")
         raise HTTPException(status_code=500, detail="Configuration error preventing comparison.")
    except Exception as e:
        logger.error(f"Error comparing search results for {search_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error comparing search results: {str(e)}"
        )

class TestSearchRequest(BaseModel):
    search_ids: List[str]
    iterations: int = 3
    analysis_id: str

class TestSearchResult(BaseModel):
    search_id: str
    average_total_matches: float
    average_total_filtered: float
    average_total_filtered_out: float

@router.post("/test-multiple-searches")
async def test_multiple_searches(
    request: TestSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test endpoint that runs multiple searches and AI filtering multiple times and calculates averages.
    """
    results = {}
    
    # Get tender analysis configuration from database
    tender_analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(request.analysis_id)})
    if not tender_analysis_doc:
        raise HTTPException(status_code=404, detail="Tender analysis configuration not found")
    tender_analysis = TenderAnalysis(**tender_analysis_doc)
    
    for search_id in request.search_ids:
        total_matches_sum = 0
        total_filtered_sum = 0
        total_filtered_out_sum = 0
        
        for _ in range(request.iterations):
            try:
                # Get search results
                search_results = await get_saved_search_results(search_id)
                if not search_results:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Search results with ID {search_id} not found"
                    )
                
                # Perform AI filtering
                filter_results = await perform_ai_filtering(
                    tender_analysis=tender_analysis,
                    all_tender_matches=search_results["all_tender_matches"],
                    combined_search_matches=search_results.get("combined_search_matches", {}),
                    analysis_id=request.analysis_id,
                    current_user=current_user,
                    ai_batch_size=20,
                    search_id=search_id,
                    save_results=False
                )
                
                total_matches_sum += len(search_results["all_tender_matches"])
                total_filtered_sum += len(filter_results.get("filtered_tenders", []))
                total_filtered_out_sum += len(filter_results.get("filtered_out_tenders", []))
            
            except Exception as e:
                logger.error(f"Error in iteration for search {search_id}: {str(e)}", exc_info=True)
                continue
        
        # Calculate averages
        results[search_id] = {
            "search_id": search_id,
            "average_total_matches": total_matches_sum / request.iterations,
            "average_total_filtered": total_filtered_sum / request.iterations,
            "average_total_filtered_out": total_filtered_out_sum / request.iterations
        }
    
    return results