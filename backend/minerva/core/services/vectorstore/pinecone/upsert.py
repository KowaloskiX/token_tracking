# services/vectorstore/upsert.py

import logging
import os
import asyncio
import concurrent.futures
import atexit
from typing import List, Dict, Any, Union, Optional
from minerva.core.services.vectorstore.helpers import MAX_TOKENS, count_tokens
from pinecone import Pinecone
from openai import AsyncOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from functools import partial

load_dotenv()

openai = AsyncOpenAI()

# Optional: Dedicated thread pool for blocking IO like Pinecone sync client
pinecone_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
# Register for clean shutdown
atexit.register(lambda: pinecone_executor.shutdown(wait=False))

pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

class EmbeddingConfig(BaseModel):
    index_name: str
    namespace: str = ""
    embedding_model: str = "text-embedding-3-large"
    encoding_format: str = "float"
    dimensions: int | None = None
    batch_size: int = 100

class EmbeddingTool:
    def __init__(self, config: EmbeddingConfig):
        self.openai = openai
        self.index = pinecone.Index(config.index_name)
        self.config = config
        self.loop = asyncio.get_running_loop() # Get loop for run_in_executor

    async def create_embedding(self, input: Union[str, List[str]]) -> List[List[float]]:
        """Create embeddings for input text(s)"""
        response = await self.openai.embeddings.create(
            input=input,
            model=self.config.embedding_model,
            encoding_format=self.config.encoding_format,
            dimensions=self.config.dimensions
        )
        return [data.embedding for data in response.data]

    def prepare_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metadata for storage by removing None values"""
        return {k: v for k, v in metadata.items() if v is not None}

    async def embed_and_store_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Batch create and store embeddings with metadata, with extractor/source logging."""
        processed_count = 0
        failed_items = []

        # Always use the configured batch_size (default 100). This is the maximum supported by
        # Pinecone bulk-upsert and gives best throughput.
        batch_size = self.config.batch_size

        logging.info(f"Processing {len(items)} items in batches of {batch_size} items per batch")

        for i in range(0, len(items), batch_size):
            batch_items_to_process = items[i:i + batch_size]
            
            batch_texts_for_embedding = []
            valid_items_for_batch = [] # Items that are within token limits and will be attempted

            for item in batch_items_to_process:
                item_input = item["input"]
                tokens = count_tokens(item_input, self.config.embedding_model)
                extractor = item["metadata"].get("extractor", "unknown")
                source_type = item["metadata"].get("source_type", "unknown")

                if tokens > MAX_TOKENS: # MAX_TOKENS is from .helpers
                    logging.error(
                        f"Chunk OVER LIMIT and SKIPPED: extractor={extractor}, source_type={source_type}, "
                        f"tokens={tokens}/{MAX_TOKENS}, id={item['id']}. Preview: {item_input[:120]!r}"
                    )
                    failed_items.append({
                        "item_id": item['id'],
                        "reason": f"Chunk exceeded MAX_TOKENS ({tokens}/{MAX_TOKENS}) and was skipped.",
                        "preview": item_input[:200] # Add preview of skipped item
                    })
                    continue # Skip this item, do not add to batch_texts_for_embedding
                
                # Original logging for chunks being embedded (optional)
                # logging.info(
                #     f"Embedding chunk: extractor={extractor}, source_type={source_type}, "
                #     f"tokens={tokens}, id={item['id']}, preview={item_input[:120]!r}"
                # )
                batch_texts_for_embedding.append(item_input)
                valid_items_for_batch.append(item)

            if not valid_items_for_batch: # If all items in this batch were too long
                continue

            try:
                logging.info(f"Creating embeddings for batch starting at index {i} (size: {len(batch_texts_for_embedding)})")
                embeddings = await self.create_embedding(batch_texts_for_embedding)

                vectors_to_upsert: list[dict[str, Any]] = []
                for item_data, embedding_values in zip(valid_items_for_batch, embeddings):
                    prepared_metadata = self.prepare_metadata(item_data["metadata"])
                    vectors_to_upsert.append({
                        "id": item_data["id"],
                        "values": embedding_values,
                        "metadata": prepared_metadata,
                    })
                    processed_count += 1

                if vectors_to_upsert: # Ensure there's something to upsert
                    await self.loop.run_in_executor(
                        pinecone_executor,
                        partial(self.index.upsert, vectors=vectors_to_upsert, namespace=self.config.namespace)
                    )

            except Exception as e:
                logging.error(f"Error processing batch starting at index {i}: {str(e)}")
                # If batch embedding fails, log these items as failed without individual retries here
                # Individual retries can be complex if the batch error isn't due to a single item
                for failed_item_in_batch in valid_items_for_batch:
                    failed_items.append({
                        "item_id": failed_item_in_batch['id'],
                        "reason": f"Part of batch that failed with error: {str(e)}",
                        "preview": failed_item_in_batch['input'][:200]
                    })

        return {
            "processed_count": processed_count,
            "total_items": len(items),
            "failed_items": failed_items,
        }


