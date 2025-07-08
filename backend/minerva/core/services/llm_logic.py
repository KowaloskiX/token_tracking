from asyncio.log import logger
from fastapi import HTTPException
import json
import os
from typing import Union
from contextvars import ContextVar
from typing import Optional, Dict, Any
from minerva.core.models.request.ai import LLMSearchRequest, LLMSearchResponse, SearchResult
from minerva.core.services.llm_providers.anthropic import AnthropicLLM
from minerva.core.services.llm_providers.google_gemini import GeminiLLM
from minerva.core.services.llm_providers.response import LLMResponse
from minerva.core.services.llm_providers.openai import OpenAILLM
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool

# Configuration for universal LLM fallback
ENABLE_LLM_FALLBACK = os.getenv("ENABLE_LLM_FALLBACK", "true").lower() == "true"
FALLBACK_PROVIDER = os.getenv("FALLBACK_PROVIDER", "openai")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4.1-mini")

MODEL_PRICING = {
    # OpenAI models
    "gpt-4o": {"input_cost_per_million": 2.50, "output_cost_per_million": 10.00},
    "gpt-4o-mini": {"input_cost_per_million": 0.15, "output_cost_per_million": 0.60},
    "gpt-4.1": {"input_cost_per_million": 2.00, "output_cost_per_million": 8.00},
    "gpt-4.1-mini": {"input_cost_per_million": 0.40, "output_cost_per_million": 1.60},
    "gpt-4.1-nano": {"input_cost_per_million": 0.10, "output_cost_per_million": 0.40},
    "o3": {"input_cost_per_million": 2.00, "output_cost_per_million": 8.00},
    "o4-mini": {"input_cost_per_million": 1.10, "output_cost_per_million": 4.40},
    
    # Gemini models
    "gemini-2.5-flash-preview-05-20": {"input_cost_per_million": 0.30, "output_cost_per_million": 2.50},
    "gemini-2.5-flash": {"input_cost_per_million": 0.30, "output_cost_per_million": 2.50},
    "gemini-2.5-pro": {"input_cost_per_million": 1.25, "output_cost_per_million": 10.00},
    "gemini-1.5-pro": {"input_cost_per_million": 3.50, "output_cost_per_million": 10.50},
    "gemini-1.5-flash": {"input_cost_per_million": 0.075, "output_cost_per_million": 0.30},
    "gemini-2.0-flash-exp": {"input_cost_per_million": 0.075, "output_cost_per_million": 0.30},
    "gemini-1.5-pro-002": {"input_cost_per_million": 1.25, "output_cost_per_million": 5.00},
    "gemini-1.5-flash-002": {"input_cost_per_million": 0.075, "output_cost_per_million": 0.30},
    
    # Embedding models
    "text-embedding-3-large": {"input_cost_per_million": 0.13, "output_cost_per_million": 0.0},
    "text-embedding-3-small": {"input_cost_per_million": 0.02, "output_cost_per_million": 0.0},
    "text-embedding-ada-002": {"input_cost_per_million": 0.10, "output_cost_per_million": 0.0},
    
    # Anthropic Claude models
    "claude-4-opus":   {"input_cost_per_million": 15.00, "output_cost_per_million": 75.00},
    "claude-4-sonnet": {"input_cost_per_million":  3.00, "output_cost_per_million": 15.00},
    "claude-3.5-sonnet": {"input_cost_per_million": 3.00, "output_cost_per_million": 15.00},
    "claude-3.5-haiku":  {"input_cost_per_million": 0.80, "output_cost_per_million": 4.00},
    "claude-3-opus":   {"input_cost_per_million": 15.00, "output_cost_per_million": 75.00},
    "claude-3-sonnet": {"input_cost_per_million":  3.00, "output_cost_per_million": 15.00},
    "claude-3-haiku":  {"input_cost_per_million": 0.25, "output_cost_per_million": 1.25},
}


