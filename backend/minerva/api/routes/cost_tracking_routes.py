from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.core.models.cost_tracking import TenderAnalysisCost, UserCostSummary
from minerva.core.services.cost_tracking_service import CostTrackingService
from bson import ObjectId
import logging

router = APIRouter()
logger = logging.getLogger("minerva.cost_tracking")

@router.get("/user/cost-summary", response_model=UserCostSummary)
async def get_user_cost_summary(
    days: int = Query(30, description="Number of days to look back"),
    current_user: User = Depends(get_current_user)
):
    """Get cost summary for the current user over the specified period"""
    try:
        summary = await CostTrackingService.get_user_cost_summary(
            user_id=str(current_user.id),
            days=days
        )
        return summary
    except Exception as e:
        logger.error(f"Error getting cost summary for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis/{analysis_id}/costs", response_model=List[TenderAnalysisCost])
async def get_analysis_costs(
    analysis_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed cost breakdown for all tenders in a specific analysis"""
    try:
        # Verify user has access to the analysis
        from minerva.core.database.database import db
        analysis = await db.tender_analysis.find_one({
            "_id": ObjectId(analysis_id),
            "$or": [
                {"user_id": current_user.id},
                {"org_id": current_user.org_id} if current_user.org_id else {}
            ]
        })
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Get cost records for this analysis
        cost_records = await db.tender_analysis_costs.find({
            "tender_analysis_id": ObjectId(analysis_id)
        }).to_list(None)
        
        return [TenderAnalysisCost(**record) for record in cost_records]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis costs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tender/{tender_id}/cost", response_model=TenderAnalysisCost)
async def get_tender_cost_details(
    tender_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed cost breakdown for a specific tender analysis"""
    try:
        cost_record = await CostTrackingService.get_detailed_analysis_cost(tender_id)
        
        if not cost_record:
            raise HTTPException(status_code=404, detail="Cost record not found")
        
        # Verify user has access
        if str(cost_record.user_id) != str(current_user.id) and (
            not current_user.org_id or 
            not await _user_has_org_access(current_user, cost_record.user_id)
        ):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return cost_record
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tender cost details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/org/cost-summary")
async def get_organization_cost_summary(
    days: int = Query(30, description="Number of days to look back"),
    current_user: User = Depends(get_current_user)
):
    """Get cost summary for the entire organization"""
    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="Organization access required")
    
    try:
        from minerva.core.database.database import db
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all users in the organization
        org_users = await db.users.find({"org_id": current_user.org_id}).to_list(None)
        user_ids = [ObjectId(str(user["_id"])) for user in org_users]
        
        # Aggregate costs for all users in the organization
        pipeline = [
            {
                "$match": {
                    "user_id": {"$in": user_ids},
                    "started_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": "$user_id",
                    "user_total_cost": {"$sum": "$total_cost_usd"},
                    "user_total_tokens": {"$sum": "$total_tokens"},
                    "user_total_analyses": {"$sum": 1}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$project": {
                    "_id": 1,
                    "user_name": "$user_info.name",
                    "user_email": "$user_info.email",
                    "total_cost": "$user_total_cost",
                    "total_tokens": "$user_total_tokens",
                    "total_analyses": "$user_total_analyses"
                }
            },
            {
                "$sort": {"total_cost": -1}
            }
        ]
        
        user_costs = await db.tender_analysis_costs.aggregate(pipeline).to_list(None)
        
        # Calculate organization totals
        org_total_cost = sum(user["total_cost"] for user in user_costs)
        org_total_tokens = sum(user["total_tokens"] for user in user_costs)
        org_total_analyses = sum(user["total_analyses"] for user in user_costs)
        
        return {
            "organization_id": current_user.org_id,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_cost_usd": org_total_cost,
            "total_tokens": org_total_tokens,
            "total_analyses": org_total_analyses,
            "user_breakdown": user_costs
        }
    
    except Exception as e:
        logger.error(f"Error getting organization cost summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cost-trends")
async def get_cost_trends(
    days: int = Query(30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user)
):
    """Get cost trends over time for the user"""
    try:
        from minerva.core.database.database import db
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Group costs by day
        pipeline = [
            {
                "$match": {
                    "user_id": current_user.id,
                    "started_at": {"$gte": start_date, "$lte": end_date}
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
                    "daily_tokens": {"$sum": "$total_tokens"},
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
                    "cost": item["daily_cost"],
                    "tokens": item["daily_tokens"],
                    "analyses": item["daily_analyses"]
                }
                for item in daily_costs
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting cost trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _user_has_org_access(current_user: User, target_user_id: ObjectId) -> bool:
    """Check if the current user has access to view another user's costs (same org)"""
    if not current_user.org_id:
        return False
    
    from minerva.core.database.database import db
    target_user = await db.users.find_one({"_id": target_user_id})
    return (target_user and 
            target_user.get("org_id") == current_user.org_id)