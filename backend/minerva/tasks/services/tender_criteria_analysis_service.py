from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from minerva.core.models.extensions.tenders.tender_analysis import AnalysisCriteria
from minerva.core.models.user import User
from minerva.tasks.services.analyze_tender_files import ElasticsearchConfig, RAGManager
from minerva.core.database.database import db
import psutil, os

logger = logging.getLogger("minerva.tasks.analysis_tasks")

# Memory logging helper
def log_mem(tag: str = ""):
    try:
        process_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        logger.info(f"[{tag}] Memory usage: {process_mem:.1f} MB")
    except Exception as mem_exc:
        logger.debug(f"Unable to log memory usage for tag '{tag}': {mem_exc}")

async def perform_criteria_analysis(
    tender_pinecone_id: str,
    rag_index_name: str,
    embedding_model: str,
    criteria: List[AnalysisCriteria],
    criteria_definitions: Optional[List[AnalysisCriteria]] = None,
    extraction_id: Optional[str] = None,
    analysis_id: Optional[str] = None,
    current_user: Optional[User] = None,
    save_results: bool = False,
    include_vector_results: bool = False,
    use_elasticsearch: bool = False,
    language: str = "polish",
    original_tender_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    rag_manager = None
    try:
        # Memory log before criteria analysis
        log_mem(f"{tender_pinecone_id} perform_criteria_analysis:start")
        # Initialize RAG manager with ES config if enabled
        es_config = None
        if use_elasticsearch:
            es_config = ElasticsearchConfig(index_name="files-rag")
            
        rag_manager = RAGManager(
            index_name=rag_index_name,
            namespace="",
            embedding_model=embedding_model,
            tender_pinecone_id=tender_pinecone_id,
            use_elasticsearch=use_elasticsearch,
            es_config=es_config,
            language=language
        )
        if use_elasticsearch:
            await rag_manager.ensure_elasticsearch_index_initialized()
        
        logger.info(f"[{tender_pinecone_id}] Starting criteria and location analysis")
        
        # Perform criteria analysis with ES if enabled
        criteria_and_location_result = await rag_manager.analyze_tender_criteria_and_location(
            current_user=current_user,
            criteria=criteria,
            include_vector_results=include_vector_results,
            original_tender_metadata=original_tender_metadata
        )
        
        logger.info(f"[{tender_pinecone_id}] Completed criteria and location analysis")
        
        # Memory log after criteria analysis computation
        log_mem(f"{tender_pinecone_id} perform_criteria_analysis:after_analysis")
        
        # # Check for disqualifying criteria
        if criteria_definitions:
            criteria_map = {crit.name: crit for crit in criteria_definitions}
            for item in criteria_and_location_result['analysis']["criteria_analysis"]:
                criteria_met = item["analysis"].get("criteria_met", False)
                crit_obj = criteria_map.get(item["criteria"])
                
                if crit_obj is not None and crit_obj.is_disqualifying:
                    if not criteria_met:
                        logger.warning(f"[{tender_pinecone_id}] Disqualifying criteria {item['criteria']} not met")
                        result = {
                            "status": "disqualified",
                            "reason": f"Disqualifying criteria {item['criteria']} not met",
                            "tender_pinecone_id": tender_pinecone_id,
                            "criteria_analysis": criteria_and_location_result
                        }
                        
                        if include_vector_results:
                            result["vector_search_results"] = criteria_and_location_result.get("vector_search_results")
                        
                        # Save disqualified result if requested
                        if save_results:
                            disqualified_doc = {
                                "analysis_id": analysis_id,
                                "extraction_id": extraction_id,
                                "tender_pinecone_id": tender_pinecone_id,
                                "created_at": datetime.utcnow(),
                                "user_id": str(current_user.id) if current_user else None,
                                "status": "disqualified",
                                "disqualifying_criteria": item["criteria"],
                                "criteria_analysis": criteria_and_location_result,
                                "use_elasticsearch": use_elasticsearch
                            }
                            
                            if include_vector_results:
                                disqualified_doc["vector_search_results"] = criteria_and_location_result.get("vector_search_results")
                            
                            db_result = await db.tender_criteria_analysis_results.insert_one(disqualified_doc)
                            result["criteria_analysis_id"] = str(db_result.inserted_id)
                            
                        return result
        
        # All criteria passed or no disqualifying criteria
        result = {
            "status": "success",
            "tender_pinecone_id": tender_pinecone_id,
            "criteria_analysis": criteria_and_location_result,
            "use_elasticsearch": use_elasticsearch
        }
        
        if include_vector_results:
            result["vector_search_results"] = criteria_and_location_result.get("vector_search_results")
        
        # Save results if requested
        if save_results:
            criteria_doc = {
                "analysis_id": analysis_id,
                "extraction_id": extraction_id,
                "tender_pinecone_id": tender_pinecone_id,
                "created_at": datetime.utcnow(),
                "user_id": str(current_user.id) if current_user else None,
                "status": "success",
                "criteria_analysis": criteria_and_location_result,
                "use_elasticsearch": use_elasticsearch
            }
            
            if include_vector_results:
                criteria_doc["vector_search_results"] = criteria_and_location_result.get("vector_search_results")
            
            db_result = await db.tender_criteria_analysis_results.insert_one(criteria_doc)
            result["criteria_analysis_id"] = str(db_result.inserted_id)
            logger.info(f"[{tender_pinecone_id}] Saved criteria analysis with ID: {result['criteria_analysis_id']}")
        
        return result
        
    except Exception as e:
        logger.error(f"[{tender_pinecone_id}] Error during criteria analysis: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "reason": f"Criteria analysis error: {str(e)}",
            "tender_pinecone_id": tender_pinecone_id
        }
    finally:
        if rag_manager:
            rag_manager.clean_up()
        # Final memory log in finally block
        log_mem(f"{tender_pinecone_id} perform_criteria_analysis:finally")