import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Union
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis, TenderAnalysisResult, TenderToAnalyseDescription
from minerva.core.models.user import User
from minerva.tasks.services.analyze_tender_files import RAGManager
from minerva.core.database.database import db
from bson.objectid import ObjectId


logger = logging.getLogger("minerva.tasks.analysis_tasks")

async def perform_description_filtering(
    tender_analysis: TenderAnalysis,
    tender_results: List[Union[TenderAnalysisResult, TenderToAnalyseDescription]],
    analysis_id: str,
    current_user: Optional[User] = None,
    ai_batch_size: int = 20,
    save_results: bool = False
) -> Dict[str, Any]:
    """
    Filter tenders based on their descriptions.
    
    Args:
        tender_analysis: TenderAnalysis configuration
        tender_results: List of tender results with descriptions
        analysis_id: Analysis ID
        current_user: Optional user making the request
        ai_batch_size: Batch size for AI processing
        save_results: Whether to save filter results
        
    Returns:
        Dictionary containing filtered tenders based on descriptions
    """
    try:
        logger.info(f"Starting description-based filtering for {len(tender_results)} tenders")
        
        if not tender_results:
            logger.info("No tenders to filter by description")
            return {
                "status": "no_tenders",
                "filtered_tenders": [],
                "filtered_out_tenders": []
            }
        
        async def filter_descriptions_batch(batch):
            try:
                filtered_batch = await RAGManager.ai_filter_tenders_based_on_description(
                    tender_analysis, batch, current_user
                )
                return filtered_batch.matches if filtered_batch and filtered_batch.matches else []
            except Exception as e:
                logger.error(f"Error in description filtering batch: {str(e)}")
                return []
        
        all_filtered_description_matches = []
        if len(tender_results) > ai_batch_size:
            batches = [tender_results[i:i + ai_batch_size]
                      for i in range(0, len(tender_results), ai_batch_size)]
                      
            logger.info(f"Splitting {len(tender_results)} tenders into {len(batches)} batches for description filtering")
            
            filtered_batches = await asyncio.gather(
                *(filter_descriptions_batch(batch) for batch in batches)
            )
            
            for batch_results in filtered_batches:
                all_filtered_description_matches.extend(batch_results)
        else:
            filtered_results = await RAGManager.ai_filter_tenders_based_on_description(
                tender_analysis, tender_results, current_user
            )
            all_filtered_description_matches = filtered_results.matches if filtered_results else []
            
        logger.info(f"Description filtering resulted in {len(all_filtered_description_matches)} tenders")
        
        # Identify filtered-out tenders using only the IDs returned by the AI filter.
        # We avoid relying on any optional attributes (e.g. tender_score) that may be
        # absent in the TenderDecriptionProfileMatch objects.
        matched_ids = {item.id for item in all_filtered_description_matches}

        filtered_tenders = []
        filtered_out_tenders = []

        for result in tender_results:
            result_id = str(result.id) if hasattr(result, "id") else result.get("id", "")
            if result_id in matched_ids:
                filtered_tenders.append(result)
            else:
                filtered_out_tenders.append(result)
        
        result = {
            "status": "success",
            "filtered_tenders": filtered_tenders,
            "filtered_out_tenders": filtered_out_tenders,
            "total_filtered": len(filtered_tenders),
            "total_filtered_out": len(filtered_out_tenders)
        }
        
        # Save results if requested
        if save_results:
            description_filter_doc = {
                "analysis_id": analysis_id,
                "created_at": datetime.utcnow(),
                "user_id": str(current_user.id) if current_user else None,
                "filtered_tenders": [tender.model_dump() for tender in filtered_tenders],
                "filtered_out_tenders": [tender.model_dump() for tender in filtered_out_tenders],
                "total_filtered": len(filtered_tenders),
                "total_filtered_out": len(filtered_out_tenders)
            }

            print(description_filter_doc)
            
            db_result = await db.tender_description_filter_results.insert_one(description_filter_doc)
            result["description_filter_id"] = str(db_result.inserted_id)
            logger.info(f"Saved description filter results with ID: {result['description_filter_id']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error during description-based filtering: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "reason": f"Description filtering error: {str(e)}"
        }

async def get_saved_description_filter_results(
    description_filter_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve previously saved description filter results from the database.
    
    Args:
        description_filter_id: ID of the saved description filter results
        
    Returns:
        Dictionary containing filter results or None if not found
    """
    
    filter_doc = await db.tender_description_filter_results.find_one({"_id": ObjectId(description_filter_id)})
    
    if not filter_doc:
        return None
    
    # Get basic filter information
    result = {
        "description_filter_id": str(filter_doc["_id"]),
        "analysis_id": filter_doc.get("analysis_id"),
        "created_at": filter_doc.get("created_at"),
        "total_filtered": filter_doc.get("total_filtered", 0),
        "total_filtered_out": filter_doc.get("total_filtered_out", 0),
        # You might want to return more fields if needed, like the IDs of filtered/filtered_out tenders
    }

    return result