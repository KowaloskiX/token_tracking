import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from bson import ObjectId
from minerva.core.database.database import db
from minerva.core.models.cost_tracking import LLMModelPricing

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
    
    async def track_ai_operation(self, model_name: str, input_tokens: int, output_tokens: int, 
                                operation_type: str, metadata: Optional[Dict] = None):
        """Track an AI operation (LLM call) - accumulate totals only"""
        try:
            input_cost, output_cost, total_cost = AutomaticCostTracker.calculate_cost(
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
            
            logger.debug(f"Tracked AI operation: {operation_type} with {model_name}, "
                        f"${total_cost:.6f} ({input_tokens}+{output_tokens} tokens)")
            
        except Exception as e:
            logger.error(f"Error tracking AI operation: {str(e)}")
    
    async def track_embedding_operation(self, model_name: str, input_tokens: int, 
                                      operation_type: str, metadata: Optional[Dict] = None):
        """Track an embedding operation - accumulate totals only"""
        try:
            input_cost, _, total_cost = AutomaticCostTracker.calculate_cost(
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
            
            logger.debug(f"Tracked embedding operation: {operation_type} with {model_name}, "
                        f"${total_cost:.6f} ({input_tokens} tokens)")
            
        except Exception as e:
            logger.error(f"Error tracking embedding operation: {str(e)}")
    
    @classmethod
    def for_analysis(cls, user_id: str, tender_analysis_id: str, analysis_session_id: Optional[str] = None):
        """Create a cost tracking context for an analysis session"""
        if not analysis_session_id:
            analysis_session_id = str(uuid4())
        
        return cls(user_id, tender_analysis_id, analysis_session_id)


class AutomaticCostTracker:
    """Utilities for automatic cost tracking"""
    
    # Same pricing as your existing service
    MODEL_PRICING: Dict[str, LLMModelPricing] = {
        "gpt-4o": LLMModelPricing(
            model_name="gpt-4o",
            input_cost_per_million=5.00,
            output_cost_per_million=20.00
        ),
        "gpt-4o-mini": LLMModelPricing(
            model_name="gpt-4o-mini",
            input_cost_per_million=0.60,
            output_cost_per_million=2.40
        ),
        "gpt-4.1": LLMModelPricing(
            model_name="gpt-4.1",
            input_cost_per_million=2.00,
            output_cost_per_million=8.00
        ),
        "gpt-4.1-mini": LLMModelPricing(
            model_name="gpt-4.1-mini",
            input_cost_per_million=0.40,
            output_cost_per_million=1.60
        ),
        "gpt-4.1-nano": LLMModelPricing(
            model_name="gpt-4.1-nano",
            input_cost_per_million=0.10,
            output_cost_per_million=0.40
        ),
        "o3": LLMModelPricing(
            model_name="o3",
            input_cost_per_million=10.00,
            output_cost_per_million=40.00
        ),
        "o4-mini": LLMModelPricing(
            model_name="o4-mini",
            input_cost_per_million=1.10,
            output_cost_per_million=4.40
        ),
        "text-embedding-3-large": LLMModelPricing(
            model_name="text-embedding-3-large",
            input_cost_per_million=0.13,
            output_cost_per_million=0.0
        ),
    }
    
    @classmethod
    def calculate_cost(cls, model_name: str, input_tokens: int, output_tokens: int = 0):
        """Calculate cost for given tokens and model"""
        pricing = cls.MODEL_PRICING.get(model_name)
        if not pricing:
            logger.warning(f"No pricing found for model: {model_name}. Using default pricing.")
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
    def get_current_context(cls) -> Optional[CostTrackingContext]:
        """Get the current cost tracking context"""
        return _current_cost_context.get()
    
    @classmethod
    async def track_ai_call(cls, model_name: str, input_tokens: int, output_tokens: int, 
                           operation_type: str = "ai_features", metadata: Optional[Dict] = None):
        """Track an AI call if there's an active cost tracking context"""
        context = cls.get_current_context()
        if context:
            await context.track_ai_operation(
                model_name, input_tokens, output_tokens, operation_type, metadata
            )
    
    @classmethod  
    async def track_embedding_call(cls, model_name: str, input_tokens: int, 
                                  operation_type: str = "embedding", metadata: Optional[Dict] = None):
        """Track an embedding call if there's an active cost tracking context"""
        context = cls.get_current_context()
        if context:
            await context.track_embedding_operation(
                model_name, input_tokens, operation_type, metadata
            )


# Updated LLM Cost Wrapper
class AutomaticLLMCostWrapper:
    """LLM wrapper that automatically tracks costs using the current context"""
    
    @staticmethod
    async def ask_llm(request, operation_type: str = "ai_features", metadata: Optional[Dict] = None):
        """Make an LLM call with automatic cost tracking"""
        from minerva.core.services.llm_logic import ask_llm_logic
        
        try:
            response = await ask_llm_logic(request)
            
            # Auto-track costs if context exists
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.get('prompt_tokens', 0)
                output_tokens = response.usage.get('completion_tokens', 0)
                model_name = request.llm.model
                
                await AutomaticCostTracker.track_ai_call(
                    model_name, input_tokens, output_tokens, operation_type, metadata
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in LLM call: {str(e)}")
            raise
    
    @staticmethod
    async def llm_rag_search(request, tender_pinecone_id: Optional[str] = None, 
                           operation_type: str = "ai_features", metadata: Optional[Dict] = None):
        """Make an LLM RAG search with automatic cost tracking"""
        from minerva.core.services.llm_logic import llm_rag_search_logic
        
        try:
            response = await llm_rag_search_logic(request, tender_pinecone_id)
            
            # Auto-track costs if context exists
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.get('prompt_tokens', 0)
                output_tokens = response.usage.get('completion_tokens', 0)
                model_name = request.llm.model
                
                await AutomaticCostTracker.track_ai_call(
                    model_name, input_tokens, output_tokens, operation_type, metadata
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in LLM RAG call: {str(e)}")
            raise