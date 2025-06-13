import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from minerva.core.models.extensions.tenders.tender_analysis import FilterStage, FilteredTenderAnalysisResult, TenderAnalysis
from minerva.core.models.user import User
from minerva.tasks.services.analyze_tender_files import RAGManager
from minerva.core.database.database import db
import psutil
import os


logger = logging.getLogger("minerva.tasks.analysis_tasks")

# Memory logging helper
def log_mem(tag: str = ""):
    try:
        process_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        logger.info(f"[{tag}] Memory usage: {process_mem:.1f} MB")
    except Exception as mem_exc:
        logger.debug(f"Unable to log memory usage for tag '{tag}': {mem_exc}")


async def perform_ai_filtering(
    tender_analysis: TenderAnalysis,
    all_tender_matches: List[Dict[str, Any]],
    combined_search_matches: Dict[str, Any],
    analysis_id: str,
    current_user: Optional[User] = None,
    ai_batch_size: int = 50,
    save_results: bool = False,
    search_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Filter tenders using AI based on relevance.
    
    Args:
        tender_analysis: TenderAnalysis configuration
        all_tender_matches: List of all tender matches from search
        combined_search_matches: Combined matches with details
        analysis_id: Analysis ID to associate with filtered results
        current_user: Optional user making the request
        ai_batch_size: Batch size for AI processing
        save_results: Whether to save filter results to database
        search_id: Optional ID of saved search results used
        
    Returns:
        Dictionary containing filtered tenders and metadata
    """
    # --- Memory usage BEFORE AI filtering ---
    log_mem("perform_ai_filtering:start")
    logger.info(f"Starting AI filtering for {len(all_tender_matches)} tenders")
    
    if not all_tender_matches:
        logger.info("No tenders found to filter.")
        return {
            "filtered_tenders": [],
            "filtered_out_tenders": [],
            "all_tender_matches": all_tender_matches
        }
    
    async def filter_batch_with_ai(batch):
        try:
            filtered_batch = await RAGManager.ai_filter_tenders(
                tender_analysis=tender_analysis,
                tender_matches=batch,
                current_user=current_user,
            )
            return filtered_batch.matches if filtered_batch and filtered_batch.matches else []
        except Exception as e:
            logger.error(f"Error in AI filtering batch: {str(e)}")
            return []

    all_filtered_tenders = []
    if len(all_tender_matches) > ai_batch_size:
        batches = [all_tender_matches[i:i + ai_batch_size]
                  for i in range(0, len(all_tender_matches), ai_batch_size)]

        logger.info(f"Splitting {len(all_tender_matches)} tenders into {len(batches)} batches for AI filtering")

        ai_semaphore = asyncio.Semaphore(6)

        async def process_batch_with_semaphore(batch):
            async with ai_semaphore:
                return await filter_batch_with_ai(batch)

        filtered_batches = await asyncio.gather(
            *(process_batch_with_semaphore(batch) for batch in batches)
        )

        for batch_results in filtered_batches:
            all_filtered_tenders.extend(batch_results)

        logger.info(f"AI filtering reduced {len(all_tender_matches)} tenders to {len(all_filtered_tenders)} relevant tenders")
    else:
        filtered_results = await RAGManager.ai_filter_tenders(
            tender_analysis=tender_analysis,
            tender_matches=all_tender_matches,
            current_user=current_user,
        )
        all_filtered_tenders = filtered_results.matches if filtered_results and filtered_results.matches else []
        logger.info(f"AI filtering reduced {len(all_tender_matches)} tenders to {len(all_filtered_tenders)} relevant tenders")

    # Identify and save filtered out tenders
    ai_filtered_out_tenders = []
    filtered_ids = {tender.id for tender in all_filtered_tenders}

    for tender_match in all_tender_matches:
        if tender_match["id"] not in filtered_ids:
            ai_filtered_out_tenders.append(
                FilteredTenderAnalysisResult(
                    tender_id=tender_match["id"],
                    tender_name=tender_match["name"],
                    organization=tender_match.get("organization"),
                    location=tender_match.get("location"),
                    analysis_id=str(analysis_id),
                    filter_stage=FilterStage.AI_INITIAL_FILTER,
                    filter_reason="Not relevant according to initial AI filter",
                    search_phrase=tender_match.get("search_phrase"),
                    source=tender_match.get("source"),
                    original_match=combined_search_matches.get(tender_match["id"]),
                    user_id=str(current_user.id) if current_user else None
                )
            )

    if ai_filtered_out_tenders:
        logger.info(f"Saving {len(ai_filtered_out_tenders)} tenders filtered out by initial AI filtering")
        await db.filtered_tender_analysis_results.insert_many(
            [tender.dict(by_alias=True) for tender in ai_filtered_out_tenders]
        )
    
    # Save filtering results in database with reference to search_id if provided
    initial_ai_filter_id = None
    if search_id:
        filter_result_doc = {
            "search_id": search_id,
            "analysis_id": analysis_id,
            "created_at": datetime.utcnow(),
            "user_id": str(current_user.id) if current_user else None,
            "filtered_tenders_count": len(all_filtered_tenders),
            "filtered_out_count": len(ai_filtered_out_tenders),
            "filtered_tenders_ids": [str(tender.id) for tender in all_filtered_tenders],
            "filtered_out_ids": [str(tender.tender_id) for tender in ai_filtered_out_tenders]
        }
        
        db_result = await db.tender_initial_ai_filter_results.insert_one(filter_result_doc)
        logger.info(f"Saved filter results with reference to search ID: {db_result.inserted_id}")

        initial_ai_filter_id = str(db_result.inserted_id)
    
    # --- Memory usage AFTER AI filtering and DB save ---
    log_mem("perform_ai_filtering:end")
    return {
        "filtered_tenders": all_filtered_tenders,
        "filtered_out_tenders": ai_filtered_out_tenders,
        "all_tender_matches": all_tender_matches,
        "initial_ai_filter_id": initial_ai_filter_id
    }

async def get_saved_initial_ai_filter_results(
    initial_ai_filter_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve previously saved initial AI filter results from the database.
    
    Args:
        initial_ai_filter_id: ID of the saved initial AI filter results
        
    Returns:
        Dictionary containing filter results or None if not found
    """
    
    filter_doc = await db.tender_initial_ai_filter_results.find_one({"_id": ObjectId(initial_ai_filter_id)})
    
    if not filter_doc:
        return None
    
    # Get basic filter information
    result = {
        "initial_ai_filter_id": str(filter_doc["_id"]),
        "search_id": filter_doc.get("search_id"),
        "analysis_id": filter_doc.get("analysis_id"),
        "created_at": filter_doc.get("created_at"),
        "filtered_tenders_count": filter_doc.get("filtered_tenders_count", 0),
        "filtered_out_count": filter_doc.get("filtered_out_count", 0),
        "filtered_tenders_ids": filter_doc.get("filtered_tenders_ids", []),
        "filtered_out_ids": filter_doc.get("filtered_out_ids", [])
    }

    return result
    