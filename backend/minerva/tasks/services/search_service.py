from datetime import datetime
import json
import logging
import pprint
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from minerva.core.database.database import db
from minerva.core.models.request.ai import LLMRAGRequest
from minerva.core.services.keyword_search.elasticsearch import es_client
from minerva.core.services.llm_logic import ask_llm_logic
from minerva.core.services.llm_providers.model_config import get_model_config, get_optimal_max_tokens
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from pinecone import Pinecone
import os
import psutil
import asyncio

logger = logging.getLogger("minerva.tasks.analysis_tasks")

# Initialize Pinecone client (assuming API key is in env)
pinecone_api_key = os.getenv("PINECONE_API_KEY")
if pinecone_api_key:
    pinecone = Pinecone(api_key=pinecone_api_key)
else:
    pinecone = None
    logger.warning("PINECONE_API_KEY not found in environment variables. Pinecone operations will fail.")

# Memory logging helper

def log_mem(tag: str = ""):
    """Log the current RSS memory usage (in MB) with an optional tag."""
    try:
        process_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        logger.info(f"[{tag}] Memory usage: {process_mem:.1f} MB")
    except Exception as mem_exc:
        logger.debug(f"Unable to log memory usage for tag '{tag}': {mem_exc}")

FIELD_MAPPING = {
    "initiation_date": {
        "elasticsearch": "initiation_date", 
        "pinecone": "initiation_date"
    },
    "source_type": {
        "elasticsearch": "metadata.source_type.keyword",  # Nested keyword field
        "pinecone": "source_type"
    }
}

def translate_filters_to_pinecone(filters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert generic filters to Pinecone format.
    Example input: [{"field": "source_type", "op": "in", "value": ["egospodarka"]}]
    Output: {"source_type": {"$in": ["egospodarka"]}}
    """
    pinecone_filters = {}
    for f in filters:
        field = FIELD_MAPPING.get(f["field"], {}).get("pinecone", f["field"])
        op = f.get("op")
        value = f.get("value")
        
        if op == "eq":
            pinecone_filters[field] = {"$eq": value}
        elif op == "in":
            if isinstance(value, list):
                pinecone_filters[field] = {"$in": value}
            else:
                logger.warning(f"Invalid 'in' filter value for {field}: {value}, expected list")
        else:
            logger.warning(f"Unsupported Pinecone filter operation: {op}")
    
    return pinecone_filters

def translate_filters_to_elasticsearch(filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert generic filters to Elasticsearch format.
    Example input: [{"field": "source_type", "op": "in", "value": ["egospodarka"]}]
    Output: [{"terms": {"metadata.source_type.keyword": ["egospodarka"]}}]
    """
    es_filters = []
    for f in filters:
        field = FIELD_MAPPING.get(f["field"], {}).get("elasticsearch", f"metadata.{f['field']}")
        op = f.get("op")
        value = f.get("value")
        
        if op == "eq":
            es_filters.append({"term": {field: value}})
        elif op == "in":
            if isinstance(value, list):
                es_filters.append({"terms": {field: value}})
            else:
                logger.warning(f"Invalid 'in' filter value for {field}: {value}, expected list")
        else:
            logger.warning(f"Unsupported Elasticsearch filter operation: {op}")
    
    return es_filters

async def generate_pinecone_queries(
        search_phrases: List[str],
        company_description: str,
        max_queries: int = 30
) -> List[str]:
    """
    Turn keyword-style search_phrases + company_description into
    short, name-like semantic queries optimised for Pinecone.
    """
    system_prompt = (
        # "You are an expert procurement analyst who rewrites keyword lists "
        "You are an expert procurement analyst who based on company description and keyword lists create "
        "concise phrases suitable for semantic "
        # "into concise tender-title style phrases suitable for semantic "
        "vector search. You NEVER invent company names."
    )

    user_prompt = f"""
    ## COMPANY DESCRIPTION
    {company_description}

    ## ORIGINAL KEYWORDS
    {", ".join(search_phrases)}

    ## TASK
    Produce up to {max_queries} distinct, **short** search strings that
    capture the business needs implied by the company description. Each
    string should be 2-7 words. They will be used for semantic search in pinecone
    so create them so that they will result in retrieving satisfying results for company.

    ## RESPONSE FORMAT (JSON)
    {{
      "queries": ["...", "..."]
    }}
    """

    # Produce up to {max_queries} distinct, **short** search strings that
    # capture the business needs implied by the company description. Each
    # string should be 2-7 words, look like something that could appear in
    # a tender title, and avoid generic filler words.

    model = "o4-mini"
    provider, max_tokens = get_model_config(model)
    optimized_tokens = get_optimal_max_tokens(model, "high")

    req = LLMRAGRequest(
        query=user_prompt,
        rag_query="",
        vector_store=None,
        llm={
            "provider": provider,
            "model": model,
            "temperature": 0,
            # "max_tokens": optimized_tokens,
            "system_message": system_prompt,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                        "name": "pinecone_request_queries_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "queries": {
                                    "type": "array",
                                    "description": "List of queries to pinecone.",
                                    "items": {"type": "string", "description": "Pinecone query"}
                                }
                            },
                            "required": ["queries"],
                            "additionalProperties": False
                        }
                    }
            }
        }
    )
    raw = await ask_llm_logic(req)
    try:
        parsed = json.loads(raw.llm_response)
        return parsed.get("queries", [])[:max_queries]
    except Exception as e:
        logger.warning(f"Query-expander JSON parse failed: {e}")
        return []

