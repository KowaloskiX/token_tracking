from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from minerva.core.database.database import db
from minerva.core.models.user import User
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.config.constants import UserRole
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Active users list for reliable analytics (excluding inactive users)
ACTIVE_USER_EMAILS = [
    "daniel.heina@ondre.pl",
    "biuro@hydratec.pl", 
    "office@lafrentz.pl",
    "jasek@jasek-transport.pl",
    "sklep@dtpsoftware.pl",
    "jan.borowiak@foliarex.com.pl",
    "marcin.krusze@neomedpolska.pl",
    "agnieszka.czolnik@esinvest.pl",
    "bartlomiejsosna1@gmail.com",
    "m.mielcarek@mph.net.pl",
    "kontakt@proton-polska.pl",
    "fgoeldner@annfil.pl",
    "test@account.ai",
    "pawel.zawislak@ironmountain.com",
    "abasinska@hammer.pl",
    "bartek@senda.com.pl",
    "inwestycje@kznrail.pl",
    "boguslaw.groblewski@arisonconstruction.pl"
]

async def get_active_user_ids():
    """Get ObjectIds for active users to filter analytics queries"""
    active_users = await db.users.find({
        "email": {"$in": ACTIVE_USER_EMAILS}
    }, {"_id": 1}).to_list(None)
    return [user["_id"] for user in active_users]

class MetricsPeriod(BaseModel):
    daily: float  # Average per business day
    weekly: float  # Weekly total (actual if <7 days, projected if ≥7 days)
    monthly: float  # Monthly total (actual if <14 days, projected if ≥14 days)

class UserEngagementMetrics(BaseModel):
    total_users: int
    active_users: MetricsPeriod
    new_registrations: MetricsPeriod
    user_activation_rate: float  # Percentage of users who marked analyses as active in period
    retention_rate: MetricsPeriod  # Users active in each period

class TenderAnalysisMetrics(BaseModel):
    total_analyses: int
    active_analyses: int
    analyses_created: MetricsPeriod
    tender_results_generated: MetricsPeriod
    tender_open_rate: float  # Percentage of results that were opened
    avg_time_to_open_hours: float  # Average time from created to opened
    avg_criteria_per_analysis: float

class AssistantMetrics(BaseModel):
    total_assistants: int
    assistants_created: MetricsPeriod
    avg_assistants_per_user: float
    assistant_sharing_rate: float  # Percentage of assistants that are shared

class ConversationMetrics(BaseModel):
    total_conversations: int
    conversations_started: MetricsPeriod  # New conversations (based on first message date)
    total_messages: int
    messages_sent: MetricsPeriod  # Actual message count in period
    avg_messages_per_conversation: float
    avg_conversation_length_days: float

class OrganizationMetrics(BaseModel):
    total_organizations: int
    avg_users_per_org: float
    enterprise_adoption_rate: float  # Users with org_id / total users
    collaboration_score: float  # Average assigned users across analyses/assistants

class PlatformHealthMetrics(BaseModel):
    token_consumption: MetricsPeriod
    avg_daily_tokens_per_user: float
    file_uploads: MetricsPeriod
    successful_analysis_rate: float  # Non-filtered results / total attempts

class ComprehensiveAnalytics(BaseModel):
    period_start: datetime
    period_end: datetime
    user_engagement: UserEngagementMetrics
    tender_analysis: TenderAnalysisMetrics
    assistants: AssistantMetrics
    conversations: ConversationMetrics
    organizations: OrganizationMetrics
    platform_health: PlatformHealthMetrics

