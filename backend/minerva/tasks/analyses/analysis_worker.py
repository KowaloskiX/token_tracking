import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any
from minerva.core.helpers.external_comparison import TenderExternalComparison
from minerva.tasks.analyses.analysis_queue import AnalysisQueue
from minerva.tasks.services.analysis_service import analyze_relevant_tenders_with_our_rag
from minerva.tasks.sources.helpers import assign_order_numbers
from minerva.core.database.database import db
from minerva.core.models.user import User
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis
from bson import ObjectId

logger = logging.getLogger(__name__)

class SimpleAnalysisWorker:
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.queue = AnalysisQueue(os.getenv("REDIS_URL", "redis://localhost:6379/1"))
        self.processed_count = 0
    
    async def process_analysis_task(self, task: Dict[str, Any]):
        """Process a complete analysis using existing analyze_relevant_tenders_with_our_rag logic"""
        task_id = task["task_id"]
        analysis_doc = task["analysis_doc"]
        target_date = task["target_date"]
        
        try:
            analysis_id = str(analysis_doc["_id"])
            logger.info(f"Worker {self.worker_id} starting analysis {analysis_id} for date {target_date}")
            
            # Get user
            user_doc = await db.users.find_one({"_id": ObjectId(analysis_doc["user_id"])})
            if not user_doc:
                raise ValueError(f"User not found for analysis {analysis_id}")
            
            current_user = User(**user_doc)
            tender_analysis = TenderAnalysis(**analysis_doc)
            
            # Prepare filter conditions (same as existing code)
            filter_conditions = [
                {"field": "initiation_date", "op": "eq", "value": target_date}
            ]
            if analysis_doc.get("sources"):
                filter_conditions.append({
                    "field": "source_type",
                    "op": "in", 
                    "value": analysis_doc["sources"]
                })
            
            # Call existing analysis function - NO CHANGES TO CORE LOGIC!
            result = await analyze_relevant_tenders_with_our_rag(
                analysis_id=analysis_id,
                tender_names_index_name="tenders",
                rag_index_name="files-rag-23-04-2025", 
                embedding_model="text-embedding-3-large",
                elasticsearch_index_name="tenders",
                score_threshold=0.5,
                top_k=30,
                current_user=current_user,
                filter_conditions=filter_conditions,
                ai_batch_size=75,
                criteria_definitions=tender_analysis.criteria,
                batch_size=7,
                language=tender_analysis.language or "polish"
            )
            
            # Assign order numbers (same as existing)
            await assign_order_numbers(ObjectId(analysis_id), current_user)

            # Perform comparison
            comparison_service = TenderExternalComparison()
            result = await comparison_service.update_external_compare_status(
                analysis_id=analysis_id,
                start_date=target_date,
                end_date=target_date,
            )
                
            # Update analysis timestamp (same as existing)
            await db.tender_analysis.update_one(
                {"_id": ObjectId(analysis_id)},
                {"$set": {
                    "last_run": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Mark task as completed with detailed statistics
            await self.queue.complete_analysis(task_id, {
                "total_tenders_analyzed": result.total_tenders_analyzed,
                "analysis_id": analysis_id,
                "initial_ai_filter_id": getattr(result, "initial_ai_filter_id", None),
                "description_filter_id": getattr(result, "description_filter_id", None)
            }, analysis_stats=getattr(result, "analysis_stats", None))
            
            self.processed_count += 1
            logger.info(f"Worker {self.worker_id} completed analysis {analysis_id} - {result.total_tenders_analyzed} tenders processed (total completed: {self.processed_count})")
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id} - Analysis task {task_id} failed: {e}", exc_info=True)
            await self.queue.fail_analysis(task_id, str(e))
    
    async def run(self):
        """Main worker loop"""
        logger.info(f"Starting simple analysis worker {self.worker_id}")
        
        while True:
            try:
                # Get next analysis to process
                task = await self.queue.get_next_analysis(self.worker_id)
                
                if task:
                    # Process the entire analysis
                    await self.process_analysis_task(task)
                else:
                    # No tasks available, short sleep
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        return {
            "worker_id": self.worker_id,
            "processed_count": self.processed_count,
            "status": "running"
        }

async def main():
    worker_id = os.getenv("WORKER_ID", f"simple-analysis-worker-{os.getpid()}")
    
    worker = SimpleAnalysisWorker(worker_id)
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main()) 