import pprint
import re
from uuid import uuid4
from bson import ObjectId
from minerva.core.services.vectorstore.helpers import MAX_TOKENS, count_tokens, safe_chunk_text
from minerva.api.routes.retrieval_routes import sanitize_id
from minerva.core.models.file import FilePineconeConfig
from minerva.core.models.request.ai import LLMSearchRequest, LLMRAGRequest
from minerva.core.services.llm_logic import ask_llm_logic, llm_rag_search_logic
from minerva.core.models.user import User
from minerva.core.middleware.token_tracking import update_user_token_usage
from minerva.core.models.extensions.tenders.tender_analysis import AnalysisCriteria, TenderAnalysis, TenderAnalysisResult, TenderDecriptionProfileMatches, TenderProfileMatches, TenderToAnalyseDescription, Citation
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, EmbeddingTool
from minerva.core.services.vectorstore.text_chunks import ChunkingConfig, TextChunker
from minerva.tasks.services.keyword_service import KeywordPresenceValidator
from minerva.core.services.llm_providers.model_config import get_model_config, get_optimal_max_tokens
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

# Whitelist of user IDs that get access to gpt-4.1-mini model
PREMIUM_MODEL_USERS = {
    "67c6cb742fee91862e135247", #hydratec
    "67e0fc72cc9438c03bab1601", #eupol
    "6841555abb4e90deb07f9690", #hebu
    "68357b5f94b3cd20aaae436d", #hammermed
    "67f129dc9f404265240342df", #projectsteel
    "67f129dc9f404265240342df", #foliarex
    "67e8300a74179050a8ad7db2", #neomed
    "67ef3e119f404265240341d9", #esinvest
    "682847cfc6e45120af03fca1", #ironmountain
    "680608e336901be8673cc7c6", #masterprint
    "681b17c837e582ff42246c52", #annfil
    "683e9cbeef2a46d00c424c0e", #senda
    "679736290723807cbe67ad15", #ondre
    "680f94b869d687dfec1ed9e6", #testaccount
    "6846ac0084451731b166b6ca", #arison construction
    "68497788549963dce215b3f4" #wodpol
}

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


