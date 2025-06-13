import asyncio
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from minerva.tasks.sources.helpers import assign_order_numbers
from minerva.core.helpers.s3_upload import delete_files_from_s3
from minerva.core.helpers.vercel_upload import delete_files_from_vercel_blob
from minerva.core.services.browser_service import BrowserService
from minerva.core.services.vectorstore.file_content_extract.zip_extractor import ZipFileExtractor
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig
from minerva.tasks.sources.source_types import TenderSourceType
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from minerva.tasks.services.analysis_service import analyze_relevant_tenders_with_our_rag, run_all_analyses_for_user, run_all_tender_analyses, run_partial_tender_analyses
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, Response
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import CriteriaAnalysisUpdate, AnalysisCriteria, FilterStage, TenderAnalysis, TenderAnalysisResult, FilteredTenderAnalysisResult, TenderAnalysisResultSummary
from minerva.core.models.request.tender_analysis import (
    TenderAnalysisCreate,
    TenderAnalysisResultUpdate,
    TenderAnalysisUpdate,
    TenderSearchRequest,
    UserAnalysisTestRequest
)
from minerva.core.models.user import User
from minerva.core.models.utils import PyObjectId
from minerva.core.database.database import db
from bson import ObjectId
from pydantic import ValidationError, BaseModel, Field
import pytz
import json
import random

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_CRITERIA = [
    {
        "name": "Wartość kontraktu",
        "description": "potencjalny budżet, opłacalność",
        "weight": 5
    },
    {
        "name": "Lokalizacja",
        "description": "odległość, możliwość realizacji, koszty transportu",
        "weight": 4
    },
    {
        "name": "Wadium",
        "description": "obowiązek wniesienia, wysokość, forma zabezpieczenia",
        "weight": 3
    },
    {
        "name": "Specyfikacja produktów i usług",
        "description": "zakres zamówienia, rodzaj technologii, wymagane materiały",
        "weight": 4
    },
    {
        "name": "Termin realizacji",
        "description": "czas wykonania, elastyczność harmonogramu",
        "weight": 3
    },
    {
        "name": "Doświadczenie w realizacji podobnych zamówień",
        "description": "referencje, portfolio",
        "weight": 4
    },
    {
        "name": "Gwarancje i jakość usług",
        "description": "okres gwarancji, certyfikaty, standardy jakości",
        "weight": 3
    },
    {
        "name": "Pozostałe czynniki",
        "description": "np. warunki płatności, wymagania formalno-prawne",
        "weight": 2
    },
]

class TenderAnalysisResultSummary(BaseModel):
    id: PyObjectId = Field(alias="_id")
    tender_name: Optional[str] = Field(alias="tender_metadata.name", default=None)
    organization: Optional[str] = Field(alias="tender_metadata.organization", default=None)
    tender_description: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# kanban helper functions:
async def reorder_tenders(board_id: str, column_id: str) -> None:
    # Fetch latest board state
    board = await db["kanban_boards"].find_one({"_id": ObjectId(board_id)})
    if not board:
        return

    # Find the target column
    column = next(
        (col for col in board["columns"] if str(col["_id"]) == column_id),
        None
    )
    if not column:
        return

    # Get and sort tenders by current order
    tenders = column.get("tender_items", [])
    tenders.sort(key=lambda x: x.get("order", 0))

    # Renumber orders sequentially starting at 1
    for index, tender in enumerate(tenders):
        tender["order"] = index + 1

    # Update the database with new order values
    await db["kanban_boards"].update_one(
        {"_id": ObjectId(board_id), "columns._id": ObjectId(column_id)},
        {"$set": {
            "columns.$.tender_items": tenders,
            "updated_at": datetime.now()
        }}
    )

async def remove_tender_from_kanban_boards(tender_result_id: str) -> int:
    """Remove a tender from all kanban boards it appears in.
    Returns the number of boards affected."""
    try:
        # Convert string ID to ObjectId
        tender_oid = ObjectId(tender_result_id)
        
        # Find all boards that have this tender in any column
        boards_cursor = db["kanban_boards"].find({
            "columns.tender_items.tender_analysis_result_id": tender_oid
        })
        
        boards = await boards_cursor.to_list(None)
        affected_boards = 0
        
        for board in boards:
            board_id = board["_id"]
            affected_columns = 0
            for column in board.get("columns", []):
                column_id = column["_id"]
                # Check if there are any tender items referencing this result
                has_items = any(
                    str(item.get("tender_analysis_result_id")) == str(tender_oid)
                    for item in column.get("tender_items", [])
                )
                
                if has_items:
                    # Pull any tender items that reference this tender
                    update_result = await db["kanban_boards"].update_one(
                        {"_id": board_id, "columns._id": column_id},
                        {"$pull": {"columns.$.tender_items": {"tender_analysis_result_id": tender_oid}}}
                    )
                    
                    if update_result.modified_count > 0:
                        affected_columns += 1
                        logger.info(f"Removed tender {tender_result_id} from board {board_id}, column {column_id}")
                        
                        # Reorder the remaining tenders in this column
                        await reorder_tenders(str(board_id), str(column_id))
            
            if affected_columns > 0:
                affected_boards += 1
                
        return affected_boards
    except Exception as e:
        logger.error(f"Error removing tender from kanban boards: {str(e)}")
        return 0

@router.post("/run_all_tender_analyses_for_user/{user_id}", response_model=Dict[str, Any])
async def run_all_analyses_for_user_endpoint(
    user_id: str,
    top_k: int = 20,
    score_threshold: float = 0.1,
    current_user: User = Depends(get_current_user)
):

    try:
        result = await run_all_analyses_for_user(
            user_id=user_id, top_k=top_k, score_threshold=score_threshold
        )
        return {"status": "Successfully ran all analyses for user", "result": result}
    except Exception as e:
        logger.error(f"Error running analyses for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-tender-analysis", response_model=Dict[str, Any])
async def run_tender_search(request: TenderSearchRequest, current_user: User = Depends(get_current_user)):
    try:
        analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(request.analysis_id)})
        if not analysis_doc:
            raise HTTPException(status_code=404, detail="Tender analysis configuration not found")

        filter_conditions = [
            {"field": "initiation_date", "op": "eq", "value": "2025-05-21"}
        ]
        if analysis_doc.get("sources"):
            filter_conditions.append({
                "field": "source_type",
                "op": "in",
                "value": analysis_doc["sources"]
            })

        tender_analysis = TenderAnalysis(**analysis_doc)
        
        if not tender_analysis.criteria or len(tender_analysis.criteria) == 0:
            tender_analysis.criteria = [AnalysisCriteria(**crit) for crit in DEFAULT_CRITERIA]
        else:
            updated_criteria = []
            for crit in tender_analysis.criteria:
                if crit.weight is None:
                    default = next((d for d in DEFAULT_CRITERIA if d["name"].lower() == crit.name.lower()), None)
                    if default:
                        crit.weight = default["weight"]
                    else:
                        crit.weight = 3
                
                if not hasattr(crit, 'instruction'):
                    crit.instruction = None
                    
                updated_criteria.append(crit)
            tender_analysis.criteria = updated_criteria
        
        criteria_definitions = tender_analysis.criteria
        
        result = await analyze_relevant_tenders_with_our_rag(
            analysis_id=request.analysis_id,
            current_user=current_user,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            filter_conditions=filter_conditions,
            tender_names_index_name="tenders",
            elasticsearch_index_name="tenders",
            embedding_model="text-embedding-3-large",
            rag_index_name="files-rag-23-04-2025",
            criteria_definitions=criteria_definitions
        )
        await assign_order_numbers(ObjectId(request.analysis_id), current_user)

        return {
            "status": "Tender analysis completed",
            "result": result,
        }
    except Exception as e:
        logger.error(f"Error running tender search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running tender search: {str(e)}")
    
@router.post("/run_all_tender_analyses", response_model=Dict[str, Any])
async def run_all_analyses():
    try:
        result = await run_all_tender_analyses()
        return {"status": "All tender analyses completed", "result": result}
    except Exception as e:
        logger.error(f"Error running all tender analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running batch analysis: {str(e)}")


