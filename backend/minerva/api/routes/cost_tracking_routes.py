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

# @router.get("/org/cost-summary")
# async def get_organization_cost_summary(
#     days: int = Query(30, description="Number of days to look back"),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get cost summary for the entire organization"""
#     if not current_user.org_id:
#         raise HTTPException(status_code=403, detail="Organization access required")
    
#     try:
#         end_date = datetime.utcnow()
#         start_date = end_date - timedelta(days=days)
        
#         # Get all users in the organization
#         org_users = await db.users.find({"org_id": current_user.org_id}).to_list(None)
#         user_ids = [ObjectId(str(user["_id"])) for user in org_users]
        
#         # Aggregate costs for all users in the organization with simplified schema
#         pipeline = [
#             {
#                 "$match": {
#                     "user_id": {"$in": user_ids},
#                     "started_at": {"$gte": start_date, "$lte": end_date},
#                     "status": "completed"
#                 }
#             },
#             {
#                 "$group": {
#                     "_id": "$user_id",
#                     "user_total_cost": {"$sum": "$total_cost_usd"},
#                     "user_ai_cost": {"$sum": "$total_ai_cost_usd"},
#                     "user_embedding_cost": {"$sum": "$total_embedding_cost_usd"},
#                     "user_total_tokens": {"$sum": "$total_tokens"},
#                     "user_ai_input_tokens": {"$sum": "$total_ai_input_tokens"},
#                     "user_ai_output_tokens": {"$sum": "$total_ai_output_tokens"},
#                     "user_embedding_tokens": {"$sum": "$total_embedding_tokens"},
#                     "user_total_analyses": {"$sum": 1}
#                 }
#             },
#             {
#                 "$lookup": {
#                     "from": "users",
#                     "localField": "_id",
#                     "foreignField": "_id",
#                     "as": "user_info"
#                 }
#             },
#             {
#                 "$unwind": "$user_info"
#             },
#             {
#                 "$project": {
#                     "_id": 1,
#                     "user_name": "$user_info.name",
#                     "user_email": "$user_info.email",
#                     "total_cost": "$user_total_cost",
#                     "ai_cost": "$user_ai_cost",
#                     "embedding_cost": "$user_embedding_cost",
#                     "total_tokens": "$user_total_tokens",
#                     "total_analyses": "$user_total_analyses"
#                 }
#             },
#             {
#                 "$sort": {"total_cost": -1}
#             }
#         ]
        
#         user_costs = await db.tender_analysis_costs.aggregate(pipeline).to_list(None)
        
#         # Calculate organization totals
#         org_total_cost = sum(user["total_cost"] for user in user_costs)
#         org_total_tokens = sum(user["total_tokens"] for user in user_costs)
#         org_total_analyses = sum(user["total_analyses"] for user in user_costs)
        
#         return {
#             "organization_id": current_user.org_id,
#             "period_start": start_date.isoformat(),
#             "period_end": end_date.isoformat(),
#             "total_cost_usd": org_total_cost,
#             "total_tokens": org_total_tokens,
#             "total_analyses": org_total_analyses,
#             "user_breakdown": user_costs
#         }
    
#     except Exception as e:
#         logger.error(f"Error getting organization cost summary: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

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

# Simplified test endpoint
# @router.post("/test-automatic-tracking")
# async def test_automatic_tracking(current_user: User = Depends(get_current_user)):
#     """Test endpoint to verify automatic cost tracking is working"""
#     try:
#         from minerva.core.services.cost_tracking_service import CostTrackingContext, AutomaticLLMCostWrapper
#         from minerva.core.models.request.ai import LLMSearchRequest
#         from uuid import uuid4
        
#         # Test the automatic cost tracking system
#         test_analysis_id = str(ObjectId())  # Generate a valid ObjectId for testing
        
#         async with CostTrackingContext.for_analysis(
#             user_id=str(current_user.id),
#             tender_analysis_id=test_analysis_id,
#             analysis_session_id=str(uuid4())
#         ):
#             # Make a simple LLM call with automatic cost tracking
#             request = LLMSearchRequest(
#                 query="What is 2+2?",
#                 llm={
#                     "provider": "openai",
#                     "model": "gpt-4o-mini",
#                     "temperature": 0,
#                     "max_tokens": 50,
#                     "system_message": "You are a helpful assistant.",
#                     "stream": False
#                 }
#             )
            
#             response = await AutomaticLLMCostWrapper.ask_llm(
#                 request=request,
#                 operation_type="test_operation",
#                 metadata={"test": True}
#             )
            
#             # The cost tracking context manager will automatically handle cost recording
            
#         return {
#             "message": "Automatic cost tracking test completed",
#             "response": response.llm_response if hasattr(response, 'llm_response') else str(response),
#             "test_analysis_id": test_analysis_id,
#             "note": "Check the cost tracking tables for recorded totals (no individual operations stored)"
#         }
        
#     except Exception as e:
#         logger.error(f"Error in automatic cost tracking test: {str(e)}")
#         return {"error": str(e)}