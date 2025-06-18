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

pinecone_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
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
        self.loop = asyncio.get_running_loop()

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

        batch_size = self.config.batch_size

        logging.info(f"Processing {len(items)} items in batches of {batch_size} items per batch")

        for i in range(0, len(items), batch_size):
            batch_items_to_process = items[i:i + batch_size]
            
            batch_texts_for_embedding = []
            valid_items_for_batch = []

            for item in batch_items_to_process:
                item_input = item["input"]
                tokens = count_tokens(item_input, self.config.embedding_model)
                extractor = item["metadata"].get("extractor", "unknown")
                source_type = item["metadata"].get("source_type", "unknown")

                if tokens > MAX_TOKENS:
                    logging.error(
                        f"Chunk OVER LIMIT and SKIPPED: extractor={extractor}, source_type={source_type}, "
                        f"tokens={tokens}/{MAX_TOKENS}, id={item['id']}. Preview: {item_input[:120]!r}"
                    )
                    failed_items.append({
                        "item_id": item['id'],
                        "reason": f"Chunk exceeded MAX_TOKENS ({tokens}/{MAX_TOKENS}) and was skipped.",
                        "preview": item_input[:200]
                    })
                    continue

                batch_texts_for_embedding.append(item_input)
                valid_items_for_batch.append(item)

            if not valid_items_for_batch:
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

                if vectors_to_upsert:
                    await self.loop.run_in_executor(
                        pinecone_executor,
                        partial(self.index.upsert, vectors=vectors_to_upsert, namespace=self.config.namespace)
                    )

            except Exception as e:
                logging.error(f"Error processing batch starting at index {i}: {str(e)}")
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
        
        if tender_dict.get("name"):
            content_parts.append(f"Tender: {tender_dict['name']}")
        if tender_dict.get("organization"):
            content_parts.append(f"Organization: {tender_dict['organization']}")
        if tender_dict.get("location"):
            content_parts.append(f"Location: {tender_dict['location']}")
        
        total_parts = tender_dict.get("total_parts", 1)
        if total_parts > 1:
            content_parts.append(f"Multi-part tender with {total_parts} parts")
            if tender_dict.get("parts_summary"):
                content_parts.append(f"Parts: {tender_dict['parts_summary']}")
        
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
        
        if tender_dict.get("parts") and len(tender_dict["parts"]) > 0:
            parts_details = []
            for part in tender_dict["parts"]:
                if isinstance(part, dict):
                    part_detail = f"Part {part.get('part_number', 'X')}: {part.get('description', 'No description')}"
                    if part.get('cpv_code'):
                        part_detail += f" (CPV: {part['cpv_code']})"
                    if part.get('part_value'):
                        part_detail += f" Value: {part['part_value']}"
                    if part.get('winner_name'):
                        part_detail += f" Winner: {part['winner_name']}"
                    parts_details.append(part_detail)
            
            if parts_details:
                content_parts.append("Detailed parts: " + " | ".join(parts_details))
        
        if tender_dict.get("full_content"):
            truncated_content = tender_dict["full_content"][:2000] if len(tender_dict["full_content"]) > 2000 else tender_dict["full_content"]
            content_parts.append(f"Details: {truncated_content}")
        
        return " | ".join(content_parts)

    async def upsert_tenders_from_dict(self, tenders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert tender dictionaries to the format expected by EmbeddingTool and upsert them."""
        
        items_for_embedding = []
        
        excluded_fields = {
            "searchable_content",
            "full_content",
            "parts",
            "content_type",
            "details_url",
            "source_type",
            "_content_type",
            "_details_url",
            "_source_type",
        }
        
        for tender_dict in tenders:
            searchable_content = tender_dict.get("searchable_content")
            if not searchable_content:
                searchable_content = self._create_searchable_content(tender_dict)
            
            tender_id = tender_dict.get("details_url", f"tender_{len(items_for_embedding)}")
            
            metadata = {}
            for k, v in tender_dict.items():
                if k not in excluded_fields and v is not None:
                    if isinstance(v, str) and len(v) > 1000:
                        metadata[k] = v[:1000] + "..." if len(v) > 1000 else v
                    elif isinstance(v, list):
                        if k == "parts" and v:
                            parts_summary = f"{len(v)} parts: " + ", ".join([
                                f"Part {p.get('part_number', i+1)}: {p.get('description', 'No desc')[:50]}"
                                for i, p in enumerate(v[:3])
                            ])
                            if len(v) > 3:
                                parts_summary += f" and {len(v)-3} more"
                            metadata["parts_info"] = parts_summary
                        else:
                            metadata[k] = str(v)[:500] + "..." if len(str(v)) > 500 else str(v)
                    else:
                        metadata[k] = v
            
            item = {
                "id": tender_id,
                "input": searchable_content,
                "metadata": metadata
            }
            
            items_for_embedding.append(item)
        
        return await self.embedding_tool.embed_and_store_batch(items_for_embedding)