@router.post("/tender-analysis", response_model=TenderAnalysis)
async def create_tender_analysis(
    analysis: TenderAnalysisCreate,
    current_user: User = Depends(get_current_user)
):
    try:
        criteria_with_weights = []
        for criterion in analysis.criteria:
            # Get default weight if not provided
            if not hasattr(criterion, 'weight') or criterion.weight is None:
                default_crit = next(
                    (c for c in DEFAULT_CRITERIA 
                    if c['name'].lower() == criterion.name.lower()),
                    None
                )
                weight = default_crit['weight'] if default_crit else 3
            else:
                weight = criterion.weight
            
            # Get optional flags
            is_disqualifying = getattr(criterion, 'is_disqualifying', False)
            exclude_from_score = getattr(criterion, 'exclude_from_score', False)
            
            # Get optional instruction
            instruction = getattr(criterion, 'instruction', None)
            subcriteria = getattr(criterion, 'subcriteria', None)
            
            criteria_with_weights.append({
                "name": criterion.name,
                "description": criterion.description,
                "weight": weight,
                "is_disqualifying": is_disqualifying,
                "exclude_from_score": exclude_from_score,
                "instruction": instruction,  # Add the instruction field
                "subcriteria": subcriteria,
            })

        # Rest of the function remains the same
        tender_analysis_data = {
            "user_id": current_user.id,
            "org_id": current_user.org_id,
            "name": analysis.name,
            "company_description": analysis.company_description,
            "search_phrase": analysis.search_phrase,
            "sources": analysis.sources,
            "criteria": criteria_with_weights,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "active": True
        }

        tender_analysis = TenderAnalysis(**tender_analysis_data)
        
        result = await db.tender_analysis.insert_one(
            tender_analysis.dict(by_alias=True))
        
        created_analysis = await db.tender_analysis.find_one(
            {"_id": result.inserted_id})
        return TenderAnalysis(**created_analysis)

    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
        
    except Exception as e:
        logger.error(f"Error creating tender analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating tender analysis: {str(e)}"
        )

@router.get("/tender-analysis", response_model=List[TenderAnalysis])
async def list_tender_analysis(
    current_user: User = Depends(get_current_user)
):
    """List all tender analyses for the current user or anyone in their organization"""
    try:
        base_query = [{"user_id": current_user.id}]
        # Only add org_id filter if it is defined and not empty
        if current_user.org_id and current_user.org_id.strip():
            base_query.append({"org_id": current_user.org_id})
        
        query = {"$or": base_query}
        
        analyses_cursor = db.tender_analysis.find(query)
        analyses = await analyses_cursor.to_list(None)
        return [TenderAnalysis(**analysis) for analysis in analyses]
    
    except Exception as e:
        logger.error(f"Error listing tender analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing tender analysis: {str(e)}"
        )

@router.get("/tender-analysis/{analysis_id}", response_model=TenderAnalysis)
async def get_tender_analysis(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Get a specific tender analysis by ID for the user or their organization"""
    try:
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
        
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found"
            )
        
        return TenderAnalysis(**analysis)
    
    except Exception as e:
        logger.error(f"Error getting tender analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting tender analysis: {str(e)}"
        )

@router.put("/tender-analysis/{analysis_id}", response_model=TenderAnalysis)
async def update_tender_analysis(
    analysis_id: PyObjectId,
    update_data: TenderAnalysisUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a tender analysis configuration"""
    try:
        # Check if analysis exists and belongs to user
        # This query should also check for org_id like the GET endpoint does
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
            
        existing = await db.tender_analysis.find_one(query)
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found"
            )
        
        # Filter out None values and prepare update
        update_dict = {
            k: v for k, v in update_data.dict().items() 
            if v is not None
        }
        
        if not update_dict:
            return TenderAnalysis(**existing)
        
        # Add updated_at timestamp
        update_dict["updated_at"] = datetime.utcnow()
        
        # Perform update
        await db.tender_analysis.update_one(
            {"_id": analysis_id},
            {"$set": update_dict}
        )
        
        # Get updated document
        updated = await db.tender_analysis.find_one({"_id": analysis_id})
        return TenderAnalysis(**updated)
    
    except Exception as e:
        logger.error(f"Error updating tender analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating tender analysis: {str(e)}"
        )

@router.delete("/tender-analysis/{analysis_id}", response_model=dict)
async def delete_tender_analysis(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Delete a tender analysis and its results"""
    try:
        # Check if analysis exists and belongs to user
        existing = await db.tender_analysis.find_one({
            "_id": analysis_id,
            "user_id": current_user.id
        })
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found"
            )
        
        # Delete the analysis
        await db.tender_analysis.delete_one({"_id": analysis_id})
        
        # Delete associated results
        delete_result = await db.tender_analysis_results.delete_many({
            "tender_analysis_id": analysis_id
        })
        
        return {
            "message": "Tender analysis deleted successfully",
            "deleted_results": delete_result.deleted_count
        }
    
    except Exception as e:
        logger.error(f"Error deleting tender analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting tender analysis: {str(e)}"
        )

@router.get("/tender-analysis/{analysis_id}/results")
async def get_tender_analysis_results(
    analysis_id: PyObjectId,
    page: int = 1,
    limit: int = 10,
    org_id: Optional[str] = None,  # Add org_id as a query parameter
    current_user: User = Depends(get_current_user)
):
    """Get paginated results for a specific tender analysis"""
    try:
        # Check if analysis exists and belongs to user or their organization
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
        elif org_id and org_id.strip() and org_id == current_user.org_id:
            query["$or"].append({"org_id": org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found"
            )
        
        # Calculate skip for pagination
        skip = (page - 1) * limit
        
        # Heavy sub-documents are not needed in the list view, exclude them to
        # keep the payload small (≈ 10× smaller) and to avoid the Pydantic
        # cost of validating thousands of big objects.
        projection = {
            # textual blobs / big arrays
            "criteria_analysis": 0,
            "criteria_analysis_archive": 0,
            "company_match_explanation": 0,
            "tender_description": 0,
            "uploaded_files": 0,
            "file_extraction_status": 0,
            "pinecone_config": 0,
        }

        cursor = db.tender_analysis_results.find(
            {
                "tender_analysis_id": analysis_id,
                "pinecone_config": {"$ne": None, "$exists": True},
            },
            projection,
        ).sort("created_at", -1).skip(skip).limit(limit)

        raw_results = await cursor.to_list(None)

        # Convert ObjectId instances to strings so they are JSON-serialisable.
        def _stringify_ids(doc):
            for k in ("_id", "tender_analysis_id", "user_id"):
                if k in doc and isinstance(doc[k], ObjectId):
                    doc[k] = str(doc[k])
            return doc

        results = [_stringify_ids(r) for r in raw_results]

        total = await db.tender_analysis_results.count_documents(
            {"tender_analysis_id": analysis_id}
        )

        # Dump JSON manually, falling back to str() on unknown types (ObjectId, datetime)
        payload = {"results": results, "total": total}
        return Response(
            content=json.dumps(payload, default=str, ensure_ascii=False),
            media_type="application/json",
        )

    except Exception as e:
        logger.error(f"Error getting tender analysis results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting tender analysis results: {str(e)}"
        )

@router.get("/tender-analysis/{analysis_id}/results/all")
async def get_all_tender_analysis_results(
    analysis_id: PyObjectId,
    org_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get all results (non-paginated) for a specific tender analysis.
    """
    # The same logic for verifying analysis ownership
    query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
    if current_user.org_id and current_user.org_id.strip():
        query["$or"].append({"org_id": current_user.org_id})
    elif org_id and org_id.strip() and org_id == current_user.org_id:
        query["$or"].append({"org_id": org_id})

    analysis = await db.tender_analysis.find_one(query)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Tender analysis not found"
        )

    # Simply fetch ALL results (no skip/limit)
    results = await db.tender_analysis_results.find({
        "tender_analysis_id": analysis_id
    }).sort("created_at", -1).to_list(None)

    # Dump JSON manually to ensure ObjectId is converted via str()
    serializable_results = [TenderAnalysisResult(**result) for result in results]
    return Response(
        content=json.dumps(serializable_results, default=str, ensure_ascii=False),
        media_type="application/json",
    )

