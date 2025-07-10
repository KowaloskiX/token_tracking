from datetime import datetime
import os
import json
import logging
from pprint import pprint
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from minerva.core.helpers.external_comparison import TenderExternalComparison
from rapidfuzz import fuzz
from bson import ObjectId
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import FileExtractionStatus, TenderAnalysis, TenderAnalysisResult, TenderLocation, TenderMetadata
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.tasks.services.search_service import perform_tender_search
from minerva.tasks.services.tender_initial_ai_filtering_service import AIFilteringMode, perform_ai_filtering
from minerva.tasks.sources.oferent.extract_tenders import OferentReportExtractor
from minerva.tasks.sources.vergapeplatforms.extract_tender import VergabePlatformsTenderExtractor
from minerva.tasks.sources.vergabe.extract_tender import DTVPLikeTenderExtractor
from minerva.tasks.sources.bazakonkurencyjnosci.extract_tenders import BazaKonkurencyjnosciTenderExtractor
from minerva.tasks.sources.platformazakupowa.extract_tenders import PlatformaZakupowaTenderExtractor
from minerva.tasks.sources.ezamowienia.extract_tenders import TenderExtractor
from minerva.tasks.sources.egospodarka.extract_tenders import EGospodarkaTenderExtractor
from minerva.tasks.sources.logintrade.extract_tenders import LoginTradeExtractor
from minerva.tasks.services.scraping_service import scrape_and_embed_all_sources
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, Dict, List, Optional, Union
from minerva.core.models.request.tender_extract import ExtractionRequest
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig
from minerva.tasks.services.tender_insert_service import TenderInsertConfig, TenderInsertService
from minerva.tasks.sources.ezamawiajacy.extract_tenders import EzamawiajacyTenderExtractor
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.tasks.sources.orlenconnect.extract_tenders import OrlenConnectTenderExtractor
from minerva.tasks.sources.pge.extract_tenders import PGETenderExtractor
from minerva.tasks.sources.eb2b.extract_tenders import Eb2bTenderExtractor
from minerva.tasks.sources.ted.tender_countries import IrelandTedTenderExtractor, ItalyTedTenderExtractor, TedTenderExtractor
from minerva.tasks.sources.ezamowienia.extract_historical_tenders import HistoricalTenderExtractor, HistoricalTender
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from openai import OpenAI
from pinecone import Pinecone
from pydantic import BaseModel
from minerva.tasks.sources.biznespolska.extract_tenders import BiznesPolskaReportExtractor
from minerva.core.helpers.biznespolska_oferent_shared import (
    get_best_tender_url,
    normalize_eb2b_id,
    prepare_tender_analysis,
    run_search_and_filter,
    calculate_pre_filter_differences,
    ai_filter_tenders,
    generate_comparison_summary,
    calculate_tender_differences,
    transform_endpoint_result
)

openai = OpenAI()
pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

load_dotenv()

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
        
        example_extractor = Eb2bTenderExtractor()
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


class ExtractionRequest(BaseModel):
    # Existing oferent extraction parameters
    target_date: Optional[Union[str, List[str]]] = None  # Accept single date or list of dates
    account_number: Optional[str] = None
    email: Optional[str] = None
    
    # New search and filtering parameters
    run_search_and_filter: Optional[bool] = False
    analysis_id: Optional[str] = None
    search_phrase: Optional[str] = None
    company_description: Optional[str] = None
    
    # Search parameters
    tender_names_index_name: Optional[str] = "tenders"
    elasticsearch_index_name: Optional[str] = "tenders"
    tender_subjects_index_name: Optional[str] = "tender-subjects"
    embedding_model: Optional[str] = "text-embedding-3-large"
    score_threshold: Optional[float] = 0.5
    top_k: Optional[int] = 30
    sources: Optional[List[str]] = None
    filter_conditions: Optional[List[Dict[str, Any]]] = None
    
    # Filtering parameters
    ai_batch_size: Optional[int] = 20
    save_results: Optional[bool] = False

class FilteredResults(BaseModel):
    initial_ai_filter_id: Optional[str] = None
    total_filtered: int
    total_filtered_out: int
    filtered_tenders: List[Any]

class SearchResults(BaseModel):
    search_id: Optional[str] = None
    query: str
    total_matches: int
    matches: List[Dict[str, Any]]
    detailed_results: Optional[Dict[str, Dict[str, List[Dict]]]] = None


