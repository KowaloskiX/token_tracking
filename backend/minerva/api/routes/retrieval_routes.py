from dataclasses import Field
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Dict, Any, Optional
import logging
from uuid import uuid4
import asyncio
from datetime import datetime
from pathlib import Path
import re
from elasticsearch import helpers
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, EmbeddingTool
from minerva.core.services.vectorstore.text_chunks import ChunkingConfig, TextChunker
from pydantic import BaseModel
from minerva.core.services.keyword_search.elasticsearch import es_client

router = APIRouter()
logger = logging.getLogger(__name__)

file_service = FileExtractionService()
chunker = TextChunker(ChunkingConfig())

# Pydantic model for query request body
class QueryRequest(BaseModel):
    query_text: str
    index_name: str = "default-index"
    embedding_model: str = "text-embedding-3-large"
    top_k: int = 3
    score_threshold: float = 0.7
    filter_conditions: Optional[Dict[str, Any]] = None


class ElasticDoc(BaseModel):
    text: str
    initiation_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ElasticIngestionRequest(BaseModel):
    docs: List[ElasticDoc]
    index_name: str



def sanitize_id(text: str) -> str:
    replacements = {
        'ą': 'a', 'ł': 'l', 'ę': 'e', 'ó': 'o', 'ć': 'c', 'ń': 'n', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ł': 'L', 'Ę': 'E', 'Ó': 'O', 'Ć': 'C', 'Ń': 'N', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    text = re.sub(r'[^\x00-\x7F]+', '_', text)
    text = re.sub(r'[^a-zA-Z0-9_.-]', '_', text)
    text = text[:512].strip('_')
    return text or 'default_id'

@router.post("/upsert-file", response_model=Dict[str, Any])
async def upsert_file(
    file: UploadFile = File(...),
    index_name: str = Form("default-index")
):
    try:
        embedding_tool = EmbeddingTool(EmbeddingConfig(index_name=index_name))
        original_filename = file.filename
        original_extension = Path(original_filename).suffix
        sanitized_filename = sanitize_id(Path(original_filename).stem) + original_extension
        temp_file_path = Path(f"temp_{uuid4()}_{sanitized_filename}")

        with temp_file_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Use the async wrapper
        extracted_files = await file_service.process_file_async(temp_file_path)
        
        all_results = []
        for file_content, filename, preview_chars, original_bytes, original_filename in extracted_files:
            response_filename = original_filename
            sanitized_filename = sanitize_id(Path(response_filename).stem) + (Path(response_filename).suffix or '.txt')

            if filename.endswith('.txt'):
                chunks = chunker.create_chunks(file_content.decode('utf-8'))
                items = [
                    {
                        "id": f"{sanitized_filename}_{uuid4()}",
                        "input": chunk,
                        "metadata": {
                            "source": response_filename,
                            "chunk_index": i,
                            "text": chunk,
                            "preview": chunk[:200],
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    for i, chunk in enumerate(chunks)
                ]
                result = await embedding_tool.embed_and_store_batch(items)
                all_results.append({
                    "filename": response_filename,
                    "chunks_processed": result["processed_count"],
                    "failed_items": result["failed_items"]
                })
            else:
                item = [{
                    "id": f"{sanitized_filename}_{uuid4()}",
                    "input": preview_chars or f"Binary file: {response_filename}",
                    "metadata": {
                        "source": response_filename,
                        "is_binary": True,
                        "timestamp": datetime.now().isoformat()
                    }
                }]
                result = await embedding_tool.embed_and_store_batch(item)
                all_results.append({
                    "filename": response_filename,
                    "chunks_processed": result["processed_count"],
                    "failed_items": result["failed_items"]
                })

        temp_file_path.unlink()

        return {
            "status": "success",
            "index_name": index_name,
            "processed_files": all_results,
            "total_chunks": sum(r["chunks_processed"] for r in all_results)
        }

    except Exception as e:
        logger.error(f"Error in upsert_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=Dict[str, Any])
async def query_pinecone(request: QueryRequest):
    """
    Endpoint to query Pinecone with parameters provided in JSON body
    """
    try:
        query_tool = QueryTool(QueryConfig(index_name=request.index_name, embedding_model=request.embedding_model))

        # Use filter_conditions directly as a dictionary (no JSON parsing needed)
        result = await query_tool.query_by_text(
            query_text=request.query_text,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            filter_conditions=request.filter_conditions
        )

        return {
            "status": "success",
            "index_name": request.index_name,
            "query": request.query_text,
            "results": result
        }

    except Exception as e:
        logger.error(f"Error in query_pinecone: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    



@router.post("/ingest-elasticsearch")
async def ingest_elasticsearch(request: ElasticIngestionRequest):
    try:
        # Convert ElasticDoc objects to dictionaries with action metadata
        actions = []
        for doc in request.docs:
            # Convert Pydantic model to dict
            doc_dict = doc.dict(exclude_none=True)
            
            # Prepare document for bulk ingestion
            actions.append({
                "_index": request.index_name,
                "_source": doc_dict
            })
        
        # Perform bulk ingestion
        success, failed = helpers.bulk(es_client, actions, stats_only=True)
        
        return {
            "status": "success", 
            "index_name": request.index_name,
            "documents_indexed": success,
            "failed_documents": failed
        }
    except Exception as e:
        logger.error(f"Error in ingest_elasticsearch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/search-by-date/{index_name}", response_model=Dict[str, Any])
async def search_by_date(
    index_name: str,
    q: str,
    date: str,
    size: int = 10,
    from_: int = 0
):
    try:
        # Build the Elasticsearch query with date filter
        query = {
            "bool": {
                "must": [
                    {"match": {"text": q}}
                ],
                "filter": [
                    {"term": {"initiation_date": date}}
                ]
            }
        }
        
        # Execute the search
        result = es_client.search(
            index=index_name,
            body={
                "query": query,
                "size": size,
                "from": from_
            }
        )
        
        return {
            "status": "success",
            "index_name": index_name,
            "query": q,
            "date": date,
            "total_hits": result["hits"]["total"]["value"],
            "hits": result["hits"]["hits"]
        }
    
    except Exception as e:
        logger.error(f"Error in search_by_date: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
class CompareSearchRequest(BaseModel):
    query: str
    date: str
    index_name_pinecone: str = "test-tenders"
    embedding_model: str = "text-embedding-3-large"
    index_name_es: str = "test-tenders"
    top_k: int = 45
@router.post("/compare-search", response_model=Dict[str, Any])
async def compare_search_results(request: CompareSearchRequest):
    """
    Compare search results between Pinecone (vector search) and Elasticsearch (lexical search)
    for the same query with date filtering
    """
    try:
        # 1. Elasticsearch query with date filter
        es_query = {
            "bool": {
                "must": [
                    {"match": {"text": request.query}}
                ],
                "filter": [
                    {"term": {"metadata.source_type.keyword": "egospodarka"}}
                ]
            }
        }
        
        # Execute Elasticsearch search
        es_result = es_client.search(
            index=request.index_name_es,
            body={
                "query": es_query,
                "size": request.top_k
            }
        )
        
        # 2. Pinecone query with date filter
        query_tool = QueryTool(QueryConfig(index_name=request.index_name_pinecone, embedding_model=request.embedding_model))
        
        # Filter conditions for Pinecone
        filter_conditions = {
            "source_type": {"$eq": "egospodarka"}
        }

        # Use filter_conditions directly as a dictionary (no JSON parsing needed)
        pinecone_result = await query_tool.query_by_text(
            query_text=request.query,
            top_k=request.top_k,
            score_threshold=0.1,
            filter_conditions=filter_conditions
        )

        
        # 3. Extract and format results for comparison
        
        # Format Elasticsearch results
        es_hits = []
        es_id_to_hit_map = {}  # Map ID to hit for quick lookup later
        
        for hit in es_result["hits"]["hits"]:
            formatted_hit = {
                "id": hit["_id"],
                "score": hit["_score"],
                "text": hit["_source"].get("text", ""),
                "title": hit["_source"].get("title", ""),
                "organization": hit["_source"].get("organization", ""),
                "initiation_date": hit["_source"].get("initiation_date", ""),
                "metadata": hit["_source"].get("metadata", {})
            }
            es_hits.append(formatted_hit)
            es_id_to_hit_map[hit["_id"]] = formatted_hit
        
        # Format Pinecone results
        pinecone_hits = []
        pinecone_id_to_hit_map = {}  # Map ID to hit for quick lookup later
        
        for match in pinecone_result.get("matches", []):
            formatted_match = {
                "id": match.get("id", ""),
                "score": match.get("score", 0),
                "text": match.get("metadata", {}).get("name", "") + " " + match.get("metadata", {}).get("organization", ""),
                "title": match.get("metadata", {}).get("name", ""),
                "organization": match.get("metadata", {}).get("organization", ""),
                "initiation_date": match.get("metadata", {}).get("initiation_date", ""),
                "metadata": match.get("metadata", {})
            }
            pinecone_hits.append(formatted_match)
            pinecone_id_to_hit_map[match.get("id", "")] = formatted_match
        
        # 4. Find overlap between results
        es_ids = {hit["id"] for hit in es_hits}
        pinecone_ids = {hit["id"] for hit in pinecone_hits}
        
        common_ids = es_ids.intersection(pinecone_ids)
        only_in_es = es_ids - pinecone_ids
        only_in_pinecone = pinecone_ids - es_ids
        
        # 5. Create a summary with names and links for easier comparison
        summary = {
            "common_results": [
                {
                    "id": id,
                    "name": es_id_to_hit_map[id]["title"],
                    "link": id,
                    "es_score": es_id_to_hit_map[id]["score"],
                    "pinecone_score": pinecone_id_to_hit_map[id]["score"],
                    "organization": es_id_to_hit_map[id]["organization"]
                } for id in common_ids
            ],
            "only_in_elasticsearch": [
                {
                    "id": id,
                    "name": es_id_to_hit_map[id]["title"],
                    "link": id,
                    "score": es_id_to_hit_map[id]["score"],
                    "organization": es_id_to_hit_map[id]["organization"]
                } for id in only_in_es
            ],
            "only_in_pinecone": [
                {
                    "id": id,
                    "name": pinecone_id_to_hit_map[id]["title"],
                    "link": id,
                    "score": pinecone_id_to_hit_map[id]["score"],
                    "organization": pinecone_id_to_hit_map[id]["organization"]
                } for id in only_in_pinecone
            ]
        }
        
        # Sort results by score (descending)
        summary["common_results"].sort(key=lambda x: x["es_score"], reverse=True)
        summary["only_in_elasticsearch"].sort(key=lambda x: x["score"], reverse=True)
        summary["only_in_pinecone"].sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "status": "success",
            "query": request.query,
            "date_filter": request.date,
            "summary": summary,  # Add the new summary section
            "elasticsearch_results": {
                "total_hits": es_result["hits"]["total"]["value"],
                "hits": es_hits
            },
            "pinecone_results": {
                "total_hits": len(pinecone_result.get("matches", [])),
                "hits": pinecone_hits
            },
            "comparison": {
                "total_common": len(common_ids),
                "common_ids": list(common_ids),
                "only_in_elasticsearch": list(only_in_es),
                "only_in_pinecone": list(only_in_pinecone),
                "elasticsearch_hit_count": len(es_hits),
                "pinecone_hit_count": len(pinecone_hits)
            }
        }
    
    except Exception as e:
        logger.error(f"Error in compare_search_results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error comparing search results: {str(e)}")