@router.get("/test-downloads")
async def test_extractors():

    embedding_config = EmbeddingConfig(
        index_name="tenders",
        namespace="",
        embedding_model="text-embedding-3-large"
    )

    # Initialize the source manager
    source_manager = TenderSourceManager(embedding_config)
    browser = BrowserService()
    
    # Initialize browser service if needed
    await browser.initialize()
    
    # Create a browser context
    context = await browser.browser.new_context(
        ignore_https_errors=True,
        viewport={'width': 1920, 'height': 1080},
        accept_downloads=True,
    )
    
    to_test = [
        # ("bazakonkurencyjnosci", "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/ogloszenia/205364"),
        # ("egospodarka", "https://www.przetargi.egospodarka.pl/100012793_Przedmiotem-Zamowienia-sa-uslugi-krajowego-transportu-drogowego-w-zakresie-przewozu-osob-taksowka-pracownikow-i-innych-osob-wskazanych-przez-Zamawiajacego-oraz-rzeczy-na-warunkach-odroczonej-platnosci-w-grani_2025.html"),
        # ("epropublico_main", "https://e-propublico.pl/Ogloszenia/Details/d7f144e7-2693-442f-bd07-6ffb7995a063"),
        # ("platformazakupowa", "https://platformazakupowa.pl/transakcja/1065234"),
        # ("smartpzp", "https://portal.smartpzp.pl/pazp/public/postepowanie?postepowanie=76699829"),
        # ("logintrade", "https://platformazakupowa.grupaazoty.com/zapytania_email,1612179,d7931f2b96e75a1c7d742ca775b1e22e.html"),
        # ("ted", "https://ted.europa.eu/en/notice/-/detail/129599-2025"),
    # ("ezamawiajacy", "https://zimkrakow.ezamawiajacy.pl/app/demand/notice/public/164269/details"),
        # ("eb2b", "https://platforma.eb2b.com.pl/open-preview-auction.html/468376/wykonanie-okresowej-kontroli-instalacji-gazowych-w-nieruchomosciach-polozonych-w-obszarze-dzialania-oddzialu-terenowego-malopolskiego-2"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-b492919f-2be0-4ef6-8a25-4e9e8644f29f"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-425db1bc-bebb-445e-98e9-ffb5755efb68"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-dae85848-b230-41c5-87af-82474ea65c67"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-6ee274d0-5ecd-46a2-b4a2-7b699c833649").
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-6ad19e30-8eb1-4acb-b3ee-29e804f68590")
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-d1c9e5f6-b4b1-4660-b573-aabb973989a4")
        # ("orlenconnect", "https://connect.orlen.pl/app/outRfx/492099/supplier/status"),
        # ("pge", "https://swpp2.gkpge.pl/app/demand/notice/public/96084/details")
        ("logintrade", "https://suus.logintrade.net/portal,szczegolyZapytaniaOfertowe,51f45516c9f09f4f0fb4eb2af1845f2f.html")

        # ("eb2b", "https://platforma.eb2b.com.pl/open-preview-auction.html/471684/remont-pustostanow-lokali-mieszkalnych-czesc-nr-1-marszalkowska-34-50-m-23-adk-2-czesc-nr-2-krucza-6-14-m-5-adk-2-w-podziale-na-2-czesci"),
        # ("eb2b", "https://platforma.eb2b.com.pl/open-preview-auction.html/473338/opracowanie-dokumentacji-projektowo-kosztorysowej-na-remont-budynku-rozdzielnicy-agregatorowni-zlokalizowanej-na-terenie-stacji-pomp-rzecznych-przy-ul-czerniakowskiej-124-dzielnica-srodmiescie-1"),
        # ("eb2b", "https://platforma.eb2b.com.pl/open-preview-auction.html/473313/wykonanie-dokumentacji-projektowo-kosztorysowej-w-zakresie-projektu-budowlanego-specyfikacji-technicznej-wykonania-i-odbioru-robot-przedmiarow-i-kosztorysow-inwestorskich-na-przebudowy-komunalnych-lokali-mieszkalnych"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-da351595-ce41-4e45-b94b-4250f61eb053"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-da351595-ce41-4e45-b94b-4250f61eb053"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-d0a56ad4-70cd-465a-84eb-981e85014822"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-4a5c1d10-25c1-4c20-bea2-d535a9bd91ee"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-abf7a8c0-51e8-4ce5-92b9-07c667cd87bb"),
        # ("orlenconnect", "https://connect.orlen.pl/app/outRfx/497829/supplier/status"),
        # ("orlenconnect", "https://connect.orlen.pl/app/outRfx/497808/supplier/status"),
        # ("orlenconnect", "https://connect.orlen.pl/app/outRfx/497818/supplier/status"),
        # ("platformazakupowa", "https://platformazakupowa.pl/transakcja/1098119"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-c94cdb8a-6166-4aa2-adab-305e14b61227"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-1ca991c3-d398-41ed-9a59-aaf4e1698efc"),
        # ("ezamowienia", "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-4411716a-bb74-490a-b5c4-c219be75fa8c"),


    ]

    async def process_tender(source, url):
        logger.info(f"Started extracting: {source}")
        source_type = TenderSourceType(source)
        source_config = source_manager.source_configs.get(source_type)
        tender_extractor = (
                        source_config.extractor_class(**source_config.organization_config)
                        if source_config.organization_config
                        else source_config.extractor_class()
                    )
        processed_files = await tender_extractor.extract_files_from_detail_page(
                    context=context,  # Use the context created above
                    details_url=url
                )
        if not processed_files:
            logger.warning(f"No files successfully processed for tender: {source}")
            return None
        successful_files = []
        for file_content, filename, url, preview_chars, original_bytes  in processed_files:
            successful_files.append({
                            "name": filename,
                            "url": url,
                            "preview_chars": preview_chars
                        })

        logger.info(f"Finished extracting: {source}")
        return {"source": source,
             "files": successful_files}

    batch_size = 7
    semaphore = asyncio.Semaphore(batch_size)
    async def process_with_semaphore(source, url):
            async with semaphore:
                return await process_tender(source, url)

    try:
        resp = await asyncio.gather(*(
            process_with_semaphore(source, url)
            for source, url in to_test
        ))
        
        return {"ok": resp}
    finally:
        # Make sure to close the context to avoid resource leaks
        await context.close()


@router.post("/test-extractor")
async def test_extractor(file: UploadFile):

    file_extension = os.path.splitext(file.filename)[1].lower()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = Path(temp_dir) / file.filename
        
        # Write the uploaded file to the temporary file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        try:
            # Create an archive extractor
            extractor = ZipFileExtractor()
            
            # Extract the archive contents
            extracted_files = []
            for content in extractor.extract_file_content(temp_file_path):
                # Convert FileContent objects to a dict that can be serialized to JSON
                file_info = {
                    "filename": content.metadata.get("filename", "Unknown"),
                    "path": content.metadata.get("path_in_archive", "Unknown"),
                    "extension": content.metadata.get("original_extension", "Unknown"),
                    "archive_source": content.metadata.get("archive_source", file.filename),
                    "archive_type": content.metadata.get("archive_type", file_extension[1:]),
                    "file_size": content.metadata.get("file_size", 0),
                }
                
                # Add preview if available
                if "preview_chars" in content.metadata and content.metadata["preview_chars"]:
                    file_info["preview"] = content.metadata["preview_chars"][:100] + "..." if len(content.metadata["preview_chars"]) > 100 else content.metadata["preview_chars"]
                
                extracted_files.append(file_info)
            
            # Return the results
            return {
                    "message": f"Successfully extracted {len(extracted_files)} files from {file.filename}",
                    "archive_type": file_extension[1:],
                    "file_count": len(extracted_files),
                    "extracted_files": extracted_files
            }
        
        except Exception as e:
            logger.error(f"Error extracting archive: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error extracting archive: {str(e)}")



@router.get("/tender-result/{result_id}", response_model=TenderAnalysisResult)
async def get_tender_result(
    result_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific tender analysis result by ID"""
    # 1) Parse and convert the string to ObjectId
    try:
        oid = ObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tender result ID format")

    # 2) Fetch from DB
    try:
        result = await db.tender_analysis_results.find_one({"_id": oid})
    except Exception:
        logger.error("Database error fetching tender result", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if not result:
        raise HTTPException(status_code=404, detail="Tender analysis result not found")

    # 3) Ensure default criteria weight
    for crit in result.get("criteria_analysis", []):
        analysis = crit.get("analysis", {})
        if "weight" not in analysis:
            analysis["weight"] = 3

    try:
        return TenderAnalysisResult(**result)
    except Exception:
        logger.error("Error processing tender result model", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing tender result")

@router.put("/tender-result/{result_id}", response_model=TenderAnalysisResult)
async def update_tender_result(
    result_id: PyObjectId,
    update_data: TenderAnalysisResultUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a tender analysis result"""
    try:
        # Check if result exists and belongs to user
        existing = await db.tender_analysis_results.find_one({
            "_id": result_id,
            "user_id": str(current_user.id)  # Convert user_id to string for comparison
        })
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis result not found"
            )
        
        # Filter out None values and prepare update
        update_dict = {
            k: v for k, v in update_data.dict().items() 
            if v is not None
        }
        
        if not update_dict:
            return TenderAnalysisResult(**existing)
        
        # Perform update
        await db.tender_analysis_results.update_one(
            {"_id": result_id},
            {"$set": update_dict}
        )
        
        # Get updated document
        updated = await db.tender_analysis_results.find_one({"_id": result_id})
        return TenderAnalysisResult(**updated)
    
    except Exception as e:
        logger.error(f"Error updating tender result: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating tender result: {str(e)}"
        )