async def perform_tender_search(
    search_phrase: str,
    company_description: str,      
    tender_names_index_name: str,
    elasticsearch_index_name: str = "tenders",
    tender_subjects_index_name: str = "tender-subjects",
    embedding_model: str = "text-embedding-3-large",
    score_threshold: float = 0.5,
    top_k: int = 30,
    sources: Optional[List[str]] = None,
    filter_conditions: Optional[List[Dict[str, Any]]] = None,
    analysis_id: Optional[str] = None,
    current_user_id: Optional[str] = None,
    save_results: bool = False
) -> Dict[str, Any]:
    """
    Perform search for tenders using Pinecone and Elasticsearch.
    
    Args:
        search_phrase: The search phrase to query
        tender_names_index_name: Pinecone index name for tender names
        elasticsearch_index_name: Elasticsearch index name
        score_threshold: Minimum score threshold for Pinecone results
        top_k: Maximum number of results to return from Pinecone
        sources: Optional list of sources to search within
        filter_conditions: Optional filter conditions for search
        analysis_id: Optional analysis ID to associate with saved results
        current_user_id: Optional user ID making the request
        save_results: Whether to save search results to database for later reuse
    
    Returns:
        Dictionary containing:
        - all_tender_matches: List of all tender matches
        - combined_search_matches: Combined matches with details
        - search_id: ID of the saved search results (if save_results=True)
    """
    query_config = QueryConfig(
        index_name=tender_names_index_name,
        namespace="",
        embedding_model=embedding_model
    )
    query_tool = QueryTool(config=query_config)

    query_config_subjects = QueryConfig(
        index_name=tender_subjects_index_name,
        namespace="",
        embedding_model=embedding_model
    )
    query_tool_subjects = QueryTool(config=query_config_subjects)

    logger.info(f"Searching with query: {search_phrase}")

    # --- Memory usage BEFORE search operations ---
    log_mem("perform_tender_search:start")

    all_tender_matches = []
    combined_search_matches = {}
    processed_ids = set()
    detailed_results = {}

    search_phrases = [phrase.strip() for phrase in search_phrase.split(",")]

    semantic_phrases = await generate_pinecone_queries(search_phrase, company_description) 
    
    pinecone_filters = translate_filters_to_pinecone(filter_conditions or [])
    es_filters = translate_filters_to_elasticsearch(filter_conditions or [])

    # Prepare all Pinecone query tasks
    pinecone_tasks = []
    task_metadata = []

    if sources and isinstance(sources, list) and len(sources) > 0:
        # Create tasks for each source + phrase combination
        for source in sources:
            source_pinecone_filters = pinecone_filters.copy()
            source_pinecone_filters["source_type"] = {"$eq": source}

            # Add Elasticsearch tasks for each search phrase
            for phrase in search_phrases:
                es_query = {
                    "bool": {
                        "must": [
                            {"match": {"text": phrase}}
                        ],
                        "filter": [
                            {"term": {"metadata.source_type.keyword": source}}
                        ] + es_filters
                    }
                }

                logger.info(f"Querying Elasticsearch for source: {source} with query: {es_query}")
                es_result = await es_client.search(
                    index=elasticsearch_index_name,
                    body={
                        "query": es_query,
                        "size": 500
                    }
                )

                for hit in es_result["hits"]["hits"]:
                    match_id = hit["_id"]
                    if match_id in processed_ids:
                        continue
                    processed_ids.add(match_id)
                    metadata = hit["_source"].get("metadata", {})
                    tender_name = hit["_source"].get("title", "")
                    es_match = {
                        "id": match_id,
                        "score": hit["_score"],
                        "metadata": metadata
                    }
                    all_tender_matches.append({
                        "id": match_id,
                        "name": tender_name,
                        "organization": hit["_source"].get("organization", ""),
                        "location": metadata.get("location", ""),
                        "source": "elasticsearch",
                        "search_phrase": phrase,
                        "source_type": metadata.get("source_type")
                    })
                    combined_search_matches[match_id] = es_match
                    detailed_results.setdefault(phrase, {}).setdefault("elasticsearch", []).append({
                        "id": match_id,
                        "name": tender_name,
                        "score": hit["_score"],
                        "source": "elasticsearch",
                        "source_type": metadata.get("source_type")
                    })

                es_hits = es_result.get("hits", {}).get("hits", [])
                es_count = len(es_hits)
                logger.info(f"Elasticsearch found: {es_count} unique tenders for source: {source}.")

            # Add Pinecone tasks for each semantic phrase
            for phrase in semantic_phrases:
                # Tender names query task
                task = query_tool.query_by_text(
                    query_text=phrase,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    filter_conditions=source_pinecone_filters
                )
                pinecone_tasks.append(task)
                task_metadata.append({
                    "phrase": phrase,
                    "source": source,
                    "index_type": "tender_names",
                    "filters": source_pinecone_filters
                })

                # Tender subjects query task
                task = query_tool_subjects.query_by_text(
                    query_text=phrase,
                    top_k=top_k,
                    score_threshold=0.3,
                    filter_conditions=source_pinecone_filters
                )
                pinecone_tasks.append(task)
                task_metadata.append({
                    "phrase": phrase,
                    "source": source,
                    "index_type": "tender_subjects",
                    "filters": source_pinecone_filters
                })
    else:
        logger.info("No specific sources provided, running single query across both search engines.")

        # Add Elasticsearch tasks for each search phrase
        for phrase in search_phrases:
            es_query = {
                "bool": {
                    "must": [
                        {"match": {"text": phrase}}
                    ],
                    "filter": es_filters
                }
            }

            logger.info(f"Querying Elasticsearch with query: {es_query}")
            es_result = await es_client.search(
                index=elasticsearch_index_name,
                body={
                    "query": es_query,
                    "size": 500
                }
            )

            for hit in es_result["hits"]["hits"]:
                match_id = hit["_id"]
                if match_id in processed_ids:
                    continue
                processed_ids.add(match_id)
                metadata = hit["_source"].get("metadata", {})
                tender_name = hit["_source"].get("title", "")
                es_match = {
                    "id": match_id,
                    "score": hit["_score"],
                    "metadata": metadata
                }
                all_tender_matches.append({
                    "id": match_id,
                    "name": tender_name,
                    "organization": hit["_source"].get("organization", ""),
                    "location": metadata.get("location", ""),
                    "source": "elasticsearch",
                    "search_phrase": phrase,
                    "source_type": metadata.get("source_type")
                })
                combined_search_matches[match_id] = es_match
                detailed_results.setdefault(phrase, {}).setdefault("elasticsearch", []).append({
                    "id": match_id,
                    "name": tender_name,
                    "score": hit["_score"],
                    "source": "elasticsearch",
                    "source_type": metadata.get("source_type")
                })

            es_hits = es_result.get("hits", {}).get("hits", [])
            es_count = len(es_hits)
            logger.info(f"Elasticsearch found: {es_count} unique tenders.")

        # Add Pinecone tasks for each semantic phrase
        for phrase in semantic_phrases:
            # Tender names query task
            task = query_tool.query_by_text(
                query_text=phrase,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_conditions=pinecone_filters
            )
            pinecone_tasks.append(task)
            task_metadata.append({
                "phrase": phrase,
                "source": None,
                "index_type": "tender_names",
                "filters": pinecone_filters
            })

            # Tender subjects query task
            task = query_tool_subjects.query_by_text(
                query_text=phrase,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_conditions=pinecone_filters
            )
            pinecone_tasks.append(task)
            task_metadata.append({
                "phrase": phrase,
                "source": None,
                "index_type": "tender_subjects",
                "filters": pinecone_filters
            })

    # Execute Pinecone queries in controlled batches to avoid rate limits
    logger.info(f"Executing {len(pinecone_tasks)} Pinecone queries in controlled batches...")
    
    # Create semaphore to limit concurrent queries (adjust based on your Pinecone plan)
    max_concurrent_queries = 10  # Adjust this based on your rate limits
    semaphore = asyncio.Semaphore(max_concurrent_queries)
    
    async def execute_with_semaphore(task):
        async with semaphore:
            # Add small delay to further reduce rate limit risk
            await asyncio.sleep(0.1)
            return await task
    
    # Execute tasks with concurrency control
    pinecone_results = await asyncio.gather(
        *[execute_with_semaphore(task) for task in pinecone_tasks], 
        return_exceptions=True
    )

    # Process results
    for i, (result, metadata) in enumerate(zip(pinecone_results, task_metadata)):
        if isinstance(result, Exception):
            logger.error(f"Pinecone query failed for phrase '{metadata['phrase']}', source '{metadata['source']}', index '{metadata['index_type']}': {result}")
            continue

        phrase = metadata["phrase"]
        source = metadata["source"]
        index_type = metadata["index_type"]

        if index_type == "tender_names":
            # Process tender names results
            if result.get("matches"):
                for match in result["matches"]:
                    match_id = match["id"]
                    if match_id in processed_ids:
                        continue
                    processed_ids.add(match_id)
                    tender_name = match["metadata"].get("name", "")
                    all_tender_matches.append({
                        "id": match_id,
                        "name": tender_name,
                        "organization": match["metadata"].get("organization", ""),
                        "location": match["metadata"].get("location", ""),
                        "source": "pinecone",
                        "search_phrase": phrase,
                        "source_type": match["metadata"].get("source_type")
                    })
                    combined_search_matches[match_id] = match
                    detailed_results.setdefault(phrase, {}).setdefault("pinecone", []).append({
                        "id": match_id,
                        "name": tender_name,
                        "score": match.get("score"),
                        "source": "pinecone",
                        "source_type": match["metadata"].get("source_type")
                    })

            pinecone_matches = result.get("matches", [])
            pinecone_count = len(pinecone_matches)
            source_info = f" for source: {source}" if source else ""
            logger.info(f"Pinecone found: {pinecone_count} unique tenders{source_info} and phrase: {phrase}.")

        elif index_type == "tender_subjects":
            # Process tender subjects results
            if result.get("matches"):
                for match in result["matches"]:
                    match_id = match["id"]
                    match_metadata = match["metadata"]
                    tender_id = match_metadata.get("tender_id")
                    if tender_id in processed_ids:
                        continue
                    processed_ids.add(tender_id)
                    chunk_index = match_metadata.get("chunk_index")
                    
                    # Skip if we don't have the required metadata
                    if not tender_id:
                        logger.warning(f"Skipping tender subject match {match_id} - missing tender_id")
                        continue

                    # Fetch complete tender metadata from default index
                    try:
                        default_index_results = await query_tool.query_by_id(
                            id=tender_id,
                            top_k=1,
                            filter_conditions=metadata["filters"]
                        )
                        if default_index_results.get("matches"):
                            default_metadata = default_index_results["matches"][0]["metadata"]
                            # Merge metadata, preferring subject match metadata for specific fields
                            match_metadata.update({
                                "name": default_metadata.get("name", match_metadata.get("name", "")),
                                "organization": default_metadata.get("organization", match_metadata.get("organization", "")),
                                "location": default_metadata.get("location", match_metadata.get("location", "")),
                                "source_type": default_metadata.get("source_type", match_metadata.get("source_type", ""))
                            })
                    except Exception as e:
                        logger.warning(f"Failed to fetch complete metadata for tender {tender_id}: {e}")

                    # Add the tender subject match
                    all_tender_matches.append({
                        "id": tender_id,  # Use the parent tender ID
                        "name": match_metadata.get("name", ""),
                        "organization": match_metadata.get("organization", ""),
                        "location": match_metadata.get("location", ""),
                        "source": "tender_subjects",
                        "search_phrase": phrase,
                        "source_type": match_metadata.get("source_type"),
                        "subject_match": {
                            "id": match_id,
                            "chunk_index": chunk_index,
                            "score": match.get("score"),
                            "text": match_metadata.get("text", "")
                        }
                    })
                    
                    # Store the full match data with the parent tender ID
                    combined_search_matches[tender_id] = {
                        "id": tender_id,
                        "score": match.get("score"),
                        "metadata": match_metadata,
                        "subject_match": {
                            "id": match_id,
                            "chunk_index": chunk_index,
                            "score": match.get("score"),
                            "text": match_metadata.get("text", "")
                        }
                    }
                    
                    detailed_results.setdefault(phrase, {}).setdefault("tender_subjects", []).append({
                        "id": tender_id,  # Use the parent tender ID
                        "name": match_metadata.get("name", ""),
                        "score": match.get("score"),
                        "source": "tender_subjects",
                        "source_type": match_metadata.get("source_type"),
                        "subject_match": {
                            "id": match_id,
                            "chunk_index": chunk_index,
                            "score": match.get("score"),
                            "text": match_metadata.get("text", "")
                        }
                    })

            pinecone_subjects_matches = result.get("matches", [])
            pinecone_subjects_count = len(pinecone_subjects_matches)
            source_info = f" for source: {source}" if source else ""
            logger.info(f"Tender-subjects Pinecone found: {pinecone_subjects_count} unique tenders{source_info} and phrase: {phrase}.")

    logger.info(f"Combined search found {len(all_tender_matches)} unique tenders.")
    
    # --- Memory usage after search aggregation ---
    log_mem("perform_tender_search:end")
    
    pinecone_tenders = set()
    elasticsearch_tenders = set()
    tender_subjects_tenders = set()
    
    for match in all_tender_matches:
        if match["source"] == "pinecone":
            pinecone_tenders.add(match["id"])
        elif match["source"] == "elasticsearch":
            elasticsearch_tenders.add(match["id"])
        elif match["source"] == "tender_subjects":
            tender_subjects_tenders.add(match["id"])
    
    logger.info("Unique tenders found:")
    logger.info(f"Tender-subjects: {len(tender_subjects_tenders)} unique tenders")
    logger.info(f"Pinecone: {len(pinecone_tenders)} unique tenders")
    logger.info(f"Elasticsearch: {len(elasticsearch_tenders)} unique tenders")
    logger.info(f"Total unique tenders: {len(processed_ids)}")
    pprint.pprint(tender_subjects_tenders)
    result = {
        "all_tender_matches": all_tender_matches,
        "combined_search_matches": combined_search_matches,
        "detailed_results": detailed_results
    }
    
    # Save search results if requested
    if save_results:
        
        # Create search result document
        search_result_doc = {
            "analysis_id": analysis_id,
            "search_phrase": search_phrase,
            "created_at": datetime.utcnow(),
            "user_id": current_user_id,
            "all_tender_matches": all_tender_matches,
            "combined_search_matches": combined_search_matches,
            "sources": sources,
            "filter_conditions": filter_conditions,
            "tender_names_index_name": tender_names_index_name,
            "elasticsearch_index_name": elasticsearch_index_name,
            "detailed_results": detailed_results,
            "metadata": {
                "tender_count": len(all_tender_matches),
                "search_phrases": search_phrases
            }
        }
        
        # Insert into database
        db_result = await db.tender_search_results.insert_one(search_result_doc)
        logger.info(f"Saved search results with ID: {db_result.inserted_id}")
        
        result["search_id"] = str(db_result.inserted_id)
    
    return result


