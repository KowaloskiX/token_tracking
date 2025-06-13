import asyncio
from datetime import datetime
from enum import Enum
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

class AIFilteringMode(Enum):
    STANDARD = "standard"  # Current approach
    TRIPLE_RUN = "triple_run"  # Run each batch 3 times and merge
    REVIEW_CORRECTION = "review_correction"  # Initial filter + review pass

async def filter_batch_with_ai_triple_run(
    tender_analysis: TenderAnalysis,
    batch: List[dict],
    current_user: Optional[User] = None
) -> List[dict]:
    """
    Run AI filtering 3 times for the same batch and merge unique results.
    """
    logger.info(f"Running triple-run AI filtering for batch of {len(batch)} tenders")
    
    # Run filtering 3 times concurrently
    tasks = []
    for run_num in range(3):
        task = RAGManager.ai_filter_tenders(
            tender_analysis, 
            batch, 
            current_user, 
            run_id=f"run_{run_num+1}"
        )
        tasks.append(task)
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Track which tenders appear in which runs
        run_matches = {}  # run_index -> set of tender IDs
        all_matches = {}  # tender_id -> tender object
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Run {i+1} failed: {str(result)}")
                run_matches[i] = set()
                continue
            
            run_matches[i] = set()
            if result and result.matches:
                for match in result.matches:
                    tender_id = None
                    if hasattr(match, 'id'):
                        tender_id = match.id
                        all_matches[tender_id] = match
                    elif isinstance(match, dict) and 'id' in match:
                        tender_id = match['id']
                        all_matches[tender_id] = match
                    
                    if tender_id:
                        run_matches[i].add(tender_id)
        
        # Find tenders that appear uniquely in each run
        unique_per_run = {}
        for run_idx in run_matches:
            other_runs = [run_matches[other_idx] for other_idx in run_matches if other_idx != run_idx]
            if other_runs:
                combined_other_runs = set().union(*other_runs)
                unique_per_run[run_idx] = run_matches[run_idx] - combined_other_runs
            else:
                unique_per_run[run_idx] = run_matches[run_idx]
        
        # Log summary of unique tenders per run
        for run_idx, unique_ids in unique_per_run.items():
            if unique_ids:
                logger.info(f"Run {run_idx+1} found {len(unique_ids)} unique tenders not found by other runs:")
                for tender_id in unique_ids:
                    tender = all_matches.get(tender_id)
                    tender_title = getattr(tender, 'name', None) or (tender.get('name') if isinstance(tender, dict) else None) or f"ID: {tender_id}"
                    logger.info(f"  - {tender_title}\n")
            else:
                logger.info(f"Run {run_idx+1} found no unique tenders")
        
        merged_results = list(all_matches.values())
        logger.info(f"Triple-run filtering: merged {len(merged_results)} unique tenders from {len(results)} runs")
        
        return merged_results
        
    except Exception as e:
        logger.error(f"Error in triple-run AI filtering: {str(e)}")
        # Fallback to single run
        try:
            fallback_result = await RAGManager.ai_filter_tenders(
                tender_analysis, batch, current_user, run_id="fallback"
            )
            return fallback_result.matches if fallback_result and fallback_result.matches else []
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            return []

