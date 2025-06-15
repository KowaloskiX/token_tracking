from datetime import datetime
import logging
from typing import Any, Dict, Optional
from minerva.core.models.user import User
from minerva.tasks.services.analyze_tender_files import RAGManager
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

async def generate_tender_description(
    tender_pinecone_id: str,
    rag_index_name: str,
    embedding_model: str,
    analysis_id: Optional[str] = None,
    current_user: Optional[User] = None,
    save_results: bool = False,
    language: str = "polish"
) -> Dict[str, Any]:
    rag_manager = None
    try:
        # Memory log before description generation
        log_mem(f"{tender_pinecone_id} generate_tender_description:start")
        # Initialize RAG manager
        rag_manager = RAGManager(rag_index_name, "", embedding_model, tender_pinecone_id, language=language)
        
        logger.info(f"[{tender_pinecone_id}] Starting tender description generation")
        
        # Generate description
        tender_description = await rag_manager.generate_tender_description()
        
        logger.info(f"[{tender_pinecone_id}] Completed tender description generation")
        
        result = {
            "status": "success",
            "tender_pinecone_id": tender_pinecone_id,
            "tender_description": tender_description
        }
        
        # Save results if requested
        if save_results:
            description_doc = {
                "analysis_id": analysis_id,
                "tender_pinecone_id": tender_pinecone_id,
                "created_at": datetime.utcnow(),
                "user_id": str(current_user.id) if current_user else None,
                "tender_description": tender_description
            }
            
            db_result = await db.tender_description_generation_results.insert_one(description_doc)
            result["description_id"] = str(db_result.inserted_id)
            logger.info(f"[{tender_pinecone_id}] Saved description with ID: {result['description_id']}")
        
        # Memory log after description generated
        log_mem(f"{tender_pinecone_id} generate_tender_description:end")
        
        return result
        
    except Exception as e:
        logger.error(f"[{tender_pinecone_id}] Error during description generation: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "reason": f"Description generation error: {str(e)}",
            "tender_pinecone_id": tender_pinecone_id
        }
    finally:
        if rag_manager:
            rag_manager.clean_up()
        # Final memory log after cleanup
        log_mem(f"{tender_pinecone_id} generate_tender_description:finally")