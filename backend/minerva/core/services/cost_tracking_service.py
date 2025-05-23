import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from bson import ObjectId
from minerva.core.database.database import db
from minerva.core.models.cost_tracking import (
    LLMModelPricing, OperationCost, TenderAnalysisCost, UserCostSummary
)

logger = logging.getLogger("minerva.cost_tracking")

class CostTrackingService:
    """Service for tracking and calculating LLM costs"""
    
    # Model pricing (as of 2024 - update these regularly)
    MODEL_PRICING = {
        "gpt-4o": LLMModelPricing(
            model_name="gpt-4o",
            input_cost_per_million=2.50,
            output_cost_per_million=10.00
        ),
        "gpt-4o-mini": LLMModelPricing(
            model_name="gpt-4o-mini",
            input_cost_per_million=0.15,
            output_cost_per_million=0.60
        ),
        "gpt-4.1": LLMModelPricing(  # Assuming this is a typo for gpt-4-turbo
            model_name="gpt-4.1",
            input_cost_per_million=10.00,
            output_cost_per_million=30.00
        ),
        "o4-mini": LLMModelPricing(  # Assuming this is o1-mini
            model_name="o4-mini",
            input_cost_per_million=3.00,
            output_cost_per_million=12.00
        ),
        "text-embedding-3-large": LLMModelPricing(
            model_name="text-embedding-3-large",
            input_cost_per_million=0.13,
            output_cost_per_million=0.0  # Embeddings don't have output tokens
        )
    }
    
    @classmethod
    def calculate_cost(cls, model_name: str, input_tokens: int, output_tokens: int = 0) -> Tuple[float, float, float]:
        """
        Calculate cost for given tokens and model.
        Returns: (input_cost, output_cost, total_cost) in USD
        """
        pricing = cls.MODEL_PRICING.get(model_name)
        if not pricing:
            logger.warning(f"No pricing found for model: {model_name}. Using default pricing.")
            # Default pricing (conservative estimate)
            pricing = LLMModelPricing(
                model_name=model_name,
                input_cost_per_million=5.00,
                output_cost_per_million=15.00
            )
        
        input_cost = (input_tokens / 1_000_000) * pricing.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * pricing.output_cost_per_million
        total_cost = input_cost + output_cost
        
        return input_cost, output_cost, total_cost
    
    @classmethod
    async def create_analysis_cost_record(cls, user_id: str, tender_analysis_id: str, 
                                        tender_id: str, analysis_session_id: str) -> str:
        """Create a new cost tracking record for a tender analysis"""
        cost_record = TenderAnalysisCost(
            user_id=ObjectId(user_id),
            tender_analysis_id=ObjectId(tender_analysis_id),
            tender_id=tender_id,
            analysis_session_id=analysis_session_id
        )
        
        result = await db.tender_analysis_costs.insert_one(cost_record.dict(by_alias=True))
        logger.info(f"Created cost tracking record: {result.inserted_id}")
        return str(result.inserted_id)
    
    @classmethod
    async def track_operation_cost(cls, cost_record_id: str, operation_type: str, 
                                 model_name: str, input_tokens: int, output_tokens: int = 0,
                                 operation_id: Optional[str] = None, metadata: Optional[Dict] = None):
        """Track cost for a specific operation"""
        input_cost, output_cost, total_cost = cls.calculate_cost(model_name, input_tokens, output_tokens)
        
        operation_cost = OperationCost(
            operation_type=operation_type,
            operation_id=operation_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            metadata=metadata
        )
        
        # Update the cost record
        update_operations = {
            f"${operation_type}_costs": operation_cost.dict(),
            "$inc": {
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "total_cost_usd": total_cost
            }
        }
        
        await db.tender_analysis_costs.update_one(
            {"_id": ObjectId(cost_record_id)},
            {"$push": update_operations}
        )
        
        # Also update user's total tokens (existing functionality)
        cost_record = await db.tender_analysis_costs.find_one({"_id": ObjectId(cost_record_id)})
        if cost_record:
            from minerva.core.middleware.token_tracking import update_user_token_usage
            await update_user_token_usage(str(cost_record["user_id"]), input_tokens + output_tokens)
        
        logger.info(f"Tracked {operation_type} cost: ${total_cost:.6f} ({input_tokens + output_tokens} tokens)")
    
    @classmethod
    async def complete_analysis_cost_record(cls, cost_record_id: str, status: str = "completed"):
        """Mark a cost record as completed"""
        await db.tender_analysis_costs.update_one(
            {"_id": ObjectId(cost_record_id)},
            {"$set": {
                "completed_at": datetime.utcnow(),
                "status": status
            }}
        )
    
    @classmethod
    async def get_user_cost_summary(cls, user_id: str, days: int = 30) -> UserCostSummary:
        """Get cost summary for a user over the specified period"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "user_id": ObjectId(user_id),
                    "started_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_cost": {"$sum": "$total_cost_usd"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_analyses": {"$sum": 1},
                    "search_cost": {"$sum": {"$sum": "$search_costs.total_cost_usd"}},
                    "ai_filtering_cost": {"$sum": {"$sum": "$ai_filtering_costs.total_cost_usd"}},
                    "file_extraction_cost": {"$sum": {"$sum": "$file_extraction_costs.total_cost_usd"}},
                    "criteria_analysis_cost": {"$sum": {"$sum": "$criteria_analysis_costs.total_cost_usd"}},
                    "description_generation_cost": {"$sum": {"$sum": "$description_generation_costs.total_cost_usd"}},
                    "description_filtering_cost": {"$sum": {"$sum": "$description_filtering_costs.total_cost_usd"}}
                }
            }
        ]
        
        result = await db.tender_analysis_costs.aggregate(pipeline).to_list(1)
        
        if result:
            data = result[0]
            return UserCostSummary(
                user_id=ObjectId(user_id),
                period_start=start_date,
                period_end=end_date,
                search_cost=data.get("search_cost", 0),
                ai_filtering_cost=data.get("ai_filtering_cost", 0),
                file_extraction_cost=data.get("file_extraction_cost", 0),
                criteria_analysis_cost=data.get("criteria_analysis_cost", 0),
                description_generation_cost=data.get("description_generation_cost", 0),
                description_filtering_cost=data.get("description_filtering_cost", 0),
                total_cost_usd=data.get("total_cost", 0),
                total_tokens=data.get("total_tokens", 0),
                total_analyses=data.get("total_analyses", 0)
            )
        else:
            return UserCostSummary(
                user_id=ObjectId(user_id),
                period_start=start_date,
                period_end=end_date
            )
    
    @classmethod
    async def get_detailed_analysis_cost(cls, cost_record_id: str) -> Optional[TenderAnalysisCost]:
        """Get detailed cost breakdown for a specific analysis"""
        cost_record = await db.tender_analysis_costs.find_one({"_id": ObjectId(cost_record_id)})
        if cost_record:
            return TenderAnalysisCost(**cost_record)
        return None