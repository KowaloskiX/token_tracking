from datetime import datetime
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.tasks.analyses.analysis_task_producer import create_daily_analysis_tasks, create_analysis_tasks_for_date, get_queue_status
from minerva.tasks.analyses.analysis_queue import AnalysisQueue
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

class CreateTasksRequest(BaseModel):
    target_date: str

@router.post("/create-daily-tasks", response_model=Dict[str, Any])
async def create_daily_tasks(current_user: User = Depends(get_current_user)):
    """Create analysis tasks for today's date"""
    try:
        result = await create_daily_analysis_tasks()
        return {
            "status": "success",
            "message": "Daily analysis tasks created successfully",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error creating daily tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating daily tasks: {str(e)}")

@router.post("/create-tasks-for-date", response_model=Dict[str, Any])
async def create_tasks_for_date(
    request: CreateTasksRequest,
    current_user: User = Depends(get_current_user)
):
    """Create analysis tasks for a specific date"""
    try:
        result = await create_analysis_tasks_for_date(request.target_date)
        return {
            "status": "success",
            "message": f"Analysis tasks created for date {request.target_date}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error creating tasks for date {request.target_date}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating tasks: {str(e)}")

@router.get("/queue-status", response_model=Dict[str, Any])
async def get_queue_status_endpoint(current_user: User = Depends(get_current_user)):
    """Get current analysis queue status"""
    try:
        stats = await get_queue_status()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting queue status: {str(e)}")

@router.get("/queue-detailed-status", response_model=Dict[str, Any])
async def get_detailed_queue_status(current_user: User = Depends(get_current_user)):
    """Get detailed queue status including completed tasks"""
    try:
        queue = AnalysisQueue()  # Use default Redis URL handling
        
        # Get basic stats
        stats = await queue.get_queue_stats()
        
        # Get completed tasks from last 24 hours
        from datetime import timedelta
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        completed_tasks = await queue.get_completed_tasks_since(yesterday)
        
        return {
            "status": "success",
            "data": {
                "queue_stats": stats,
                "completed_tasks_count": len(completed_tasks),
                "completed_tasks": list(completed_tasks.keys())[:10]  # Show first 10 task IDs
            }
        }
    except Exception as e:
        logger.error(f"Error getting detailed queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting detailed status: {str(e)}")

@router.delete("/clear-queue", response_model=Dict[str, Any])
async def clear_analysis_queue(current_user: User = Depends(get_current_user)):
    """Clear the analysis queue (for testing purposes)"""
    try:
        queue = AnalysisQueue()  # Use default Redis URL handling
        
        # Clear the main queue
        await queue.redis.delete("analysis_queue")
        
        # Clear task metadata (be careful in production)
        keys = await queue.redis.keys("analysis_task:*")
        if keys:
            await queue.redis.delete(*keys)
        
        logger.info(f"Queue cleared by user {current_user.email}")
        
        return {
            "status": "success",
            "message": "Analysis queue cleared successfully",
            "cleared_keys": len(keys)
        }
    except Exception as e:
        logger.error(f"Error clearing queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing queue: {str(e)}") 