@router.get("/analytics/comprehensive", response_model=ComprehensiveAnalytics)
async def get_comprehensive_analytics(
    days_back: Optional[int] = Query(None, description="Number of days to look back for analytics (alternative to date range)"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive platform analytics for VC presentation"""
    
    # Only allow admin users to access analytics
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only admin users can access analytics"
        )
    
    try:
        # Handle date range logic
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                # Set end date to end of day
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                days_back = (end_dt - start_dt).days + 1
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        elif start_date or end_date:
            raise HTTPException(status_code=400, detail="Both start_date and end_date must be provided together")
        else:
            # Default to days_back logic
            days_back = days_back or 30
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(days=days_back)
        
        # Get active user IDs for filtering
        active_user_ids = await get_active_user_ids()
        
        # Helper function to calculate period averages (excluding weekends for daily)
        def calculate_period_metrics(total_count: int, days: int) -> MetricsPeriod:
            # Calculate business days (approximately 5/7 of total days)
            business_days = max((days * 5) // 7, 1)
            
            # Daily average (based on business days)
            daily = round(total_count / business_days, 2)
            
            # For weekly/monthly: only extrapolate if we have sufficient data
            # Otherwise, show actual counts or reasonable estimates
            if days >= 7:
                # We have at least a week of data - can extrapolate weekly
                weekly = round((total_count / max(days, 1)) * 7, 2)
            else:
                # Less than a week - show actual count, don't extrapolate
                weekly = round(total_count, 2)
            
            if days >= 14:
                # We have at least 2 weeks of data - can extrapolate monthly
                monthly = round((total_count / max(days, 1)) * 30, 2)
            else:
                # Less than 2 weeks - show actual count, don't extrapolate
                monthly = round(total_count, 2)
                
            return MetricsPeriod(daily=daily, weekly=weekly, monthly=monthly)
        
        # === USER ENGAGEMENT METRICS ===
        total_users = len(active_user_ids)
        
        # Active users (users with any activity in period - including tender opens)
        # First get users with token activity or new registrations
        token_active_users = await db.users.find({
            "_id": {"$in": active_user_ids},
            "$or": [
                {"last_token_reset": {"$gte": start_dt}},
                {"created_at": {"$gte": start_dt}}
            ]
        }, {"_id": 1}).to_list(None)
        
        # Then get users who opened tenders in the period
        tender_active_users = await db.tender_analysis_results.distinct(
            "user_id", 
            {
                "user_id": {"$in": active_user_ids},
                "opened_at": {"$gte": start_dt, "$exists": True, "$ne": None}
            }
        )
        
        # Combine both activity types (remove duplicates)
        all_active_user_ids = set([user["_id"] for user in token_active_users] + tender_active_users)
        active_users_count = len(all_active_user_ids)
        
        # New registrations (from active users list)
        new_users_count = await db.users.count_documents({
            "_id": {"$in": active_user_ids},
            "created_at": {"$gte": start_dt}
        })
        
        # User activation rate (users who marked tender analyses as active in the period)
        # Count users who have at least one active tender analysis
        users_with_active_analyses = await db.tender_analysis.distinct(
            "user_id",
            {
                "user_id": {"$in": active_user_ids},
                "active": True,
                "$or": [
                    {"created_at": {"$gte": start_dt}},  # Created in period
                    {"updated_at": {"$gte": start_dt}}   # Or updated to active in period
                ]
            }
        )
        
        activated_users = len(users_with_active_analyses)
        activation_rate = round((activated_users / max(total_users, 1)) * 100, 2)
        
        user_engagement = UserEngagementMetrics(
            total_users=total_users,
            active_users=calculate_period_metrics(active_users_count, days_back),
            new_registrations=calculate_period_metrics(new_users_count, days_back),
            user_activation_rate=activation_rate,
            retention_rate=calculate_period_metrics(active_users_count, days_back)
        )
        
        # === TENDER ANALYSIS METRICS ===
        total_analyses = await db.tender_analysis.count_documents({
            "user_id": {"$in": active_user_ids}
        })
        active_analyses = await db.tender_analysis.count_documents({
            "user_id": {"$in": active_user_ids},
            "active": True
        })
        
        analyses_created = await db.tender_analysis.count_documents({
            "user_id": {"$in": active_user_ids},
            "created_at": {"$gte": start_dt}
        })
        
        tender_results_created = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids},
            "created_at": {"$gte": start_dt}
        })
        
        # Tender open rate calculation
        total_results = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids}
        })
        opened_results = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids},
            "opened_at": {"$exists": True, "$ne": None}
        })
        open_rate = round((opened_results / max(total_results, 1)) * 100, 2)
        
        # Average time to open calculation
        pipeline_time_to_open = [
            {
                "$match": {
                    "user_id": {"$in": active_user_ids},
                    "opened_at": {"$exists": True, "$ne": None},
                    "created_at": {"$exists": True}
                }
            },
            {
                "$project": {
                    "time_diff_hours": {
                        "$divide": [
                            {"$subtract": ["$opened_at", "$created_at"]},
                            1000 * 60 * 60  # Convert milliseconds to hours
                        ]
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_time_to_open": {"$avg": "$time_diff_hours"}
                }
            }
        ]
        
        time_to_open_result = await db.tender_analysis_results.aggregate(pipeline_time_to_open).to_list(1)
        avg_time_to_open = round(time_to_open_result[0]["avg_time_to_open"], 2) if time_to_open_result else 0
        
        # Average criteria per analysis
        pipeline_criteria = [
            {"$match": {"user_id": {"$in": active_user_ids}}},
            {"$project": {"criteria_count": {"$size": "$criteria"}}},
            {"$group": {"_id": None, "avg_criteria": {"$avg": "$criteria_count"}}}
        ]
        criteria_result = await db.tender_analysis.aggregate(pipeline_criteria).to_list(1)
        avg_criteria = round(criteria_result[0]["avg_criteria"], 2) if criteria_result else 0
        
        tender_analysis_metrics = TenderAnalysisMetrics(
            total_analyses=total_analyses,
            active_analyses=active_analyses,
            analyses_created=calculate_period_metrics(analyses_created, days_back),
            tender_results_generated=calculate_period_metrics(tender_results_created, days_back),
            tender_open_rate=open_rate,
            avg_time_to_open_hours=avg_time_to_open,
            avg_criteria_per_analysis=avg_criteria
        )
        
        # === ASSISTANT METRICS ===
        # Convert user IDs to strings for assistants collection (owner_id is string)
        active_user_id_strings = [str(uid) for uid in active_user_ids]
        
        total_assistants = await db.assistants.count_documents({
            "owner_id": {"$in": active_user_id_strings}
        })
        
        assistants_created = await db.assistants.count_documents({
            "owner_id": {"$in": active_user_id_strings},
            "created_at": {"$gte": start_dt}
        })
        
        avg_assistants_per_user = round(total_assistants / max(total_users, 1), 2)
        
        shared_assistants = await db.assistants.count_documents({
            "owner_id": {"$in": active_user_id_strings},
            "shared_with": {"$exists": True, "$ne": [], "$not": {"$size": 0}}
        })
        sharing_rate = round((shared_assistants / max(total_assistants, 1)) * 100, 2)
        
        assistant_metrics = AssistantMetrics(
            total_assistants=total_assistants,
            assistants_created=calculate_period_metrics(assistants_created, days_back),
            avg_assistants_per_user=avg_assistants_per_user,
            assistant_sharing_rate=sharing_rate
        )
        
        # === CONVERSATION METRICS ===
        total_conversations = await db.conversations.count_documents({
            "user_id": {"$in": active_user_id_strings}
        })
        
        # Conversations created in period (based on first message date)
        conversations_created = await db.conversations.count_documents({
            "user_id": {"$in": active_user_id_strings},
            "messages.0.created_at": {"$gte": start_dt}  # First message created in period
        })
        
        # Count total messages
        pipeline_messages = [
            {"$match": {"user_id": {"$in": active_user_id_strings}}},
            {"$project": {"message_count": {"$size": "$messages"}}},
            {"$group": {"_id": None, "total_messages": {"$sum": "$message_count"}}}
        ]
        messages_result = await db.conversations.aggregate(pipeline_messages).to_list(1)
        total_messages = messages_result[0]["total_messages"] if messages_result else 0
        
        # Count actual messages created in period
        pipeline_messages_in_period = [
            {
                "$match": {
                    "user_id": {"$in": active_user_id_strings},
                    "messages": {"$exists": True, "$ne": []}
                }
            },
            {
                "$project": {
                    "messages_in_period": {
                        "$size": {
                            "$filter": {
                                "input": "$messages",
                                "cond": {"$gte": ["$$this.created_at", start_dt]}
                            }
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_messages_in_period": {"$sum": "$messages_in_period"}
                }
            }
        ]
        
        messages_in_period_result = await db.conversations.aggregate(pipeline_messages_in_period).to_list(1)
        messages_in_period = messages_in_period_result[0]["total_messages_in_period"] if messages_in_period_result else 0
        
        avg_messages_per_conversation = round(total_messages / max(total_conversations, 1), 2)
        
        # Average conversation length
        pipeline_conversation_length = [
            {
                "$match": {
                    "user_id": {"$in": active_user_id_strings},
                    "messages": {"$exists": True, "$ne": []},
                    "last_updated": {"$exists": True}
                }
            },
            {
                "$project": {
                    "first_message_date": {"$arrayElemAt": ["$messages.created_at", 0]},
                    "last_updated": "$last_updated"
                }
            },
            {
                "$project": {
                    "length_days": {
                        "$divide": [
                            {"$subtract": ["$last_updated", "$first_message_date"]},
                            1000 * 60 * 60 * 24  # Convert to days
                        ]
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_length_days": {"$avg": "$length_days"}
                }
            }
        ]
        
        conversation_length_result = await db.conversations.aggregate(pipeline_conversation_length).to_list(1)
        avg_conversation_length = round(conversation_length_result[0]["avg_length_days"], 2) if conversation_length_result else 0
        
        conversation_metrics = ConversationMetrics(
            total_conversations=total_conversations,
            conversations_started=calculate_period_metrics(conversations_created, days_back),
            total_messages=total_messages,
            messages_sent=calculate_period_metrics(messages_in_period, days_back),
            avg_messages_per_conversation=avg_messages_per_conversation,
            avg_conversation_length_days=avg_conversation_length
        )
        
        # === ORGANIZATION METRICS ===
        total_orgs = await db.organizations.count_documents({}) if "organizations" in await db.list_collection_names() else 0
        
        users_with_org = await db.users.count_documents({
            "_id": {"$in": active_user_ids},
            "org_id": {"$exists": True, "$ne": None, "$ne": ""}
        })
        
        enterprise_adoption = round((users_with_org / max(total_users, 1)) * 100, 2)
        avg_users_per_org = round(users_with_org / max(total_orgs, 1), 2)
        
        # Collaboration score - average assigned users
        pipeline_collaboration_analysis = [
            {"$match": {"user_id": {"$in": active_user_ids}}},
            {"$project": {"assigned_count": {"$size": {"$ifNull": ["$assigned_users", []]}}}},
            {"$group": {"_id": None, "avg_assigned": {"$avg": "$assigned_count"}}}
        ]
        
        pipeline_collaboration_assistants = [
            {"$match": {"owner_id": {"$in": active_user_id_strings}}},
            {"$project": {"assigned_count": {"$size": {"$ifNull": ["$assigned_users", []]}}}},
            {"$group": {"_id": None, "avg_assigned": {"$avg": "$assigned_count"}}}
        ]
        
        analysis_collaboration = await db.tender_analysis.aggregate(pipeline_collaboration_analysis).to_list(1)
        assistant_collaboration = await db.assistants.aggregate(pipeline_collaboration_assistants).to_list(1)
        
        collaboration_score = round((
            (analysis_collaboration[0]["avg_assigned"] if analysis_collaboration else 0) +
            (assistant_collaboration[0]["avg_assigned"] if assistant_collaboration else 0)
        ) / 2, 2)
        
        organization_metrics = OrganizationMetrics(
            total_organizations=total_orgs,
            avg_users_per_org=avg_users_per_org,
            enterprise_adoption_rate=enterprise_adoption,
            collaboration_score=collaboration_score
        )
        
        # === PLATFORM HEALTH METRICS ===
        # Token consumption
        pipeline_tokens = [
            {"$match": {"_id": {"$in": active_user_ids}}},
            {"$group": {"_id": None, "total_tokens": {"$sum": "$total_tokens"}}}
        ]
        tokens_result = await db.users.aggregate(pipeline_tokens).to_list(1)
        total_tokens = tokens_result[0]["total_tokens"] if tokens_result else 0
        
        avg_daily_tokens_per_user = round((total_tokens / max(total_users, 1)) / max(days_back, 1), 2)
        
        # File uploads (from tender analysis results)
        files_uploaded = await db.tender_analysis_results.aggregate([
            {"$match": {
                "user_id": {"$in": active_user_ids},
                "created_at": {"$gte": start_dt}
            }},
            {"$project": {"file_count": {"$size": {"$ifNull": ["$uploaded_files", []]}}}},
            {"$group": {"_id": None, "total_files": {"$sum": "$file_count"}}}
        ]).to_list(1)
        
        total_files_uploaded = files_uploaded[0]["total_files"] if files_uploaded else 0
        
        # Success rate calculation
        total_analysis_attempts = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids}
        })
        filtered_attempts = await db.filtered_tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_id_strings}
        })
        successful_analyses = total_analysis_attempts
        success_rate = round((successful_analyses / max(total_analysis_attempts + filtered_attempts, 1)) * 100, 2)
        
        platform_health = PlatformHealthMetrics(
            token_consumption=calculate_period_metrics(total_tokens, days_back),
            avg_daily_tokens_per_user=avg_daily_tokens_per_user,
            file_uploads=calculate_period_metrics(total_files_uploaded, days_back),
            successful_analysis_rate=success_rate
        )
        
        return ComprehensiveAnalytics(
            period_start=start_dt,
            period_end=end_dt,
            user_engagement=user_engagement,
            tender_analysis=tender_analysis_metrics,
            assistants=assistant_metrics,
            conversations=conversation_metrics,
            organizations=organization_metrics,
            platform_health=platform_health
        )
        
    except Exception as e:
        logger.error(f"Error generating comprehensive analytics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating analytics: {str(e)}"
        )

@router.get("/analytics/user-cohorts", response_model=Dict[str, Any])
async def get_user_cohort_analysis(
    current_user: User = Depends(get_current_user)
):
    """Get user cohort analysis for retention insights"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Group users by registration month and track their activity over time
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"}
                    },
                    "users": {"$push": "$_id"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id.year": 1, "_id.month": 1}},
            {"$limit": 12}  # Last 12 months
        ]
        
        cohorts = await db.users.aggregate(pipeline).to_list(None)
        
        # For each cohort, calculate retention in subsequent months
        cohort_data = []
        for cohort in cohorts:
            cohort_month = f"{cohort['_id']['year']}-{cohort['_id']['month']:02d}"
            
            # Calculate retention for each subsequent month
            retention_data = {"cohort": cohort_month, "size": cohort["count"]}
            
            for months_later in range(1, 7):  # Track 6 months of retention
                retention_date = datetime(cohort["_id"]["year"], cohort["_id"]["month"], 1) + timedelta(days=30 * months_later)
                
                # Count users from this cohort who were active in the retention month
                active_users = await db.users.count_documents({
                    "_id": {"$in": cohort["users"]},
                    "last_token_reset": {"$gte": retention_date, "$lt": retention_date + timedelta(days=30)}
                })
                
                retention_data[f"month_{months_later}"] = {
                    "count": active_users,
                    "rate": round((active_users / cohort["count"]) * 100, 2)
                }
            
            cohort_data.append(retention_data)
        
        return {"cohorts": cohort_data}
        
    except Exception as e:
        logger.error(f"Error generating cohort analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating cohort analysis: {str(e)}")

@router.get("/analytics/power-users", response_model=List[Dict[str, Any]])
async def get_power_user_analysis(
    limit: int = Query(20, description="Number of top users to return"),
    current_user: User = Depends(get_current_user)
):
    """Identify and analyze power users across the platform"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Complex aggregation to score users across multiple dimensions
        pipeline = [
            {
                "$lookup": {
                    "from": "tender_analysis",
                    "localField": "_id",
                    "foreignField": "user_id",
                    "as": "analyses"
                }
            },
            {
                "$lookup": {
                    "from": "assistants",
                    "localField": "_id",
                    "foreignField": "owner_id",
                    "as": "assistants"
                }
            },
            {
                "$lookup": {
                    "from": "conversations",
                    "localField": "_id",
                    "foreignField": "user_id",
                    "as": "conversations"
                }
            },
            {
                "$project": {
                    "email": 1,
                    "name": 1,
                    "created_at": 1,
                    "total_tokens": 1,
                    "org_id": 1,
                    "analysis_count": {"$size": "$analyses"},
                    "assistant_count": {"$size": "$assistants"},
                    "conversation_count": {"$size": "$conversations"},
                    "active_analyses": {
                        "$size": {
                            "$filter": {
                                "input": "$analyses",
                                "cond": {"$eq": ["$$this.active", True]}
                            }
                        }
                    }
                }
            },
            {
                "$addFields": {
                    "power_score": {
                        "$add": [
                            {"$multiply": ["$analysis_count", 3]},
                            {"$multiply": ["$assistant_count", 2]},
                            {"$multiply": ["$conversation_count", 1]},
                            {"$multiply": ["$total_tokens", 0.001]}
                        ]
                    }
                }
            },
            {"$sort": {"power_score": -1}},
            {"$limit": limit}
        ]
        
        power_users = await db.users.aggregate(pipeline).to_list(None)
        
        # Clean up ObjectId serialization
        for user in power_users:
            user["_id"] = str(user["_id"])
            
        return power_users
        
    except Exception as e:
        logger.error(f"Error generating power user analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating power user analysis: {str(e)}")

@router.get("/analytics/feature-adoption", response_model=Dict[str, Any])
async def get_feature_adoption_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get detailed feature adoption and usage metrics"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        total_users = await db.users.count_documents({})
        
        # Feature adoption rates
        features = {
            "tender_analysis": await db.users.count_documents({
                "_id": {"$in": [
                    analysis["user_id"] async for analysis in db.tender_analysis.find({}, {"user_id": 1})
                ]}
            }),
            "assistants": await db.users.count_documents({
                "_id": {"$in": [
                    ObjectId(assistant["owner_id"]) async for assistant in db.assistants.find({}, {"owner_id": 1})
                ]}
            }),
            "conversations": await db.users.count_documents({
                "_id": {"$in": [
                    ObjectId(conv["user_id"]) async for conv in db.conversations.find({}, {"user_id": 1})
                ]}
            }),
            "file_uploads": await db.users.count_documents({
                "_id": {"$in": [
                    result["user_id"] async for result in db.tender_analysis_results.find(
                        {"uploaded_files": {"$exists": True, "$ne": []}}, 
                        {"user_id": 1}
                    )
                ]}
            })
        }
        
        # Calculate adoption rates
        adoption_rates = {
            feature: {
                "count": count,
                "rate": round((count / max(total_users, 1)) * 100, 2)
            }
            for feature, count in features.items()
        }
        
        # Multi-feature users
        multi_feature_pipeline = [
            {
                "$lookup": {
                    "from": "tender_analysis",
                    "localField": "_id",
                    "foreignField": "user_id",
                    "as": "analyses"
                }
            },
            {
                "$lookup": {
                    "from": "assistants",
                    "localField": "_id",  
                    "foreignField": "owner_id",
                    "as": "assistants"
                }
            },
            {
                "$lookup": {
                    "from": "conversations",
                    "localField": "_id",
                    "foreignField": "user_id", 
                    "as": "conversations"
                }
            },
            {
                "$project": {
                    "feature_count": {
                        "$sum": [
                            {"$cond": [{"$gt": [{"$size": "$analyses"}, 0]}, 1, 0]},
                            {"$cond": [{"$gt": [{"$size": "$assistants"}, 0]}, 1, 0]},
                            {"$cond": [{"$gt": [{"$size": "$conversations"}, 0]}, 1, 0]}
                        ]
                    }
                }
            },
            {
                "$group": {
                    "_id": "$feature_count",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        multi_feature_users = await db.users.aggregate(multi_feature_pipeline).to_list(None)
        
        return {
            "total_users": total_users,
            "feature_adoption": adoption_rates,
            "multi_feature_distribution": {
                result["_id"]: result["count"] for result in multi_feature_users
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating feature adoption metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating feature adoption: {str(e)}")

class QuickMetrics(BaseModel):
    """Simplified metrics for quick dashboard display"""
    timestamp: datetime
    total_users: int
    monthly_active_users: int
    total_tender_analyses: int
    total_assistants: int
    total_conversations: int
    daily_avg_new_users: float
    daily_avg_tender_results: float
    daily_avg_messages: float
    tender_open_rate_percent: float
    enterprise_adoption_percent: float

@router.get("/analytics/quick", response_model=QuickMetrics)
async def get_quick_metrics(
    days_back: Optional[int] = Query(None, description="Number of days to look back (alternative to date range)"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    current_user: User = Depends(get_current_user)
):
    """Get simplified metrics for quick dashboard display"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Handle date range logic
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                days_back = (end_dt - start_dt).days + 1
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        elif start_date or end_date:
            raise HTTPException(status_code=400, detail="Both start_date and end_date must be provided together")
        else:
            days_back = days_back or 30
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(days=days_back)
        
        # Get active user IDs for filtering
        active_user_ids = await get_active_user_ids()
        active_user_id_strings = [str(uid) for uid in active_user_ids]
        
        # Basic counts
        total_users = len(active_user_ids)
        total_analyses = await db.tender_analysis.count_documents({
            "user_id": {"$in": active_user_ids}
        })
        total_assistants = await db.assistants.count_documents({
            "owner_id": {"$in": active_user_id_strings}
        })
        total_conversations = await db.conversations.count_documents({
            "user_id": {"$in": active_user_id_strings}
        })
        
        # Active users (users with activity in period - including tender opens)
        # Users with token activity or new registrations
        token_active_users = await db.users.find({
            "_id": {"$in": active_user_ids},
            "$or": [
                {"last_token_reset": {"$gte": start_dt}},
                {"created_at": {"$gte": start_dt}}
            ]
        }, {"_id": 1}).to_list(None)
        
        # Users who opened tenders in period
        tender_active_users = await db.tender_analysis_results.distinct(
            "user_id", 
            {
                "user_id": {"$in": active_user_ids},
                "opened_at": {"$gte": start_dt, "$exists": True, "$ne": None}
            }
        )
        
        # Combine both activity types
        all_active_ids = set([user["_id"] for user in token_active_users] + tender_active_users)
        active_users_count = len(all_active_ids)
        
        # New users in period
        new_users = await db.users.count_documents({
            "_id": {"$in": active_user_ids},
            "created_at": {"$gte": start_dt}
        })
        daily_avg_new_users = round(new_users / max(days_back, 1), 2)
        
        # Tender results in period
        tender_results = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids},
            "created_at": {"$gte": start_dt}
        })
        daily_avg_tender_results = round(tender_results / max(days_back, 1), 2)
        
        # Messages in period (approximate)
        conversations_with_recent_messages = await db.conversations.count_documents({
            "user_id": {"$in": active_user_id_strings},
            "last_updated": {"$gte": start_dt}
        })
        daily_avg_messages = round(conversations_with_recent_messages / max(days_back, 1), 2)  # Rough approximation
        
        # Tender open rate
        total_results = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids}
        })
        opened_results = await db.tender_analysis_results.count_documents({
            "user_id": {"$in": active_user_ids},
            "opened_at": {"$exists": True, "$ne": None}
        })
        open_rate = round((opened_results / max(total_results, 1)) * 100, 2)
        
        # Enterprise adoption
        users_with_org = await db.users.count_documents({
            "_id": {"$in": active_user_ids},
            "org_id": {"$exists": True, "$ne": None, "$ne": ""}
        })
        enterprise_adoption = round((users_with_org / max(total_users, 1)) * 100, 2)
        
        return QuickMetrics(
            timestamp=end_dt,
            total_users=total_users,
            monthly_active_users=active_users_count,
            total_tender_analyses=total_analyses,
            total_assistants=total_assistants,
            total_conversations=total_conversations,
            daily_avg_new_users=daily_avg_new_users,
            daily_avg_tender_results=daily_avg_tender_results,
            daily_avg_messages=daily_avg_messages,
            tender_open_rate_percent=open_rate,
            enterprise_adoption_percent=enterprise_adoption
        )
        
    except Exception as e:
        logger.error(f"Error generating quick metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating quick metrics: {str(e)}")

