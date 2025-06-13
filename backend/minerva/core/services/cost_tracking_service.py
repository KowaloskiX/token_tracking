import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from bson import ObjectId
from minerva.core.database.database import db

logger = logging.getLogger("minerva.cost_tracking")

# Context variable to store current cost tracking session
_current_cost_context: ContextVar[Optional['CostTrackingContext']] = ContextVar('cost_context', default=None)

class CostTrackingContext:
    """Context manager for automatic cost tracking during analysis sessions"""
    
    def __init__(self, user_id: str, tender_analysis_id: str, analysis_session_id: str):
        self.user_id = user_id
        self.tender_analysis_id = tender_analysis_id
        self.analysis_session_id = analysis_session_id
        self.cost_record_id: Optional[str] = None
        self.total_ai_cost = 0.0
        self.total_embedding_cost = 0.0
        self.total_ai_input_tokens = 0
        self.total_ai_output_tokens = 0
        self.total_embedding_tokens = 0
    
    async def __aenter__(self):
        """Initialize cost tracking for this analysis session"""
        try:
            # Create simple cost record in database - only totals, no operation arrays
            cost_record = {
                "user_id": ObjectId(self.user_id),
                "tender_analysis_id": ObjectId(self.tender_analysis_id),
                "analysis_session_id": self.analysis_session_id,
                "started_at": datetime.utcnow(),
                "status": "in_progress",
                "total_ai_cost_usd": 0.0,
                "total_embedding_cost_usd": 0.0,
                "total_ai_input_tokens": 0,
                "total_ai_output_tokens": 0,
                "total_embedding_tokens": 0
            }
            
            result = await db.tender_analysis_costs.insert_one(cost_record)
            self.cost_record_id = str(result.inserted_id)
            
            # Set this context as current
            _current_cost_context.set(self)
            
            logger.info(f"Started cost tracking session: {self.cost_record_id}")
            return self
            
        except Exception as e:
            logger.error(f"Error starting cost tracking: {str(e)}")
            # Continue without cost tracking rather than failing
            return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Complete cost tracking for this analysis session"""
        try:
            if self.cost_record_id:
                status = "failed" if exc_type else "completed"
                total_cost = self.total_ai_cost + self.total_embedding_cost
                total_tokens = self.total_ai_input_tokens + self.total_ai_output_tokens + self.total_embedding_tokens
                
                # Update final totals only - no operation arrays
                await db.tender_analysis_costs.update_one(
                    {"_id": ObjectId(self.cost_record_id)},
                    {"$set": {
                        "completed_at": datetime.utcnow(),
                        "status": status,
                        "total_ai_cost_usd": self.total_ai_cost,
                        "total_embedding_cost_usd": self.total_embedding_cost,
                        "total_ai_input_tokens": self.total_ai_input_tokens,
                        "total_ai_output_tokens": self.total_ai_output_tokens,
                        "total_embedding_tokens": self.total_embedding_tokens,
                        "total_cost_usd": total_cost,
                        "total_tokens": total_tokens
                    }}
                )
                
                # Update user's total token usage
                from minerva.core.middleware.token_tracking import update_user_token_usage
                if total_tokens > 0:
                    await update_user_token_usage(self.user_id, total_tokens)
                
                logger.info(f"Completed cost tracking session: {self.cost_record_id}, "
                          f"AI: ${self.total_ai_cost:.6f} ({self.total_ai_input_tokens}+{self.total_ai_output_tokens} tokens), "
                          f"Embedding: ${self.total_embedding_cost:.6f} ({self.total_embedding_tokens} tokens)")
        
        except Exception as e:
            logger.error(f"Error completing cost tracking: {str(e)}")
        
        finally:
            # Clear context
            _current_cost_context.set(None)
    
    async def track_ai_operation(self, model_name: str, input_tokens: int, output_tokens: int):
        """Track an AI operation (LLM call) - accumulate totals only"""
        try:
            # Import here to avoid circular imports
            from minerva.core.services.llm_logic import calculate_cost
            
            input_cost, output_cost, total_cost = calculate_cost(
                model_name, input_tokens, output_tokens
            )
            
            # Accumulate totals in memory
            self.total_ai_cost += total_cost
            self.total_ai_input_tokens += input_tokens
            self.total_ai_output_tokens += output_tokens
            
            # Update database totals directly - no operation arrays
            if self.cost_record_id:
                await db.tender_analysis_costs.update_one(
                    {"_id": ObjectId(self.cost_record_id)},
                    {"$inc": {
                        "total_ai_cost_usd": total_cost,
                        "total_ai_input_tokens": input_tokens,
                        "total_ai_output_tokens": output_tokens,
                        "total_cost_usd": total_cost,
                        "total_tokens": input_tokens + output_tokens
                    }}
                )
            
            logger.debug(f"Tracked AI operation: {model_name}, "
                        f"${total_cost:.6f} ({input_tokens}+{output_tokens} tokens)")
            
        except Exception as e:
            logger.error(f"Error tracking AI operation: {str(e)}")
    
    async def track_embedding_operation(self, model_name: str, input_tokens: int):
        """Track an embedding operation - accumulate totals only"""
        try:
            # Import here to avoid circular imports
            from minerva.core.services.llm_logic import calculate_cost
            
            input_cost, _, total_cost = calculate_cost(
                model_name, input_tokens, 0
            )
            
            # Accumulate totals in memory  
            self.total_embedding_cost += total_cost
            self.total_embedding_tokens += input_tokens
            
            # Update database totals directly - no operation arrays
            if self.cost_record_id:
                await db.tender_analysis_costs.update_one(
                    {"_id": ObjectId(self.cost_record_id)},
                    {"$inc": {
                        "total_embedding_cost_usd": total_cost,
                        "total_embedding_tokens": input_tokens,
                        "total_cost_usd": total_cost,
                        "total_tokens": input_tokens
                    }}
                )
            
            logger.debug(f"Tracked embedding operation: {model_name}, "
                        f"${total_cost:.6f} ({input_tokens} tokens)")
            
        except Exception as e:
            logger.error(f"Error tracking embedding operation: {str(e)}")
    
    @classmethod
    def for_analysis(cls, user_id: str, tender_analysis_id: str, analysis_session_id: Optional[str] = None):
        """Create a cost tracking context for an analysis session"""
        if not analysis_session_id:
            analysis_session_id = str(uuid4())
        
        return cls(user_id, tender_analysis_id, analysis_session_id)