class UpsertTool:
    """Wrapper around EmbeddingTool to provide the expected interface for tender upserting."""
    
    def __init__(self, config: EmbeddingConfig):
        self.embedding_tool = EmbeddingTool(config)
        self.config = config

    def _create_searchable_content(self, tender_dict: Dict[str, Any]) -> str:
        """Create searchable text content from tender data"""
        content_parts = []
        
        # Basic tender info
        if tender_dict.get("name"):
            content_parts.append(f"Tender: {tender_dict['name']}")
        if tender_dict.get("organization"):
            content_parts.append(f"Organization: {tender_dict['organization']}")
        if tender_dict.get("location"):
            content_parts.append(f"Location: {tender_dict['location']}")
        
        # Historical tender specific fields
        if tender_dict.get("winner_name"):
            content_parts.append(f"Winner: {tender_dict['winner_name']}")
        if tender_dict.get("winner_location"):
            content_parts.append(f"Winner Location: {tender_dict['winner_location']}")
        if tender_dict.get("contract_value"):
            content_parts.append(f"Contract Value: {tender_dict['contract_value']}")
        if tender_dict.get("winning_price"):
            content_parts.append(f"Winning Price: {tender_dict['winning_price']}")
        if tender_dict.get("completion_status"):
            content_parts.append(f"Status: {tender_dict['completion_status']}")
        if tender_dict.get("realization_period"):
            content_parts.append(f"Realization Period: {tender_dict['realization_period']}")
        
        # Add full content if available (truncated for embedding)
        if tender_dict.get("full_content"):
            truncated_content = tender_dict["full_content"][:2000] if len(tender_dict["full_content"]) > 2000 else tender_dict["full_content"]
            content_parts.append(f"Details: {truncated_content}")
        
        return " | ".join(content_parts)

    async def upsert_tenders_from_dict(self, tenders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert tender dictionaries to the format expected by EmbeddingTool and upsert them."""
        
        items_for_embedding = []
        
        # Fields to exclude from metadata due to size limits (40KB max per vector in Pinecone)
        excluded_fields = {
            "searchable_content",  # Used for embedding input, not needed in metadata
            "full_content",        # Too large for metadata, but used in searchable content
        }
        
        for tender_dict in tenders:
            # Create searchable content for embedding
            searchable_content = tender_dict.get("searchable_content")
            if not searchable_content:
                searchable_content = self._create_searchable_content(tender_dict)
            
            # Create unique ID for the tender
            tender_id = tender_dict.get("details_url", f"tender_{len(items_for_embedding)}")
            
            # Prepare metadata - exclude large fields to stay within Pinecone's 40KB limit
            metadata = {}
            for k, v in tender_dict.items():
                if k not in excluded_fields and v is not None:
                    # Convert to string and limit size for safety
                    if isinstance(v, str) and len(v) > 1000:
                        # Truncate very long string fields
                        metadata[k] = v[:1000] + "..." if len(v) > 1000 else v
                    else:
                        metadata[k] = v
            
            # Create item in the format expected by EmbeddingTool
            item = {
                "id": tender_id,
                "input": searchable_content,
                "metadata": metadata
            }
            
            items_for_embedding.append(item)
        
        # Use the underlying EmbeddingTool to process the batch
        return await self.embedding_tool.embed_and_store_batch(items_for_embedding)