@router.delete("/tender-result/{result_id}", response_model=dict)
async def delete_tender_result(
    result_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Delete a specific tender analysis result"""
    try:
        result = await db.tender_analysis_results.find_one({
            "_id": result_id
        })
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis result not found"
            )
        
        # Remove the tender from all kanban boards it appears in
        logger.info(f"Removing tender {result_id} from kanban boards before deletion")
        boards_affected = await remove_tender_from_kanban_boards(str(result_id))
        
        # Check if there are other analyses using the same tender URL
        tender_url = result.get("tender_url")
        other_analyses_count = await db.tender_analysis_results.count_documents({
            "tender_url": tender_url,
            "_id": {"$ne": result_id}  # Exclude current analysis
        })
        
        files_deleted_from_storage = 0
        # Only delete files and Pinecone data if this is the last analysis with this tender URL
        if other_analyses_count == 0:
            logger.info(f"This is the last analysis with tender URL {tender_url}. Cleaning up files and Pinecone data.")
            
            s3_blob_urls_to_delete = []
            vercel_blob_urls_to_delete = []

            for file_doc in result.get("uploaded_files", []):
                blob_url = file_doc.get("blob_url")
                if blob_url:
                    if "s3.amazonaws.com" in blob_url: # Basic check for S3 URL
                        s3_blob_urls_to_delete.append(blob_url)
                    elif "vercel.app" in blob_url: # Basic check for Vercel URL
                        vercel_blob_urls_to_delete.append(blob_url)
                    else:
                        logger.warning(f"Unknown blob_url format, cannot delete: {blob_url}")
            
            if s3_blob_urls_to_delete:
                try:
                    delete_files_from_s3(s3_blob_urls_to_delete)
                    files_deleted_from_storage += len(s3_blob_urls_to_delete)
                    logger.info(f"Deleted {len(s3_blob_urls_to_delete)} files from S3.")
                except Exception as e:
                    logger.error(f"Error deleting files from S3: {str(e)}")

            if vercel_blob_urls_to_delete:
                try:
                    # Assuming delete_files_from_vercel_blob takes a list like the S3 one
                    # If it takes one by one, this needs a loop
                    delete_files_from_vercel_blob(vercel_blob_urls_to_delete)
                    files_deleted_from_storage += len(vercel_blob_urls_to_delete)
                    logger.info(f"Deleted {len(vercel_blob_urls_to_delete)} files from Vercel Blob.")
                except Exception as e:
                    logger.error(f"Error deleting files from Vercel Blob: {str(e)}")

        # Always delete the analysis result record
        await db.tender_analysis_results.delete_one({"_id": result_id})
        
        return {
            "message": "Tender analysis result deleted successfully",
            "deleted_result_id": str(result_id),
            "files_deleted": files_deleted_from_storage > 0 # Updated to reflect actual deletions
        }
    
    except Exception as e:
        logger.error(f"Error deleting tender result: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting tender result: {str(e)}"
        )

@router.post("/tender-result", response_model=TenderAnalysisResult)
async def create_tender_result(
    analysis_id: PyObjectId,
    result_data: TenderAnalysisResult,
    current_user: User = Depends(get_current_user)
):
    """Create a new tender analysis result"""
    try:
        # Check if the analysis exists and belongs to the user
        analysis = await db.tender_analysis.find_one({
            "_id": analysis_id,
            "user_id": current_user.id
        })
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found"
            )
        
        # Set the user_id and analysis_id
        result_data.user_id = current_user.id
        result_data.tender_analysis_id = analysis_id
        
        # Insert the result
        result = await db.tender_analysis_results.insert_one(
            result_data.dict(by_alias=True)
        )
        
        # Get the created document
        created_result = await db.tender_analysis_results.find_one({"_id": result.inserted_id})
        return TenderAnalysisResult(**created_result)
    
    except Exception as e:
        logger.error(f"Error creating tender result: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating tender result: {str(e)}"
        )

@router.get("/tender-results", response_model=List[TenderAnalysisResult])
async def list_tender_results(
    analysis_id: Optional[PyObjectId] = None,
    current_user: User = Depends(get_current_user)
):
    """List all tender analysis results for the current user, optionally filtered by analysis ID"""
    try:
        # Build query
        query = {"user_id": ObjectId(current_user.id)}  # Convert user_id to string for comparison
        if analysis_id:
            query["tender_analysis_id"] = analysis_id

        print(query)
            
        # Check if the analysis exists and belongs to the user if analysis_id is provided
        if analysis_id:
            analysis = await db.tender_analysis.find_one({
                "_id": analysis_id,
                "user_id": current_user.id
            })
            if not analysis:
                raise HTTPException(
                    status_code=404,
                    detail="Tender analysis not found"
                )
        
        # Fetch results
        results = await db.tender_analysis_results.find(query).to_list(None)
        return [TenderAnalysisResult(**result) for result in results]
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing tender results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing tender results: {str(e)}"
        )
    
@router.patch("/tender-results/{result_id}/edit-criteria/{criteria}")
async def update_criteria_analysis(
    result_id: str, 
    criteria: str, 
    update_data: CriteriaAnalysisUpdate
):
    result_doc = await db.tender_analysis_results.find_one({"_id": ObjectId(result_id)})
    if not result_doc:
        raise HTTPException(status_code=404, detail="TenderAnalysisResult not found")
    
    criteria_list = result_doc.get("criteria_analysis", [])
    archive_list = result_doc.get("criteria_analysis_archive", [])
    
    if not result_doc.get("criteria_analysis_edited", False):
        archive_list = [crit.copy() for crit in criteria_list]

    found = False
    for idx, crit in enumerate(criteria_list):
        if crit.get("criteria") == criteria:
            current_analysis = crit.get("analysis", {})
            updated_analysis = {**current_analysis, **update_data.dict(exclude_unset=True)}
            criteria_list[idx]["analysis"] = updated_analysis
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Criteria '{criteria}' not found")
    
    await db.tender_analysis_results.update_one(
        {"_id": ObjectId(result_id)},
        {"$set": {
            "criteria_analysis": criteria_list,
            "criteria_analysis_archive": archive_list,
            "criteria_analysis_edited": True
        }}
    )
    
    return {"message": "Criteria analysis updated successfully"}


@router.patch("/tender-result/{result_id}/mark_opened")
async def mark_result_opened(result_id: str):
    # 1) Find the document in DB
    result_doc = await db.tender_analysis_results.find_one({"_id": ObjectId(result_id)})

    if not result_doc:
        raise HTTPException(status_code=404, detail="TenderAnalysisResult not found")

    await db.tender_analysis_results.update_one(
        {"_id": ObjectId(result_id)},
        {"$set": {"opened_at": datetime.utcnow()}}
    )
    return {"message": "Tender result marked as opened."}

@router.patch("/tender-result/{result_id}/mark_unopened")
async def mark_result_unopened(result_id: str):
    # 1) Find the document in DB
    result_doc = await db.tender_analysis_results.find_one({"_id": ObjectId(result_id)})
    if not result_doc:
        raise HTTPException(status_code=404, detail="TenderAnalysisResult not found")

    await db.tender_analysis_results.update_one(
        {"_id": ObjectId(result_id)},
        {"$set": {"opened_at": None}}
    )
    return {"message": "Tender result marked as unopened."}



@router.patch("/tender-result/{result_id}/update_status")
async def update_result_status(
    result_id: str,
    status: str,
    current_user: User = Depends(get_current_user)
):
    """Update the status of a tender result"""
    try:
        # Validate status is one of the allowed values
        if status not in ["inactive", "active", "archived"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be one of: inactive, active, archived"
            )
        
        # Convert string ID to ObjectId
        result_oid = ObjectId(result_id)
            
        # Check if result exists
        existing = await db.tender_analysis_results.find_one({
            "_id": result_oid
        })
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis result not found"
            )
        
        
        # Update the status and set updated_at timestamp
        await db.tender_analysis_results.update_one(
            {"_id": result_oid},
            {"$set": {
                "status": status
            }}
        )
        
        boards_affected = 0
        # If setting to inactive or archived, remove from kanban boards
        if status in ["inactive", "archived"]:
            logger.info(f"Removing tender {result_id} from kanban boards due to status change to {status}")
            boards_affected = await remove_tender_from_kanban_boards(result_id)
        
        return {
            "message": f"Tender result status updated to {status}.",
            "boards_affected": boards_affected
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating tender result status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating tender result status: {str(e)}"
        )


@router.delete("/tender-results/remove-duplicates", response_model=dict)
async def remove_duplicate_tender_results(
    email: str
):
    """Remove duplicate tender analysis results based on tender_url for the user with given email"""
    try:
        # Find user by email
        user = await db.users.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id_obj = ObjectId(str(user["_id"]))
        # Step 1: Fetch all tender analyses for the user
        tender_analyses = await db.tender_analysis.find({
            "user_id": user_id_obj
        }).to_list(None)

        if not tender_analyses:
            return {
                "message": "No tender analyses found for the user",
                "duplicates_removed": 0,
                "remaining_results": 0
            }

        total_duplicates_removed = 0
        total_remaining_results = 0
        total_files_deleted = 0

        # Step 2: For each tender analysis, check its results for duplicates
        for analysis in tender_analyses:
            analysis_id = analysis["_id"]
            # Fetch all results for this tender analysis
            results = await db.tender_analysis_results.find({
                "tender_analysis_id": ObjectId(analysis_id)
            }).to_list(None)

            # Step 3: Identify duplicates based on tender_url
            seen_urls = {}
            duplicates_to_remove = []

            for result in results:
                tender_url = result.get("tender_url")
                result_id = result["_id"]
                # Ensure result_id is an ObjectId
                if isinstance(result_id, str):
                    result_id = ObjectId(result_id)

                if not tender_url:
                    print(f"Skipping result {result_id} - no tender_url")
                    continue

                if tender_url in seen_urls:
                    print(f"Found duplicate tender_url '{tender_url}' - marking {result_id} for removal")
                    duplicates_to_remove.append(result_id)
                else:
                    print(f"Keeping first occurrence of tender_url '{tender_url}' - ID: {result_id}")
                    seen_urls[tender_url] = result_id

            # Step 4: Delete duplicates if any found
            deleted_count = 0
            if duplicates_to_remove:
                # Collect all duplicate results to be deleted
                duplicate_results = await db.tender_analysis_results.find({
                    "_id": {"$in": duplicates_to_remove}
                }).to_list(None)

                # Process each duplicate result individually
                for result in duplicate_results:
                    result_id = result["_id"]
                    tender_url = result.get("tender_url")
                    
                    # Check if there are other analyses using the same tender URL
                    # (outside of our duplicates_to_remove list)
                    other_analyses_count = await db.tender_analysis_results.count_documents({
                        "tender_url": tender_url,
                        "_id": {"$nin": duplicates_to_remove}  # Not in our duplicates list
                    })
                    
                    # Collect blob URLs that need to be deleted
                    result_blob_urls = [
                        file.get("blob_url")
                        for file in result.get("uploaded_files", [])
                        if file.get("blob_url")
                    ]
                    
                    # Only delete files and Pinecone data if this is the last analysis with this tender URL
                    if other_analyses_count == 0 and result_blob_urls:
                        logger.info(f"No other analyses found using tender URL '{tender_url}'. Deleting {len(result_blob_urls)} files.")
                        delete_files_from_s3(result_blob_urls)
                        total_files_deleted += len(result_blob_urls)
                        
                        # Handle Pinecone data deletion if needed
                        if result.get("pinecone_config"):
                            pinecone_config = result.get("pinecone_config")
                            if pinecone_config.get("namespace") != "":
                                pinecone_query_tool = QueryTool(config=QueryConfig(
                                    index_name=pinecone_config.get("index_name"),
                                    namespace=pinecone_config.get("namespace"),
                                    embedding_model=pinecone_config.get("embedding_model")
                                ))
                                pinecone_query_tool.delete_namespace()
                                logger.info(f"Deleted Pinecone namespace: {pinecone_config.get('namespace')}")

                        file_pinecone_configs = [
                            file.get("file_pinecone_config")
                            for file in result.get("uploaded_files", [])
                            if file.get("file_pinecone_config")
                        ]
                        
                        for config in file_pinecone_configs:
                            if config.get("pinecone_unique_id_prefix", None):
                                pinecone_query_tool = QueryTool(config=QueryConfig(
                                        index_name=pinecone_config.get("index_name"),
                                        namespace=pinecone_config.get("namespace")
                                    ))
                                pinecone_query_tool.delete_from_pinecone_by_id_prefix(config.get("pinecone_unique_id_prefix", None))
                                logger.info(f"Deleted Pinecone data with prefix: {config.get('pinecone_unique_id_prefix')}")
                    else:
                        logger.info(f"Found {other_analyses_count} other analyses using tender URL '{tender_url}'. Skipping file deletion.")


                # Delete all duplicate results from database
                delete_result = await db.tender_analysis_results.delete_many({
                    "_id": {"$in": duplicates_to_remove}
                })
                deleted_count = delete_result.deleted_count
                print(f"Deleted {deleted_count} duplicate documents for analysis {analysis_id}")
                total_duplicates_removed += deleted_count

            remaining_count = await db.tender_analysis_results.count_documents({
                "tender_analysis_id": analysis_id
            })
            print(f"Remaining results for analysis {analysis_id}: {remaining_count}")
            total_remaining_results += remaining_count

        return {
            "message": "Duplicate tender results removed successfully",
            "duplicates_removed": total_duplicates_removed,
            "remaining_results": total_remaining_results,
            "files_deleted": total_files_deleted
        }

    except Exception as e:
        logger.error(f"Error removing duplicate tender results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error removing duplicate tender results: {str(e)}"
        )
    
@router.get("/tender-analysis/{analysis_id}/active-results", response_model=List[TenderAnalysisResult])
async def get_active_tender_results(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    try:
        # Build query to allow access for owners or org members.
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
        
        analysis = await db.tender_analysis.find_one(query)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found"
            )

        # Fetch active results
        results = await db.tender_analysis_results.find({
            "tender_analysis_id": analysis_id,
            "status": "active"
        }).sort("created_at", -1).to_list(None)

        return [TenderAnalysisResult(**result) for result in results]

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting active tender results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting active tender results: {str(e)}"
        )
    

@router.post("/test-user-analysis/{user_id}", response_model=Dict[str, Any])
async def test_user_analysis(
    user_id: str,
    request: UserAnalysisTestRequest
):
    try:
        # Verify user exists
        user_data = await db['users'].find_one({"_id": ObjectId(user_id)})
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {user_id} not found"
            )
        
        # Set default target date to today if not provided
        target_date = "2025-05-12"
            
        filter_conditions = [
            {"field": "initiation_date", "op": "eq", "value": target_date}
        ]
        
        # Get analyses to process
        if request.specific_analysis_id:
            # If specific analysis ID is provided, run only that analysis
            analysis_doc = await db.tender_analysis.find_one({
                "_id": ObjectId(request.specific_analysis_id),
                "user_id": ObjectId(user_id),
                "active": True
            })
            
            if not analysis_doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Active tender analysis with ID {request.specific_analysis_id} not found for user {user_id}"
                )
            
            analyses_to_process = [analysis_doc]
        else:
            # Run all analyses for the specified user
            analyses_cursor = db.tender_analysis.find({
                "user_id": ObjectId(user_id),
                "active": True
            })
            
            analyses_to_process = await analyses_cursor.to_list(None)
            
            if not analyses_to_process:
                return {
                    "status": "No active analyses found for user",
                    "user_id": user_id,
                    "target_date": target_date
                }
        
        logger.info(f"Running {len(analyses_to_process)} analyses for user {user_id} using run_partial_tender_analyses")
        
        # Use the run_partial_tender_analyses function
        result = await run_partial_tender_analyses(
            analyses=analyses_to_process,
            target_date=target_date,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            filter_conditions=filter_conditions
        )
        
        # Structure response for API
        formatted_results = []
        for batch_result in result.analysis_results:
            formatted_results.append({
                "analysis_id": batch_result.analysis_id,
                "query": batch_result.query,
                "total_tenders_analyzed": batch_result.total_tenders_analyzed,
                "tender_ids": [str(r.id) for r in batch_result.analysis_results]
            })
        
        return {
            "status": "Test completed using run_partial_tender_analyses",
            "user_id": user_id,
            "target_date": target_date,
            "total_analyses": result.total_analyses,
            "successful_analyses": result.successful_analyses,
            "failed_analyses": result.failed_analyses,
            "results": formatted_results,
            "summary_data": result.analysis_summary_data if hasattr(result, 'analysis_summary_data') else []
        }
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error testing user analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error testing user analysis: {str(e)}"
        )

@router.post("/tender-results/batch", response_model=List[TenderAnalysisResult])
async def get_tender_results_batch(
    result_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    """Get multiple tender analysis results by their IDs in a single request"""
    try:
        # Convert string IDs to ObjectIds
        object_ids = [ObjectId(id) for id in result_ids]
        
        # Fetch all requested tender results
        results = await db.tender_analysis_results.find({
            "_id": {"$in": object_ids}
        }).to_list(None)
        
        return [TenderAnalysisResult(**result) for result in results]
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting batch tender results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting batch tender results: {str(e)}"
        )
    
@router.get("/tender-analysis/{analysis_id}/filtered-results", response_model=Dict[str, Any])
async def get_filtered_tender_analysis_results(
    analysis_id: PyObjectId,
    filter_stage: Optional[FilterStage] = Query(None, description="Filter by stage: ai_initial_filter, file_extraction, or ai_description_filter"),
    org_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user)
):
    """Get paginated filtered results for a specific tender analysis"""
    try:
        # Check if analysis exists and belongs to user or their organization
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
        elif org_id and org_id.strip() and org_id == current_user.org_id:
            query["$or"].append({"org_id": org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Build query for filtered results
        filtered_query = {"analysis_id": str(analysis_id)}
        
        # Add filter_stage to query if provided
        if filter_stage:
            filtered_query["filter_stage"] = filter_stage
        
        # Fetch paginated results
        results = await db.filtered_tender_analysis_results.find(
            filtered_query
        ).sort("filter_timestamp", -1).to_list(None)
        
        # Get total count of results
        total = await db.filtered_tender_analysis_results.count_documents(filtered_query)
        
        # Convert results for response
        formatted_results = []
        for result in results:
            # Handle ObjectId conversion
            if "_id" in result and isinstance(result["_id"], ObjectId):
                result["_id"] = str(result["_id"])
            
            # Handle any nested ObjectIds
            if "original_match" in result and result["original_match"] and "id" in result["original_match"] and isinstance(result["original_match"]["id"], ObjectId):
                result["original_match"]["id"] = str(result["original_match"]["id"])
                
            formatted_results.append(result)
        
        return {
            "total": total,
            "results": formatted_results
        }
    
    except Exception as e:
        logger.error(f"Error getting filtered tender analysis results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting filtered tender analysis results: {str(e)}"
        )
    
@router.get("/tender-analysis/{analysis_id}/filtered-results/stats", response_model=Dict[str, Any])
async def get_filtered_tender_analysis_stats(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Get statistics about filtered results for a specific tender analysis"""
    try:
        # Check if analysis exists and belongs to user or their organization
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Get counts by filter stage
        pipeline = [
            {"$match": {"analysis_id": str(analysis_id)}},
            {"$group": {"_id": "$filter_stage", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        
        stage_counts = await db.filtered_tender_analysis_results.aggregate(pipeline).to_list(None)
        
        # Get counts by filter reason
        reason_pipeline = [
            {"$match": {"analysis_id": str(analysis_id)}},
            {"$group": {"_id": "$filter_reason", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}  # Top 10 reasons
        ]
        
        reason_counts = await db.filtered_tender_analysis_results.aggregate(reason_pipeline).to_list(None)
        
        stats = {
            "total_filtered": sum(item["count"] for item in stage_counts),
            "by_stage": {item["_id"]: item["count"] for item in stage_counts},
            "top_reasons": {str(item["_id"] or "Unknown"): item["count"] for item in reason_counts}
        }
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting filtered tender analysis stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting filtered tender analysis stats: {str(e)}"
        )

@router.get("/tender-analysis/{analysis_id}/filtered-results/all", response_model=List[FilteredTenderAnalysisResult])
async def get_all_filtered_tender_analysis_results(
    analysis_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10000, ge=10, le=10000, description="Number of results per page"),
    current_user: User = Depends(get_current_user)
):
    """Get filtered results for a specific tender analysis with pagination"""
    try:
        # Check if analysis exists and belongs to user or their organization
        query = {"_id": ObjectId(analysis_id), "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Calculate skip value for pagination
        skip = (page - 1) * page_size
        
        # Use an aggregation pipeline to handle ObjectId conversions in the database
        pipeline = [
            {"$match": {"analysis_id": analysis_id}},
            {"$sort": {"filter_timestamp": -1}},
            {"$skip": skip},
            {"$limit": page_size},
            # Convert ObjectIds to strings in the database
            {"$addFields": {
                "_id": {"$toString": "$_id"},
                "user_id": {"$toString": "$user_id"},
                "original_match._id": {"$cond": [
                    {"$and": [
                        {"$ifNull": ["$original_match", False]},
                        {"$ifNull": ["$original_match._id", False]}
                    ]},
                    {"$toString": "$original_match._id"},
                    "$original_match._id"
                ]},
                "original_match.id": {"$cond": [
                    {"$and": [
                        {"$ifNull": ["$original_match", False]},
                        {"$ifNull": ["$original_match.id", False]}
                    ]},
                    {"$toString": "$original_match.id"},
                    "$original_match.id"
                ]}
            }}
        ]
        
        # Execute the aggregation pipeline
        filtered_results = await db.filtered_tender_analysis_results.aggregate(pipeline).to_list(None)
        
        if not filtered_results:
            return []
        
        # Convert results to FilteredTenderAnalysisResult model objects
        return [FilteredTenderAnalysisResult(**result) for result in filtered_results]
    
    except Exception as e:
        logger.error(f"Error getting filtered tender analysis results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting filtered tender analysis results: {str(e)}"
        )

@router.get("/filtered-tender/{tender_id}", response_model=FilteredTenderAnalysisResult)
async def get_filtered_tender_by_id(
    tender_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific filtered tender by its tender_id"""
    try:
        # Find the filtered tender by tender_id
        filtered_tender = await db.filtered_tender_analysis_results.find_one(
            {"tender_id": tender_id}
        )
        
        if not filtered_tender:
            raise HTTPException(
                status_code=404,
                detail=f"Filtered tender with ID {tender_id} not found"
            )
        
        # Get the analysis to check access permissions
        analysis_id = filtered_tender.get("analysis_id")
        if not analysis_id:
            raise HTTPException(
                status_code=404,
                detail="Analysis ID not found for this filtered tender"
            )
            
        # Check if user has access to the analysis
        query = {"_id": ObjectId(analysis_id), "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this filtered tender"
            )
        
        # Return the filtered tender result
        return FilteredTenderAnalysisResult(**filtered_tender)
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving filtered tender: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving filtered tender: {str(e)}"
        )
    
@router.post("/cleanup-filtered-files-by-date")
async def cleanup_files_by_date(
    days_old: int = Query(0, description="Delete files older than this many days"),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Starting cleanup of filtered files older than {days_old} days, initiated by user {current_user.id}")
    
    async def delete_from_storage(blob_url: str) -> bool: # Renamed for clarity
        try:
            if "s3.amazonaws.com" in blob_url:
                logger.debug(f"Attempting to delete file from S3: {blob_url}")
                delete_files_from_s3([blob_url]) # delete_files_from_s3 expects a list
                logger.debug(f"Successfully deleted file from S3: {blob_url}")
            elif "vercel.app" in blob_url:
                logger.debug(f"Attempting to delete file from Vercel blob: {blob_url}")
                delete_files_from_vercel_blob([blob_url]) # delete_files_from_vercel_blob expects a list
                logger.debug(f"Successfully deleted file from Vercel blob: {blob_url}")
            else:
                logger.warning(f"Unknown blob_url format, cannot delete: {blob_url}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error deleting file from storage ({blob_url}): {str(e)}", exc_info=True)
            return False

    # Calculate the cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    logger.info(f"Cutoff date for file cleanup: {cutoff_date.isoformat()}")
    
    # Find all filtered tenders older than the cutoff date
    logger.info(f"Querying database for filtered tenders older than {cutoff_date.isoformat()}")
    filtered_tenders = await db.filtered_tender_analysis_results.find({
        "filter_timestamp": {"$lt": cutoff_date},
    }).to_list()
    
    logger.info(f"Found {len(filtered_tenders)} filtered tenders older than {days_old} days")
    
    deletion_stats = {
        "total_processed": 0,
        "blob_deleted": 0,
        "pinecone_deleted": 0,
        "already_deleted": 0,
        "errors": 0
    }
    
    for tender_index, tender in enumerate(filtered_tenders):
        tender_id = str(tender.get("_id", "unknown"))
        # logger.info(f"Processing tender {tender_index+1}/{len(filtered_tenders)} - ID: {tender_id}")
        
        # Skip if there are no processed files or storage info
        if not tender.get("processed_files") or not tender.get("processed_files", {}).get("storage_info"):
            # logger.warning(f"Tender {tender_id} has no storage_info, skipping")
            continue
            
        storage_info = tender["processed_files"]["storage_info"]
        logger.info(f"Tender {tender_id} has {len(storage_info)} files to process")
        
        for i, file_info in enumerate(storage_info):
            filename = file_info.get("filename", "unknown")
            logger.info(f"Processing file {i+1}/{len(storage_info)} - '{filename}' for tender {tender_id}")
            
            # Skip if already fully deleted
            if file_info.get("deletion_status") == "deleted_both":
                logger.info(f"File '{filename}' already fully deleted, skipping")
                deletion_stats["already_deleted"] += 1
                continue
                
            deletion_stats["total_processed"] += 1
            update_needed = False
            
            # Delete from Vercel Blob if needed
            if file_info.get("blob_url") and file_info.get("deletion_status") not in ["deleted_blob", "deleted_both"]:
                blob_url = file_info["blob_url"]
                logger.info(f"Attempting to delete file '{filename}' from storage: {blob_url}")
                storage_deleted = await delete_from_storage(blob_url) # Use the new helper
                
                if storage_deleted:
                    previous_status = file_info.get("deletion_status", "pending")
                    if previous_status == "deleted_pinecone":
                        file_info["deletion_status"] = "deleted_both"
                        logger.info(f"File '{filename}' now completely deleted (blob + pinecone)")
                    else:
                        file_info["deletion_status"] = "deleted_blob"
                        logger.info(f"File '{filename}' deleted from blob successfully")
                    
                    file_info["deletion_timestamp"] = datetime.utcnow().isoformat()
                    update_needed = True
                    deletion_stats["blob_deleted"] += 1 # Keep this stat name for now, or rename if it's more general
                else:
                    file_info["deletion_status"] = "error"
                    file_info["deletion_error"] = f"Failed to delete from storage ({('S3' if 's3.amazonaws.com' in blob_url else 'Vercel') if blob_url else 'Unknown'})"
                    update_needed = True
                    deletion_stats["errors"] += 1
                    logger.error(f"Failed to delete file '{filename}' from storage")
            
            # Delete from Pinecone if needed
            if file_info.get("file_pinecone_config") and file_info.get("deletion_status") not in ["deleted_pinecone", "deleted_both"]:
                config = file_info["file_pinecone_config"]
                prefix = config.get("pinecone_unique_id_prefix", "unknown")
                
                logger.info(f"Attempting to delete file '{filename}' vectors from Pinecone with prefix: {prefix}")
                pinecone_deleted = await delete_from_pinecone(config)
                
                if pinecone_deleted:
                    previous_status = file_info.get("deletion_status", "pending")
                    if previous_status == "deleted_blob":
                        file_info["deletion_status"] = "deleted_both"
                        logger.info(f"File '{filename}' now completely deleted (blob + pinecone)")
                    else:
                        file_info["deletion_status"] = "deleted_pinecone"
                        logger.info(f"File '{filename}' deleted from Pinecone successfully")
                        
                    file_info["deletion_timestamp"] = datetime.utcnow().isoformat()
                    update_needed = True
                    deletion_stats["pinecone_deleted"] += 1
                else:
                    if file_info.get("deletion_status") != "error":
                        file_info["deletion_status"] = "error"
                        file_info["deletion_error"] = "Failed to delete from Pinecone"
                        update_needed = True
                        deletion_stats["errors"] += 1
                        logger.error(f"Failed to delete file '{filename}' vectors from Pinecone")
            
            # Update the database if changes were made
            if update_needed:
                logger.debug(f"Updating database for file '{filename}' with new deletion status: {file_info['deletion_status']}")
                await db.filtered_tender_analysis_results.update_one(
                    {"_id": ObjectId(tender["_id"])},
                    {"$set": {f"processed_files.storage_info.{i}": file_info}}
                )
    
    # Log summary statistics
    logger.info("File cleanup process completed with the following results:")
    logger.info(f"Total files processed: {deletion_stats['total_processed']}")
    logger.info(f"Files deleted from blob: {deletion_stats['blob_deleted']}")
    logger.info(f"Files deleted from Pinecone: {deletion_stats['pinecone_deleted']}")
    logger.info(f"Files already deleted: {deletion_stats['already_deleted']}")
    logger.info(f"Errors encountered: {deletion_stats['errors']}")
    
    return {
        "message": f"Processed {deletion_stats['total_processed']} files",
        "stats": deletion_stats
    }

@router.post("/tender-analysis/{analysis_id}/duplicate", response_model=TenderAnalysis)
async def duplicate_tender_analysis(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Duplicate an existing tender analysis for the current user."""
    try:
        # Find the original analysis
        original_analysis_doc = await db.tender_analysis.find_one({"_id": analysis_id})
        
        if not original_analysis_doc:
            raise HTTPException(
                status_code=404,
                detail="Original tender analysis not found"
            )
            
        # Create a copy and update necessary fields
        new_analysis_data = original_analysis_doc.copy()
        new_analysis_data["user_id"] = current_user.id
        new_analysis_data["org_id"] = current_user.org_id
        new_analysis_data["name"] = f"{new_analysis_data.get('name', 'Untitled Analysis')} - Copy"
        new_analysis_data["created_at"] = datetime.utcnow()
        new_analysis_data["updated_at"] = datetime.utcnow()
        
        # Remove the original ID
        new_analysis_data.pop("_id", None)
        
        # Create and insert the new analysis
        new_tender_analysis = TenderAnalysis(**new_analysis_data)
        
        insert_result = await db.tender_analysis.insert_one(
            new_tender_analysis.dict(by_alias=True)
        )
        
        # Fetch and return the newly created analysis
        created_analysis = await db.tender_analysis.find_one(
            {"_id": insert_result.inserted_id}
        )
        if not created_analysis:
             raise HTTPException(
                status_code=500,
                detail="Failed to retrieve duplicated analysis after creation"
            )
            
        return TenderAnalysis(**created_analysis)

    except HTTPException as e:
        raise e
    except ValidationError as e:
        logger.error(f"Validation error during duplication: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error duplicating tender analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error duplicating tender analysis: {str(e)}"
        )
    
@router.patch("/tender-analysis/increase-relevancy")
async def increase_relevancy_score(
    analysis_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    """Decrease the tender_score for all results of a given analysis by a random amount per result."""
    try:
        logger.info(f"Starting tender_score decrease for analysis_id={analysis_id} by user {current_user.id}")
        
        # Check if analysis exists and belongs to user or their organization
        query = {"_id": ObjectId(analysis_id), "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
        
        logger.debug(f"Looking for analysis with query: {query}")    
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            logger.warning(f"Analysis not found or access denied for ID: {analysis_id}, user: {current_user.id}")
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        logger.info(f"Found analysis: {analysis.get('name', 'unnamed')} (ID: {analysis_id})")
        
        # Find all results for this analysis with the specified initiation date
        results_query = {
            "tender_analysis_id": ObjectId(analysis_id),
            "tender_metadata.initiation_date": "2025-05-06"
        }
        
        logger.info(f"Finding results with query: {results_query}")
        results = await db.tender_analysis_results.find(results_query).to_list(None)
        logger.info(f"Found {len(results)} matching results")
        
        # Generate and apply a random score decrease for each result individually
        updated_count = 0
        score_decreases = []
        
        for result in results:
            # Generate a random score decrease between 0.1 and 0.2 for this specific result
            score_decrease_value = round(random.uniform(0.05, 0.1), 2)
            score_decreases.append(score_decrease_value)
            
            # Update this specific result by subtracting the score_decrease_value
            update_result = await db.tender_analysis_results.update_one(
                {"_id": result["_id"]},
                {"$inc": {"tender_score": -score_decrease_value}} # Use negative value for subtraction
            )
            
            if update_result.modified_count > 0:
                updated_count += 1
                logger.info(f"Decreased score for result {result['_id']} by {score_decrease_value}")
        
        # Calculate average decrease if any results were updated
        avg_decrease = round(sum(score_decreases) / len(score_decreases), 2) if score_decreases else 0
        
        logger.info(f"Update complete: found={len(results)}, modified={updated_count}, avg_decrease={avg_decrease}")

        return {
            "message": f"Successfully decreased tender scores for {updated_count} results from 2025-05-06, with an average decrease of {avg_decrease}.",
            "analysis_id": str(analysis_id),
            "results_found": len(results),
            "results_modified": updated_count,
            "average_score_decrease": avg_decrease,
            "individual_decreases": len(score_decreases)
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error decreasing tender_score: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error decreasing tender_score: {str(e)}"
        )

@router.patch("/tender-analysis/{analysis_id}/fix-platforma-deadlines", response_model=Dict[str, Any])
async def fix_platforma_zakupowa_deadlines(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Corrects submission deadlines for Platforma Zakupowa results for a specific analysis.
    
    Changes dates like 'YYYY-07-DD HH:MM' to 'YYYY-05-DD HH:MM' 
    only if DD is 12 or less.
    """
    try:
        # 1. Verify analysis exists and user has access
        query = {"_id": analysis_id, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )

        # 2. Define the update pipeline
        pipeline = [
            {
                "$set": {
                    "tender_metadata.submission_deadline": {
                        "$let": {
                            "vars": {
                                "deadline": "$tender_metadata.submission_deadline",
                            },
                            "in": {
                                "$cond": {
                                    "if": {
                                        "$and": [
                                            # Check if it's a string of expected length
                                            {"$eq": [{"$type": "$$deadline"}, "string"]},
                                            {"$gte": [{"$strLenCP": "$$deadline"}, 16]},
                                            # Check if day is <= 12
                                            {"$lte": [{"$toInt": {"$substrCP": ["$$deadline", 8, 2]}}, 12]}
                                        ]
                                    },
                                    "then": {
                                        # Construct the new date string: YYYY-DD-MM HH:MM
                                        "$concat": [
                                            {"$substrCP": ["$$deadline", 0, 5]},  # YYYY-
                                            {"$substrCP": ["$$deadline", 8, 2]},  # DD (original day)
                                            "-",                                    # Separator
                                            {"$substrCP": ["$$deadline", 5, 2]},  # MM (original month)
                                            {"$substrCP": ["$$deadline", 10, 6]} # " HH:MM" (original time part)
                                        ]
                                    },
                                    "else": "$$deadline" # Keep original value
                                }
                            }
                        }
                    }
                }
            }
        ]

        # 3. Execute the update operation
        update_result = await db.tender_analysis_results.update_many(
            {
                "tender_analysis_id": analysis_id,
                "source_type": "platformazakupowa", # Filter by source type
                "tender_metadata.submission_deadline": {"$exists": True} # Ensure the field exists
            },
            pipeline
        )

        return {
            "message": "Deadline correction process completed for Platforma Zakupowa results.",
            "analysis_id": str(analysis_id),
            "documents_matched": update_result.matched_count, # How many platformazakupowa results were found
            "documents_modified": update_result.modified_count # How many had their deadline updated
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fixing Platforma Zakupowa deadlines: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fixing Platforma Zakupowa deadlines: {str(e)}"
        )
    
@router.delete("/tender-results/by-date/{initiation_date}", response_model=Dict[str, Any])
async def delete_tender_results_by_date(
    initiation_date: str = "2025-05-06",
    current_user: User = Depends(get_current_user)
):
    """
    Delete all tender analysis results with the specified initiation date.
    This includes cleaning up associated files and vector embeddings.
    """
    try:
        # Query to find all results with the target initiation date
        query = {"tender_metadata.initiation_date": initiation_date}
        
        # First count how many results will be affected
        total_count = await db.tender_analysis_results.count_documents(query)
        logger.info(f"Found {total_count} results with initiation date {initiation_date}")
        
        if total_count == 0:
            return {
                "message": f"No tender results found with initiation date {initiation_date}",
                "deleted": 0,
                "files_deleted": 0,
                "vectors_deleted": 0
            }
        
        # Get all matching results
        results = await db.tender_analysis_results.find(query).to_list(None)
        
        deleted_count = 0
        files_deleted_count = 0
        vector_namespaces_cleaned = 0
        vector_prefixes_cleaned = 0
        
        for result in results:
            result_id = result["_id"]
            logger.info(f"Processing result {result_id}")
            
            try:
                # 1. Delete files from Vercel Blob or S3
                s3_blob_urls_to_delete = []
                vercel_blob_urls_to_delete = []

                for file_doc in result.get("uploaded_files", []):
                    blob_url = file_doc.get("blob_url")
                    if blob_url:
                        if "s3.amazonaws.com" in blob_url:
                            s3_blob_urls_to_delete.append(blob_url)
                        elif "vercel.app" in blob_url:
                            vercel_blob_urls_to_delete.append(blob_url)
                        else:
                            logger.warning(f"Unknown blob_url format for result {result_id}, cannot delete: {blob_url}")
                
                if s3_blob_urls_to_delete:
                    try:
                        delete_files_from_s3(s3_blob_urls_to_delete)
                        files_deleted_count += len(s3_blob_urls_to_delete)
                        logger.info(f"Deleted {len(s3_blob_urls_to_delete)} files from S3 for result {result_id}")
                    except Exception as e:
                        logger.error(f"Error deleting files from S3 for result {result_id}: {str(e)}")

                if vercel_blob_urls_to_delete:
                    try:
                        delete_files_from_vercel_blob(vercel_blob_urls_to_delete)
                        files_deleted_count += len(vercel_blob_urls_to_delete)
                        logger.info(f"Deleted {len(vercel_blob_urls_to_delete)} files from Vercel Blob for result {result_id}")
                    except Exception as e:
                        logger.error(f"Error deleting files from Vercel Blob for result {result_id}: {str(e)}")
                
                # 2. Delete vectors from Pinecone
                # First check for the tender's overall namespace
                if result.get("pinecone_config"):
                    pinecone_config = result.get("pinecone_config")
                    if pinecone_config.get("namespace") != "":
                        try:
                            pinecone_query_tool = QueryTool(config=QueryConfig(
                                index_name=pinecone_config.get("index_name"),
                                namespace=pinecone_config.get("namespace"),
                                embedding_model=pinecone_config.get("embedding_model")
                            ))
                            pinecone_query_tool.delete_namespace()
                            vector_namespaces_cleaned += 1
                            logger.info(f"Deleted namespace for result {result_id}")
                        except Exception as e:
                            logger.error(f"Error deleting namespace for result {result_id}: {str(e)}")
                
                # Then check for individual file vector prefixes
                file_pinecone_configs = [
                    file.get("file_pinecone_config")
                    for file in result.get("uploaded_files", [])
                    if file.get("file_pinecone_config")
                ]
                
                for config in file_pinecone_configs:
                    if config.get("pinecone_unique_id_prefix"):
                        try:
                            pinecone_query_tool = QueryTool(config=QueryConfig(
                                index_name=config.get("query_config", {}).get("index_name"),
                                namespace=config.get("query_config", {}).get("namespace", ""),
                                embedding_model=config.get("query_config", {}).get("embedding_model")
                            ))
                            pinecone_query_tool.delete_from_pinecone_by_id_prefix(config.get("pinecone_unique_id_prefix"))
                            vector_prefixes_cleaned += 1
                            logger.info(f"Deleted vectors with prefix for result {result_id}")
                        except Exception as e:
                            logger.error(f"Error deleting vectors with prefix for result {result_id}: {str(e)}")
                
                # 3. Delete the document from MongoDB
                await db.tender_analysis_results.delete_one({"_id": result_id})
                deleted_count += 1
                logger.info(f"Deleted result document {result_id}")
                
            except Exception as e:
                logger.error(f"Error processing result {result_id}: {str(e)}")
        
        summary = {
            "message": f"Successfully deleted tender results with initiation date {initiation_date}",
            "date": initiation_date,
            "total_found": total_count,
            "deleted": deleted_count,
            "files_deleted": files_deleted_count,
            "vector_namespaces_cleaned": vector_namespaces_cleaned,
            "vector_prefixes_cleaned": vector_prefixes_cleaned
        }
        
        logger.info(f"Deletion summary: {summary}")
        return summary

    except Exception as e:
        logger.error(f"Error deleting tender results by date: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error deleting tender results: {str(e)}"
        )
    
@router.get("/tender-analysis/{analysis_id}/summary-results", response_model=List[TenderAnalysisResultSummary])
async def get_tender_analysis_summary_results(
    analysis_id: str,  # Changed from PyObjectId to str
    current_user: User = Depends(get_current_user)
):
    """Get summarized results (name, org, description) for a specific tender analysis"""
    try:
        # Convert string analysis_id to ObjectId for database query
        try:
            analysis_oid = ObjectId(analysis_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid analysis_id format")

        # 1. Check if analysis exists and belongs to user/org
        query = {"_id": analysis_oid, "$or": [{"user_id": current_user.id}]}
        if current_user.org_id and current_user.org_id.strip():
            query["$or"].append({"org_id": current_user.org_id})
            
        analysis = await db.tender_analysis.find_one(query)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
            
        # 2. Define projection to fetch only necessary fields
        projection = {
            "_id": 1,
            "tender_metadata.name": 1,
            "tender_metadata.organization": 1,
            "tender_description": 1
        }
        
        # 3. Fetch results with projection
        results_cursor = db.tender_analysis_results.find(
            {"tender_analysis_id": analysis_oid},  # Use analysis_oid here
            projection
        ).sort("created_at", -1) # Optional: Sort by creation date
        
        raw_results = await results_cursor.to_list(None)

        # 4. Manually map to the response model (handling potential nesting)
        summary_results = []
        for res in raw_results:
            summary_data = {
                "_id": res.get("_id"),
                "tender_metadata.name": res.get("tender_metadata", {}).get("name"),
                "tender_metadata.organization": res.get("tender_metadata", {}).get("organization"),
                "tender_description": res.get("tender_description")
            }
            # Filter out None values before creating the model instance
            filtered_data = {k: v for k, v in summary_data.items() if v is not None}
            if "_id" in filtered_data: # Ensure ID is always present
                summary_results.append(TenderAnalysisResultSummary(**filtered_data))
            else:
                 logger.warning(f"Skipping result due to missing _id: {res}")


        return summary_results

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting summary tender results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting summary tender results: {str(e)}"
        )


@router.patch("/tender-results/{result_id}/edit-criteria/{criteria}")
async def update_criteria_analysis(
    result_id: str, 
    criteria: str, 
    update_data: CriteriaAnalysisUpdate
):
    result_doc = await db.tender_analysis_results.find_one({"_id": ObjectId(result_id)})
    if not result_doc:
        raise HTTPException(status_code=404, detail="TenderAnalysisResult not found")
    
    criteria_list = result_doc.get("criteria_analysis", [])
    archive_list = result_doc.get("criteria_analysis_archive", [])
    
    if not result_doc.get("criteria_analysis_edited", False):
        archive_list = [crit.copy() for crit in criteria_list]

    found = False
    for idx, crit in enumerate(criteria_list):
        if crit.get("criteria") == criteria:
            current_analysis = crit.get("analysis", {})
            updated_analysis = {**current_analysis, **update_data.dict(exclude_unset=True)}
            criteria_list[idx]["analysis"] = updated_analysis
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Criteria '{criteria}' not found")
    
    await db.tender_analysis_results.update_one(
        {"_id": ObjectId(result_id)},
        {"$set": {
            "criteria_analysis": criteria_list,
            "criteria_analysis_archive": archive_list,
            "criteria_analysis_edited": True
        }}
    )
    
    return {"message": "Criteria analysis updated successfully"}
    
    