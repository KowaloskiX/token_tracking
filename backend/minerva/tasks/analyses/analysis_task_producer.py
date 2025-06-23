import asyncio
import logging
import os
from datetime import datetime
from minerva.tasks.analyses.analysis_queue import AnalysisQueue
from minerva.core.database.database import db
import pytz
import json

logger = logging.getLogger(__name__)

def serialize_for_json(obj):
    """Custom JSON serializer for MongoDB documents"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__class__') and 'ObjectId' in str(obj.__class__):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj

async def create_daily_analysis_tasks():
    """Create analysis tasks for today's date"""
    target_date = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d")
    logger.info(f"Creating analysis tasks for date: {target_date}")
    
    queue = AnalysisQueue()  # Use default Redis URL handling
    
    # Get all active analyses
    analyses = await db.tender_analysis.find({"active": True}).to_list(None)
    
    if not analyses:
        logger.info("No active analyses found")
        return {"total_analyses": 0, "tasks_created": 0}
    
    tasks_created = 0
    
    for analysis_doc in analyses:
        try:
            # Serialize the entire document for JSON compatibility
            analysis_doc_serialized = serialize_for_json(analysis_doc)
            
            await queue.enqueue_analysis(analysis_doc_serialized, target_date)
            tasks_created += 1
            
            logger.info(f"Enqueued analysis: {analysis_doc_serialized.get('name', 'Unnamed')} (ID: {analysis_doc_serialized['_id']})")
            
        except Exception as e:
            logger.error(f"Error creating task for analysis {analysis_doc.get('_id')}: {e}", exc_info=True)
    
    # Log queue statistics
    stats = await queue.get_queue_stats()
    logger.info(f"Created {tasks_created} analysis tasks for {len(analyses)} analyses. Queue stats: {stats}")
    
    return {
        "total_analyses": len(analyses), 
        "tasks_created": tasks_created,
        "target_date": target_date,
        "queue_stats": stats
    }

async def create_analysis_tasks_for_date(target_date: str):
    """Create analysis tasks for a specific date (for manual runs)"""
    logger.info(f"Creating analysis tasks for specific date: {target_date}")
    
    queue = AnalysisQueue()  # Use default Redis URL handling
    
    # Get all active analyses
    analyses = await db.tender_analysis.find({"active": True}).to_list(None)
    
    if not analyses:
        logger.info("No active analyses found")
        return {"total_analyses": 0, "tasks_created": 0}
    
    tasks_created = 0
    
    for analysis_doc in analyses:
        try:
            # Serialize the entire document for JSON compatibility
            analysis_doc_serialized = serialize_for_json(analysis_doc)
            
            await queue.enqueue_analysis(analysis_doc_serialized, target_date)
            tasks_created += 1
            
        except Exception as e:
            logger.error(f"Error creating task for analysis {analysis_doc.get('_id')}: {e}")
    
    stats = await queue.get_queue_stats()
    logger.info(f"Created {tasks_created} analysis tasks for date {target_date}. Queue stats: {stats}")
    
    return {
        "total_analyses": len(analyses), 
        "tasks_created": tasks_created,
        "target_date": target_date,
        "queue_stats": stats
    }

async def get_queue_status():
    """Get current queue status"""
    queue = AnalysisQueue()  # Use default Redis URL handling
    stats = await queue.get_queue_stats()
    
    logger.info(f"Current queue status: {stats}")
    return stats

async def main():
    """Main entry point for daily task creation"""
    try:
        result = await create_daily_analysis_tasks()
        logger.info(f"Task creation completed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in task creation: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 