def _is_provider_error(error: Exception, provider: str) -> bool:
    """Check if the error indicates a provider failure that should trigger fallback."""
    error_str = str(error).lower()
    
    # Common error keywords that suggest provider issues
    fallback_keywords = [
        "quota", "resource_exhausted", "exceeded your current quota",
        "rate limit", "too many requests", "429", "503", "500",
        "service unavailable", "timeout", "connection", "api key",
        "invalid_api_key", "insufficient_quota", "model_not_found"
    ]
    
    # Provider-specific error patterns
    provider_patterns = {
        "google": ["resource_exhausted", "quota", "429"],
        "openai": ["insufficient_quota", "rate_limit_exceeded", "invalid_api_key"],
        "anthropic": ["rate_limit_exceeded", "overloaded_error", "invalid_api_key"]
    }
    
    # Check for general fallback keywords
    matched_keywords = [keyword for keyword in fallback_keywords if keyword in error_str]
    if matched_keywords:
        logger.info(f"Provider error detected for {provider} - matched keywords: {matched_keywords}")
        return True
        
    # Check for provider-specific patterns
    if provider in provider_patterns:
        matched_patterns = [pattern for pattern in provider_patterns[provider] if pattern in error_str]
        if matched_patterns:
            logger.info(f"Provider error detected for {provider} - matched provider-specific patterns: {matched_patterns}")
            return True
    
    logger.info(f"Error not classified as provider error for {provider}: {type(error).__name__}: {str(error)}")
    return False

def _is_gemini_rate_limit_error(error: Exception) -> bool:
    """Check if the error is specifically a Gemini rate limit error that should trigger API key rotation."""
    error_str = str(error).lower()
    gemini_rate_limit_indicators = [
        "quota", "resource_exhausted", "rate limit", "429", 
        "too many requests", "quota exceeded"
    ]
    matched_indicators = [indicator for indicator in gemini_rate_limit_indicators if indicator in error_str]
    
    if matched_indicators:
        logger.info(f"Gemini rate limit error detected - matched indicators: {matched_indicators}")
        return True
    
    logger.debug(f"Error not classified as Gemini rate limit error: {type(error).__name__}: {str(error)}")
    return False

def _get_llm_instance(provider: str, model: str, request: LLMSearchRequest):
    """Get an LLM instance for the specified provider and model."""
    llm_classes = {
        "openai": OpenAILLM,
        "google": GeminiLLM, 
        "anthropic": AnthropicLLM
    }
    
    if provider not in llm_classes:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    
    llm_cls = llm_classes[provider]
    return llm_cls(
        model=model,
        stream=request.llm.stream,
        temperature=request.llm.temperature,
        max_tokens=request.llm.max_tokens,
        tools=request.llm.tools,
        instructions=request.llm.system_message,
        response_format=request.llm.response_format
    )

