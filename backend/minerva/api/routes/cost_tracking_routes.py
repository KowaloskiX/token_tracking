# Updated cost_tracking_routes.py for new automatic cost tracking

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.core.database.database import db
from bson import ObjectId
import logging

router = APIRouter()
logger = logging.getLogger("minerva.cost_tracking")

@router.get("/user/cost-summary")
async def get_user_cost_summary(
    days: int = Query(30, description="Number of days to look back"),
    current_user: User = Depends(get_current_user)
):
    """Get cost summary for the current user over the specified period"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Updated aggregation pipeline for new simplified schema
        pipeline = [
            {
                "$match": {
                    "user_id": current_user.id,
                    "started_at": {"$gte": start_date, "$lte": end_date},
                    "status": "completed"  # Only completed analyses
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_ai_cost": {"$sum": "$total_ai_cost_usd"},
                    "total_embedding_cost": {"$sum": "$total_embedding_cost_usd"},
                    "total_cost": {"$sum": "$total_cost_usd"},
                    "total_ai_input_tokens": {"$sum": "$total_ai_input_tokens"},
                    "total_ai_output_tokens": {"$sum": "$total_ai_output_tokens"},
                    "total_embedding_tokens": {"$sum": "$total_embedding_tokens"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_analyses": {"$sum": 1}
                }
            }
        ]
        
        result = await db.tender_analysis_costs.aggregate(pipeline).to_list(1)
        
        if result:
            data = result[0]
            return {
                "user_id": str(current_user.id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_cost_usd": data.get("total_cost", 0.0),
                "ai_cost_usd": data.get("total_ai_cost", 0.0),
                "embedding_cost_usd": data.get("total_embedding_cost", 0.0),
                "total_tokens": data.get("total_tokens", 0),
                "ai_input_tokens": data.get("total_ai_input_tokens", 0),
                "ai_output_tokens": data.get("total_ai_output_tokens", 0),
                "embedding_tokens": data.get("total_embedding_tokens", 0),
                "total_analyses": data.get("total_analyses", 0)
            }
        else:
            return {
                "user_id": str(current_user.id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_cost_usd": 0.0,
                "ai_cost_usd": 0.0,
                "embedding_cost_usd": 0.0,
                "total_tokens": 0,
                "ai_input_tokens": 0,
                "ai_output_tokens": 0,
                "embedding_tokens": 0,
                "total_analyses": 0
            }
    except Exception as e:
        logger.error(f"Error getting cost summary for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis/{analysis_id}/costs")
async def get_analysis_costs(
    analysis_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed cost breakdown for all tenders in a specific analysis"""
    try:
        # Check if analysis exists and belongs to user or their organization
        query = {"_id": ObjectId(analysis_id), "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
        
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Get cost records for this analysis with simplified schema
        cost_records = await db.tender_analysis_costs.find({
            "tender_analysis_id": ObjectId(analysis_id),
            "status": {"$in": ["completed", "failed"]}  # Include both completed and failed
        }).to_list(None)
        
        # Format response for simplified schema
        formatted_records = []
        for record in cost_records:
            formatted_record = {
                "id": str(record["_id"]),
                "analysis_session_id": record.get("analysis_session_id"),
                "status": record.get("status"),
                "started_at": record.get("started_at"),
                "completed_at": record.get("completed_at"),
                "total_cost_usd": record.get("total_cost_usd", 0.0),
                "ai_cost_usd": record.get("total_ai_cost_usd", 0.0),
                "embedding_cost_usd": record.get("total_embedding_cost_usd", 0.0),
                "total_tokens": record.get("total_tokens", 0),
                "ai_input_tokens": record.get("total_ai_input_tokens", 0),
                "ai_output_tokens": record.get("total_ai_output_tokens", 0),
                "embedding_tokens": record.get("total_embedding_tokens", 0)
            }
            formatted_records.append(formatted_record)
        
        return {
            "analysis_id": analysis_id,
            "cost_records": formatted_records,
            "summary": {
                "total_records": len(formatted_records),
                "total_cost_usd": sum(r["total_cost_usd"] for r in formatted_records),
                "total_tokens": sum(r["total_tokens"] for r in formatted_records)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis costs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cost-trends")
async def get_cost_trends(
    days: int = Query(30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user)
):
    """Get cost trends over time for the user"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Group costs by day with simplified schema
        pipeline = [
            {
                "$match": {
                    "user_id": current_user.id,
                    "started_at": {"$gte": start_date, "$lte": end_date},
                    "status": "completed"
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$started_at"
                        }
                    },
                    "daily_cost": {"$sum": "$total_cost_usd"},
                    "daily_ai_cost": {"$sum": "$total_ai_cost_usd"},
                    "daily_embedding_cost": {"$sum": "$total_embedding_cost_usd"},
                    "daily_tokens": {"$sum": "$total_tokens"},
                    "daily_ai_input_tokens": {"$sum": "$total_ai_input_tokens"},
                    "daily_ai_output_tokens": {"$sum": "$total_ai_output_tokens"},
                    "daily_embedding_tokens": {"$sum": "$total_embedding_tokens"},
                    "daily_analyses": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]
        
        daily_costs = await db.tender_analysis_costs.aggregate(pipeline).to_list(None)
        
        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "daily_breakdown": [
                {
                    "date": item["_id"],
                    "total_cost": item["daily_cost"],
                    "ai_cost": item["daily_ai_cost"],
                    "embedding_cost": item["daily_embedding_cost"],
                    "total_tokens": item["daily_tokens"],
                    "ai_input_tokens": item["daily_ai_input_tokens"],
                    "ai_output_tokens": item["daily_ai_output_tokens"],
                    "embedding_tokens": item["daily_embedding_tokens"],
                    "analyses": item["daily_analyses"]
                }
                for item in daily_costs
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting cost trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))