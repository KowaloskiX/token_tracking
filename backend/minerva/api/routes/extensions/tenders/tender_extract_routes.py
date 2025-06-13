from datetime import datetime
import logging
from minerva.tasks.sources.vergapeplatforms.extract_tender import VergabePlatformsTenderExtractor
from minerva.tasks.sources.vergabe.extract_tender import DTVPLikeTenderExtractor
from minerva.tasks.sources.bazakonkurencyjnosci.extract_tenders import BazaKonkurencyjnosciTenderExtractor
from minerva.tasks.sources.platformazakupowa.extract_tenders import PlatformaZakupowaTenderExtractor
from minerva.tasks.sources.ezamowienia.extract_tenders import TenderExtractor
from minerva.tasks.sources.egospodarka.extract_tenders import EGospodarkaTenderExtractor
from minerva.tasks.sources.logintrade.extract_tenders import LoginTradeExtractor
from minerva.tasks.services.scraping_service import scrape_and_embed_all_sources
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional
from minerva.core.models.request.tender_extract import ExtractionRequest
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig
from minerva.tasks.services.tender_insert_service import TenderInsertConfig, TenderInsertService
from minerva.tasks.sources.ezamawiajacy.extract_tenders import EzamawiajacyTenderExtractor
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.tasks.sources.orlenconnect.extract_tenders import OrlenConnectTenderExtractor
from minerva.tasks.sources.pge.extract_tenders import PGETenderExtractor
from minerva.tasks.sources.ted.tender_countries import IrelandTedTenderExtractor, ItalyTedTenderExtractor, TedTenderExtractor
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from openai import OpenAI
from pinecone import Pinecone
from pydantic import BaseModel
import os

openai = OpenAI()
pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    index_name: str
    top_k: Optional[int] = 20
    embedding_model: Optional[str]
    score_threshold: Optional[float] = 0.0

class CompareScrapingRequest(BaseModel):
    date: str
    source1: str
    source1_index_name: str
    source2: str
    source2_index_name: str

