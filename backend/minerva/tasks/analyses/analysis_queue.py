import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional
import redis.asyncio as redis
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def get_redis_url() -> str:
    """Get Redis URL with environment-specific fallbacks"""
    # Try environment variable first (production)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url
    
    # Development fallbacks
    if os.getenv("ENVIRONMENT") == "development" or os.path.exists("/.dockerenv") == False:
        # Local development
        return "redis://localhost:6379/1"
    else:
        # Docker development
        return "redis://redis-analysis:6379/1"

class AnalysisQueue:
    def __init__(self, redis_url: str = None):
        if redis_url is None:
            redis_url = get_redis_url()
        
        logger.info(f"Connecting to Redis at: {redis_url}")
        self.redis = redis.from_url(redis_url)
    
    async def enqueue_analysis(self, analysis_doc: Dict[str, Any], target_date: str) -> str:
        """Enqueue a complete analysis for processing"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "analysis_doc": analysis_doc,
            "target_date": target_date,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        # Single queue for all analyses - workers pick up as available
        await self.redis.lpush("analysis_queue", json.dumps(task, cls=CustomJSONEncoder))
        await self.redis.hset(f"analysis_task:{task_id}", mapping={
            "task_id": task_id,
            "analysis_doc": json.dumps(analysis_doc, cls=CustomJSONEncoder),
            "target_date": target_date,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending"
        })
        await self.redis.expire(f"analysis_task:{task_id}", 86400)  # 24h expiry
        
        logger.info(f"Enqueued analysis {analysis_doc['_id']} as task {task_id}")
        return task_id
    
    async def get_next_analysis(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get next analysis to process"""
        task_data = await self.redis.brpop("analysis_queue", timeout=10)
        
        if task_data:
            task = json.loads(task_data[1])
            task_id = task["task_id"]
            
            # Mark as processing
            await self.redis.hset(f"analysis_task:{task_id}", mapping={
                "status": "processing",
                "worker_id": worker_id,
                "started_at": datetime.utcnow().isoformat()
            })
            
            return task
        
        return None
    
    async def complete_analysis(self, task_id: str, result: Dict[str, Any], analysis_stats: Optional[Dict[str, Any]] = None):
        """Mark analysis as completed with detailed statistics"""
        completion_data = {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "tenders_processed": result.get("total_tenders_analyzed", 0),
            "initial_ai_filter_id": result.get("initial_ai_filter_id") or "",
            "description_filter_id": result.get("description_filter_id") or ""
        }
        
        # Add detailed analysis statistics if provided
        if analysis_stats:
            completion_data["analysis_stats"] = json.dumps(analysis_stats, cls=CustomJSONEncoder)
        
        await self.redis.hset(f"analysis_task:{task_id}", mapping=completion_data)
        logger.info(f"Analysis task {task_id} completed with {result.get('total_tenders_analyzed', 0)} tenders")
    
    async def fail_analysis(self, task_id: str, error: str):
        """Mark analysis as failed"""
        await self.redis.hset(f"analysis_task:{task_id}", mapping={
            "status": "failed",
            "failed_at": datetime.utcnow().isoformat(),
            "error": error
        })
        logger.error(f"Analysis task {task_id} failed: {error}")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        queue_length = await self.redis.llen("analysis_queue")
        
        # Get task status counts
        keys = await self.redis.keys("analysis_task:*")
        stats = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        
        for key in keys:
            task_data = await self.redis.hgetall(key)
            status = task_data.get("status", "unknown")
            if status in stats:
                stats[status] += 1
        
        stats["queue_length"] = queue_length
        return stats
    
    async def get_completed_tasks_since(self, since_timestamp: str) -> Dict[str, Dict[str, Any]]:
        """Get all completed analysis tasks since a timestamp"""
        keys = await self.redis.keys("analysis_task:*")
        completed_tasks = {}
        
        for key in keys:
            task_data = await self.redis.hgetall(key)
            if (task_data.get("status") == "completed" and 
                task_data.get("completed_at", "") > since_timestamp):
                task_id = key.decode().split(":")[1]
                # Convert bytes to strings
                completed_tasks[task_id] = {k.decode() if isinstance(k, bytes) else k: 
                                          v.decode() if isinstance(v, bytes) else v 
                                          for k, v in task_data.items()}
        
        return completed_tasks
    
    async def get_all_completed_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all completed analysis tasks for today's summary"""
        keys = await self.redis.keys("analysis_task:*")
        completed_tasks = {}
        
        for key in keys:
            task_data = await self.redis.hgetall(key)
            if task_data.get("status") == "completed":
                task_id = key.decode().split(":")[1] if isinstance(key, bytes) else key.split(":")[1]
                # Convert bytes to strings and handle analysis_stats JSON
                task_dict = {}
                for k, v in task_data.items():
                    key_str = k.decode() if isinstance(k, bytes) else k
                    value_str = v.decode() if isinstance(v, bytes) else v
                    
                    # Parse analysis_stats JSON if present
                    if key_str == "analysis_stats" and value_str:
                        try:
                            task_dict[key_str] = json.loads(value_str)
                        except json.JSONDecodeError:
                            task_dict[key_str] = {}
                    else:
                        task_dict[key_str] = value_str
                
                completed_tasks[task_id] = task_dict
        
        return completed_tasks 