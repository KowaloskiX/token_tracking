import logging
from typing import Any, Dict, Optional
from minerva.core.services.cost_tracking_service import CostTrackingService
from minerva.core.services.llm_logic import ask_llm_logic, llm_rag_search_logic
from minerva.core.models.request.ai import LLMSearchRequest, LLMRAGRequest

logger = logging.getLogger("minerva.llm_cost_wrapper")

class LLMCostWrapper:
    """Wrapper for LLM calls that automatically tracks costs"""
    
    @staticmethod
    async def ask_llm_with_cost_tracking(
        request: LLMSearchRequest,
        cost_record_id: str,
        operation_type: str,
        operation_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Wrapper for ask_llm_logic that tracks costs"""
        try:
            response = await ask_llm_logic(request)
            
            # Extract token usage from LLMSearchResponse
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.get('prompt_tokens', 0)
                output_tokens = response.usage.get('completion_tokens', 0)
                model_name = request.llm.model
                
                await CostTrackingService.track_operation_cost(
                    cost_record_id=cost_record_id,
                    operation_type=operation_type,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    operation_id=operation_id,
                    metadata=metadata
                )
                
                logger.info(f"Tracked cost for {operation_type}: {input_tokens} input + {output_tokens} output tokens")
            else:
                logger.warning(f"No usage information available for {operation_type}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in LLM call for {operation_type}: {str(e)}")
            raise
    
    @staticmethod
    async def llm_rag_search_with_cost_tracking(
        request: LLMRAGRequest,
        cost_record_id: str,
        operation_type: str,
        tender_pinecone_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Wrapper for llm_rag_search_logic that tracks costs"""
        try:
            response = await llm_rag_search_logic(request, tender_pinecone_id)
            
            # Extract token usage from LLMSearchResponse
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.get('prompt_tokens', 0)
                output_tokens = response.usage.get('completion_tokens', 0)
                model_name = request.llm.model
                
                await CostTrackingService.track_operation_cost(
                    cost_record_id=cost_record_id,
                    operation_type=operation_type,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    operation_id=operation_id,
                    metadata=metadata or {}
                )
                
                logger.info(f"Tracked cost for {operation_type}: {input_tokens} input + {output_tokens} output tokens")
            else:
                logger.warning(f"No usage information available for {operation_type}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in LLM RAG call for {operation_type}: {str(e)}")
            raise