async def _try_llm_with_universal_fallback(
    request: LLMSearchRequest, 
    messages: list, 
    vector_search_results: list
) -> Union[LLMSearchResponse, object]:
    """
    Try primary LLM provider first, with enhanced Gemini API key rotation, then fallback to configured provider if needed.
    
    For Gemini providers:
    1. First tries GEMINI_API_KEY
    2. On rate limit, automatically rotates to GEMINI_API_KEY_2 within the GeminiLLM class
    3. Only falls back to OpenAI after all Gemini API keys are exhausted
    
    For other providers:
    - Uses the standard fallback mechanism directly
    """
    
    primary_provider = request.llm.provider
    primary_model = request.llm.model
    
    try:
        # Try primary provider first
        primary_llm = _get_llm_instance(primary_provider, primary_model, request)
        response = await primary_llm.generate_response(messages)
        
        # Add metadata about actual provider/model used
        if hasattr(response, '__dict__') and not hasattr(response, 'provider'):
            response.provider = primary_provider
            response.model = primary_model
        
        if not request.llm.stream:
            # Non-streaming response - return the raw response for cost tracking
            return response
        else:
            # Streaming response: return the generator as-is
            return response
            
    except Exception as error:
        # Log the specific error details for debugging
        logger.error(f"Primary provider {primary_provider}:{primary_model} failed with error: {error}", exc_info=True)
        
        # Special handling for Gemini rate limit errors - try API key rotation first
        if primary_provider == "google" and _is_gemini_rate_limit_error(error):
            logger.warning(f"Gemini rate limit detected, API key rotation was already attempted in GeminiLLM class")
            # The GeminiLLM class already handles API key rotation internally
            # If we're here, it means all Gemini API keys were exhausted
            logger.info("All Gemini API keys exhausted, proceeding with fallback to configured provider")
        
        error_detected = _is_provider_error(error, primary_provider)
        
        if ENABLE_LLM_FALLBACK and error_detected:
            logger.warning(f"Provider {primary_provider}:{primary_model} failed, falling back to {FALLBACK_PROVIDER}:{FALLBACK_MODEL}")
            logger.info(f"Fallback triggered due to error: {type(error).__name__}: {str(error)}")
            
            # Don't fallback to the same provider that just failed
            if FALLBACK_PROVIDER == primary_provider:
                logger.error(f"Fallback provider ({FALLBACK_PROVIDER}) is the same as failed provider ({primary_provider}). Cannot fallback.")
                raise
            
            try:
                # Create a modified request with appropriate max_tokens for fallback model
                from minerva.core.services.llm_providers.model_config import get_full_model_config
                
                # Get the fallback model's configuration
                try:
                    fallback_config = get_full_model_config(FALLBACK_MODEL)
                    adjusted_max_tokens = fallback_config.max_tokens
                except Exception:
                    # If we can't get the config, use a safe default
                    adjusted_max_tokens = 32768
                
                # Create a modified request for the fallback
                fallback_request = type(request.llm)(
                    provider=FALLBACK_PROVIDER,
                    model=FALLBACK_MODEL,
                    max_tokens=adjusted_max_tokens,
                    temperature=request.llm.temperature,
                    stream=request.llm.stream,
                    tools=request.llm.tools,
                    system_message=request.llm.system_message,
                    response_format=request.llm.response_format
                )
                
                # Create the modified main request
                modified_request = type(request)(
                    query=request.query,
                    rag_query=getattr(request, 'rag_query', request.query),
                    vector_store=request.vector_store,
                    llm=fallback_request
                )
                
                fallback_llm = _get_llm_instance(FALLBACK_PROVIDER, FALLBACK_MODEL, modified_request)
                response = await fallback_llm.generate_response(messages)
                
                # Add metadata about actual provider/model used (fallback)
                if hasattr(response, '__dict__') and not hasattr(response, 'provider'):
                    response.provider = FALLBACK_PROVIDER
                    response.model = FALLBACK_MODEL
                
                if not request.llm.stream:
                    # Non-streaming response - return the raw response for cost tracking
                    return response
                else:
                    # Streaming response: return the generator as-is
                    return response
                    
            except Exception as fallback_error:
                logger.error(f"Fallback provider {FALLBACK_PROVIDER}:{FALLBACK_MODEL} also failed with error: {fallback_error}", exc_info=True)
                logger.error(f"Fallback error details: {type(fallback_error).__name__}: {str(fallback_error)}")
                # Re-raise the original error since fallback also failed
                raise error
        else:
            # Re-raise non-fallback errors or if fallback is disabled
            logger.info(f"Not attempting fallback - ENABLE_LLM_FALLBACK: {ENABLE_LLM_FALLBACK}, error_detected: {error_detected}")
            raise


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int = 0) -> tuple[float, float, float]:
    """Calculate cost for given tokens and model"""
    pricing = MODEL_PRICING.get(model_name)
    if not pricing:
        logger.warning(f"No pricing found for model: {model_name}. Using default pricing.")
        pricing = {"input_cost_per_million": 5.00, "output_cost_per_million": 15.00}
    
    input_cost = (input_tokens / 1_000_000) * pricing["input_cost_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_cost_per_million"]
    total_cost = input_cost + output_cost
    
    return input_cost, output_cost, total_cost

def get_current_cost_context():
    """Get the current cost tracking context"""
    try:
        from minerva.core.services.cost_tracking_service import _current_cost_context
        return _current_cost_context.get()
    except ImportError:
        return None

async def track_ai_call(model_name: str, input_tokens: int, output_tokens: int):
    """Track an AI call if there's an active cost tracking context"""
    context = get_current_cost_context()
    if context:
        await context.track_ai_operation(
            model_name, input_tokens, output_tokens
        )

async def track_embedding_call(model_name: str, input_tokens: int):
    """Track an embedding call if there's an active cost tracking context"""
    context = get_current_cost_context()
    if context:
        await context.track_embedding_operation(
            model_name, input_tokens
        )

