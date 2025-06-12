# analysis_service.py

import os
import gc
from uuid import uuid4
from minerva.core.services.cost_tracking_service import CostTrackingService
from minerva.tasks.services.tender_criteria_analysis_service import perform_criteria_analysis
from minerva.tasks.services.tender_description_filtering_service import perform_description_filtering
from minerva.tasks.services.tender_description_generation_service import generate_tender_description
from minerva.tasks.services.tender_file_extraction_service import perform_file_extraction
from minerva.tasks.services.tender_initial_ai_filtering_service import perform_ai_filtering
from minerva.tasks.services.search_service import perform_tender_search
from minerva.tasks.sources.helpers import assign_order_numbers
from minerva.core.models.file import File
from minerva.core.models.request.tender_analysis import BatchAnalysisResult, TenderAnalysisResponse, TenderSearchResponse
from minerva.core.models.user import User
from minerva.core.models.extensions.tenders.tender_analysis import (
    AnalysisCriteria,
    FilterStage,
    FilteredTenderAnalysisResult,
    TenderAnalysis,
    TenderAnalysisResult,
    CriteriaAnalysis,
    CriteriaAnalysisResult,
    TenderLocation,
    TenderMetadata,
    FileExtractionStatus
)
from minerva.core.database.database import db
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig
from bson import ObjectId
from datetime import datetime, timedelta
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from fastapi import HTTPException
import pytz
from playwright.async_api import async_playwright, BrowserContext, Browser, Playwright

logger = logging.getLogger("minerva.tasks.analysis_tasks")


def calculate_final_score(criteria_results: list, criteria_definitions: list) -> float:
    """
    Return a final score in the range 0 – 1.

    * 40 % is awarded automatically (the "base").
    * The remaining 60 % is distributed across the criteria whose
      `exclude_from_score` attribute is not True.
    """
    BASE_SCORE = 0.40          # 40 %
    CRITERIA_PORTION = 0.60    # 60 %

    # logger.info(f"Calculating final score. Criteria results: {criteria_results}, Criteria definitions: {criteria_definitions}")

    # Map name → definition
    criteria_map = {crit.name: crit for crit in criteria_definitions}

    included_defs = [
        crit for crit in criteria_definitions
        if crit.weight is not None and not getattr(crit, "exclude_from_score", False)
    ]

    total_weight = sum(crit.weight for crit in included_defs)
    if total_weight <= 0:
        raise ValueError("Total criteria weight (after exclusions) must be greater than 0")

    achieved_weight = 0.0
    logger.info(f"Total weight for score calculation (after exclusions): {total_weight}")
    for res in criteria_results:
        crit_obj = criteria_map.get(res.criteria)

        # Skip missing or excluded criteria
        if crit_obj is None or getattr(crit_obj, "exclude_from_score", False):
            continue

        weight_value = crit_obj.weight if crit_obj.weight is not None else 3

        if res.analysis.criteria_met is None:
            confidence = (res.analysis.confidence or "").upper()
            effective_met = confidence == "HIGH"
        else:
            effective_met = res.analysis.criteria_met

        achieved_weight += weight_value * (1.0 if effective_met else 0.0)
        logger.info(f"Processing criterion: {res.criteria}, Weight: {weight_value}, Met: {effective_met}, Current achieved_weight: {achieved_weight}")

    # Convert achieved_weight into its share of the 60 % portion
    variable_score = (achieved_weight / total_weight) * CRITERIA_PORTION
    final_score = BASE_SCORE + variable_score
    logger.info(f"Achieved weight: {achieved_weight}, Variable score: {variable_score}, Final score: {final_score}")

    return round(final_score, 2)