@router.post("/test-fetch-and-embed")
async def fetch_and_embed_tenders_by_date(request: ExtractionRequest) -> Dict:
    try:
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Please use YYYY-MM-DD format."
            )

        # Create configuration using the new pattern
        tender_insert_config = TenderInsertConfig.create_default(
            pinecone_index="tenders",
            pinecone_namespace="",
            embedding_model="text-embedding-3-large",
            elasticsearch_index="tenders"
        )
        
        example_extractor = VergabePlatformsTenderExtractor()
        # Create the service with the new configuration
        tender_service = TenderInsertService(
            config=tender_insert_config,
            tender_source=example_extractor
        )

        result = await tender_service.process_tenders(request)
        
        # Extract some useful metrics for the response
        pinecone_processed = result.get("embedding_result", {}).get("processed_count", 0)
        es_processed = result.get("elasticsearch_result", {}).get("stored_count", 0)
        
        return {
            "result": result,
            "summary": {
                "pinecone_processed": pinecone_processed,
                "elasticsearch_processed": es_processed,
                "total_processed": pinecone_processed + es_processed
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
@router.post("/test-fetch-and-embed-all")
async def f(request: ExtractionRequest):

    tender_insert_config = TenderInsertConfig.create_default(
        pinecone_index="test-tenders3",
        pinecone_namespace="",
        embedding_model="text-embedding-3-large",
        elasticsearch_index="test-tenders3"
    )
    source_manager = TenderSourceManager(tender_insert_config)


    active_sources = source_manager.get_active_sources()

    if not active_sources:
        logging.info("No active sources to process.")
        return {
            "date": request.start_date,
            "processed_results": {},
            "total_processed": 0,
            "elasticsearch_results": {}
        }

    processed_results = {}
    elasticsearch_results = {}
    total_processed = 0
    
    for source in active_sources:
        try:
            # Create the TenderInsertService for this source
            service = source_manager.create_tender_insert_service(source)
            
            # Process tenders for both Pinecone and Elasticsearch
            result = await service.process_tenders(request)
            
            # Extract results
            pinecone_result = result.get("embedding_result", {})
            es_result = result.get("elasticsearch_result", {})
            
            # Update results tracking
            processed_count = pinecone_result.get("processed_count", 0)
            processed_results[source.value] = f"Processed {processed_count} tenders."
            total_processed += processed_count
            elasticsearch_results[source.value] = es_result
            
        except Exception as e:
            logging.error(f"Error processing source {source.value}: {str(e)}")
            processed_results[source.value] = f"Error: {str(e)}"
            elasticsearch_results[source.value] = {"error": str(e)}

    return {
        "date": request.start_date,
        "processed_results": processed_results,
        "total_processed": total_processed,
        "elasticsearch_results": elasticsearch_results
    }


@router.post("/fetch-and-embed-all", response_model=Dict[str, Any])
async def fetch_and_embed_tenders_all_sources() -> Dict:
    try:
        scraping_summary = await scrape_and_embed_all_sources(70, "2025-03-26", 1, 2)
        return {
            "status": "Completed scraping and embedding all tenders",
            "summary": scraping_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running scraping and embedding: {str(e)}")


@router.post("/query")
async def search_tenders(search_request: SearchRequest):
    try:
        query_tool = QueryTool(config=QueryConfig(index_name=search_request.index_name, embedding_model=search_request.embedding_model))
        results = await query_tool.query_by_text(
            query_text=search_request.query,
            top_k=search_request.top_k,
            score_threshold=search_request.score_threshold
        )
        return {
            "matches": results["matches"],
            "total_results": len(results["matches"]),
            "filters_applied": results.get("filter_applied"),
            "query": search_request.query
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching tenders: {str(e)}")

@router.post("/compare-scraping-results")
async def compare_scraping_results(request: CompareScrapingRequest):
    try:
        # Initialize query tool with the specified configuration
        query_tool = QueryTool(config=QueryConfig(
            index_name=request.source1_index_name,
            namespace="",
            embedding_model="text-embedding-3-large"
        ))

        query_tool2 = QueryTool(config=QueryConfig(
            index_name=request.source2_index_name,
            namespace="",
            embedding_model="text-embedding-3-large"
        ))

        # Search for tenders from source1
        source1_results = await query_tool.query_by_text(
            query_text="",  # Empty query to get all results
            top_k=1000,  # Large number to get all results
            score_threshold=0.0,
            filter_conditions={"source_type": {"$eq": request.source1}, "initiation_date": {"$eq": request.date}}
        )

        # Search for tenders from source2
        source2_results = await query_tool2.query_by_text(
            query_text="",  # Empty query to get all results
            top_k=1000,  # Large number to get all results
            score_threshold=0.0,
            filter_conditions={"source_type": {"$eq": request.source2}, "initiation_date": {"$eq": request.date}}
        )

        # Extract IDs (details_urls) from results
        source1_ids = {match["id"] for match in source1_results.get("matches", [])}
        source2_ids = {match["id"] for match in source2_results.get("matches", [])}

        # Calculate overlaps and unique items
        common_ids = source1_ids.intersection(source2_ids)
        unique_to_source1 = source1_ids - source2_ids
        unique_to_source2 = source2_ids - source1_ids

        # Get full details for common items
        common_items = []
        for match in source1_results.get("matches", []):
            if match["id"] in common_ids:
                common_items.append({
                    "id": match["id"],
                    "name": match["metadata"].get("name", ""),
                    "organization": match["metadata"].get("organization", ""),
                    "location": match["metadata"].get("location", ""),
                    "initiation_date": match["metadata"].get("initiation_date", ""),
                    "submission_deadline": match["metadata"].get("submission_deadline", "")
                })

        return {
            "date": request.date,
            "source1": request.source1,
            "source2": request.source2,
            "summary": {
                "total_source1": len(source1_ids),
                "total_source2": len(source2_ids),
                "common_count": len(common_ids),
                "unique_to_source1_count": len(unique_to_source1),
                "unique_to_source2_count": len(unique_to_source2)
            },
            "common_items": common_items,
            "unique_to_source1": list(unique_to_source1),
            "unique_to_source2": list(unique_to_source2)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing scraping results: {str(e)}")