async def rag_search_logic(query: str, vector_store_config: QueryConfig, tender_pinecone_id: str = None):
    try:
        # Build the initial prompt
        user_content = f"Query: {query}"
        vector_search_results = []

        filter_conditions = None
        if tender_pinecone_id:
            filter_conditions = {"tender_pinecone_id":  tender_pinecone_id}

        if vector_store_config is not None:
            query_tool = QueryTool(config=vector_store_config)
            search_results = await query_tool.query_by_text(
                query_text=query,
                top_k=5,
                score_threshold=0.1,
                filter_conditions=filter_conditions
            )
            if search_results.get("status") == "error":
                raise Exception(search_results["error"])

            if search_results.get("matches"):
                # Build a cleaner context block that shows filename and text snippet
                formatted_chunks = []
                for idx, match in enumerate(search_results.get("matches", []), 1):
                    snippet = match["metadata"].get("text") or match["metadata"].get("preview", "")
                    formatted_chunks.append(
                        f"{idx}. From {match['metadata'].get('source', 'unknown')} (score {match['score']:.2f}):\n{snippet}\n"
                    )
                search_context = "\n<DOCUMENT_CONTEXT>\n" + "\n".join(formatted_chunks) + "\n</DOCUMENT_CONTEXT>\n"
                user_content += search_context

            vector_search_results = [
                SearchResult(
                    text=match["metadata"].get("text", match["metadata"].get("preview", "")),
                    score=match["score"],
                    source=match["metadata"].get("source", "unknown")
                )
                for match in search_results.get("matches", [])
            ]

        # Build the messages for the LLM
        messages = [{"role": "user", "content": user_content}]
        
        return messages, vector_search_results

    except Exception as e:
        logger.error(f"Error processing RAG search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def llm_rag_search_logic(request: LLMSearchRequest, tender_pinecone_id: str = None, top_k: int = 4):
    """
    Internal function that performs the LLM RAG search with automatic cost tracking.
    Returns either a LLMSearchResponse (non-streaming) or an async generator (for streaming).
    """
    try:
        # Build the initial prompt
        user_content = f"{request.query}"
        vector_search_results = []

        filter_conditions = None
        if tender_pinecone_id:
            filter_conditions = {"tender_pinecone_id":  tender_pinecone_id}

        # Optionally perform a vector search if a store is provided
        if request.vector_store is not None:
            query_tool = QueryTool(config=request.vector_store)
            search_results = await query_tool.query_by_text(
                query_text=request.rag_query,
                top_k=top_k,
                score_threshold=0.1,
                filter_conditions=filter_conditions
            )
            
            if search_results.get("status") == "error":
                raise Exception(search_results["error"])

            if search_results.get("matches"):
                formatted_chunks = []
                for idx, match in enumerate(search_results.get("matches", []), 1):
                    snippet = match["metadata"].get("text")
                    formatted_chunks.append(
                        f"{idx}. From {match['metadata'].get('source', 'unknown')}:\n{snippet}\n"
                    )
                search_context = "\n<TENDER_DOCUMENTATION_CONTEXT>\n" + "\n".join(formatted_chunks) + "\n</TENDER_DOCUMENTATION_CONTEXT>\n"
                user_content += search_context

            vector_search_results = [
                SearchResult(
                    text=match["metadata"].get("text", match["metadata"].get("preview", "")),
                    score=match["score"],
                    source=match["metadata"].get("source", "unknown")
                )
                for match in search_results.get("matches", [])
            ]

        # Build the messages for the LLM
        messages = [{"role": "user", "content": user_content}]
        # print(f"prompt to LLM with rag: {user_content}")
        
        # Use universal fallback for all providers
        response_result = await _try_llm_with_universal_fallback(request, messages, vector_search_results)
        
        if not request.llm.stream:
            # Handle LLMResponse wrapper for usage tracking
            if isinstance(response_result, LLMResponse):
                llm_response_text = response_result.content
                usage_info = response_result.usage
                # Use the actual provider/model used (may be fallback)
                actual_provider = response_result.provider if hasattr(response_result, 'provider') else request.llm.provider
                actual_model = response_result.model if hasattr(response_result, 'model') else request.llm.model
            else:
                llm_response_text = response_result if isinstance(response_result, str) else ""
                usage_info = None
                actual_provider = request.llm.provider
                actual_model = request.llm.model
            
            # Track costs automatically if context exists
            if usage_info:
                input_tokens = usage_info.get('prompt_tokens', 0)
                output_tokens = usage_info.get('completion_tokens', 0)
                total_tokens = usage_info.get('total_tokens', input_tokens + output_tokens)
                
                await track_ai_call(
                    model_name=actual_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )
                
            search_response = LLMSearchResponse(
                llm_response=llm_response_text,
                vector_search_results=vector_search_results,
                llm_provider=actual_provider,
                llm_model=actual_model
            )
            
            # Add usage information for cost tracking
            if usage_info:
                search_response.usage = usage_info
                
            return search_response
        else:
            # Streaming response: wrap the generator
            async def stream_response():
                # Optionally yield vector search results first
                if vector_search_results:
                    yield f"data: {json.dumps({'type': 'vector_search_results', 'content': [result.dict() for result in vector_search_results]})}\n\n"
                # Stream the LLM response chunks
                async for chunk in response_result:
                    if chunk["type"] == "text":
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "function_call":
                        yield f"data: {json.dumps({'type': 'function_call', 'name': chunk['name'], 'arguments': chunk['arguments']})}\n\n"
            return stream_response()

    except Exception as e:
        logger.error(f"Error processing LLM RAG search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def ask_llm_logic(request: LLMSearchRequest):
    """
    Internal function for the simple LLM query with automatic cost tracking.
    Returns either a LLMSearchResponse (non-streaming) or an async generator (for streaming).
    """
    request_id = f"req_{id(request)}_{request.query[:10].replace(' ', '_')}"
    try:
        # Build the message list from the user query
        message_list = [{"role": "user", "content": request.query}]
        vector_search_results = []  # Remains empty in this case

        # Use universal fallback for all providers
        fallback_request = LLMSearchRequest(
            query=request.query,
            rag_query=request.query,
            llm=request.llm,
            vector_store=None
        )
        
        response_result = await _try_llm_with_universal_fallback(fallback_request, message_list, vector_search_results)
        
        if not request.llm.stream:
            # Handle LLMResponse wrapper for usage tracking
            if isinstance(response_result, LLMResponse):
                if response_result.response_type == "function_call":
                    llm_response_text = response_result.content  # Already JSON string for function calls
                else:
                    llm_response_text = response_result.content
                usage_info = response_result.usage
                # Use the actual provider/model used (may be fallback)
                actual_provider = response_result.provider if hasattr(response_result, 'provider') else request.llm.provider
                actual_model = response_result.model if hasattr(response_result, 'model') else request.llm.model
            else:
                llm_response_text = response_result if isinstance(response_result, str) else ""
                usage_info = None
                actual_provider = request.llm.provider
                actual_model = request.llm.model
                # Handle dict response (function call) for backward compatibility
                if isinstance(response_result, dict) and response_result.get("type") == "function_call":
                    llm_response_text = f"Function call: {response_result['name']} with arguments {response_result['arguments']}"
            
            # Track costs automatically if context exists
            if usage_info:
                input_tokens = usage_info.get('prompt_tokens', 0)
                output_tokens = usage_info.get('completion_tokens', 0)
                total_tokens = usage_info.get('total_tokens', input_tokens + output_tokens)
                
                await track_ai_call(
                    model_name=actual_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )
                    
            search_response = LLMSearchResponse(
                llm_response=llm_response_text,
                vector_search_results=vector_search_results,
                llm_provider=actual_provider,
                llm_model=actual_model
            )
            
            # Add usage information for cost tracking
            if usage_info:
                search_response.usage = usage_info
                
            return search_response
        else:
            # Streaming response: return the generator
            async def stream_response():
                async for chunk in response_result:
                    if chunk["type"] == "text":
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "function_call":
                        yield f"data: {json.dumps({'type': 'function_call', 'name': chunk['name'], 'arguments': chunk['arguments']})}\n\n"
            return stream_response()

    except Exception as e:
        logger.error(f"[{request_id}] Error processing ask-llm: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))