async def filter_batch_with_ai_review_correction(
    tender_analysis: TenderAnalysis,
    batch: List[dict],
    current_user: Optional[User] = None
) -> List[dict]:
    """
    Run initial AI filtering followed by a review/correction pass.
    """
    logger.info(f"Running review-correction AI filtering for batch of {len(batch)} tenders")
    
    try:
        # Step 1: Initial filtering
        initial_result = await RAGManager.ai_filter_tenders(
            tender_analysis, batch, current_user, run_id="initial"
        )
        
        initial_filtered = initial_result.matches if initial_result and initial_result.matches else []
        
        # Identify filtered out tenders
        initial_filtered_ids = set()
        for match in initial_filtered:
            if hasattr(match, 'id'):
                initial_filtered_ids.add(match.id)
            elif isinstance(match, dict) and 'id' in match:
                initial_filtered_ids.add(match['id'])
        
        initial_filtered_out = [
            tender for tender in batch 
            if tender.get('id') not in initial_filtered_ids
        ]
        
        logger.info(f"Initial filtering: {len(initial_filtered)} included, {len(initial_filtered_out)} excluded")
        
        # Step 2: Review and correction
        if initial_filtered or initial_filtered_out:
            # Convert to dict format for review
            filtered_dicts = []
            for match in initial_filtered:
                if hasattr(match, '__dict__'):
                    filtered_dicts.append(match.__dict__)
                elif isinstance(match, dict):
                    filtered_dicts.append(match)
            
            review_result = await RAGManager.ai_review_filter_results(
                tender_analysis, filtered_dicts, initial_filtered_out, current_user
            )
            
            corrected_filtered = review_result.get("corrected_filtered_in", filtered_dicts)
            
            # Compare initial vs corrected results to find differences
            initial_ids = set(tender.get('id') for tender in filtered_dicts if tender.get('id'))
            corrected_ids = set(tender.get('id') for tender in corrected_filtered if tender.get('id'))
            
            # Find newly included and newly excluded tenders
            newly_included_ids = corrected_ids - initial_ids
            newly_excluded_ids = initial_ids - corrected_ids
            
            # Log summary of changes made during review
            if newly_included_ids or newly_excluded_ids:
                logger.info(f"Review made {len(newly_included_ids) + len(newly_excluded_ids)} changes:")
                
                if newly_included_ids:
                    logger.info(f"  Newly included ({len(newly_included_ids)} tenders):")
                    for tender_id in newly_included_ids:
                        # Find the tender in the original batch to get its title
                        tender = next((t for t in batch if t.get('id') == tender_id), None)
                        tender_title = tender.get('name') if tender else f"ID: {tender_id}"
                        logger.info(f"    + {tender_title}\n {tender.get("reason")}")
                
                if newly_excluded_ids:
                    logger.info(f"  Newly excluded ({len(newly_excluded_ids)} tenders):")
                    for tender_id in newly_excluded_ids:
                        # Find the tender in the original batch to get its title
                        tender = next((t for t in batch if t.get('id') == tender_id), None)
                        tender_title = tender.get('name') if tender else f"ID: {tender_id}"
                        logger.info(f"    - {tender_title}\n {tender.get("reason")}")
            else:
                logger.info("Review made no changes to the initial filtering results")
            
            logger.info(f"Final result: {len(corrected_filtered)} tenders after review-correction")
            return corrected_filtered
        else:
            logger.warning("No results from initial filtering to review")
            return []
        
    except Exception as e:
        logger.error(f"Error in review-correction filtering: {str(e)}")
        # Fallback to standard filtering
        try:
            fallback_result = await RAGManager.ai_filter_tenders(
                tender_analysis, batch, current_user, run_id="fallback"
            )
            return fallback_result.matches if fallback_result and fallback_result.matches else []
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            return []

async def filter_batch_with_ai_standard(
    tender_analysis: TenderAnalysis,
    batch: List[dict],
    current_user: Optional[User] = None
) -> List[dict]:
    """
    Standard AI filtering (original approach).
    """
    try:
        filtered_batch = await RAGManager.ai_filter_tenders(
            tender_analysis, batch, current_user
        )
        return filtered_batch.matches if filtered_batch and filtered_batch.matches else []
    except Exception as e:
        logger.error(f"Error in standard AI filtering batch: {str(e)}")
        return []