@router.get("/analytics/daily-activity", response_model=Dict[str, Any])
async def get_daily_activity_breakdown(
    days_back: Optional[int] = Query(None, description="Number of days to analyze (alternative to date range)"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    current_user: User = Depends(get_current_user)
):
    """Get detailed daily activity breakdown to understand user engagement patterns"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Handle date range logic
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                days_back = (end_dt - start_dt).days + 1
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        elif start_date or end_date:
            raise HTTPException(status_code=400, detail="Both start_date and end_date must be provided together")
        else:
            days_back = days_back or 7
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(days=days_back)
        
        active_user_ids = await get_active_user_ids()
        active_user_id_strings = [str(uid) for uid in active_user_ids]
        
        # Daily tender opening activity
        pipeline_daily_opens = [
            {
                "$match": {
                    "user_id": {"$in": active_user_ids},
                    "opened_at": {"$gte": start_dt, "$exists": True, "$ne": None}
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$opened_at"},
                        "month": {"$month": "$opened_at"},
                        "day": {"$dayOfMonth": "$opened_at"}
                    },
                    "unique_users": {"$addToSet": "$user_id"},
                    "total_opens": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "date": {
                        "$dateFromParts": {
                            "year": "$_id.year",
                            "month": "$_id.month",
                            "day": "$_id.day"
                        }
                    },
                    "unique_users": {"$size": "$unique_users"},
                    "total_opens": 1
                }
            },
            {"$sort": {"date": -1}}
        ]
        
        daily_activity = await db.tender_analysis_results.aggregate(pipeline_daily_opens).to_list(None)
        
        # Recent active users summary
        recent_active_users = await db.tender_analysis_results.distinct(
            "user_id", 
            {
                "user_id": {"$in": active_user_ids},
                "opened_at": {"$gte": start_dt, "$exists": True, "$ne": None}
            }
        )
        
        # Get user emails for the active users
        active_user_details = await db.users.find({
            "_id": {"$in": recent_active_users}
        }, {"email": 1, "_id": 1}).to_list(None)
        
        return {
            "period_days": days_back,
            "total_active_users_in_period": len(recent_active_users),
            "active_user_emails": [user["email"] for user in active_user_details],
            "daily_breakdown": [
                {
                    "date": item["date"].strftime("%Y-%m-%d"),
                    "day_of_week": item["date"].strftime("%A"),
                    "unique_users_active": item["unique_users"],
                    "total_tender_opens": item["total_opens"]
                } for item in daily_activity
            ],
            "summary": {
                "avg_daily_active_users": round(len(recent_active_users) / max(days_back, 1), 2),
                "avg_business_days_active_users": round(len(recent_active_users) / max((days_back * 5) // 7, 1), 2),
                "total_tender_opens": sum(item["total_opens"] for item in daily_activity)
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating daily activity breakdown: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating daily activity breakdown: {str(e)}")

@router.get("/analytics/users-with-active-tenders", response_model=List[Dict[str, Any]])
async def get_users_with_active_tenders(
    current_user: User = Depends(get_current_user)
):
    """Get all users who have either created at least one project (assistant) OR activated at least one public tender analysis"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Get all user IDs who have at least one active tender analysis result
        users_with_active_tenders = await db.tender_analysis_results.distinct(
            "user_id",
            {"status": "active"}
        )
        
        # Get all user IDs who have created at least one assistant (project)
        users_with_assistants_str = await db.assistants.distinct("owner_id")
        users_with_assistants = [ObjectId(user_id) for user_id in users_with_assistants_str if ObjectId.is_valid(user_id)]
        
        # Combine both sets of users (union)
        all_relevant_users = list(set(users_with_active_tenders + users_with_assistants))
        
        if not all_relevant_users:
            return []
        
        # Get user details for these users
        users_details = await db.users.find({
            "_id": {"$in": all_relevant_users}
        }, {
            "_id": 1,
            "email": 1,
            "name": 1,
            "created_at": 1,
            "org_id": 1,
            "total_tokens": 1
        }).to_list(None)
        
        # Get count of active tender analysis results for each user
        # First get all active tender analysis results
        all_active_results = await db.tender_analysis_results.find(
            {"status": "active"},
            {"user_id": 1, "created_at": 1}
        ).to_list(None)
        
        # Count them by user_id
        tender_counts_dict = {}
        for result in all_active_results:
            user_id_str = str(result["user_id"])
            if user_id_str not in tender_counts_dict:
                tender_counts_dict[user_id_str] = {
                    "active_tender_count": 0,
                    "latest_creation": result["created_at"]
                }
            tender_counts_dict[user_id_str]["active_tender_count"] += 1
            if result["created_at"] > tender_counts_dict[user_id_str]["latest_creation"]:
                tender_counts_dict[user_id_str]["latest_creation"] = result["created_at"]
        
        # Get count of assistants (projects) for each user
        user_id_strings = [str(uid) for uid in all_relevant_users]
        pipeline_assistant_counts = [
            {
                "$match": {
                    "owner_id": {"$in": user_id_strings}
                }
            },
            {
                "$group": {
                    "_id": "$owner_id",
                    "projects_count": {"$sum": 1},
                    "latest_project_creation": {"$max": "$created_at"}
                }
            }
        ]
        
        assistant_counts = await db.assistants.aggregate(pipeline_assistant_counts).to_list(None)
        assistant_counts_dict = {item["_id"]: item for item in assistant_counts}
        
        # Get count of opened tender analysis results for each user
        all_opened_results = await db.tender_analysis_results.find(
            {
                "user_id": {"$in": all_relevant_users},
                "opened_at": {"$exists": True, "$ne": None}
            },
            {"user_id": 1}
        ).to_list(None)
        
        # Count opened results by user_id
        opened_counts_dict = {}
        for result in all_opened_results:
            user_id_str = str(result["user_id"])
            if user_id_str not in opened_counts_dict:
                opened_counts_dict[user_id_str] = 0
            opened_counts_dict[user_id_str] += 1
        
        # Combine user details with tender analysis, assistant, and opened results counts
        result = []
        for user in users_details:
            user_id_str = str(user["_id"])
            tender_info = tender_counts_dict.get(user_id_str, {})
            assistant_info = assistant_counts_dict.get(user_id_str, {})
            opened_count = opened_counts_dict.get(user_id_str, 0)
            
            result.append({
                "email": user["email"],
                "name": user.get("name"),
                "total_tokens": user.get("total_tokens", 0),
                "active_tender_analyses_count": tender_info.get("active_tender_count", 0),
                "projects_count": assistant_info.get("projects_count", 0),
                "total_opened_results": opened_count,
            })
        
        # Sort by token usage (descending)
        result.sort(key=lambda x: x["total_tokens"], reverse=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting users with active tenders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting users with active tenders: {str(e)}")