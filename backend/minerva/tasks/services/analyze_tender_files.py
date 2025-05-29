import re
from uuid import uuid4
from minerva.core.services.vectorstore.helpers import MAX_TOKENS, count_tokens, safe_chunk_text
from minerva.api.routes.retrieval_routes import sanitize_id
from minerva.core.models.file import FilePineconeConfig
from minerva.core.models.request.ai import LLMSearchRequest, LLMRAGRequest
from minerva.core.services.llm_logic import ask_llm_logic, llm_rag_search_logic
from minerva.core.models.user import User
from minerva.core.middleware.token_tracking import update_user_token_usage
from minerva.core.models.extensions.tenders.tender_analysis import AnalysisCriteria, TenderAnalysis, TenderAnalysisResult, TenderDecriptionProfileMatches, TenderProfileMatches, TenderToAnalyseDescription
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, EmbeddingTool
from minerva.core.services.vectorstore.text_chunks import ChunkingConfig, TextChunker
from openai import AssistantEventHandler
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from typing_extensions import override
from pathlib import Path
import asyncio
import os
import time
import gc
import shutil
from datetime import datetime
from playwright.async_api import async_playwright
import logging
from openai import OpenAI
import tempfile
import json
import io
import psutil
import sys
import ctypes  # for malloc_trim on Linux
from minerva.core.services.keyword_search.elasticsearch import es_client
from elasticsearch import helpers

logger = logging.getLogger("minerva.tasks.analysis_tasks")

# Memory logging helper
def log_mem(tag: str = ""):
    try:
        process_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        logger.info(f"[{tag}] Memory usage: {process_mem:.1f} MB")
    except Exception as mem_exc:
        logger.debug(f"Unable to log memory usage for tag '{tag}': {mem_exc}")

# Force the C allocator to release free arenas back to the OS (only works on Linux/glibc)
def malloc_trim():
    if sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except Exception:
            pass


class FileURL(BaseModel):
    url: str
    file_type: str

class DownloadConfig:
    def __init__(self):
        self.timeout = 5000
        self.download_selectors = [
            'a[download]',
            'button[download]',
            'a[href*=".pdf"]',
            'a[href*=".doc"]',
            'a[href*=".txt"]'
        ]