async def get_saved_search_results(
    search_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve previously saved search results from the database.
    
    Args:
        search_id: ID of the saved search results
        
    Returns:
        Dictionary containing search results or None if not found
    """
    search_doc = await db.tender_search_results.find_one({"_id": ObjectId(search_id)})
    
    if not search_doc:
        return None
    
    return {
        "all_tender_matches": search_doc.get("all_tender_matches", []),
        "combined_search_matches": search_doc.get("combined_search_matches", {}),
        "search_id": search_doc.get("search_id"),
        "search_phrase": search_doc.get("search_phrase"),
        "analysis_id": search_doc.get("analysis_id"),
        "created_at": search_doc.get("created_at"),
        "tender_names_index_name": search_doc.get("tender_names_index_name"),
        "elasticsearch_index_name": search_doc.get("elasticsearch_index_name"),
        "detailed_results": search_doc.get("detailed_results", {})
    }

async def compare_tender_search_results(
    search_id: str,
    tender_ids_to_compare: List[str],
) -> Dict[str, List[str]]:
    """
    Compares a list of tender IDs against saved search results and the source indices.

    Args:
        search_id: The ID of the saved search result.
        tender_ids_to_compare: A list of tender IDs (URLs/Pinecone IDs) to compare.

    Returns:
        A dictionary containing:
        - found_in_search: IDs present in both the input list and the saved search.
        - missing_from_index: IDs present in the input list but not found in Pinecone/ES.
        - not_found_by_search: IDs present in the input list and Pinecone/ES, but not in the saved search.
        
    Raises:
        ValueError: If the search_id is not found or required index names are missing.
        Exception: For issues during Pinecone or Elasticsearch queries.
    """
    saved_search = await get_saved_search_results(search_id)
    if not saved_search:
        raise ValueError(f"Search results with ID {search_id} not found")

    pinecone_index_name = saved_search.get("tender_names_index_name")
    es_index_name = saved_search.get("elasticsearch_index_name")
    
    if not pinecone_index_name or not es_index_name:
         raise ValueError(f"Index names missing for search ID {search_id}. Cannot perform comparison.")

    if not pinecone:
        raise EnvironmentError("Pinecone client not initialized. Check PINECONE_API_KEY.")

    found_search_ids = {match['id'] for match in saved_search.get("all_tender_matches", [])}
    input_ids_set = set(tender_ids_to_compare)
    existing_ids_in_source = set()

    try:
        # Check Pinecone (Assuming empty namespace based on QueryConfig)
        pinecone_index = pinecone.Index(pinecone_index_name)
        # Fetch returns a dict with a 'vectors' key containing found IDs
        fetch_response = pinecone_index.fetch(ids=tender_ids_to_compare, namespace="")
        if fetch_response and fetch_response.get('vectors'):
            existing_ids_in_source.update(fetch_response['vectors'].keys())
        logger.info(f"Checked {len(tender_ids_to_compare)} IDs in Pinecone index '{pinecone_index_name}'. Found {len(fetch_response.get('vectors', {}))} existing IDs.")

    except Exception as e:
        logger.error(f"Error fetching from Pinecone index '{pinecone_index_name}': {e}", exc_info=True)
        # Decide if we should raise or continue with potentially partial results
        # For now, let's try ES even if Pinecone fails
        # raise  # Uncomment to make Pinecone check mandatory

    try:
        # Check Elasticsearch
        # Note: mget might return fewer docs if some IDs don't exist
        if tender_ids_to_compare: # Avoid empty mget request
            mget_response = await es_client.mget(index=es_index_name, body={"ids": tender_ids_to_compare})
            found_in_es = {doc['_id'] for doc in mget_response.get('docs', []) if doc.get('found')}
            existing_ids_in_source.update(found_in_es)
            logger.info(f"Checked {len(tender_ids_to_compare)} IDs in Elasticsearch index '{es_index_name}'. Found {len(found_in_es)} existing IDs.")
        else:
            logger.info(f"Skipping Elasticsearch check as input ID list is empty.")

    except Exception as e:
        logger.error(f"Error fetching from Elasticsearch index '{es_index_name}': {e}", exc_info=True)
        # Decide if we should raise or continue 
        # raise # Uncomment to make ES check mandatory
    
    found_in_search = list(input_ids_set.intersection(found_search_ids))
    missing_from_index = list(input_ids_set.difference(existing_ids_in_source))
    # Exist in source AND in input list, but NOT in the search results
    not_found_by_search = list(existing_ids_in_source.intersection(input_ids_set).difference(found_search_ids))

    return {
        "found_in_search": found_in_search,
        "missing_from_index": missing_from_index,
        "not_found_by_search": not_found_by_search,
    }