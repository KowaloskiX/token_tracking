from minerva.core.services.vectorstore.pinecone.query import QueryConfig
from pydantic import BaseModel
from typing import Any, Dict, Literal, Optional, List
from fastapi import Form

class AskAiRequest(BaseModel):
    prompt: str
    model: str
    thread_id: str
    stream: bool
    assistant_id: str
    run_id: Optional[str] = None
    call_id: Optional[str] = None

    @classmethod
    def as_form(
        cls,
        prompt: str = Form(...),
        model: str = Form(...),
        thread_id: str = Form(...),
        stream: bool = Form(...),
        assistant_id: str = Form(...),
        run_id: Optional[str] = Form(None),
        call_id: Optional[str] = Form(None),
    ):
        return cls(
            prompt=prompt,
            model=model,
            thread_id=thread_id,
            stream=stream,
            assistant_id=assistant_id,
            run_id=run_id,
            call_id=call_id
        )
    
class ListRuns(BaseModel):
    thread_id: str

class CancelRun(BaseModel):
    thread_id: str
    run_id: str

class ToolOutput(BaseModel):
    tool_call_id: str
    output: str 
    
class SubmitToolResponse(BaseModel):
    thread_id: str
    run_id: str
    tool_outputs: List[ToolOutput]

class LLMConfig(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: Optional[int] = None
    system_message: str  # Instructions for the LLM
    tools: Optional[List[Dict[str, Any]]] = None  # User-provided tools
    stream: bool = False  # Streaming option
    response_format: Optional[dict[str, Any]] = None

# LLMSearchRequest without vector_store since retrieval is removed
class LLMSearchRequest(BaseModel):
    query: str
    vector_store: Optional[QueryConfig] = None
    llm: LLMConfig

class LLMRAGRequest(BaseModel):
    query: str
    rag_query: str
    vector_store: Optional[QueryConfig] = None
    llm: LLMConfig

# SearchResult (kept for consistency, though not used in this version unless tools return it)
class SearchResult(BaseModel):
    text: str
    score: float
    source: str

# Updated LLMSearchResponse with usage tracking
class LLMSearchResponse(BaseModel):
    llm_response: str
    vector_search_results: List[SearchResult]  # Empty unless tools provide results
    llm_provider: str
    llm_model: str
    usage: Optional[Dict[str, int]] = None  # Added for cost tracking
    
    class Config:
        arbitrary_types_allowed = True