class ElasticsearchConfig:
    def __init__(
        self,
        index_name: str = "files-rag",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.index_name = index_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

class RAGManager:
    def __init__(self, index_name: str, namespace: str, embedding_model: str, tender_pinecone_id: str, use_elasticsearch: bool = False, es_config: Optional[ElasticsearchConfig] = None):
        # Memory log on RAGManager init
        log_mem(f"{tender_pinecone_id} RAGManager:init")
        self.index_name = index_name
        self.namespace = namespace
        self.embedding_model = embedding_model
        self.tender_pinecone_id = tender_pinecone_id
        self.chunker = TextChunker(ChunkingConfig())
        self.embedding_tool = EmbeddingTool(EmbeddingConfig(
            index_name=index_name, namespace=namespace, embedding_model=embedding_model))
        self.temp_dir = tempfile.mkdtemp()
        self.registry = ExtractorRegistry()
        self.use_elasticsearch = use_elasticsearch
        self.es_config = es_config or ElasticsearchConfig()
        
        # Ensure Elasticsearch index exists if enabled
        if self.use_elasticsearch:
            self.ensure_elasticsearch_index()

    def ensure_elasticsearch_index(self):
        """Create or update Elasticsearch index with proper mappings for file chunks"""
        if not es_client.indices.exists(index=self.es_config.index_name):
            # Create index with mappings
            mappings = {
                "mappings": {
                    "properties": {
                        "text": {
                            "type": "text"
                        },
                        "metadata": {
                            "type": "object",
                            "dynamic": True
                        },
                        "created_at": {
                            "type": "date",
                            "format": "strict_date_optional_time||epoch_millis"
                        }
                    }
                }
            }
            es_client.indices.create(
                index=self.es_config.index_name,
                body=mappings
            )
            logger.info(f"Created Elasticsearch index: {self.es_config.index_name}")
        else:
            # Update existing index mapping if needed
            mappings = {
                "properties": {
                    "text": {
                        "type": "text"
                    },
                    "metadata": {
                        "type": "object",
                        "dynamic": True
                    },
                    "created_at": {
                        "type": "date",
                        "format": "strict_date_optional_time||epoch_millis"
                    }
                }
            }
            es_client.indices.put_mapping(
                index=self.es_config.index_name,
                body=mappings
            )
            logger.info(f"Updated Elasticsearch index mappings: {self.es_config.index_name}")

    def clean_up(self):
        """Enhanced cleanup to properly release memory resources"""
        logger.info(f"Cleaning up RAGManager resources for tender {self.tender_pinecone_id}")
        
        # Clear any large object references
        self.chunker = None
        self.registry = None
        
        # Explicitly release embedding_tool
        if hasattr(self, 'embedding_tool'):
            self.embedding_tool = None
        
        # Clean up temp directory
        if os.path.exists(self.temp_dir):
            try:
                # Remove all files in temp directory
                for file in os.listdir(self.temp_dir):
                    try:
                        file_path = os.path.join(self.temp_dir, file)
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f"Error removing file {file}: {str(e)}")
                
                # Remove directory itself
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info(f"Removed temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error removing temp directory: {str(e)}")
        
        # Force garbage collection
        gc.collect()
        logger.info(f"RAGManager cleanup completed for tender {self.tender_pinecone_id}")
        # Memory log after cleanup
        log_mem(f"{self.tender_pinecone_id} RAGManager:cleanup")

    EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "8"))  # safe small default

    async def index_chunk_to_elasticsearch(self, chunk: str, metadata: dict) -> bool:
        try:
            document = {
                "text": chunk,
                "metadata": metadata,
                "created_at": datetime.utcnow().isoformat() 
            }
            
            doc_id = metadata.get("id")
            
            # Use bulk operation for better performance
            actions = [{
                "_index": self.es_config.index_name,
                "_id": doc_id,
                "_source": document
            }]
            
            success, failed = helpers.bulk(es_client, actions, stats_only=True)
            return success > 0 and failed == 0
            
        except Exception as e:
            logger.error(f"Error indexing chunk to Elasticsearch: {str(e)}")
            return False

    async def upload_file_content_to_pinecone(self, file_content: bytes, filename: str):
        # Memory log before chunking
        log_mem(f"{self.tender_pinecone_id} upload_file_content_to_pinecone:start:{filename}")

        sanitized_filename = sanitize_id(filename)
        filename_unique_prefix = f"{sanitized_filename}_{uuid4()}"

        # Decode bytes only once, then release
        text: str = file_content.decode("utf-8") if isinstance(file_content, bytes) else file_content
        file_content = None  # release raw bytes early
        gc.collect()

        if not text or not text.strip():
            logger.warning(f"No text extracted from file '{filename}'. Skipping embedding.")
            return FilePineconeConfig(
                query_config=QueryConfig(
                    index_name=self.index_name,
                    namespace=self.namespace,
                    embedding_model=self.embedding_model
                ),
                pinecone_unique_id_prefix=filename_unique_prefix
            )
        
        es_success = True
        
        chunk_index_global = 0
        # Stream chunks in small batches to keep memory low
        current_batch: list = []
        current_es_batch: list = []
        
        for chunk in safe_chunk_text(text, self.chunker, self.embedding_model):
            if not chunk or not chunk.strip():
                continue

            tokens = count_tokens(chunk, self.embedding_model)
            if tokens > MAX_TOKENS:
                logger.error(
                    f"Chunk {chunk_index_global} from filename={filename} is OVER LIMIT ({tokens} tokens)." )
                # still embed smaller preview or skip – we skip to stay safe
                chunk_index_global += 1
                continue

            chunk_id = f"{filename_unique_prefix}_{uuid4()}"
            # Store both a short preview (200 chars) and the full text of the chunk
            metadata = {
                "tender_pinecone_id": self.tender_pinecone_id,
                "source": sanitized_filename,
                "extractor": "",
                "source_type": "",
                "chunk_index": chunk_index_global,
                "preview": chunk[:200],
                "text": chunk,
                "timestamp": datetime.now().isoformat()
            }

            current_batch.append({
                "id": chunk_id,
                "input": chunk,
                "metadata": metadata
            })

            # Prepare Elasticsearch action if enabled
            if self.use_elasticsearch:
                metadata["id"] = chunk_id
                current_es_batch.append({
                    "_index": self.es_config.index_name,
                    "_id": chunk_id,
                    "_source": {
                        "text": chunk,
                        "metadata": metadata,
                        "created_at": datetime.utcnow().isoformat()
                    }
                })

            chunk_index_global += 1

            # Once we hit BATCH_SIZE, process both Pinecone and Elasticsearch batches
            if len(current_batch) >= self.EMBED_BATCH_SIZE:
                # Upload to Pinecone
                await self.embedding_tool.embed_and_store_batch(current_batch)
                current_batch = []
                
                # Bulk index to Elasticsearch if enabled
                if self.use_elasticsearch and current_es_batch:
                    try:
                        success, failed = helpers.bulk(es_client, current_es_batch, stats_only=True)
                        if not (success > 0 and failed == 0):
                            logger.warning(f"Failed to index {failed} chunks to Elasticsearch for file {filename}")
                            es_success = False
                    except Exception as e:
                        logger.error(f"Error during bulk Elasticsearch indexing: {str(e)}")
                        es_success = False
                    current_es_batch = []
                
                gc.collect()
                malloc_trim()

        # Process any remaining chunks
        if current_batch:
            # Upload to Pinecone
            await self.embedding_tool.embed_and_store_batch(current_batch)
            current_batch = []

        # Process any remaining Elasticsearch documents
        if self.use_elasticsearch and current_es_batch:
            try:
                success, failed = helpers.bulk(es_client, current_es_batch, stats_only=True)
                if not (success > 0 and failed == 0):
                    logger.warning(f"Failed to index {failed} chunks to Elasticsearch for file {filename}")
                    es_success = False
            except Exception as e:
                logger.error(f"Error during bulk Elasticsearch indexing: {str(e)}")
                es_success = False

        # release large string 'text'
        text = None
        current_es_batch = None
        gc.collect()
        malloc_trim()

        # Memory log after embedding
        log_mem(f"{self.tender_pinecone_id} upload_file_content_to_pinecone:after_embed:{filename}")

        return FilePineconeConfig(
            query_config=QueryConfig(
                index_name=self.index_name,
                namespace=self.namespace,
                embedding_model=self.embedding_model
            ),
            pinecone_unique_id_prefix=filename_unique_prefix,
            elasticsearch_indexed=self.use_elasticsearch and es_success
        )
        
    @staticmethod
    async def ai_filter_tenders(
        tender_analysis: TenderAnalysis,
        tender_matches: List[dict],
        current_user: Optional[User] = None  # Made optional to align with previous fix
    ) -> TenderProfileMatches:
        # Memory log before AI tender filtering
        log_mem("ai_filter_tenders:start")
        system_message = (
            "You are a well-balanced system that identifies public tenders that best match the company profile and offer. "
            "Only returning relevant tenders."
        )
        
        user_message = (
            "Look at the company profile in <COMPANY_PROFILE> and pick only public tenders from <PUBLIC_TENDERS_LIST> that match the company profile.\n"
            f"<COMPANY_PROFILE>\n\"{tender_analysis.company_description}\"\n</COMPAMY_PROFILE>\n"
            f"Public tenders to choose from:\n<PUBLIC_TENDERS_LIST>{json.dumps(tender_matches)}\n</PUBLIC_TENDERS_LIST>"
            "The output JSON must strictly follow this schema:\n"
            "{\n"
            "   \"matches\": [\n"
            "      {\n"
            "         \"id\": \"exact-id-from-input\",\n"
            "         \"name\": \"...\",\n"
            "         \"organization\": \"...\"\n"
            "      },\n"
            "      ...\n"
            "   ]\n"
            "}\n\n"
        )

        request_data = LLMSearchRequest(
            query=user_message,
            vector_store=None,
            llm={
                "provider": "openai",
                "model": "o4-mini",
                "temperature": 0,
                # "max_tokens": 16000,
                "system_message": system_message,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "tender_matches_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "matches": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "organization": {"type": "string"},
                                        },
                                        "required": ["id", "name", "organization"],  # Added 'id' to required
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["matches"],
                            "additionalProperties": False
                        }
                    }
                }
            }
        )

        try:
            response = await ask_llm_logic(request_data)
            parsed_output = json.loads(response.llm_response)
            # logger.info(f"OpenAI response: {parsed_output}")  # Log raw response for debugging

            # Post-process to ensure 'id' is present (fallback if OpenAI omits it)
            tender_lookup = {match["id"]: match for match in tender_matches}
            for match in parsed_output["matches"]:
                if "id" not in match or not match["id"]:
                    original_match = tender_lookup.get(match.get("id", ""), {})
                    match["id"] = original_match.get("id", match.get("id", "unknown"))
                    if match["id"] == "unknown":
                        logger.warning(f"Could not find ID for tender: {match['name']}")

            if current_user and hasattr(response, "usage") and response.usage:
                await update_user_token_usage(str(current_user.id), response.usage.total_tokens)

            # Memory log after AI tender filtering
            log_mem("ai_filter_tenders:end")
            return TenderProfileMatches(**parsed_output)
        
        except Exception as e:
            logger.error(f"Error filtering tenders with AI using ask_llm_logic: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to filter tenders: {str(e)}")


    async def analyze_subcriteria(self, subcriteria: str, tender_pinecone_id: str) -> Dict[str, Any]:
        """
        Analyze a single subcriteria query using both RAG search and Elasticsearch if enabled.
        Returns the search results with metadata.
        """
        try:
            # Vector search results
            query_tool = QueryTool(config=QueryConfig(
                index_name=self.index_name,
                namespace=self.namespace,
                embedding_model=self.embedding_model
            ))

            filter_conditions = {"tender_pinecone_id": tender_pinecone_id}
            
            search_results = await query_tool.query_by_text(
                query_text=subcriteria,
                top_k=3,
                score_threshold=0.1,
                filter_conditions=filter_conditions
            )

            if search_results.get("status") == "error":
                raise Exception(search_results["error"])

            result = {
                "subcriteria": subcriteria,
                "vector_results": search_results.get("matches", []),
                "vector_total_matches": len(search_results.get("matches", [])),
                "elasticsearch_results": [],
                "elasticsearch_total_matches": 0
            }

            # Add Elasticsearch results if enabled
            if self.use_elasticsearch:
                # Build Elasticsearch query using the subcriteria text directly
                es_query = {
                    "bool": {
                        "should": [
                            {"match": {"text": subcriteria}}
                        ],
                        "minimum_should_match": 1,
                        "filter": [
                            {"term": {"metadata.tender_pinecone_id.keyword": tender_pinecone_id}}
                        ]
                    }
                }
                
                try:
                    es_results = es_client.search(
                        index=self.es_config.index_name,
                        body={
                            "query": es_query,
                            "size": 2
                        }
                    )
                    
                    # Use a set to track unique texts
                    seen_texts = set()
                    unique_results = []
                    
                    for hit in es_results["hits"]["hits"]:
                        text = hit["_source"]["text"]
                        # Only add if we haven't seen this text before
                        if text not in seen_texts:
                            seen_texts.add(text)
                            unique_results.append({
                                "text": text,
                                "score": hit["_score"],
                                "source": hit["_source"]["metadata"]["source"]
                            })
                    
                    result["elasticsearch_results"] = unique_results
                    result["elasticsearch_total_matches"] = len(unique_results)
                    
                except Exception as e:
                    logger.error(f"Error during Elasticsearch search for subcriteria: {str(e)}", exc_info=True)

            return result

        except Exception as e:
            logger.error(f"Error analyzing subcriteria '{subcriteria}': {str(e)}")
            return {
                "subcriteria": subcriteria,
                "vector_results": [],
                "vector_total_matches": 0,
                "elasticsearch_results": [],
                "elasticsearch_total_matches": 0,
                "error": str(e)
            }

    async def analyze_tender_criteria_and_location(self, current_user: User, criteria: List[AnalysisCriteria], include_vector_results: bool = False) -> Dict[str, Any]:
        # Memory log at start
        log_mem(f"{self.tender_pinecone_id} analyze_tender_criteria_and_location:start")
        """
        Analyze multiple criteria + location concurrently, using a semaphore to limit concurrency.
        Now includes Elasticsearch results if enabled and handles subcriteria queries.
        """
        # Limit concurrency to 3 tasks at a time
        semaphore = asyncio.Semaphore(4)

        async def analyze_one_criteria(criterion: AnalysisCriteria) -> Dict[str, Any]:
            """
            Analyze a single criterion using the assistant, with optional instruction if provided.
            Now includes Elasticsearch results if enabled and handles subcriteria queries.
            """
            try:
                # Base prompt
                base_prompt = (
                    f"Please answer this question based on the public tender document content:\n\n"
                    f"<QUESTION>{criterion.name}</QUESTION>\n"
                )

                has_instruction = False
                if hasattr(criterion, 'instruction') and criterion.instruction:
                    has_instruction = True
                
                # Format template with conditional summary instructions
                summary_description = f"<Your answer to the '{criterion.name}' question based on the documents."
                if has_instruction:
                    summary_description += f"ADDITIONAL INSTRUCTION: {criterion.instruction}"
                summary_description += " Response should directly support 'criteria_met' assessment.>"
                
                format_instructions = (
                    f"Return your answer in the following JSON format. The value for the 'criteria' field in your JSON response MUST be an exact copy of the text from the <QUESTION> tag provided in the input.\n"
                    f"The summary response should ALWAYS be in the same language as the <QUESTION> unless the instruction states otherwise.\n"
                ) + f"""
                {{
                    "criteria": "<Exact copy of the input <QUESTION>>",
                    "analysis": {{
                        "summary": "{summary_description}",
                        "confidence": "<LOW|MEDIUM|HIGH - Your confidence in the summary and 'criteria_met' assessment based on the available information.>",
                        "criteria_met": <true|false - Boolean indicating if the statement/question in <QUESTION> is affirmed as true by the documents.>
                    }}
                }}
                """
                
                # Combine all parts
                prompt = base_prompt + format_instructions

                # Get vector search results
                elastic_search_results = []
                if self.use_elasticsearch:
                    # First, use LLM to extract keywords from the criterion description
                    keyword_extraction_prompt = f"""
                    You are a specialized system for analyzing public tender criteria (kryteria zamówień publicznych).
                    Your task is to extract the most important keywords and key phrases from a tender criterion description.
                    
                    Important context:
                    - This is for public tender analysis
                    - Focus on specific terms, requirements, and technical specifications
                    - Consider both formal requirements and technical details
                    - Include any numerical values, dates, or specific qualifications
                    - Extract terms that would be most useful for finding relevant documents in the tender
                    
                    Return ONLY a JSON array of strings, with each string being a keyword or key phrase.
                    Example format: ["keyword1", "key phrase 2", "technical term 3"]
                    
                    Criterion name: {criterion.name}
                    Criterion description: {criterion.description}
                    """

                    keyword_request = LLMSearchRequest(
                        query=keyword_extraction_prompt,
                        llm={
                            "provider": "openai",
                            "model": "gpt-4o-mini",
                            "temperature": 0,
                            "max_tokens": 4000,
                            "system_message": "You are a keyword extraction system. Extract only the most relevant search terms.",
                            "stream": False,
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "keyword_extraction_response",
                                    "strict": True,
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "keywords": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            }
                                        },
                                        "required": ["keywords"],
                                        "additionalProperties": False
                                    }
                                }
                            }
                        }
                    )

                    keyword_response = await ask_llm_logic(keyword_request)
                    response_data = json.loads(keyword_response.llm_response)
                    keywords = response_data["keywords"]
                    logger.info(f"Extracted keywords for criterion {criterion.name}: {keywords}")

                    # Build Elasticsearch query using the extracted keywords
                    should_clauses = []
                    for keyword in keywords:
                        should_clauses.append({"match": {"text": keyword}})

                    es_query = {
                        "bool": {
                            "should": should_clauses,
                            "minimum_should_match": 1,
                            "filter": [
                                {"term": {"metadata.tender_pinecone_id.keyword": self.tender_pinecone_id}}
                            ]
                        }
                    }
                    
                    try:
                        es_results = es_client.search(
                            index=self.es_config.index_name,
                            body={
                                "query": es_query,
                                "size": 5
                            }
                        )
                        
                        # Use a set to track unique texts
                        seen_texts = set()
                        unique_results = []
                        
                        for hit in es_results["hits"]["hits"]:
                            text = hit["_source"]["text"]
                            # Only add if we haven't seen this text before
                            if text not in seen_texts:
                                seen_texts.add(text)
                                unique_results.append({
                                    "text": text,
                                    "score": hit["_score"],
                                    "source": hit["_source"]["metadata"]["source"]
                                })
                        
                        # Create the enhanced elasticsearch_results object
                        elastic_search_results = {
                            "results": unique_results,
                            "search_keywords": keywords,
                            "total_matches": len(unique_results)
                        }
                        
                    except Exception as e:
                        logger.error(f"Error during Elasticsearch search: {str(e)}", exc_info=True)
                        elastic_search_results = {
                            "results": [],
                            "search_keywords": keywords,
                            "total_matches": 0
                        }

                # Handle subcriteria queries if present
                subcriteria_results = []
                if hasattr(criterion, 'subcriteria') and criterion.subcriteria and len(criterion.subcriteria) > 0:
                    # Create tasks for all subcriteria queries
                    subcriteria_tasks = [
                        self.analyze_subcriteria(subcrit, self.tender_pinecone_id)
                        for subcrit in criterion.subcriteria
                    ]
                    
                    # Execute all subcriteria queries concurrently
                    subcriteria_results = await asyncio.gather(*subcriteria_tasks)
                    
                    # Add subcriteria results to the prompt
                    if any(result["vector_total_matches"] > 0 or result["elasticsearch_total_matches"] > 0 for result in subcriteria_results):
                        subcriteria_context = "\n\n<SUBCRITERIA_RESULTS>\n"
                        subcriteria_context += "Additional context from specific subqueries:\n\n"
                        
                        for result in subcriteria_results:
                            has_results = result["vector_total_matches"] > 0 or result["elasticsearch_total_matches"] > 0
                            if has_results:
                                subcriteria_context += f"\nResults for subquery: '{result['subcriteria']}'\n"
                                
                                # Add vector search results
                                if result["vector_total_matches"] > 0:
                                    subcriteria_context += "\nVector search results:\n"
                                    for idx, match in enumerate(result["vector_results"], 1):
                                        subcriteria_context += f"{idx}. From {match['metadata'].get('source', 'unknown')} ):\n{match['metadata'].get('text', '')}\n"
                                
                                # Add Elasticsearch results
                                if result["elasticsearch_total_matches"] > 0:
                                    subcriteria_context += "\nKeyword search results:\n"
                                    for idx, match in enumerate(result["elasticsearch_results"], 1):
                                        subcriteria_context += f"{idx}. From {match['source']}:\n{match['text']}\n"
                        
                        subcriteria_context += "\n</SUBCRITERIA_RESULTS>\n"
                        prompt += subcriteria_context

                # Add Elasticsearch results to the prompt if available
                if self.use_elasticsearch and elastic_search_results["total_matches"] > 0:
                    es_context = "\n\n<ELASTICSEARCH_RESULTS>\n"
                    es_context += "It was keywords search. Treat them as a context but do not overthink it as it was only keyword serach\n"
                    es_context += f"Keywords used in search: {', '.join(elastic_search_results['search_keywords'])}\n\n"
                    es_context += "Relevant document excerpts:\n"
                    for idx, result in enumerate(elastic_search_results["results"], 1):
                        es_context += f"\n{idx}. From {result['source']}:\n{result['text']}\n"
                    es_context += "\n</ELASTICSEARCH_RESULTS>\n"
                    prompt += es_context

                # Rest of your function remains the same
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "criteria_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "criteria": {"type": "string"},
                                "analysis": {
                                    "type": "object",
                                    "properties": {
                                        "summary": {"type": "string"},
                                        "confidence": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                                        "criteria_met": {"type": "boolean"}
                                    },
                                    "required": ["summary", "confidence", "criteria_met"],
                                    "additionalProperties": False
                                }
                            },
                            "required": ["criteria", "analysis"],
                            "additionalProperties": False
                        }
                    }
                }
                request_data = LLMRAGRequest(
                    query=prompt,
                    rag_query=criterion.description,
                    vector_store={
                        "index_name": self.index_name,
                        "namespace": self.namespace,
                        "embedding_model": self.embedding_model
                    },
                    llm={
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "temperature": 0,
                        "max_tokens": 4000,
                        "system_message": """You are a specialist in finding the response for criteria based on context.
                        You will have access to main DOCUMENT_CONTEXT which is result of vector search by main criteria text.
                        You can also recieve SUBCRITERIA_RESULTS which are results of vector searches by subcriteria queries.

                        You should answer to main question but also consider and point out subcriteria results if provided.
                        You should also stricly stick to optional ADDITIONAL INSTRUCTION if provided.
                        """ if subcriteria_results else "You are a specialist in finding the response for criteria based on context. You should also stricly stick to optional ADDITIONAL INSTRUCTION if provided.",
                        "stream": False, 
                        "response_format": response_format
                    }
                )
                response = await llm_rag_search_logic(request_data, self.tender_pinecone_id)
                parsed_output = json.loads(response.llm_response)

                # Add ES results to the output if available
                if elastic_search_results:
                    parsed_output["elasticsearch_results"] = elastic_search_results

                # Add subcriteria results to the output
                if subcriteria_results:
                    parsed_output["subcriteria_results"] = subcriteria_results

                if include_vector_results and hasattr(response, 'vector_search_results'):
                    parsed_output['vector_search_results'] = response.vector_search_results

                # logger.info(f"Received LLM response for criterion {criterion.name}: {parsed_output}")
                return parsed_output

            except Exception as e:
                logger.error(
                    f"Error analyzing criterion {criterion.name}: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        async def analyze_location() -> Dict[str, Any]:
            """
            Analyze the inquiry documents to find the tender location (Poland or otherwise).
            Returns a structured JSON with a single key: 'tender_location'.
            """
            try:
                prompt = """
                    Polish voivodeships to choose from: Dolnośląskie, Kujawsko-pomorskie, Lubelskie, Lubuskie, Łódzkie, Małopolskie, Mazowieckie, Opolskie, Podkarpackie, Podlaskie, Pomorskie, Śląskie, Świętokrzyskie, Warmińsko-mazurskie, Wielkopolskie, Zachodniopomorskie.
                    Please determine the geographic location in terms of:
                    - country (Kraj in polish. By default make it be Polska, only if you detect that is some other country then change to polish name of this contry. For example: Niemcy)
                    - voivodeship (Województwo in polish. Choose one from the listed ones. Do not change the form or name. Example: Wielkopolskie)
                    - city (Miejscowość/Miasto in polish. Example: Poznań)
                    If information is not provided just answer with UNKNOWN.
                    Always return your answer in a structured output format.
                    """

                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                            "name": "tender_location_response",
                            "strict": False,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "country": {"type": "string"},
                                    "city": {"type": "string"},
                                    "voivodeship": {"type": "string"},
                                },
                                "required": ["country", "city", "voivodeship"],
                                "additionalProperties": False
                            }
                    }
                }

                request_data = LLMRAGRequest(
                    query=prompt,
                    rag_query="Podaj kraj, województwie i miasto realizacji.",
                    vector_store={
                        "index_name": self.index_name,
                        "namespace": self.namespace,
                        "embedding_model": self.embedding_model
                    },
                    llm={
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "temperature": 0,
                        "max_tokens": 2000,
                        "system_message": "",
                        "stream": False, 
                        "response_format": response_format
                    }
                )
                response = await llm_rag_search_logic(request_data, self.tender_pinecone_id)
                parsed_output = json.loads(response.llm_response)

                if include_vector_results and hasattr(response, 'vector_search_results'):
                    parsed_output['vector_search_results'] = response.vector_search_results

                return parsed_output

            except Exception as e:
                logger.error(f"Error analyzing tender location: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        batch_size = 4
        semaphore = asyncio.Semaphore(batch_size)

        async def process_one_criterion(crit: AnalysisCriteria):
            async with semaphore:
                return await analyze_one_criteria(
                    criterion=crit
                )

        async def process_location_task():
            async with semaphore:
                return await analyze_location()

        # Create tasks for each criterion
        criteria_tasks = [process_one_criterion(c) for c in criteria]

        # Create one task for the location
        location_task = process_location_task()

        # Gather all tasks (criteria + location)
        all_tasks = criteria_tasks + [location_task]  # Add the location task to the list
        all_results = await asyncio.gather(*all_tasks)

        # The last item is the location result, the rest are criteria results
        location_result = all_results[-1]
        criteria_results = all_results[:-1]

        result = {
                "analysis": {
                    "criteria_analysis": criteria_results,
                    "location": location_result
                },
        }

        if include_vector_results:
            # Collect all vector search results
            vector_results = {
                "criteria": [r.get('vector_search_results', {}) for r in criteria_results if 'vector_search_results' in r],
                "location": location_result.get('vector_search_results', {})
            }
            result["vector_search_results"] = vector_results

        # Memory log at end
        log_mem(f"{self.tender_pinecone_id} analyze_tender_criteria_and_location:end")
        return result


    async def generate_tender_description(self) -> str:
        # Memory log before generating description
        log_mem(f"{self.tender_pinecone_id} generate_tender_description:start")
        # Create thread and add initial message
        prompt = (
                    "Please summarize exactly what this tender is about in Polish (public tender is zamówienie publiczne in polish).."
                    "Focus on the scope, main deliverables like products and services (with parameters if present), be concise and on point."
                    "If you detect that there is no enough data to create summary or it doesn't make sense resopond with 'Brak danych'."
                    "Respond with just the complete summary. (do not include the confidence level indicator)"
                )

        request_data = LLMRAGRequest(
            query=prompt,
            # rag_query="Podaj wszystkie produkty/usługi i opis tego co jest przedmiotem zamówienia.",
            rag_query="Podaj opis tego co jest przedmiotem zamówienia.",
            vector_store={
                "index_name": self.index_name,
                "namespace": self.namespace,
                "embedding_model": self.embedding_model
            },
            llm={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.6,
                "max_tokens": 2000,
                "system_message": "",
                "stream": False,
            }
        )
        response = await llm_rag_search_logic(request_data, self.tender_pinecone_id)

        # Remove any '【...】' placeholders using regex
        description = re.sub(r'【.*?】', '', response.llm_response)

        # Memory log after generating description
        log_mem(f"{self.tender_pinecone_id} generate_tender_description:end")

        # Clean up and return
        return description.strip()


    @staticmethod
    async def ai_filter_tenders_based_on_description(tender_analysis: TenderAnalysis, tender_matches: List[Union[TenderAnalysisResult, TenderToAnalyseDescription]], current_user: User) -> TenderDecriptionProfileMatches:
        tenders_list_to_analyze = [
            dict_.model_dump(include={'id', 'tender_metadata',
                                    'tender_description'})
            for dict_ in tender_matches
        ]

        # System prompt focused on model behavior/role
        system_prompt = """
        You are a precise tender evaluation system that identifies which business opportunities match a what company is looking for. 
        You excel at understanding company profile and requirements, determining if there's a good fit.
        You provide accurate scoring, filtering out irrelevant opportunities while identifying the ones matching the search criteria.
        You follow instructions exactly and provide responses formatted as specified.
        """

        # User prompt focused on task details and conditional rules
        prompt = f"""
        # EVALUATION TASK
        Evaluate which tenders match what this company is looking for.

        # COMPANY INFORMATION:
        About company: '{tender_analysis.company_description}'

        # FILTERING RULES:
        {tender_analysis.filtering_rules if tender_analysis.filtering_rules else "-"}

        # INSTRUCTIONS:
        1. Review each tender's description carefully.
        2. Return ONLY relevant tenders.
        3. Completely exclude tenders that violate any filtering rules

        # OUTPUT FORMAT:
        Return JSON with this structure:
        {{
        "matches": [
            {{
            "id": "..."
            }},
            ...
        ]
        }}

        # TENDERS TO CHOOSE FROM:
        {tenders_list_to_analyze}
        """
        # print(f"filtering with description using prompt: {prompt}")           
        request_data = LLMRAGRequest(
            query=prompt,
            rag_query="Nothing here",
            vector_store=None,
            llm={
                "provider": "openai",
                "model": "gpt-4.1",
                "temperature": 0,
                "max_tokens": 30000,
                "system_message": system_prompt,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "tender_matches_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "matches": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"}
                                        },
                                        "required": ["id"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["matches"],
                            "additionalProperties": False
                        }
                    }
                }
            }
        )
        response = await ask_llm_logic(request_data)
        parsed_output = json.loads(response.llm_response)

        return TenderDecriptionProfileMatches(**parsed_output)