async def perform_ai_filtering(
    tender_analysis: TenderAnalysis,
    all_tender_matches: List[Dict[str, Any]],
    combined_search_matches: Dict[str, Any],
    analysis_id: str,
    current_user: Optional[User] = None,
    ai_batch_size: int = 50,
    save_results: bool = False,
    search_id: Optional[str] = None,
    filtering_mode: AIFilteringMode = AIFilteringMode.STANDARD,  # New parameter
) -> Dict[str, Any]:
    """
    Filter tenders using AI based on relevance with multiple filtering options.
    
    Args:
        tender_analysis: TenderAnalysis configuration
        all_tender_matches: List of all tender matches from search
        combined_search_matches: Combined matches with details
        analysis_id: Analysis ID to associate with filtered results
        current_user: Optional user making the request
        ai_batch_size: Batch size for AI processing
        save_results: Whether to save filter results to database
        search_id: Optional ID of saved search results used
        filtering_mode: Mode for AI filtering (STANDARD, TRIPLE_RUN, REVIEW_CORRECTION)
        
    Returns:
        Dictionary containing filtered tenders and metadata
    """
    # --- Memory usage BEFORE AI filtering ---
    log_mem(f"perform_ai_filtering:start:{filtering_mode.value}")
    logger.info(f"Starting AI filtering for {len(all_tender_matches)} tenders using {filtering_mode.value} mode")
    
    if not all_tender_matches:
        logger.info("No tenders found to filter.")
        return {
            "filtered_tenders": [],
            "filtered_out_tenders": [],
            "all_tender_matches": all_tender_matches
        }
    
    # Select the appropriate filtering function based on mode
    if filtering_mode == AIFilteringMode.TRIPLE_RUN:
        filter_function = filter_batch_with_ai_triple_run
    elif filtering_mode == AIFilteringMode.REVIEW_CORRECTION:
        filter_function = filter_batch_with_ai_review_correction
    else:  # STANDARD
        filter_function = filter_batch_with_ai_standard

    all_filtered_tenders = []
    
    if len(all_tender_matches) > ai_batch_size:
        batches = [all_tender_matches[i:i + ai_batch_size]
                  for i in range(0, len(all_tender_matches), ai_batch_size)]

        logger.info(f"Splitting {len(all_tender_matches)} tenders into {len(batches)} batches for AI filtering")

        # Adjust semaphore based on filtering mode (triple_run uses more resources)
        semaphore_limit = 3 if filtering_mode == AIFilteringMode.TRIPLE_RUN else 6
        ai_semaphore = asyncio.Semaphore(semaphore_limit)

        async def process_batch_with_semaphore(batch):
            async with ai_semaphore:
                return await filter_function(tender_analysis, batch, current_user)

        filtered_batches = await asyncio.gather(
            *(process_batch_with_semaphore(batch) for batch in batches)
        )

        for batch_results in filtered_batches:
            all_filtered_tenders.extend(batch_results)

        logger.info(f"AI filtering ({filtering_mode.value}) reduced {len(all_tender_matches)} tenders to {len(all_filtered_tenders)} relevant tenders")
    else:
        filtered_results = await filter_function(tender_analysis, all_tender_matches, current_user)
        all_filtered_tenders = filtered_results
        logger.info(f"AI filtering ({filtering_mode.value}) reduced {len(all_tender_matches)} tenders to {len(all_filtered_tenders)} relevant tenders")

    # Identify and save filtered out tenders
    ai_filtered_out_tenders = []
    
    # Handle different return types from filtering functions
    filtered_ids = set()
    for tender in all_filtered_tenders:
        if hasattr(tender, 'id'):
            filtered_ids.add(tender.id)
        elif isinstance(tender, dict) and 'id' in tender:
            filtered_ids.add(tender['id'])

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
                    filter_reason=f"Not relevant according to {filtering_mode.value} AI filter",
                    search_phrase=tender_match.get("search_phrase"),
                    source=tender_match.get("source"),
                    original_match=combined_search_matches.get(tender_match["id"]),
                    user_id=str(current_user.id) if current_user else None
                )
            )

    if ai_filtered_out_tenders:
        logger.info(f"Saving {len(ai_filtered_out_tenders)} tenders filtered out by {filtering_mode.value} AI filtering")
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
            "filtering_mode": filtering_mode.value,  # Track which mode was used
            "filtered_tenders_count": len(all_filtered_tenders),
            "filtered_out_count": len(ai_filtered_out_tenders),
            "filtered_tenders_ids": [
                str(tender.id if hasattr(tender, 'id') else tender.get('id', ''))
                for tender in all_filtered_tenders
            ],
            "filtered_out_ids": [str(tender.tender_id) for tender in ai_filtered_out_tenders]
        }
        
        db_result = await db.tender_initial_ai_filter_results.insert_one(filter_result_doc)
        logger.info(f"Saved filter results with reference to search ID: {db_result.inserted_id}")

        initial_ai_filter_id = str(db_result.inserted_id)
    
    # --- Memory usage AFTER AI filtering and DB save ---
    log_mem(f"perform_ai_filtering:end:{filtering_mode.value}")
    return {
        "filtered_tenders": all_filtered_tenders,
        "filtered_out_tenders": ai_filtered_out_tenders,
        "all_tender_matches": all_tender_matches,
        "initial_ai_filter_id": initial_ai_filter_id,
        "filtering_mode": filtering_mode.value
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
    