def create_tender_analysis_result_v2(
    original_tender_metadata: dict,
    processed_files_data: dict,
    criteria_and_location_result: dict,
    analysis_id: str,
    current_user: User,
    tender_url: str,
    pinecone_config: QueryConfig,
    criteria_definitions: list, 
    tender_pinecone_id: str,
    tender_description: Optional[str] = None,
) -> TenderAnalysisResult:
    # Map criteria name to AnalysisCriteria definition
    criteria_defs_map = {c.name: c for c in criteria_definitions}

    # Ensure canonical names are used for criteria, assuming order is preserved
    raw_criteria_analysis = criteria_and_location_result['analysis'].get("criteria_analysis", [])
    if not isinstance(raw_criteria_analysis, list):
        logger.warning(f"criteria_analysis is not a list: {raw_criteria_analysis}. Defaulting to empty list.")
        raw_criteria_analysis = []
        
    for idx, item in enumerate(raw_criteria_analysis):
        if isinstance(item, dict) and idx < len(criteria_definitions):
            original_criterion_name_from_llm = item.get("criteria")
            canonical_name = criteria_definitions[idx].name
            if original_criterion_name_from_llm != canonical_name:
                logger.info(f"Aligning criteria name. LLM returned: '{original_criterion_name_from_llm}', Canonical: '{canonical_name}'. For analysis ID: {analysis_id}, Tender URL: {tender_url}")
            item["criteria"] = canonical_name
        elif not isinstance(item, dict):
            logger.warning(f"Item in raw_criteria_analysis is not a dict: {item}. Skipping alignment. For analysis ID: {analysis_id}, Tender URL: {tender_url}")
        else: # idx >= len(criteria_definitions)
            logger.warning(f"Index mismatch when aligning criteria names. Index: {idx}, criteria_definitions length: {len(criteria_definitions)}. LLM item: {item}. For analysis ID: {analysis_id}, Tender URL: {tender_url}")


    criteria_analysis_results = [
        CriteriaAnalysisResult(
            criteria=item["criteria"], # This will now be the canonical name
            analysis=CriteriaAnalysis(
                summary=item["analysis"]["summary"],
                confidence=item["analysis"]["confidence"],
                criteria_met=item["analysis"].get("criteria_met", False),
                weight=criteria_defs_map.get(item["criteria"], AnalysisCriteria(name=item["criteria"], description="", weight=3)).weight or 3
            ),
            exclude_from_score=getattr(criteria_defs_map.get(item["criteria"]), "exclude_from_score", False),
            is_disqualifying=getattr(criteria_defs_map.get(item["criteria"]), "is_disqualifying", False),
        )
        for item in raw_criteria_analysis if isinstance(item, dict) and "criteria" in item and "analysis" in item # Ensure item is a valid dict
    ]

    # Build other tender metadata using original_tender_metadata
    tender_metadata = TenderMetadata(
        name=original_tender_metadata.get("name", ""),
        organization=original_tender_metadata.get("organization", ""),
        submission_deadline=original_tender_metadata.get("submission_deadline", ""),
        initiation_date=original_tender_metadata.get("initiation_date", ""),
        procedure_type=original_tender_metadata.get("procedure_type", "")
    )

    file_extraction_status = FileExtractionStatus(
        user_id=str(current_user.id),
        files_processed=processed_files_data.get('total_processed', 0),
        files_uploaded=processed_files_data.get('successful_count', 0),
        status="completed"
    )

    # Convert successful_files to File objects using processed_files_data
    uploaded_files = [
        File(
            filename=file["filename"],
            type=file["type"],
            url=file["url"],
            blob_url=file["blob_url"],
            bytes=file["bytes"],
            owner_id=str(file["owner_id"]) if "owner_id" in file and file["owner_id"] else str(current_user.id),
            preview_chars=file["preview_chars"],
            file_pinecone_config=file["file_pinecone_config"],
            created_at=datetime.utcnow() 
        )
        for file in processed_files_data.get('successful_files', [])
    ]

    # Improved error handling for location data remains unchanged
    try:
        location_data = criteria_and_location_result['analysis'].get("location", {})
        if not isinstance(location_data, dict):
            logger.warning(f"Location data is not a dictionary: {location_data}")
            location_data = {}
            
        location = TenderLocation(
            country=location_data.get('country', "UNKNOWN"),
            voivodeship=location_data.get('voivodeship', "UNKNOWN"),
            city=location_data.get('city', "UNKNOWN")
        )
        logger.info(f"Parsed location data: {location}")
    except Exception as e:
        logger.error(f"Error parsing location data: {str(e)}, using default values")
        location = TenderLocation(
            country="UNKNOWN",
            voivodeship="UNKNOWN",
            city="UNKNOWN"
        )

    # Compute the final tender score using our new calculation
    final_score = calculate_final_score(criteria_analysis_results, criteria_definitions)
    return TenderAnalysisResult(
        user_id=current_user.id,
        tender_analysis_id=ObjectId(analysis_id),
        tender_url=str(tender_url),
        source=original_tender_metadata.get("source_type", ""),
        location=location, 
        tender_score=final_score,
        tender_metadata=tender_metadata.dict(),
        file_extraction_status=file_extraction_status.dict(),
        criteria_analysis=criteria_analysis_results,  # Use the list directly
        company_match_explanation="",
        uploaded_files=uploaded_files,
        tender_description=tender_description,
        pinecone_config=pinecone_config,
        tender_pinecone_id=tender_pinecone_id,
        updates=[]
    )

