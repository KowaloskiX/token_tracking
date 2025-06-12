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

        batch_size = min(self.config.batch_size, len(items)) # Use config.batch_size

        logging.info(f"Processing {len(items)} items in batches of {batch_size if batch_size > 0 else len(items)} items per batch")

        for i in range(0, len(items), batch_size if batch_size > 0 else 1): # Handle batch_size=0 to mean all items
            actual_batch_size = batch_size if batch_size > 0 else len(items)
            batch_items_to_process = items[i:i + actual_batch_size]
            
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