class TenderDifferences(BaseModel):
    unique_to_oferent: List[Dict[str, Any]]
    unique_to_search: List[Dict[str, Any]]
    total_unique_to_oferent: int
    total_unique_to_search: int
    potential_overlaps: List[Dict[str, Any]]  # Overlapping tenders (same ID in both)

class PreFilterDifferences(BaseModel):
    unique_to_oferent: List[Dict[str, Any]]
    unique_to_search: List[Dict[str, Any]]
    total_unique_to_oferent: int
    total_unique_to_search: int
    potential_overlaps: List[Dict[str, Any]]  # Overlapping tenders (same ID in both)

class CompareOferentResponse(BaseModel):
    # Existing oferent results
    success: bool
    message: str
    oferent_results: Dict[str, Any]
    
    # New search and filtering results
    search_results: Optional[SearchResults] = None
    oferent_filtered_results: Optional[FilteredResults] = None
    search_filtered_results: Optional[FilteredResults] = None
    
    # Comparison metrics and differences
    comparison_summary: Optional[Dict[str, Any]] = None
    pre_filter_differences: Optional[PreFilterDifferences] = None  # Before filtering
    tender_differences: Optional[TenderDifferences] = None  # After filtering

@router.post("/compare-to-oferent", response_model=CompareOferentResponse)
async def extract_tenders_sync(
    request: ExtractionRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        # Step 1: Extract tenders from Oferent (existing functionality)
        # Support multiple dates
        dates = []
        if request.target_date:
            if isinstance(request.target_date, str):
                dates = [request.target_date]
            elif isinstance(request.target_date, list):
                dates = request.target_date
            else:
                raise HTTPException(status_code=400, detail="Invalid target_date format. Use string or list of strings.")
        else:
            dates = []
        all_oferent_tenders = []
        oferent_raw_results = []
        for date in dates:
            inputs = {"target_date": date}
            if request.account_number:
                inputs["account_number"] = request.account_number
            if request.email:
                inputs["email"] = request.email
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {date}. Use YYYY-MM-DD")
            logging.info(f"Starting synchronous extraction for date: {date}")
            extractor = OferentReportExtractor()
            oferent_result = await extractor.execute(inputs)
            oferent_raw_results.append(oferent_result)
            all_oferent_tenders.extend(oferent_result.get('tenders', []))
        # If no dates provided, run once with no date (legacy behavior)
        if not dates:
            inputs = {}
            if request.account_number:
                inputs["account_number"] = request.account_number
            if request.email:
                inputs["email"] = request.email
            logging.info(f"Starting synchronous extraction for date: today (no date provided)")
            extractor = OferentReportExtractor()
            oferent_result = await extractor.execute(inputs)
            oferent_raw_results.append(oferent_result)
            all_oferent_tenders.extend(oferent_result.get('tenders', []))

        transformed_oferent_result = transform_endpoint_result({'tenders': all_oferent_tenders}, search_phrase=request.search_phrase or "")
        # --- TESTING: Read transformed_oferent_result from JSON file instead of scraping ---
        # oferent_json_path = os.path.join(os.path.dirname(__file__), "oferent_results.json")
        # transformed_oferent_result = extract_tenders_from_file(oferent_json_path)
        all_oferent_tenders = transformed_oferent_result.get("tenders", [])
        response_data = {
            "success": True,
            "message": f"Successfully extracted {len(all_oferent_tenders)} tenders from Oferent",
            "oferent_results": transformed_oferent_result,
            "search_results": None,
            "oferent_filtered_results": None,
            "search_filtered_results": None,
            "comparison_summary": None
        }
        if request.run_search_and_filter:
            tender_analysis, search_phrase_to_use, company_description_to_use, sources_to_use = await prepare_tender_analysis(request, current_user)
            dates = []
            if request.target_date:
                if isinstance(request.target_date, str):
                    dates = [request.target_date]
                elif isinstance(request.target_date, list):
                    dates = request.target_date
            search_results = await run_search_and_filter(request, search_phrase_to_use, company_description_to_use, sources_to_use, dates)
            # Normalize eb2b.com.pl tender IDs in all_tender_matches
            for match in search_results["all_tender_matches"]:
                if match.get("source_type") == "eb2b" and isinstance(match.get("id"), str):
                    match["id"] = normalize_eb2b_id(match["id"])
            response_data["search_results"] = SearchResults(
                search_id=search_results.get("search_id"),
                query=search_phrase_to_use,
                total_matches=len(search_results["all_tender_matches"]),
                matches=search_results["all_tender_matches"],
                detailed_results=search_results.get("detailed_results", {})
            )
            response_data["pre_filter_differences"] = calculate_pre_filter_differences(transformed_oferent_result, search_results)
            # AI filtering on search results
            search_filter_results = await ai_filter_tenders(
                tender_analysis,
                search_results["all_tender_matches"],
                search_results.get("combined_search_matches", {}),
                request.analysis_id,
                current_user,
                request.ai_batch_size,
                search_results.get("search_id"),
                request.save_results,
                AIFilteringMode.STANDARD
            )
            search_filtered_tenders = search_filter_results.get("filtered_tenders", [])
            search_filtered_out_tenders = search_filter_results.get("filtered_out_tenders", [])
            response_data["search_filtered_results"] = FilteredResults(
                initial_ai_filter_id=search_filter_results.get('initial_ai_filter_id'),
                total_filtered=len(search_filtered_tenders),
                total_filtered_out=len(search_filtered_out_tenders),
                filtered_tenders=search_filtered_tenders
            )
            # Convert Oferent results for AI filtering
            oferent_matches = []
            for tender in transformed_oferent_result.get("tenders", []):
                tender_dict = tender if isinstance(tender, dict) else tender.__dict__
                match_item = {
                    "id": tender_dict.get("id", ""),
                    "name": tender_dict.get("name", ""),
                    "organization": tender_dict.get("organization", ""),
                    "location": tender_dict.get("location", ""),
                    "source": tender_dict.get("source", "oferent_tenders"),
                    "source_type": tender_dict.get("source_type", ""),
                    "search_phrase": search_phrase_to_use,
                }
                oferent_matches.append(match_item)
            oferent_filter_results = await ai_filter_tenders(
                tender_analysis,
                oferent_matches,
                {"oferent": oferent_matches},
                request.analysis_id,
                current_user,
                request.ai_batch_size,
                None,
                request.save_results,
                AIFilteringMode.STANDARD
            )
            oferent_filtered_tenders = oferent_filter_results.get("filtered_tenders", [])
            oferent_filtered_out_tenders = oferent_filter_results.get("filtered_out_tenders", [])
            response_data["oferent_filtered_results"] = FilteredResults(
                initial_ai_filter_id=oferent_filter_results.get('initial_ai_filter_id'),
                total_filtered=len(oferent_filtered_tenders),
                total_filtered_out=len(oferent_filtered_out_tenders),
                filtered_tenders=oferent_filtered_tenders
            )
            response_data["comparison_summary"] = generate_comparison_summary(
                transformed_oferent_result, search_results, oferent_filtered_tenders, search_filtered_tenders, oferent_matches
            )
            # Tender differences
            response_data["tender_differences"] = calculate_tender_differences(
                oferent_filtered_tenders, search_filtered_tenders
            )
            response_data["message"] = (
                f"Successfully extracted {len(transformed_oferent_result['tenders'])} tenders from Oferent, "
                f"found {len(search_results['all_tender_matches'])} tenders via search, "
                f"filtered to {len(oferent_filtered_tenders)} (Oferent) and {len(search_filtered_tenders)} (Search) relevant tenders"
            )
        return CompareOferentResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Extraction and comparison failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction and comparison failed: {str(e)}")
    
class CompareBiznesPolskaRequest(BaseModel):
    username: str
    password: str
    profile_name: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    current_only: Optional[bool] = True
    run_search_and_filter: Optional[bool] = False
    analysis_id: Optional[str] = None
    search_phrase: Optional[str] = None
    company_description: Optional[str] = None
    tender_names_index_name: Optional[str] = "tenders"
    elasticsearch_index_name: Optional[str] = "tenders"
    tender_subjects_index_name: Optional[str] = "tender-subjects"
    embedding_model: Optional[str] = "text-embedding-3-large"
    score_threshold: Optional[float] = 0.5
    top_k: Optional[int] = 30
    sources: Optional[List[str]] = None
    filter_conditions: Optional[List[Dict[str, Any]]] = None
    ai_batch_size: Optional[int] = 20
    save_results: Optional[bool] = False

class CompareBiznesPolskaResponse(BaseModel):
    success: bool
    message: str
    biznespolska_results: Dict[str, Any]
    search_results: Optional[SearchResults] = None
    biznespolska_filtered_results: Optional[FilteredResults] = None
    search_filtered_results: Optional[FilteredResults] = None
    comparison_summary: Optional[Dict[str, Any]] = None
    pre_filter_differences: Optional[PreFilterDifferences] = None
    tender_differences: Optional[TenderDifferences] = None

@router.post("/compare-to-biznespolska", response_model=CompareBiznesPolskaResponse)
async def compare_to_biznespolska(
    request: CompareBiznesPolskaRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        # Step 1: Extract tenders from BiznesPolska
        # --- PRODUCTION: Use extractor for real data ---
        username = request.username
        password = request.password
        profile_name = request.profile_name
        if not all((username, password, profile_name)):
            raise HTTPException(status_code=400, detail="username, password and profile_name are required in request body")
        date_from = request.date_from or datetime.now().strftime("%Y-%m-%d")
        date_to = request.date_to or datetime.now().strftime("%Y-%m-%d")
        current_only = request.current_only
        extractor = BiznesPolskaReportExtractor()
        inputs = {
            "username": username,
            "password": password,
            "profile_name": profile_name,
            "date_from": date_from,
            "date_to": date_to,
            "current_only": current_only
        }
        biznespolska_result = await extractor.execute(inputs)
        tenders = biznespolska_result.get('tenders', [])
        transformed_biznespolska_result = transform_endpoint_result({'tenders': tenders}, search_phrase=request.search_phrase or "")
        # --- END PRODUCTION ---
        # --- TESTING: Load from JSON file instead of real extraction ---
        # biznespolska_json_path = os.path.join(os.path.dirname(__file__), "bizpol_res.json")
        # transformed_biznespolska_result = extract_tenders_from_file(biznespolska_json_path)
        # --- END TESTING ---
        all_biznespolska_tenders = transformed_biznespolska_result.get("tenders", [])
        response_data = {
            "success": True,
            "message": f"Successfully extracted {len(all_biznespolska_tenders)} tenders from BiznesPolska",
            "biznespolska_results": transformed_biznespolska_result,
            "search_results": None,
            "biznespolska_filtered_results": None,
            "search_filtered_results": None,
            "comparison_summary": None
        }
        if request.run_search_and_filter:
            tender_analysis, search_phrase_to_use, company_description_to_use, sources_to_use = await prepare_tender_analysis(request, current_user)
            date_from = getattr(request, 'date_from', None) or datetime.now().strftime("%Y-%m-%d")
            date_to = getattr(request, 'date_to', None) or datetime.now().strftime("%Y-%m-%d")
            dates = [date_from, date_to]
            search_results = await run_search_and_filter(request, search_phrase_to_use, company_description_to_use, sources_to_use, dates)
            # Normalize eb2b.com.pl tender IDs in all_tender_matches
            for match in search_results["all_tender_matches"]:
                if match.get("source_type") == "eb2b" and isinstance(match.get("id"), str):
                    match["id"] = normalize_eb2b_id(match["id"])
            response_data["search_results"] = SearchResults(
                search_id=search_results.get("search_id"),
                query=search_phrase_to_use,
                total_matches=len(search_results["all_tender_matches"]),
                matches=search_results["all_tender_matches"],
                detailed_results=search_results.get("detailed_results", {})
            )
            response_data["pre_filter_differences"] = calculate_pre_filter_differences(transformed_biznespolska_result, search_results)
            # AI filtering on search results
            search_filter_results = await ai_filter_tenders(
                tender_analysis,
                search_results["all_tender_matches"],
                search_results.get("combined_search_matches", {}),
                request.analysis_id,
                current_user,
                request.ai_batch_size,
                search_results.get("search_id"),
                request.save_results,
                AIFilteringMode.STANDARD
            )
            search_filtered_tenders = search_filter_results.get("filtered_tenders", [])
            search_filtered_out_tenders = search_filter_results.get("filtered_out_tenders", [])
            response_data["search_filtered_results"] = FilteredResults(
                initial_ai_filter_id=search_filter_results.get('initial_ai_filter_id'),
                total_filtered=len(search_filtered_tenders),
                total_filtered_out=len(search_filtered_out_tenders),
                filtered_tenders=search_filtered_tenders
            )
            # Convert BiznesPolska results for AI filtering
            biznespolska_matches = []
            for tender in transformed_biznespolska_result.get("tenders", []):
                tender_dict = tender if isinstance(tender, dict) else tender.__dict__
                match_item = {
                    "id": tender_dict.get("id", ""),
                    "name": tender_dict.get("name", ""),
                    "organization": tender_dict.get("organization", ""),
                    "location": tender_dict.get("location", ""),
                    "source": tender_dict.get("source", "biznespolska_tenders"),
                    "source_type": tender_dict.get("source_type", ""),
                    "search_phrase": search_phrase_to_use,
                }
                biznespolska_matches.append(match_item)
            biznespolska_filter_results = await ai_filter_tenders(
                tender_analysis,
                biznespolska_matches,
                {"biznespolska": biznespolska_matches},
                request.analysis_id,
                current_user,
                request.ai_batch_size,
                None,
                request.save_results,
                AIFilteringMode.STANDARD
            )
            biznespolska_filtered_tenders = biznespolska_filter_results.get("filtered_tenders", [])
            biznespolska_filtered_out_tenders = biznespolska_filter_results.get("filtered_out_tenders", [])
            response_data["biznespolska_filtered_results"] = FilteredResults(
                initial_ai_filter_id=biznespolska_filter_results.get('initial_ai_filter_id'),
                total_filtered=len(biznespolska_filtered_tenders),
                total_filtered_out=len(biznespolska_filtered_out_tenders),
                filtered_tenders=biznespolska_filtered_tenders
            )
            response_data["comparison_summary"] = generate_comparison_summary(
                transformed_biznespolska_result, search_results, biznespolska_filtered_tenders, search_filtered_tenders, biznespolska_matches
            )
            response_data["tender_differences"] = calculate_tender_differences(
                biznespolska_filtered_tenders, search_filtered_tenders
            )
            response_data["message"] = (
                f"Successfully extracted {len(transformed_biznespolska_result['tenders'])} tenders from BiznesPolska, "
                f"found {len(search_results['all_tender_matches'])} tenders via search, "
                f"filtered to {len(biznespolska_filtered_tenders)} (BiznesPolska) and {len(search_filtered_tenders)} (Search) relevant tenders"
            )
        return CompareBiznesPolskaResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Extraction and comparison failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction and comparison failed: {str(e)}")
    

class SimpleExtractRequest(BaseModel):
    analysis_id: str
    user_id: str
    date: str
    profile: Optional[str] = None  # For BiznesPolska, if needed

@router.post("/extract-and-save/oferent")
async def extract_and_save_oferent(request: SimpleExtractRequest):
    # Get credentials from env
    user = request.user_id
    account_num = os.getenv(f"ANALYSIS_{request.analysis_id}_OFERENT_ACCOUNT_NUMBER")
    email = os.getenv(f"ANALYSIS_{request.analysis_id}_OFERENT_EMAIL")
    if not account_num or not email:
        raise HTTPException(status_code=400, detail="Missing Oferent credentials in environment variables.")
    extractor = OferentReportExtractor()
    try:
        inputs = {"target_date": request.date}
        inputs["account_number"] = account_num
        inputs["email"] = email
        try:
            datetime.strptime(request.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {request.date}. Use YYYY-MM-DD")
        result = await extractor.execute(inputs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    
    tenders = result.get('tenders', [])
    results = []
    for tender in tenders:
        # Fill as much as possible, leave the rest empty
        tender = tender.model_dump(by_alias=True)
        tender_metadata = TenderMetadata(
            name=tender.get('name', ''),
            organization=tender.get('organization', ''),
            submission_deadline=tender.get('submission_deadline', ''),
            procedure_type=tender.get('procedure_type', None),
            initiation_date=tender.get('initiation_date', None)
        )
        location = TenderLocation(
            country="Polska",
            voivodeship=tender.get('regoin', ''),
            city=tender.get('city', '')
        )
        file_extraction_status = FileExtractionStatus(
            user_id=user,
            files_processed=0,
            files_uploaded=0,
            status="not_extracted"
        )
        result = TenderAnalysisResult(
            user_id=ObjectId(user),
            tender_analysis_id=ObjectId(request.analysis_id),
            tender_url=tender.get('details_url', ''),
            source="oferent",
            location=location,
            tender_score=None,
            tender_metadata=tender_metadata,
            tender_description=tender.get('description', None),
            file_extraction_status=file_extraction_status,
            criteria_analysis=[],
            criteria_analysis_archive=None,
            criteria_analysis_edited=False,
            company_match_explanation="",
            assistant_id=None,
            pinecone_config=None,
            tender_pinecone_id=None,
            uploaded_files=[],
            updates=[],
            status="external",
            updated_at=None,
            created_at=datetime.utcnow(),
            opened_at=None,
            order_number=None,
            language=None,
            external_best_url=get_best_tender_url(tender)
        )
        # Save to DB
        await db.tender_analysis_results.insert_one(result.model_dump(by_alias=True))
        results.append(result)
    return {"saved": len(results), "tenders": [r.tender_metadata.name for r in results]}

@router.post("/extract-and-save/biznespolska")
async def extract_and_save_biznespolska(request: SimpleExtractRequest):
    user = request.user_id
    username = os.getenv(f"ANALYSIS_{request.analysis_id}_BIZNESPOLSKA_USERNAME")
    password = os.getenv(f"ANALYSIS_{request.analysis_id}_BIZNESPOLSKA_PASSWORD")
    profile = request.profile
    if not username or not password or not profile:
        raise HTTPException(status_code=400, detail="Missing BiznesPolska credentials in environment variables.")
    extractor = BiznesPolskaReportExtractor()
    try:
        result = await extractor.execute(
            inputs={
                "username": username,
                "password": password,
                "profile_name": profile,
                "date_from": request.date,
                "date_to": request.date,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    tenders = result.get('tenders', [])
    results = []
    for tender in tenders:
        tender = tender.model_dump(by_alias=True)
        tender_metadata = TenderMetadata(
            name=tender.get('name', ''),
            organization=tender.get('organization', ''),
            submission_deadline=tender.get('submission_deadline', ''),
            procedure_type=tender.get('procedure_type', None),
            initiation_date=tender.get('initiation_date', None)
        )
        location = TenderLocation(
            country="Polska",
            voivodeship=tender.get('regoin', ''),
            city=tender.get('city', '')
        )
        file_extraction_status = FileExtractionStatus(
            user_id=user,
            files_processed=0,
            files_uploaded=0,
            status="not_extracted"
        )
        result = TenderAnalysisResult(
            user_id=ObjectId(user),
            tender_analysis_id=ObjectId(request.analysis_id),
            tender_url=tender.get('details_url', ''),
            source="biznespolska",
            location=location,
            tender_score=None,
            tender_metadata=tender_metadata,
            tender_description=tender.get('description', None),
            file_extraction_status=file_extraction_status,
            criteria_analysis=[],
            criteria_analysis_archive=None,
            criteria_analysis_edited=False,
            company_match_explanation="",
            assistant_id=None,
            pinecone_config=None,
            tender_pinecone_id=None,
            uploaded_files=[],
            updates=[],
            status="external",
            updated_at=None,
            created_at=datetime.utcnow(),
            opened_at=None,
            order_number=None,
            language=None,
            external_best_url=get_best_tender_url(tender)
        )
        await db.tender_analysis_results.insert_one(result.model_dump(by_alias=True))
        results.append(result)
    return {"saved": len(results), "tenders": [r.tender_metadata.name for r in results]}

class CompareExternalRequest(BaseModel):
    analysis_id: str
    start_date: str  
    end_date: str

@router.post("/external-comparison")
async def compare_external_tenders(
    request: CompareExternalRequest
) -> Dict:
    """
    Compare external and internal tender results for a specific analysis and date.
    
    This endpoint:
    1. Validates that the analysis exists and has external sources enabled
    2. Queries tender results for the specified date
    3. Compares external vs internal results
    4. Updates external_compare_status for all results
    
    Args:
        analysis_id: The tender analysis ID
        target_date: Date to filter results (format: YYYY-MM-DD)
        
    Returns:
        Dictionary containing comparison results and update statistics
        
    Raises:
        HTTPException: If analysis not found, external sources disabled, or other errors
    """
    try:
        # Validate ObjectId format
        try:
            ObjectId(request.analysis_id)
        except Exception:
            raise HTTPException(
                status_code=400, 
                detail="Invalid analysis_id format. Must be a valid ObjectId."
            )
        
        # Initialize comparison service
        comparison_service = TenderExternalComparison()
        
        # Perform comparison and updates
        result = await comparison_service.update_external_compare_status(
            analysis_id=request.analysis_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        
        return result
        
    except ValueError as e:
        # Handle business logic errors (analysis not found, external sources disabled, etc.)
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        # Handle unexpected errors
        logging.error(f"Unexpected error in external comparison: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while processing the comparison"
        )