async def _process_tender_pipeline(
    tender_obj,
    original_metadata: Dict[str, Any],
    shared_browser: Browser,
    tender_analysis: TenderAnalysis,
    analysis_id: str,
    analysis_session_id: str,  # NEW parameter
    rag_index_name: str,
    embedding_model: str,
    current_user: Optional[User],
    criteria_definitions: List[AnalysisCriteria],
    semaphore: asyncio.Semaphore,
    source_manager: TenderSourceManager,
    cost_record_id: str
):
    """End-to-end processing for one tender with cost tracking"""
    async with semaphore:
        tender_id_str = original_metadata.get("details_url", "UNKNOWN_ID")
        
        try:
            tender_dict = {
                "id": original_metadata.get("details_url"),
                **original_metadata
            }
            
            # File extraction (existing logic, no LLM costs here typically)
            extraction_res = await perform_file_extraction(
                playwright_browser=shared_browser,
                source_manager=source_manager,
                tender=tender_dict,
                rag_index_name=rag_index_name,
                embedding_model=embedding_model,
                analysis_id=analysis_id,
                current_user=current_user,
                save_results=False,
                check_existing_analysis=False,
                use_elasticsearch=False,
                cost_record_id=cost_record_id
            )
            
            if extraction_res.get("status") != "success":
                logger.warning(f"Extraction failed/skipped for tender {tender_id_str}: {extraction_res.get('reason')}")
                if cost_record_id:
                    await CostTrackingService.complete_analysis_cost_record(cost_record_id, "failed")
                return None

            # --- Criteria analysis with cost tracking ---
            criteria_res = await perform_criteria_analysis(
                tender_pinecone_id=extraction_res["tender_pinecone_id"],
                rag_index_name=rag_index_name,
                embedding_model=embedding_model,
                criteria=tender_analysis.criteria,
                criteria_definitions=criteria_definitions,
                cost_record_id=cost_record_id,
                extraction_id=extraction_res.get("extraction_id"),
                analysis_id=analysis_id,
                current_user=current_user,
                save_results=False,
            )
            
            if criteria_res.get("status") != "success":
                logger.warning(f"Criteria analysis not successful for tender {tender_id_str}: {criteria_res.get('reason')}")
                if cost_record_id:
                    await CostTrackingService.complete_analysis_cost_record(cost_record_id, "failed")
                return None

            # --- Description generation with cost tracking ---
            desc_res = await generate_tender_description(
                tender_pinecone_id=extraction_res["tender_pinecone_id"],
                rag_index_name=rag_index_name,
                embedding_model=embedding_model,
                cost_record_id=cost_record_id,
                analysis_id=analysis_id,
                current_user=current_user,
                save_results=False,
            )
            description_text = desc_res.get("tender_description", "") if desc_res.get("status") == "success" else ""

            # --- Build final TenderAnalysisResult object (existing logic) ---
            tender_result_obj = create_tender_analysis_result_v2(
                original_tender_metadata=original_metadata,
                processed_files_data=extraction_res.get("processed_files", {}),
                criteria_and_location_result=criteria_res["criteria_analysis"],
                analysis_id=analysis_id,
                current_user=current_user,
                tender_url=tender_dict["id"],
                tender_description=description_text,
                pinecone_config=QueryConfig(index_name=rag_index_name, namespace="", embedding_model=embedding_model),
                criteria_definitions=criteria_definitions,
                tender_pinecone_id=extraction_res["tender_pinecone_id"],
            )
                        
            return tender_result_obj
            
        except Exception as exc:
            logger.error(f"Pipeline error for tender {tender_id_str}: {exc}", exc_info=True)
            if cost_record_id:
                await CostTrackingService.complete_analysis_cost_record(cost_record_id, "failed")
            return None

