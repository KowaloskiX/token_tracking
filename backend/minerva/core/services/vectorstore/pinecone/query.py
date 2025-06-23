from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import pinecone
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import asyncio
from functools import partial
from pinecone import Pinecone

load_dotenv()
async_openai_client = AsyncOpenAI()
pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

class QueryConfig(BaseModel):
    index_name: str
    namespace: str = ""
    embedding_model: str

class QueryTool:
    def __init__(self, config: Optional[QueryConfig] = None):
        self.async_openai = async_openai_client
        self.config = config or QueryConfig(index_name="default")
        self.index = pinecone.Index(self.config.index_name)
        self.loop = asyncio.get_running_loop()

    async def create_query_embedding(self, query_text: str) -> List[float]:
        response = await self.async_openai.embeddings.create(
            input=query_text,
            model=self.config.embedding_model
        )

        return response.data[0].embedding

    def _build_filter(
        self,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        if not filter_conditions:
            return None
        
        filter_dict = {}
        for field, condition in filter_conditions.items():
            if isinstance(condition, (str, int, float, bool)):
                filter_dict[field] = {"$eq": condition}
            elif isinstance(condition, list):
                filter_dict[field] = {"$in": condition}
            elif isinstance(condition, dict):
                filter_dict[field] = condition
        
        return filter_dict if filter_dict else None

    async def query_by_id(
        self,
        id: str,
        top_k: int = 1,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query Pinecone by ID with optional filter conditions.
        
        Args:
            id: The ID to search for
            top_k: Number of results to return
            filter_conditions: Optional dictionary of filter conditions
        """
        try:
            filter_dict = self._build_filter(filter_conditions)

            query_response = await self.loop.run_in_executor(
                None,
                partial(
                    self.index.query,
                    namespace=self.config.namespace,
                    id=id,
                    top_k=top_k,
                    include_metadata=True,
                    filter=filter_dict,
                ),
            )

            matches = [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                }
                for match in query_response.matches
            ]

            return {
                "matches": matches,
                "total_matches": len(matches),
                "filter_applied": filter_dict,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def query_by_text(
        self,
        query_text: str,
        top_k: int = 3,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query Pinecone by text with optional filter conditions.
        
        Args:
            query_text: The text to search for
            top_k: Number of results to return
            score_threshold: Minimum similarity score threshold
            filter_conditions: Optional dictionary of filter conditions
        """
        try:
            query_embedding = await self.create_query_embedding(query_text)
            
            filter_dict = self._build_filter(filter_conditions)

            query_response = await self.loop.run_in_executor(
                None,
                partial(
                    self.index.query,
                    namespace=self.config.namespace,
                    vector=query_embedding,
                    top_k=top_k,
                    include_metadata=True,
                    filter=filter_dict,
                ),
            )

            matches = [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                }
                for match in query_response.matches
                if match.score >= score_threshold
            ]

            return {
                "matches": matches,
                "total_matches": len(matches),
                "filter_applied": filter_dict,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
        
    def delete_namespace(self):
        try:
            self.index.delete(delete_all=True, namespace=self.config.namespace)
            return {"status": "success", "message": f"Namespace {self.config.namespace} deleted."}
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
        
    def delete_from_pinecone_by_id_prefix(self, id_prefix):
        deleted_count_total = 0
        try:
            for ids_batch in self.index.list_paginated(prefix=id_prefix, namespace=self.config.namespace):
                if ids_batch:
                    delete_response = self.index.delete(ids=ids_batch, namespace=self.config.namespace)
            return {"status": "success", "message": f"Deletion attempted for prefix {id_prefix} in namespace {self.config.namespace}."}
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

async def close_async_openai_client():
    global async_openai_client
    if async_openai_client:
        await async_openai_client.aclose()
        async_openai_client = None
        print("AsyncOpenAI client closed.")