def safe_json_loads(json_string: str, fallback_response: dict, context: str = "unknown") -> dict:
    """
    Safely parse JSON with error handling for Unicode escape issues.
    
    Args:
        json_string: The JSON string to parse
        fallback_response: Default response to return if parsing fails
        context: Context description for logging purposes
    
    Returns:
        Parsed JSON dict or fallback response
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as json_error:
        logger.warning(f"Initial JSON parsing failed for {context}: {str(json_error)}")
        
        # Try to sanitize the response by fixing common Unicode escape issues
        sanitized_response = json_string
        
        # Fix incomplete Unicode escapes by removing malformed \u sequences
        sanitized_response = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', sanitized_response)
        
        # Try parsing again
        try:
            parsed_output = json.loads(sanitized_response)
            logger.info(f"Successfully parsed JSON after sanitization for {context}")
            return parsed_output
        except json.JSONDecodeError as second_error:
            logger.error(f"JSON parsing failed even after sanitization for {context}: {str(second_error)}")
            return fallback_response


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
        chunk_overlap: int = 400
    ):
        self.index_name = index_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

class RAGManager:
    def __init__(self, index_name: str, namespace: str, embedding_model: str, tender_pinecone_id: str, use_elasticsearch: bool = False, es_config: Optional[ElasticsearchConfig] = None, language: str = "polish", tender_url: Optional[str] = None):
        # Memory log on RAGManager init
        log_mem(f"{tender_pinecone_id} RAGManager:init")
        
        self.index_name = index_name
        self.namespace = namespace
        self.embedding_model = embedding_model
        self.tender_pinecone_id = tender_pinecone_id
        self.tender_url = tender_url  # Store tender URL for logging context
        
        self.chunker = TextChunker(ChunkingConfig())
        
        self.embedding_tool = EmbeddingTool(EmbeddingConfig(
            index_name=index_name, namespace=namespace, embedding_model=embedding_model))
        
        self.temp_dir = tempfile.mkdtemp()
        
        self.registry = ExtractorRegistry()
        
        self.use_elasticsearch = use_elasticsearch
        self.es_config = es_config or ElasticsearchConfig()
        
        self.keyword_validator = KeywordPresenceValidator(es_client, self.es_config.index_name)
        
        if language is None:
            language = "polish"
        
        self.language = language.lower()
            
        # Ensure Elasticsearch index exists if enabled
        if self.use_elasticsearch:
            self._ensure_elasticsearch_index_pending = True

    async def ensure_elasticsearch_index_initialized(self):
        """Initialize Elasticsearch index if needed. This should be called after RAGManager creation."""
        if self.use_elasticsearch and getattr(self, '_ensure_elasticsearch_index_pending', False):
            await self.ensure_elasticsearch_index()
            self._ensure_elasticsearch_index_pending = False

    async def ensure_elasticsearch_index(self):
        """Create or update Elasticsearch index with proper mappings for file chunks"""
        if not await es_client.indices.exists(index=self.es_config.index_name):
            # Create index with mappings
            mappings = {
                "mappings": {
                    "properties": {
                        "text": {
                            "type": "text"
                        },
                        "metadata": {
                            "type": "object",
                            "dynamic": True,
                            "properties": {
                                "source": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword"
                                        }
                                    }
                                },
                                "sanitized_filename": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword"
                                        }
                                    }
                                },
                                "file_id": {
                                    "type": "keyword"
                                },
                                "tender_pinecone_id": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword"
                                        }
                                    }
                                }
                            }
                        },
                        "created_at": {
                            "type": "date",
                            "format": "strict_date_optional_time||epoch_millis"
                        }
                    }
                }
            }
            await es_client.indices.create(
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
                        "dynamic": True,
                        "properties": {
                            "source": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            },
                            "sanitized_filename": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            },
                            "file_id": {
                                "type": "keyword"
                            },
                            "tender_pinecone_id": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
                    },
                    "created_at": {
                        "type": "date",
                        "format": "strict_date_optional_time||epoch_millis"
                    }
                }
            }
            await es_client.indices.put_mapping(
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

    # Default batch size for embedding/upsert operations. Pinecone supports up to 100 vectors per
    # request, so we use 100 to maximize throughput unless overridden via the environment.
    EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "25"))

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
            
            success, failed = await helpers.async_bulk(es_client, actions, stats_only=True)
            return success > 0 and failed == 0
            
        except Exception as e:
            logger.error(f"Error indexing chunk to Elasticsearch: {str(e)}")
            return False

    async def upload_file_content(
        self,
        file_content: bytes,
        filename: str,
    ) -> FilePineconeConfig:
        tender_context = f"[{self.tender_url}]" if self.tender_url else f"[{self.tender_pinecone_id}]"
        log_mem(f"{self.tender_pinecone_id} upload:start:{filename}")

        sanitized_filename = sanitize_id(filename)
        filename_unique_prefix = f"{sanitized_filename}_{uuid4()}"

        # Extract text using the appropriate extractor first
        import tempfile
        from pathlib import Path
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
            tmp_file.write(file_content if isinstance(file_content, (bytes, bytearray)) else file_content.encode())
            tmp_file.flush()
            tmp_path = Path(tmp_file.name)
            
            try:
                # Get the appropriate extractor and set tender context if it supports it
                extractor = self.registry.get(tmp_path.suffix.lower())
                if extractor and hasattr(extractor, 'set_tender_context'):
                    extractor.set_tender_context(tender_url=self.tender_url, tender_id=self.tender_pinecone_id)
                
                # Extract text content
                file_content_list = list(extractor.extract_file_content(tmp_path)) if extractor else []
                if file_content_list:
                    text = file_content_list[0].content
                else:
                    text = file_content.decode() if isinstance(file_content, (bytes, bytearray)) else file_content
            except Exception as e:
                logger.warning(f"{tender_context} Error extracting content from {filename}: {e}")
                text = file_content.decode() if isinstance(file_content, (bytes, bytearray)) else file_content
            finally:
                # Clean up temp file
                try:
                    tmp_path.unlink()
                except:
                    pass

        file_content = None
        gc.collect()

        # Check if this is a technical drawing that was skipped
        is_technical_drawing = text.strip() == "__TECHNICAL_DRAWING_SKIP_OCR__"
        
        if is_technical_drawing:
            logger.info(f"{tender_context} Technical drawing detected for {filename} - storing file metadata only, skipping vector indexing (file will still be stored in S3)")
            return FilePineconeConfig(
                query_config=QueryConfig(self.index_name, self.namespace, self.embedding_model),
                pinecone_unique_id_prefix=filename_unique_prefix,
                is_technical_drawing=True,  # Add this flag if the model supports it
            )

        if not text or not text.strip():
            logger.info(f"{tender_context} No text content extracted from {filename}")
            return FilePineconeConfig(
                query_config=QueryConfig(
                    index_name=self.index_name,
                    namespace=self.namespace,
                    embedding_model=self.embedding_model
                ),
                pinecone_unique_id_prefix=filename_unique_prefix
            )
                
        logger.info(f"{tender_context} Processing {filename} - {len(text)} characters extracted")

        async def gen_actions():
            chunk_index_global = 0
            batch_for_pinecone = []
            total_tokens_for_embedding = 0
        
            for chunk in safe_chunk_text(text, self.chunker, self.embedding_model):
                if not chunk or not chunk.strip():
                    continue

                tokens = count_tokens(chunk, self.embedding_model)
                total_tokens_for_embedding += tokens
                if count_tokens(chunk, self.embedding_model) > MAX_TOKENS:
                    logger.error("Chunk %s from %s over token limit", chunk_index_global, filename)
                    chunk_index_global += 1
                    continue

                chunk_id = f"{filename_unique_prefix}_{uuid4()}"
                metadata = {
                    "tender_pinecone_id": self.tender_pinecone_id,
                    "source": filename,  # Keep original filename as source
                    "sanitized_filename": sanitized_filename,  # Add sanitized version for internal use
                    "file_id": filename_unique_prefix,  # Add unique file identifier
                    "extractor": "",
                    "source_type": "",
                    "chunk_index": chunk_index_global,
                    "preview": chunk[:200],
                    "text": chunk,
                    "timestamp": datetime.now().isoformat(),
                }

                batch_for_pinecone.append({"id": chunk_id, "input": chunk, "metadata": metadata})

                if self.use_elasticsearch:
                    action = {
                        "_index": self.es_config.index_name,
                        "_id": chunk_id,
                        "_source": {
                            "text": chunk,
                            "metadata": metadata,
                            "created_at": datetime.utcnow().isoformat(),
                        },
                    }
                    yield action
                chunk_index_global += 1

                if len(batch_for_pinecone) >= self.EMBED_BATCH_SIZE:
                    # Track embedding cost before calling embed_and_store_batch
                    batch_tokens = sum(count_tokens(item["input"], self.embedding_model) for item in batch_for_pinecone)
                    await self._track_embedding_batch(batch_tokens)
                    
                    await self.embedding_tool.embed_and_store_batch(batch_for_pinecone)
                    batch_for_pinecone.clear()
                    
            if batch_for_pinecone:
                # Track embedding cost for final batch
                batch_tokens = sum(count_tokens(item["input"], self.embedding_model) for item in batch_for_pinecone)
                await self._track_embedding_batch(batch_tokens)
                
                await self.embedding_tool.embed_and_store_batch(batch_for_pinecone)

        # Always process Elasticsearch if enabled
        if self.use_elasticsearch:
            async for ok, info in helpers.async_streaming_bulk(
                    es_client,
                    actions=gen_actions(),
                    chunk_size=1_000,
                    max_chunk_bytes=5 * 1024 ** 2,
                    raise_on_error=False,
                    raise_on_exception=False,
            ):
                if not ok:
                    logger.warning("Failed ES item: %s", info)
        else:
            # If Elasticsearch is disabled, still need to process the generator to handle Pinecone uploads
            async for _ in gen_actions():
                pass
        text = None
        gc.collect(); malloc_trim()
        log_mem(f"{self.tender_pinecone_id} upload:after:{filename}")
    

        return FilePineconeConfig(
            query_config=QueryConfig(
                index_name=self.index_name,
                namespace=self.namespace,
                embedding_model=self.embedding_model
            ),
            pinecone_unique_id_prefix=filename_unique_prefix,
            elasticsearch_indexed=self.use_elasticsearch,
        )

    async def _track_embedding_batch(self, token_count: int):
        """Track embedding costs for a batch of embeddings"""
        try:
            from minerva.core.services.llm_logic import track_embedding_call
            await track_embedding_call(
                model_name=self.embedding_model,
                input_tokens=token_count
            )
        except Exception as e:
            logger.debug(f"Error tracking embedding costs: {str(e)}")
            pass
        
    @staticmethod
    async def ai_filter_tenders(
        tender_analysis: TenderAnalysis,
        tender_matches: List[dict],
        current_user: Optional[User] = None,
        run_id: Optional[str] = None  # Added for tracking multiple runs
    ) -> TenderProfileMatches:
        # Memory log before AI tender filtering
        log_mem(f"ai_filter_tenders:start:{run_id or 'single'}")
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

        # Use model configuration helper
        ai_filter_model = "o4-mini"
        ai_filter_provider, ai_filter_max_tokens = get_model_config(ai_filter_model)
        
        request_data = LLMSearchRequest(
            query=user_message,
            vector_store=None,
            llm={
                "provider": ai_filter_provider,
                "model": ai_filter_model,
                "temperature": 0,
                # "max_tokens": ai_filter_optimized_tokens,
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
                                    "description": "List of tenders that match the provided company profile and requirements.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string", "description": "Exact ID (usually full url) of the tender from the input list"},
                                            "name": {"type": "string", "description": "Full title of the tender"},
                                            "organization": {"type": "string", "description": "Organization issuing the tender"}
                                        },
                                        "required": ["id", "name", "organization"],
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
            try:
                parsed_output = json.loads(response.llm_response)
            except json.JSONDecodeError as json_error:
                logger.warning(f"Initial JSON parsing failed for ai_filter_tenders: {str(json_error)}")
                
                # Try to sanitize the response by fixing common Unicode escape issues
                sanitized_response = response.llm_response
                
                # Fix incomplete Unicode escapes by removing malformed \u sequences
                sanitized_response = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', sanitized_response)
                
                # Try parsing again
                try:
                    parsed_output = json.loads(sanitized_response)
                    logger.info(f"Successfully parsed JSON after sanitization for ai_filter_tenders")
                except json.JSONDecodeError as second_error:
                    logger.error(f"JSON parsing failed even after sanitization for ai_filter_tenders: {str(second_error)}")
                    # Return a fallback response structure
                    parsed_output = {"matches": []}

            # Post-process to ensure 'id' is present (fallback if OpenAI omits it)
            tender_lookup = {match["id"]: match for match in tender_matches}
            for match in parsed_output["matches"]:
                if "id" not in match or not match["id"]:
                    original_match = tender_lookup.get(match.get("id", ""), {})
                    match["id"] = original_match.get("id", match.get("id", "unknown"))
                    if match["id"] == "unknown":
                        logger.warning(f"Could not find ID for tender: {match['name']}")

            # Memory log after AI tender filtering
            log_mem(f"ai_filter_tenders:end:{run_id or 'single'}")
            return TenderProfileMatches(**parsed_output)
        
        except Exception as e:
            logger.error(f"Error filtering tenders with AI: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to filter tenders: {str(e)}")
        
    @staticmethod
    async def ai_filter_tenders_with_subject(        
        tender_analysis: TenderAnalysis,
        tender_matches: list[dict],
        current_user: Optional[User] = None,
        run_id: Optional[str] = None
    ) -> TenderProfileMatches:
        """
        Same job as ai_filter_tenders, but every tender item *must* contain
        `subject_match.text`.  That chunk is forwarded to the LLM so it can make
        decisions based on the detailed paragraph, not only the headline fields.
        """
        log_mem(f"ai_filter_tenders_with_subject:start:{run_id or 'single'}")

        # Flatten <TENDER> so the LLM sees the paragraph right next to the meta.
        # (Avoids pushing a nested dict to the model.)
        prepared = []
        for t in tender_matches:
            text = t.get("subject_match", {}).get("text", "")
            prepared.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "organization": t["organization"],
                    "location": t.get("location", ""),
                    "semantic_chunk": text,
                }
            )

        system_message = (
            "You are a well-balanced system that identifies public tenders that "
            "best match the company profile and offer. Only return relevant tenders."
        )

        user_message = (
            "Look at the company profile in <COMPANY_PROFILE> and pick only public "
            "tenders from <PUBLIC_TENDERS_LIST> that match the company profile.\n"
            "Those tenders could have names not directly connected to company profile, so verify their relevance mainly based on 'semantic_chunk' which is text fragment from tender description"
            " but those were name is for sure not relevant should be rejected."
            f"<COMPANY_PROFILE>\n\"{tender_analysis.company_description}\"\n</COMPANY_PROFILE>\n"
            f"<PUBLIC_TENDERS_LIST>{json.dumps(prepared)}\n</PUBLIC_TENDERS_LIST>\n"
            "The output JSON must strictly follow this schema:\n"
            "{\n"
            "   \"matches\": [\n"
            "      {\"id\": \"…\", \"name\": \"…\", \"organization\": \"…\"}, …\n"
            "   ]\n"
            "}\n"
        )

        ai_filter_model = "o4-mini"
        provider, max_tokens = get_model_config(ai_filter_model)

        request_data = LLMSearchRequest(
            query=user_message,
            vector_store=None,
            llm={
                "provider": provider,
                "model": ai_filter_model,
                "temperature": 0,
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
                                            "organization": {"type": "string"}
                                        },
                                        "required": ["id", "name", "organization"],
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
             # Add robust JSON parsing with error handling
            try:
                parsed_output = json.loads(response.llm_response)
            except json.JSONDecodeError as json_error:
                logger.warning(f"Initial JSON parsing failed for ai_filter_tenders: {str(json_error)}")
                
                # Try to sanitize the response by fixing common Unicode escape issues
                sanitized_response = response.llm_response
                
                # Fix incomplete Unicode escapes by removing malformed \u sequences
                sanitized_response = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', sanitized_response)
                
                # Try parsing again
                try:
                    parsed_output = json.loads(sanitized_response)
                    logger.info(f"Successfully parsed JSON after sanitization for ai_filter_tenders")
                except json.JSONDecodeError as second_error:
                    logger.error(f"JSON parsing failed even after sanitization for ai_filter_tenders: {str(second_error)}")
                    # Return a fallback response structure
                    parsed_output = {"matches": []}
            
            # Post-process to ensure 'id' is present (fallback if OpenAI omits it)
            tender_lookup = {match["id"]: match for match in tender_matches}
            for match in parsed_output["matches"]:
                if "id" not in match or not match["id"]:
                    original_match = tender_lookup.get(match.get("id", ""), {})
                    match["id"] = original_match.get("id", match.get("id", "unknown"))
                    if match["id"] == "unknown":
                        logger.warning(f"Could not find ID for tender: {match['name']}")

            if current_user and hasattr(response, "usage") and response.usage:
                total_tokens = response.usage.get('total_tokens', 0) if isinstance(response.usage, dict) else getattr(response.usage, 'total_tokens', 0)
                if total_tokens > 0:
                    await update_user_token_usage(str(current_user.id), total_tokens)
            # …
            log_mem(f"ai_filter_tenders_with_subject:end:{run_id or 'single'}")
            return TenderProfileMatches(**parsed_output)
        except Exception as exc:
            logger.error("Error in ai_filter_tenders_with_subject", exc_info=True)
            raise HTTPException(status_code=500, detail=f"AI tender filtering failed: {exc}")

    @staticmethod
    async def ai_review_filter_results(
        tender_analysis: TenderAnalysis,
        filtered_tenders: List[dict],
        filtered_out_tenders: List[dict],
        current_user: Optional[User] = None
    ) -> Dict[str, List[dict]]:
        """
        Review initial filtering results and make corrections if needed.
        """
        log_mem("ai_review_filter_results:start")
        
        system_message = (
            "You are a quality assurance system that reviews tender filtering decisions. "
            # "Analyze filtered-out tenders to ensure accuracy. "
            "Analyze both the filtered and filtered-out tenders to ensure accuracy. "
            "You can move tenders between categories if needed."
        )
        
        user_message = (
            "Review the filtering results based on the company profile in <COMPANY_PROFILE>.\n"
            f"<COMPANY_PROFILE>\n\"{tender_analysis.company_description}\"\n</COMPANY_PROFILE>\n\n"
            f"Currently FILTERED IN (selected as relevant):\n<FILTERED_IN>{json.dumps(filtered_tenders)}</FILTERED_IN>\n\n"
            f"Currently FILTERED OUT (rejected as not relevant):\n<FILTERED_OUT>{json.dumps(filtered_out_tenders)}</FILTERED_OUT>\n\n"
            "Review these decisions and provide corrections."
            "YOU MUST PLACE EACH TENDER IN ONE OF THOSE CATEGORIES"
            # "Focus mainly on FILTERED OUT and if they have potential to go to FILTERED IN but also analyse fitered in in terms of rejecting some of them."
            " The output JSON must follow this schema:\n"
            "{\n"
            "   \"corrected_filtered_in\": [\n"
            "      {\"id\": \"exact-id\", \"name\": \"...\", \"organization\": \"...\", \"reason\": \"why this should be included\"},\n"
            "      ...\n"
            "   ],\n"
            "   \"corrected_filtered_out\": [\n"
            "      {\"id\": \"exact-id\", \"name\": \"...\", \"organization\": \"...\", \"reason\": \"why this should be excluded\"},\n"
            "      ...\n"
            "   ]\n"
            "}\n"
        )

        ai_filter_model = "o4-mini"
        ai_filter_provider, ai_filter_max_tokens = get_model_config(ai_filter_model)
        ai_filter_optimized_tokens = get_optimal_max_tokens(ai_filter_model, "high")


        # print(user_message)
        
        request_data = LLMSearchRequest(
            query=user_message,
            vector_store=None,
            llm={
                "provider": ai_filter_provider,
                "model": ai_filter_model,
                "temperature": 0,
                # "max_tokens": ai_filter_optimized_tokens,
                "system_message": system_message,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "review_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "corrected_filtered_in": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "organization": {"type": "string"},
                                            "reason": {"type": "string"}
                                        },
                                        "required": ["id", "name", "organization", "reason"],
                                        "additionalProperties": False
                                    }
                                },
                                "corrected_filtered_out": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "organization": {"type": "string"},
                                            "reason": {"type": "string"}
                                        },
                                        "required": ["id", "name", "organization", "reason"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["corrected_filtered_in", "corrected_filtered_out"],
                            "additionalProperties": False
                        }
                    }
                }
            }
        )

        try:
            response = await ask_llm_logic(request_data)
            
            try:
                parsed_output = json.loads(response.llm_response)
                pprint.pprint(parsed_output)
            except json.JSONDecodeError as json_error:
                logger.warning(f"JSON parsing failed for review: {str(json_error)}")
                # Return original results if parsing fails
                return {
                    "corrected_filtered_in": filtered_tenders,
                    "corrected_filtered_out": filtered_out_tenders
                }

            if current_user and hasattr(response, "usage") and response.usage:
                total_tokens = response.usage.get('total_tokens', 0) if isinstance(response.usage, dict) else getattr(response.usage, 'total_tokens', 0)
                if total_tokens > 0:
                    await update_user_token_usage(str(current_user.id), total_tokens)

            log_mem("ai_review_filter_results:end")
            return parsed_output
        
        except Exception as e:
            logger.error(f"Error in review filtering: {str(e)}", exc_info=True)
            # Return original results if review fails
            return {
                "corrected_filtered_in": filtered_tenders,
                "corrected_filtered_out": filtered_out_tenders
            }

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
                    es_results = await es_client.search(
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

    async def analyze_tender_criteria_and_location(self, current_user: User, criteria: List[AnalysisCriteria], include_vector_results: bool = False, original_tender_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
                    f"Please answer this user question based on the documentation content:\n"
                    f"<USER_QUESTION>{criterion.description}</USER_QUESTION>\n"
                )

                has_instruction = False
                if hasattr(criterion, 'instruction') and criterion.instruction:
                    has_instruction = True
                
                # Separate instruction guidance from JSON template
                instruction_guidance = ""
                if has_instruction:
                    instruction_guidance = f"\n<IMPORTANT_USER_INSTRUCTIONS>\n When writing your summary, please remember: '{criterion.instruction}'.\nBTW this is not part of the documentation. These are instructions from the user.\n</IMPORTANT_USER_INSTRUCTIONS>\n"
                
                # Clean placeholder for JSON template
                summary_placeholder = f"<Your concise answer to the '{criterion.description}' question based on the documentation and/or keyword presence{' strictly following the instructions provided' if has_instruction else ''}>"
                
                prompt_instructions = (
                    f"{instruction_guidance}"
                    f"<FORMATTING_GUIDE>\nPresent your summary in clean, readable format using:\n"
                    f"- **Bold text** for important terms and quantities\n"
                    f"- Lists (1. 2. 3. or -) to organize multiple items clearly\n"
                    f"- Line breaks between different topics for better readability\n</FORMATTING_GUIDE>"
                    f"The summary response must ALWAYS be in {self.language} unless the instruction states otherwise. Use native characters directly in JSON (no Unicode escapes like \\uXXXX). Ensure proper JSON formatting with escaped quotes and backslashes where needed.\n"
                    f"CRITICAL CITATION REQUIREMENT: In the 'citations' array, include ONLY the specific text fragments from the documentation that you actually used to support your analysis and 'criteria_met' decision. Each citation must contain the EXACT, UNMODIFIED text from the source document - do NOT add ellipsis (...), do NOT truncate, do NOT paraphrase, do NOT modify in any way. The citation text must be searchable with Ctrl+F in the original document.\n"
                    f"If you cannot find ANY relevant information in the provided tender documentation/keywords to answer the question or support your analysis, return an empty citations array []. However, only return empty citations when there is truly NO related information available - if there is even partial or tangentially related information that helps inform your decision, include those citations.\n"
                    f"Return your answer in the following JSON format. The value for the 'criteria' field in your JSON response MUST be an exact copy of the text from the <USER_QUESTION> tag provided in the input:\n"
                ) + f"""
                {{
                    "criteria": "<Exact copy of the input <USER_QUESTION>>",
                    "analysis": {{
                        "summary": "{summary_placeholder}",
                        "confidence": "<LOW|MEDIUM|HIGH - Your confidence in the summary and 'criteria_met' assessment based on the available information.>",
                        "criteria_met": <true|false based on answer to question based in summary. It must reflect the conclusions from summary.>
                    }},
                    "citations": [
                        {{
                            "text": "<EXACT, UNMODIFIED text fragment from documentation - must match source document exactly for Ctrl+F search - NO ellipsis, NO truncation>",
                            "source": "<Source filename>",
                            "keyword": "<Optional: keyword that led to this citation if applicable>"
                        }}
                    ]
                }}
                -----PUBLIC TENDER DOCUMENTATION STARTS HERE:
                """
                
                # Combine all parts
                prompt = base_prompt + prompt_instructions

                # Get vector search results
                keyword_validation_results = None
                if criterion.keywords and self.use_elasticsearch:                        # ← only run when user supplied keywords
                    keyword_validation_results = await self.keyword_validator.check_keywords(
                        tender_id=self.tender_pinecone_id,
                        keywords=criterion.keywords.split(",")
                    )

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
                        subcriteria_context = "\n\n<TENDER_DOCUMENTATION_CONTEXT>\n"
                        
                        for result in subcriteria_results:
                            has_results = result["vector_total_matches"] > 0 or result["elasticsearch_total_matches"] > 0
                            if has_results:
                                subcriteria_context += f"\nResults for subquery: '{result['subcriteria']}'\n"
                                
                                # Add vector search results
                                if result["vector_total_matches"] > 0:
                                    for idx, match in enumerate(result["vector_results"], 1):
                                        subcriteria_context += f"{idx}. From {match['metadata'].get('source', 'unknown')} ):\n{match['metadata'].get('text', '')}\n"
                                
                        subcriteria_context += "\n</TENDER_DOCUMENTATION_CONTEXT>\n"
                        prompt += subcriteria_context

                if keyword_validation_results and self.use_elasticsearch:
                    kw_ctx  = "\n\n<TENDER_DOCUMENTATION_KEYWORD_PRESENCE>\n"
                    if keyword_validation_results["hits"]:
                        kw_ctx += "The following keywords were found in tender documentation:\n"
                        for hit in keyword_validation_results["hits"]:
                            kw_ctx += f" - {hit['keyword']}:\n"
                            for i, snippet in enumerate(hit["snippets"], 1):
                                score_info = f" (score: {snippet.get('score', 'N/A'):.2f})" if 'score' in snippet else ""
                                kw_ctx += f"   {i}. From {snippet['source']}{score_info}: \"{snippet['text']}\"\n"
                    # if keyword_validation_results["missing"]:
                    #     kw_ctx += (
                    #         "The following keywords **were NOT found** in tender documentation: "
                    #         + ", ".join(keyword_validation_results["missing"])
                    #         + "\n"
                    #     )
                    kw_ctx += "</TENDER_DOCUMENTATION_KEYWORD_PRESENCE>\n"
                    prompt += kw_ctx

                # Rest of your function remains the same
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "criteria_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "criteria": {"type": "string", "description": "EXACT text of the criterion question."},
                                "analysis": {
                                    "type": "object",
                                    "description": "Detailed analysis regarding whether the criterion is met.",
                                    "properties": {
                                        "summary": {"type": "string", "description": "Concise, well-formatted markdown answer to the criterion question based on the documentation"},
                                        "confidence": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"], "description": "Confidence level in the assessment."},
                                        "criteria_met": {"type": "boolean", "description": "Whether the criterion is satisfied based on the documentation. It must reflect the conclusions from summary."}
                                    },
                                    "required": ["summary", "confidence", "criteria_met"],
                                    "additionalProperties": False
                                },
                                "citations": {
                                    "type": "array",
                                    "description": "Text extracts from documentation that directly support the analysis and criteria_met decision. Each citation must contain EXACT, UNMODIFIED text from source documents - no ellipsis, no truncation, no paraphrasing.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "text": {"type": "string", "description": "EXACT, UNMODIFIED text fragment from documentation - must be searchable with Ctrl+F in original document. NO ellipsis (...), NO truncation, NO modification."},
                                            "source": {"type": "string", "description": "Source filename or document identifier."},
                                            "keyword": {"type": "string", "description": "Keyword that led to this citation either from TENDER_DOCUMENTATION_KEYWORD_PRESENCE or QUESTION."}
                                        },
                                        "required": ["text", "source", "keyword"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["criteria", "analysis", "citations"],
                            "additionalProperties": False
                        }
                    }
                }
                
                # Determine model based on user ID whitelist
                # model_to_use = "gemini-2.5-flash-preview-05-20" if str(current_user.id) in PREMIUM_MODEL_USERS else "gpt-4o-mini"
                model_to_use = "gemini-2.5-flash"
                # Get provider and max_tokens from model configuration
                provider, max_tokens = get_model_config(model_to_use)
                
                # Use optimal max_tokens for high complexity task
                max_tokens = get_optimal_max_tokens(model_to_use, "low")
                
                # print(f"using model: {model_to_use}, max_tokens: {max_tokens}, provider: {provider}")
                request_data = LLMRAGRequest(
                    query=prompt,
                    rag_query=criterion.description,
                    vector_store={
                        "index_name": self.index_name,
                        "namespace": self.namespace,
                        "embedding_model": self.embedding_model
                    },
                    llm={
                        "provider": provider,
                        "model": model_to_use,
                        "temperature": 0,
                        "max_tokens": max_tokens,
                        "system_message": f"""You are a public tender expert with enormous expertise and knowledge in public tenders. 
                        You excel at finding the information in public tender documentation and determining if it is worth a proposal.
                        In your work you always ground your responses in the documentation context and respond thoughtfully, never making false assessments as it is a critical branch of our business.
                        Even the smallest mistake can cost millions and you perform the most accurate search you can.
                        You have access to TENDER_DOCUMENTATION_CONTEXT which is result of vector search in public tender documents.

                        CRITICAL CITATION RULE: When providing citations, you MUST include the EXACT, UNMODIFIED text from the source documents. Never add ellipsis (...), never truncate, never paraphrase, never modify the text in any way. The citation text must be exactly as it appears in the source document so it can be found with Ctrl+F search. This is absolutely critical for document verification.
                        Include ONLY the specific text fragments you actually used to make your assessment. Be precise and selective - include only the most relevant excerpts that directly support your analysis.
                        If there is absolutely no relevant information in the documentation to support your analysis, return an empty citations array. However, be conservative about this - if there is even minimal relevant information that informs your decision, include it as a citation.

                        Always respond in {self.language} unless specified otherwise.
                        """,
                        "stream": False, 
                        "response_format": response_format
                    }
                )

                response = await llm_rag_search_logic(request_data, self.tender_pinecone_id, 5)
                
                # Add robust JSON parsing with error handling
                try:
                    parsed_output = json.loads(response.llm_response)
                except json.JSONDecodeError as json_error:
                    logger.warning(f"Initial JSON parsing failed for criterion {criterion.description}: {str(json_error)}")
                    
                    # Try to sanitize the response by fixing common Unicode escape issues
                    sanitized_response = response.llm_response
                    
                    # Fix incomplete Unicode escapes by removing malformed \u sequences
                    sanitized_response = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', sanitized_response)
                    
                    # Try parsing again
                    try:
                        parsed_output = json.loads(sanitized_response)
                        logger.info(f"Successfully parsed JSON after sanitization for criterion {criterion.description}")
                    except json.JSONDecodeError as second_error:
                        logger.error(f"JSON parsing failed even after sanitization for criterion {criterion.description}: {str(second_error)}")
                        # Return a fallback response structure
                        parsed_output = {
                            "criteria": criterion.description,
                            "analysis": {
                                "summary": f"Error parsing LLM response: {str(second_error)}",
                                "confidence": "LOW",
                                "criteria_met": False
                            },
                            "citations": []
                        }

                # Convert the model's citations to Citation objects
                if "citations" in parsed_output and parsed_output["citations"]:
                    citations_list = []
                    for citation_data in parsed_output["citations"]:
                        citation = Citation(
                            text=citation_data.get("text", ""),
                            source=citation_data.get("source", ""),
                            keyword=citation_data.get("keyword", ""),
                            file_id=None,  # Model doesn't have access to file_id
                            sanitized_filename=None  # Model doesn't have access to sanitized_filename
                        )
                        citations_list.append(citation)
                    parsed_output["model_citations"] = citations_list
                else:
                    parsed_output["model_citations"] = []

                # Keep keyword validation results for reference but don't use as primary citations
                if keyword_validation_results:
                    parsed_output["keyword_validation_results"] = keyword_validation_results

                # Add subcriteria results to the output
                if subcriteria_results:
                    parsed_output["subcriteria_results"] = subcriteria_results

                if include_vector_results and hasattr(response, 'vector_search_results'):
                    parsed_output['vector_search_results'] = response.vector_search_results

                # logger.info(f"Received LLM response for criterion {criterion.description}: {parsed_output}")
                return parsed_output

            except Exception as e:
                logger.error(
                    f"Error analyzing criterion {criterion.description}: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        async def analyze_location() -> Dict[str, Any]:
            """
            Analyze the inquiry documents to find the tender location (Poland or otherwise).
            Returns a structured JSON with a single key: 'tender_location'.
            """
            try:
                prompt = f"""
                    Always respond in {self.language} unless specified otherwise.
                    if original_tender_metadata is provided, use it to determine the language of the tender.
                    original_tender_metadata: {original_tender_metadata}
                    Otherwise or if not all info is provided, based on the documents, determine the geographic location of the tender.
                    If you are not sure about the country, make it be Polska by default.
                    
                    For Polish tenders:
                    - Use Polish voivodeships: Dolnośląskie, Kujawsko-pomorskie, Lubelskie, Lubuskie, Łódzkie, Małopolskie, Mazowieckie, Opolskie, Podkarpackie, Podlaskie, Pomorskie, Śląskie, Świętokrzyskie, Warmińsko-mazurskie, Wielkopolskie, Zachodniopomorskie
                    - Use Polish names for countries (e.g., Niemcy for Germany)
                    
                    For non-Polish tenders:
                    - Use the country's name in specified language
                    - Set voivodeship to "UNKNOWN"
                    - Use the city name as provided in the documents
                    
                    Please determine the geographic location in terms of:
                    - country (Kraj in Polish)
                    - voivodeship (Województwo in Polish, only for Polish tenders)
                    - city (Miejscowość/Miasto in Polish)
                    
                    If information is not provided, answer with UNKNOWN.
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
                                    "country": {"type": "string", "description": "Country (in Polish) where the tender is executed."},
                                    "city": {"type": "string", "description": "City or locality of the tender execution."},
                                    "voivodeship": {"type": "string", "description": "Polish voivodeship (province) where the tender is located."},
                                },
                                "required": ["country", "city", "voivodeship"],
                                "additionalProperties": False
                            }
                    }
                }

                # Use model configuration helper
                location_model = "gpt-4.1-mini"
                location_provider, location_max_tokens = get_model_config(location_model)
                location_optimized_tokens = get_optimal_max_tokens(location_model, "low")
                
                request_data = LLMRAGRequest(
                    query=prompt,
                    rag_query="Podaj kraj, województwo i miasto dla przetargu.",
                    vector_store={
                        "index_name": self.index_name,
                        "namespace": self.namespace,
                        "embedding_model": self.embedding_model
                    },
                    llm={
                        "provider": location_provider,
                        "model": location_model,
                        "temperature": 0,
                        "max_tokens": location_optimized_tokens,
                        "system_message": "",
                        "stream": False, 
                        "response_format": response_format
                    }
                )
                response = await llm_rag_search_logic(request_data, self.tender_pinecone_id, 2)
                
                # Add robust JSON parsing with error handling
                try:
                    parsed_output = json.loads(response.llm_response)
                except json.JSONDecodeError as json_error:
                    logger.warning(f"Initial JSON parsing failed for location analysis: {str(json_error)}")
                    
                    # Try to sanitize the response by fixing common Unicode escape issues
                    sanitized_response = response.llm_response
                    
                    # Fix incomplete Unicode escapes by removing malformed \u sequences
                    sanitized_response = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', sanitized_response)
                    
                    # Try parsing again
                    try:
                        parsed_output = json.loads(sanitized_response)
                        logger.info(f"Successfully parsed JSON after sanitization for location analysis")
                    except json.JSONDecodeError as second_error:
                        logger.error(f"JSON parsing failed even after sanitization for location analysis: {str(second_error)}")
                        # Return a fallback response structure
                        parsed_output = {
                            "country": "UNKNOWN",
                            "city": "UNKNOWN", 
                            "voivodeship": "UNKNOWN"
                        }

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
        """Enhanced version with cost tracking"""
        # Memory log before generating description
        log_mem(f"{self.tender_pinecone_id} generate_tender_description_with_cost_tracking:start")
        
        prompt = (
                    f"Summarize exactly what this tender is about in {self.language} (public tender is zamówienie publiczne in polish).."
                    "Focus on the scope, main deliverables like products and services (with parameters if present), be concise and on point."
                    "If you detect that there is no enough data to create summary or it doesn't make sense resopond with information that you lack information about the tender."
                    "Respond with just the complete summary. \n"
                )

        # Use model configuration helper
        model_name = "gpt-4.1-mini"
        provider, max_tokens = get_model_config(model_name)
        optimized_tokens = get_optimal_max_tokens(model_name, "medium")
        
        request_data = LLMRAGRequest(
            query=prompt,
            rag_query="Podaj opis tego co jest przedmiotem zamówienia.",
            vector_store={
                "index_name": self.index_name,
                "namespace": self.namespace,
                "embedding_model": self.embedding_model
            },
            llm={
                "provider": provider,
                "model": model_name,
                "temperature": 0.6,
                "max_tokens": optimized_tokens,
                "system_message": f"You are a tender analysis specialist. Always respond in {self.language}.",
                "stream": False,
            }
        )
        response = await llm_rag_search_logic(request_data, self.tender_pinecone_id, 7)

        # Remove any '【...】' placeholders using regex
        description = re.sub(r'【.*?】', '', response.llm_response)

        # Memory log after generating description
        log_mem(f"{self.tender_pinecone_id} generate_tender_description_with_cost_tracking:end")

        # Clean up and return
        return description.strip()


    @staticmethod
    async def ai_filter_tenders_based_on_description(tender_analysis: TenderAnalysis, tender_matches: List[Union[TenderAnalysisResult, TenderToAnalyseDescription]], current_user: User) -> TenderDecriptionProfileMatches:
        # Check if filtering rules are present and include criteria if so
        has_filtering_rules = tender_analysis.filtering_rules and tender_analysis.filtering_rules.strip()
        
        tenders_list_to_analyze = []
        for dict_ in tender_matches:
            # Start with base fields
            tender_data = dict_.model_dump(include={'id', 'tender_metadata', 'tender_description'})
            
            # Add filtered criteria analysis if filtering rules are present
            if has_filtering_rules and hasattr(dict_, 'criteria_analysis') and dict_.criteria_analysis:
                filtered_criteria = []
                for criteria_item in dict_.criteria_analysis:
                    # Include only criteria (string) and analysis (summary, criteria_met)
                    filtered_criteria.append({
                        'criteria': criteria_item.criteria if hasattr(criteria_item, 'criteria') else criteria_item.get('criteria', ''),
                        'analysis': {
                            'summary': criteria_item.analysis.summary if hasattr(criteria_item, 'analysis') and hasattr(criteria_item.analysis, 'summary') else criteria_item.get('analysis', {}).get('summary', ''),
                            'criteria_met': criteria_item.analysis.criteria_met if hasattr(criteria_item, 'analysis') and hasattr(criteria_item.analysis, 'criteria_met') else criteria_item.get('analysis', {}).get('criteria_met', False)
                        }
                    })
                tender_data['criteria_analysis'] = filtered_criteria
            
            tenders_list_to_analyze.append(tender_data)

        # System prompt focused on model behavior/role
        system_prompt = """
        You are a precise tender evaluation system that identifies which business opportunities match a what company is looking for. 
        You excel at understanding company profile and requirements, determining if there's a good fit.
        You provide accurate scoring, filtering out irrelevant opportunities while identifying the ones matching the search criteria.
        You follow instructions exactly and provide responses formatted as specified.
        """

        # Base filtering instructions
        filtering_instructions = """
        1. Review each tender carefully.
        2. If in description there is not enough information (likely we failed to fetch) => evaluate tender solely based on the title
        3. Return ONLY tenders relevant for company search request.
        4. Only exclude tenders which description describes tender the company is not looking for.
        """
        
        # Add custom filtering rules if present
        if has_filtering_rules:
            filtering_instructions += f"""
        5. ADDITIONAL FILTERING RULES: {tender_analysis.filtering_rules}
        6. When criteria_analysis is available for a tender, use it alongside the description and title to make more informed filtering decisions.
        """

        # Determine if we need to use batching (only when filtering rules are present and we have criteria)
        needs_batching = has_filtering_rules and any(
            hasattr(dict_, 'criteria_analysis') and dict_.criteria_analysis 
            for dict_ in tender_matches
        )
        
        if needs_batching:
            # Process in batches of 25 when filtering rules are present with criteria
            BATCH_SIZE = 25
            all_matches = []
            
            for i in range(0, len(tenders_list_to_analyze), BATCH_SIZE):
                batch = tenders_list_to_analyze[i:i + BATCH_SIZE]
                
                # User prompt for this batch
                prompt = f"""
                <TASK>
                Analyze tender descriptions and titles from TENDERS_LIST. Return only tenders in OUTPUT_FORMAT matching the COMPANY_SEARCH_REQUEST based on FILTERING_INSTRUCTIONS.
                </TASK>

                <COMPANY_SEARCH_REQUEST>
                Message from company: '{tender_analysis.company_description}'
                </COMPANY_SEARCH_REQUEST>

                <FILTERING_INSTRUCTIONS>
                {filtering_instructions}
                </FILTERING_INSTRUCTIONS>

                <OUTPUT_FORMAT>
                Return JSON with this structure:
                {{
                "matches": [
                    {{
                    "id": "..."
                    }},
                    ...
                ]
                }}
                </OUTPUT_FORMAT>

                <TENDERS_LIST>
                {batch}
                </TENDERS_LIST>
                """
                # print(f'description prompt: \n{prompt}')
                
                # Use model configuration helper
                filter_model = "o4-mini"
                filter_provider, filter_max_tokens = get_model_config(filter_model)
                
                request_data = LLMRAGRequest(
                    query=prompt,
                    rag_query="Nothing here",
                    vector_store=None,
                    llm={
                        "provider": filter_provider,
                        "model": filter_model,
                        "temperature": 0,
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
                                            "description": "List of tenders that match the company's search criteria.",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string", "description": "Exact ID of the tender from the input list"}
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
                
                # Parse batch response with error handling
                batch_parsed_output = safe_json_loads(
                    response.llm_response, 
                    {"matches": []}, 
                    f"ai_filter_tenders_based_on_description batch {i//BATCH_SIZE + 1}"
                )
                
                # Add batch results to overall matches
                all_matches.extend(batch_parsed_output.get("matches", []))
                
                logger.info(f"Processed batch {i//BATCH_SIZE + 1}/{(len(tenders_list_to_analyze) + BATCH_SIZE - 1)//BATCH_SIZE} with {len(batch_parsed_output.get('matches', []))} matches")
            
            # Combine all batch results
            parsed_output = {"matches": all_matches}
            
        else:
            # Process all tenders at once (original behavior)
            prompt = f"""
            <TASK>
            Analyze tender descriptions and titles from TENDERS_LIST. Return only tenders in OUTPUT_FORMAT matching the COMPANY_SEARCH_REQUEST based on FILTERING_INSTRUCTIONS.
            </TASK>

            <COMPANY_SEARCH_REQUEST>
            Message from company: '{tender_analysis.company_description}'
            </COMPANY_SEARCH_REQUEST>

            <FILTERING_INSTRUCTIONS>
            {filtering_instructions}
            </FILTERING_INSTRUCTIONS>

            <OUTPUT_FORMAT>
            Return JSON with this structure:
            {{
            "matches": [
                {{
                "id": "..."
                }},
                ...
            ]
            }}
            </OUTPUT_FORMAT>

            <TENDERS_LIST>
            {tenders_list_to_analyze}
            </TENDERS_LIST>
            """
            # print(f'description prompt: \n{prompt}')
            # Use model configuration helper
            filter_model = "o4-mini"
            filter_provider, filter_max_tokens = get_model_config(filter_model)
            
            request_data = LLMRAGRequest(
                query=prompt,
                rag_query="Nothing here",
                vector_store=None,
                llm={
                    "provider": filter_provider,
                    "model": filter_model,
                    "temperature": 0,
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
                                        "description": "List of tenders that match the company's search criteria.",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string", "description": "Exact ID of the tender from the input list"}
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
            
            # Parse response with error handling
            parsed_output = safe_json_loads(
                response.llm_response, 
                {"matches": []}, 
                "ai_filter_tenders_based_on_description"
            )

        return TenderDecriptionProfileMatches(**parsed_output)