async def analyze_relevant_tenders_with_our_rag(
    analysis_id: str,
    tender_names_index_name: str,
    rag_index_name: str,
    embedding_model: str = "text-embedding-3-large",
    elasticsearch_index_name: str = "tenders",
    score_threshold: float = 0.1,
    top_k: int = 25,
    current_user: User = None,
    filter_conditions: Optional[List[Dict[str, Any]]] = None,
    ai_batch_size: int = 60,
    criteria_definitions: list = None,
    batch_size: int = 10
):
    # Generate unique session ID for this analysis run
    analysis_session_id = str(uuid4())
    main_cost_record_id = await CostTrackingService.create_analysis_cost_record(
        user_id=str(current_user.id),
        tender_analysis_id=analysis_id,
        tender_id="analysis_batch",  # Identifier for the whole analysis
        analysis_session_id=analysis_session_id
    )
    
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None
    try:
        # Start Playwright and create shared browser (existing code)
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        logger.info(f"Playwright browser started. Concurrency set to: {batch_size}")

        async def initialize_services():
            tender_analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(analysis_id)})
            if not tender_analysis_doc:
                raise HTTPException(status_code=404, detail="Tender analysis configuration not found")
            return TenderAnalysis(**tender_analysis_doc)

        tender_analysis = await initialize_services()

        if criteria_definitions is None or len(criteria_definitions) == 0:
            criteria_definitions = tender_analysis.criteria

        # Initialize semaphore for concurrency control (existing code)
        semaphore = asyncio.Semaphore(batch_size)
        # Embedding configuration (existing code)
        embedding_config = EmbeddingConfig(
            index_name=tender_names_index_name,
            namespace="",
            embedding_model=embedding_model
        )

        # Initialize source manager (existing code)
        source_manager = TenderSourceManager(embedding_config)

        # Search logic (existing code)
        search_results = await perform_tender_search(
                search_phrase=tender_analysis.search_phrase,
                tender_names_index_name=tender_names_index_name,
                elasticsearch_index_name=elasticsearch_index_name,
                embedding_model=embedding_model,
                score_threshold=score_threshold,
                top_k=top_k,
                sources=tender_analysis.sources,
                filter_conditions=filter_conditions,
                analysis_id=analysis_id,
                current_user_id=str(current_user.id) if current_user else None,
                save_results=False
            )
            
        all_tender_matches = search_results["all_tender_matches"]
        combined_search_matches = search_results["combined_search_matches"]
        search_id = search_results.get("search_id")

        # --- AI Filtering Logic (existing code) ---
        logger.info(f"Combined search found {len(all_tender_matches)} unique tenders before AI filtering.")
        if not all_tender_matches:
            logger.info("No tenders found in either Pinecone or Elasticsearch.")
            if browser: await browser.close()
            if playwright: await playwright.stop()
            return TenderSearchResponse(
                query=tender_analysis.search_phrase,
                total_tenders_analyzed=0,
                analysis_results=[]
            )

        filter_results = await perform_ai_filtering(
            tender_analysis=tender_analysis,
            all_tender_matches=all_tender_matches,
            combined_search_matches=combined_search_matches,
            analysis_id=analysis_id,
            current_user=current_user,
            ai_batch_size=ai_batch_size,
            cost_record_id=main_cost_record_id,
            search_id=search_id
        )
        
        all_filtered_tenders = filter_results["filtered_tenders"]
        initial_ai_filter_id = filter_results.get("initial_ai_filter_id")

        if not all_filtered_tenders:
            logger.info("No tenders left after initial AI filtering.")
            await CostTrackingService.complete_analysis_cost_record(main_cost_record_id, "completed")
            if browser: await browser.close()
            if playwright: await playwright.stop()
            return TenderSearchResponse(
                query=tender_analysis.search_phrase,
                total_tenders_analyzed=0,
                analysis_results=[],
                initial_ai_filter_id=initial_ai_filter_id,
                description_filter_id=None
            )

        # --- File extraction + criteria + description in a single pipeline task ---
        logger.info(f"Starting unified pipeline for {len(all_filtered_tenders)} tenders with concurrency {batch_size}")

        async def build_pipeline_tasks():
            tasks = []
            for tender in all_filtered_tenders:
                original_metadata = combined_search_matches.get(tender.id, {}).get("metadata", {})
                if not original_metadata:
                    logger.warning(f"Missing original metadata for tender {tender.id}; skipping")
                    continue
                tasks.append(
                    _process_tender_pipeline(
                        tender_obj=tender,
                        original_metadata=original_metadata,
                        shared_browser=browser,
                        tender_analysis=tender_analysis,
                        analysis_id=analysis_id,
                        analysis_session_id=analysis_session_id,
                        rag_index_name=rag_index_name,
                        embedding_model=embedding_model,
                        current_user=current_user,
                        criteria_definitions=criteria_definitions,
                        semaphore=semaphore,
                        source_manager=source_manager,
                        cost_record_id=main_cost_record_id  # ← Pass the main cost record to each tender
                    )
                )
            return tasks

        pipeline_results = await asyncio.gather(*await build_pipeline_tasks())
        successful_tender_results = [r for r in pipeline_results if r is not None]

        logger.info(f"Unified pipeline finished. Successful tender results: {len(successful_tender_results)}")

        if not successful_tender_results:
            logger.info("No tenders passed full pipeline processing.")
            await CostTrackingService.complete_analysis_cost_record(main_cost_record_id, "completed")
            if browser: await browser.close()
            if playwright: await playwright.stop()
            return TenderSearchResponse(
                query=tender_analysis.search_phrase,
                total_tenders_analyzed=0,
                analysis_results=[],
                initial_ai_filter_id=initial_ai_filter_id,
                description_filter_id=None
            )

        # --- Description-based filtering (existing logic) ---
        description_filter_results = await perform_description_filtering(
            tender_analysis=tender_analysis,
            tender_results=successful_tender_results,
            analysis_id=analysis_id,
            current_user=current_user,
            ai_batch_size=ai_batch_size,
            save_results=False,
        )

        filtered_tenders = description_filter_results.get("filtered_tenders", [])
        filtered_out_tenders = description_filter_results.get("filtered_out_tenders", [])
        description_filter_id = description_filter_results.get("description_filter_id")
        logger.info(f"Description filtering finished. Got {len(filtered_tenders)} tenders.")

        if not filtered_tenders:
            logger.info("No tenders passed description filtering.")
            if browser: await browser.close()
            if playwright: await playwright.stop()
            return TenderSearchResponse(
                query=tender_analysis.search_phrase,
                total_tenders_analyzed=0,
                analysis_results=[],
                initial_ai_filter_id=initial_ai_filter_id,
                description_filter_id=description_filter_id
            )

        # (Save filtered_out logic - existing code)
        description_filtered_tenders_results = []
        for filtered_out_tender in filtered_out_tenders:
            # Create file storage info while maintaining the existing processed_files structure
            file_storage_info = []
            for file in filtered_out_tender.uploaded_files:
                # Store the entire file_pinecone_config object if available
                pinecone_config = None
                if hasattr(file, 'file_pinecone_config') and file.file_pinecone_config:
                    pinecone_config = {
                        "query_config": {
                            "index_name": file.file_pinecone_config.query_config.index_name,
                            "namespace": file.file_pinecone_config.query_config.namespace,
                            "embedding_model": file.file_pinecone_config.query_config.embedding_model
                        },
                        "pinecone_unique_id_prefix": file.file_pinecone_config.pinecone_unique_id_prefix
                    }
                
                file_info = {
                    "filename": file.filename,
                    "blob_url": file.blob_url if hasattr(file, 'blob_url') and file.blob_url else None,
                    "file_pinecone_config": pinecone_config,
                    "deletion_status": "pending",
                    "deletion_timestamp": None,
                    "deletion_error": None
                }
                file_storage_info.append(file_info)
            
            # Maintain the original processed_files structure while adding storage info
            processed_files = {
                "successful_count": len(filtered_out_tender.uploaded_files),
                "filenames": [file.filename for file in filtered_out_tender.uploaded_files],
                "storage_info": file_storage_info
            }
            
            description_filtered_tender = FilteredTenderAnalysisResult(
                tender_id=str(filtered_out_tender.id),
                tender_name=filtered_out_tender.tender_metadata.name,
                organization=filtered_out_tender.tender_metadata.organization,
                location=filtered_out_tender.location.model_dump_json() if filtered_out_tender.location else None,
                analysis_id=str(analysis_id),
                filter_stage=FilterStage.AI_DESCRIPTION_FILTER,
                filter_reason="Filtered out based on description analysis",
                search_phrase=tender_analysis.search_phrase,
                tender_description=filtered_out_tender.tender_description,
                details_url=filtered_out_tender.tender_url,
                processed_files=processed_files,
                user_id=str(current_user.id) if current_user else None
            )
            description_filtered_tenders_results.append(description_filtered_tender)

        # Save tenders filtered out by description to the database
        if description_filtered_tenders_results:
            logger.info(f"Saving {len(description_filtered_tenders_results)} tenders filtered out by description analysis")
            await db.filtered_tender_analysis_results.insert_many(
                [tender.model_dump(by_alias=True) for tender in description_filtered_tenders_results]
            )

        # --- Final Save and Update Logic (existing code) ---
        for final_result in filtered_tenders:
            await db.tender_analysis_results.insert_one(final_result.dict(by_alias=True))
            logger.info(f"Successfully analyzed and saved tender: {final_result.id}")

        await db.tender_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {
                "last_run": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        await CostTrackingService.complete_analysis_cost_record(main_cost_record_id, "completed")

        logger.info(f"Completed analysis run. Saved {len(filtered_tenders)} final results.")
        return TenderSearchResponse(
            query=tender_analysis.search_phrase,
            total_tenders_analyzed=len(filtered_tenders),
            analysis_results=filtered_tenders,
            initial_ai_filter_id=initial_ai_filter_id,
            description_filter_id=description_filter_id
        )

    except Exception as e:
        logger.error(f"Fatal error in combined analysis: {str(e)}", exc_info=True)
        # ✅ Complete the cost record as failed
        if main_cost_record_id:
            await CostTrackingService.complete_analysis_cost_record(main_cost_record_id, "failed")
        raise HTTPException(
            status_code=500,
            detail=f"Error in combined analysis: {str(e)}"
        )
    finally:
        # Shared Browser Cleanup (existing code)
        if browser:
            logger.info("Closing shared Playwright browser...")
            try:
                 await browser.close()
                 logger.info("Shared browser closed.")
            except Exception as browser_close_err:
                 logger.error(f"Error closing browser: {browser_close_err}")
        if playwright:
            logger.info("Stopping Playwright...")
            try:
                 await playwright.stop()
                 logger.info("Playwright stopped.")
            except Exception as playwright_stop_err:
                 logger.error(f"Error stopping playwright: {playwright_stop_err}")
        
        # Final garbage collection
        gc.collect()
        logger.info("Final garbage collection performed after analysis completed")


async def run_all_tender_analyses(
    target_date: str = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d"),
    top_k: int = 20,
    score_threshold: float = 0.1,
    filter_conditions: Optional[List[Dict[str, Any]]] = None
) -> "TenderAnalysisResponse":
    analyses_cursor = db.tender_analysis.find({"active": True})
    all_analyses = await analyses_cursor.to_list(None)

    if not all_analyses:
        logger.info("No TenderAnalysis found to run.")
        return TenderAnalysisResponse()

    logger.info(f"Found {len(all_analyses)} analyses to process for date {target_date}.")
    semaphore = asyncio.Semaphore(1)
    successful = 0
    failed = 0
    analysis_results = []
    analysis_summary_data = []

    async def process_analysis(analysis_doc):
        nonlocal successful, failed, analysis_summary_data
        async with semaphore:
            try:
                user_id = analysis_doc["user_id"]
                user_data = await db['users'].find_one({"_id": ObjectId(user_id)})
                if not user_data:
                    logger.error(f"User not found for ID: {user_id}")
                    failed += 1
                    return None

                current_user = User(**user_data)
                analysis_id = str(analysis_doc["_id"])
                tender_analysis = TenderAnalysis(**analysis_doc)
                criteria_definitions = tender_analysis.criteria

                current_filters = filter_conditions or [
                    {"field": "initiation_date", "op": "eq", "value": target_date}
                ]
                if analysis_doc.get("sources"):
                    current_filters.append({
                        "field": "source_type",
                        "op": "in",
                        "value": analysis_doc["sources"]
                    })

                result = await analyze_relevant_tenders_with_our_rag(
                    analysis_id=analysis_id,
                    tender_names_index_name="tenders",
                    rag_index_name="files-rag-23-04-2025",
                    embedding_model="text-embedding-3-large",
                    top_k=top_k,
                    score_threshold=score_threshold,
                    current_user=current_user,
                    filter_conditions=current_filters,
                    criteria_definitions=criteria_definitions
                )

                current_time = datetime.utcnow()
                await db.tender_analysis.update_one(
                    {"_id": ObjectId(analysis_id)},
                    {"$set": {
                        "last_run": current_time,
                        "updated_at": current_time
                    }}
                )

                batch_result = BatchAnalysisResult(
                    analysis_id=analysis_id,
                    total_tenders_analyzed=result.total_tenders_analyzed,
                    query=result.query,
                    analysis_results=result.analysis_results
                )

                tender_names = [
                    tender.tender_metadata.name if tender.tender_metadata and tender.tender_metadata.name else "Unknown"
                    for tender in result.analysis_results
                ]
                analysis_summary_data.append({
                    "user_email": current_user.email,
                    "user_name": current_user.name,
                    "tender_names": tender_names
                })

                logger.info(f"Completed analysis for {analysis_id}, analyzed {result.total_tenders_analyzed} tenders")
                successful += 1
                return batch_result

            except Exception as e:
                logger.error(f"Error processing analysis {analysis_doc['_id']}: {str(e)}")
                failed += 1
                return None

    results = await asyncio.gather(*(process_analysis(a) for a in all_analyses))
    analysis_results = [r for r in results if r is not None]

    logger.info(f"Completed running all tender analyses for date {target_date}.")

    return TenderAnalysisResponse(
        total_analyses=len(all_analyses),
        successful_analyses=successful,
        failed_analyses=failed,
        analysis_results=analysis_results,
        analysis_summary_data=analysis_summary_data
    )


async def run_all_analyses_for_user(
    user_id: str,
    top_k: int = 30,
    score_threshold: float = 0.1,
    filter_conditions: Optional[List[Dict[str, Any]]] = None,
    index_name: str = "tenders"
) -> Dict[str, Any]:
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            msg = f"User not found for ID: {user_id}"
            logger.error(msg)
            return {"error": msg}

        current_user = User(**user_doc)

        analysis_docs = await db.tender_analysis.find({
            "user_id": ObjectId(user_id),
            "active": True
        }).to_list(None)
        if not analysis_docs:
            logger.info("No analyses found for user %s", user_id)
            return {"analysis_count": 0, "results": []}

        if filter_conditions is None:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            filter_conditions = [
                {"field": "initiation_date", "op": "eq", "value": yesterday}
            ]

        successful = 0
        failed = 0
        batch_results = []

        semaphore = asyncio.Semaphore(2)

        async def process_one_analysis(analysis_doc):
            nonlocal successful, failed
            async with semaphore:
                try:
                    fc = filter_conditions.copy()
                    if analysis_doc.get("sources"):
                        fc.append({
                            "field": "source_type",
                            "op": "in",
                            "value": analysis_doc["sources"]
                        })

                    analysis_oid = str(analysis_doc["_id"])
                    tender_analysis = TenderAnalysis(**analysis_doc)
                    criteria_definitions = tender_analysis.criteria

                    result = await analyze_relevant_tenders_with_our_rag(
                        analysis_id=analysis_oid,
                        tender_names_index_name="tenders",
                        embedding_model="text-embedding-3-large",
                        rag_index_name="files-rag-23-04-2025",
                        top_k=top_k,
                        score_threshold=score_threshold,
                        current_user=current_user,
                        filter_conditions=fc,
                        criteria_definitions=criteria_definitions
                    )

                    now_utc = datetime.utcnow()
                    await db.tender_analysis.update_one(
                        {"_id": ObjectId(analysis_oid)},
                        {"$set": {
                            "last_run": now_utc,
                            "updated_at": now_utc
                        }}
                    )

                    b = BatchAnalysisResult(
                        analysis_id=analysis_oid,
                        total_tenders_analyzed=result.total_tenders_analyzed,
                        query=result.query,
                        analysis_results=result.analysis_results,
                        initial_ai_filter_id=result.initial_ai_filter_id,
                        description_filter_id=result.description_filter_id
                    )
                    successful += 1
                    return b.dict()
                except Exception as exc:
                    logger.error("Error analyzing doc %s: %s", analysis_doc["_id"], exc)
                    failed += 1
                    return None

        tasks = [process_one_analysis(doc) for doc in analysis_docs]
        results = await asyncio.gather(*tasks)
        
        batch_results = [r for r in results if r is not None]

        return {
            "analysis_count": len(analysis_docs),
            "successful": successful,
            "failed": failed,
            "results": batch_results
        }
    except Exception as e:
        logger.error(f"Fatal error in run_all_analyses_for_user: {e}")
        return {"error": str(e)}

async def run_partial_tender_analyses(
    analyses: list,
    target_date: str = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d"),
    top_k: int = 30,
    score_threshold: float = 0.1,
    filter_conditions: Optional[List[Dict[str, Any]]] = None
) -> "TenderAnalysisResponse":
    active_analyses = [a for a in analyses if a.get("active", False)]
    
    if not active_analyses:
        logger.info("No active analyses provided to run.")
        return TenderAnalysisResponse()

    logger.info(f"Processing {len(active_analyses)} active analyses for date {target_date}.")
    semaphore = asyncio.Semaphore(1)
    successful = 0
    failed = 0
    analysis_results = []
    analysis_summary_data = []

    async def process_analysis(analysis_doc):
        nonlocal successful, failed, analysis_summary_data
        async with semaphore:
            try:
                user_id = analysis_doc["user_id"]
                user_data = await db['users'].find_one({"_id": ObjectId(user_id)})
                if not user_data:
                    logger.error(f"User not found for ID: {user_id}")
                    failed += 1
                    return None

                current_user = User(**user_data)
                analysis_id = str(analysis_doc["_id"])
                tender_analysis = TenderAnalysis(**analysis_doc)
                criteria_definitions = tender_analysis.criteria

                current_filters = filter_conditions or [
                    {"field": "initiation_date", "op": "eq", "value": target_date}
                ]
                if analysis_doc.get("sources"):
                    current_filters.append({
                        "field": "source_type",
                        "op": "in",
                        "value": analysis_doc["sources"]
                    })

                result = await analyze_relevant_tenders_with_our_rag(
                    analysis_id=analysis_id,
                    tender_names_index_name="tenders",
                    elasticsearch_index_name="tenders",
                    embedding_model="text-embedding-3-large",
                    rag_index_name="files-rag-23-04-2025",
                    ai_batch_size=75,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    current_user=current_user,
                    filter_conditions=current_filters,
                    criteria_definitions=criteria_definitions
                )
                await assign_order_numbers(ObjectId(analysis_id), current_user)

                current_time = datetime.utcnow()
                await db.tender_analysis.update_one(
                    {"_id": ObjectId(analysis_id)},
                    {"$set": {"last_run": current_time, "updated_at": current_time}}
                )

                batch_result = BatchAnalysisResult(
                    analysis_id=analysis_id,
                    total_tenders_analyzed=result.total_tenders_analyzed,
                    query=result.query,
                    analysis_results=result.analysis_results,
                    initial_ai_filter_id=result.initial_ai_filter_id,
                    description_filter_id=result.description_filter_id
                )

                tender_names = [
                    tender.tender_metadata.name if tender.tender_metadata and tender.tender_metadata.name else "Unknown"
                    for tender in result.analysis_results
                ]
                analysis_summary_data.append({
                    "user_email": current_user.email,
                    "user_name": current_user.name,
                    "tender_names": tender_names
                })

                logger.info(f"Completed analysis for {analysis_id}, analyzed {result.total_tenders_analyzed} tenders")
                successful += 1
                return batch_result

            except Exception as e:
                logger.error(f"Error processing analysis {analysis_doc['_id']}: {str(e)}")
                failed += 1
                return None

    results = await asyncio.gather(*(process_analysis(a) for a in active_analyses))
    analysis_results = [r for r in results if r is not None]

    logger.info(f"Completed running partial tender analyses for date {target_date}.")

    return TenderAnalysisResponse(
        total_analyses=len(active_analyses),
        successful_analyses=successful,
        failed_analyses=failed,
        analysis_results=analysis_results,
        analysis_summary_data=analysis_summary_data
    )