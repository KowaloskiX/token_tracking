from asyncio.log import logger
from fastapi import HTTPException
import json
from minerva.core.models.request.ai import LLMSearchRequest, LLMSearchResponse, SearchResult
from minerva.core.services.llm_providers.anthropic import AnthropicLLM
from minerva.core.services.llm_providers.openai import OpenAILLM, LLMResponse
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool


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


async def llm_rag_search_logic(request: LLMSearchRequest, tender_pinecone_id: str = None):
    """
    Internal function that performs the LLM RAG search.
    Returns either a LLMSearchResponse (non-streaming) or an async generator (for streaming).
    """
    try:
        # Build the initial prompt
        user_content = f"Query: {request.query}"
        vector_search_results = []

        filter_conditions = None
        if tender_pinecone_id:
            filter_conditions = {"tender_pinecone_id":  tender_pinecone_id}

        # Optionally perform a vector search if a store is provided
        if request.vector_store is not None:
            query_tool = QueryTool(config=request.vector_store)
            search_results = await query_tool.query_by_text(
                query_text=request.rag_query,
                top_k=4,
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

        # Initialize the LLM
        llm_cls = OpenAILLM if request.llm.provider == "openai" else AnthropicLLM
        llm = llm_cls(
            model=request.llm.model,
            stream=request.llm.stream,
            temperature=request.llm.temperature,
            max_tokens=request.llm.max_tokens,
            instructions=request.llm.system_message,
            response_format=request.llm.response_format
        )

        response = await llm.generate_response(messages)

        if not request.llm.stream:
            # Handle LLMResponse wrapper for usage tracking
            if isinstance(response, LLMResponse):
                llm_response_text = response.content
                usage_info = response.usage
            else:
                llm_response_text = response if isinstance(response, str) else ""
                usage_info = None
                
            search_response = LLMSearchResponse(
                llm_response=llm_response_text,
                vector_search_results=vector_search_results,
                llm_provider=request.llm.provider,
                llm_model=request.llm.model
            )
            
            # Add usage information for cost tracking
            if usage_info:
                search_response.usage = usage_info
                
            return search_response
        else:
            # Streaming response: return an async generator
            async def stream_response():
                # Optionally yield vector search results first
                if vector_search_results:
                    yield f"data: {json.dumps({'type': 'vector_search_results', 'content': [result.dict() for result in vector_search_results]})}\n\n"
                # Stream the LLM response chunks
                async for chunk in response:
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
    Internal function for the simple LLM query.
    Returns either a LLMSearchResponse (non-streaming) or an async generator (for streaming).
    """
    request_id = f"req_{id(request)}_{request.query[:10].replace(' ', '_')}"
    try:
        # Build the message list from the user query
        message_list = [{"role": "user", "content": request.query}]
        vector_search_results = []  # Remains empty in this case

        # Initialize the LLM with user-supplied tools and instructions
        llm_cls = OpenAILLM if request.llm.provider == "openai" else AnthropicLLM
        llm = llm_cls(
            model=request.llm.model,
            stream=request.llm.stream,
            temperature=request.llm.temperature,
            max_tokens=request.llm.max_tokens,
            tools=request.llm.tools,  # User-provided tools
            instructions=request.llm.system_message,
            response_format=request.llm.response_format
        )

        response = await llm.generate_response(message_list)

        if not request.llm.stream:
            # Handle LLMResponse wrapper for usage tracking
            if isinstance(response, LLMResponse):
                if response.response_type == "function_call":
                    llm_response_text = response.content  # Already JSON string for function calls
                else:
                    llm_response_text = response.content
                usage_info = response.usage
            else:
                llm_response_text = response if isinstance(response, str) else ""
                usage_info = None
                # Handle dict response (function call) for backward compatibility
                if isinstance(response, dict) and response.get("type") == "function_call":
                    llm_response_text = f"Function call: {response['name']} with arguments {response['arguments']}"
                    
            search_response = LLMSearchResponse(
                llm_response=llm_response_text,
                vector_search_results=vector_search_results,
                llm_provider=request.llm.provider,
                llm_model=request.llm.model
            )
            
            # Add usage information for cost tracking
            if usage_info:
                search_response.usage = usage_info
                
            return search_response
        else:
            async def stream_response():
                async for chunk in response:
                    if chunk["type"] == "text":
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "function_call":
                        yield f"data: {json.dumps({'type': 'function_call', 'name': chunk['name'], 'arguments': chunk['arguments']})}\n\n"
            return stream_response()

    except Exception as e:
        logger.error(f"[{request_id}] Error processing ask-llm: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))