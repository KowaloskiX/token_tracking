from datetime import datetime
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from minerva.core.models.request.tender_extract import HistoricalExtractionRequest
from minerva.tasks.services.tender_insert_service import TenderInsertConfig

router = APIRouter()

class HistoricalDateQueryRequest(BaseModel):
    initiation_date: str
    embedding_model: Optional[str] = "text-embedding-3-large"
    top_k: Optional[int] = 1000
    score_threshold: Optional[float] = 0.0

class SearchRequest(BaseModel):
    query: str
    index_name: str
    top_k: Optional[int] = 20
    embedding_model: Optional[str]
    score_threshold: Optional[float] = 0.0

class PineconeIdRequest(BaseModel):
    pinecone_id: str
    embedding_model: Optional[str] = "text-embedding-3-large"

def _create_historical_service():
    """Helper function to create historical tender service with default config"""
    historical_config = TenderInsertConfig.create_default(
        pinecone_index="historical-tenders",
        pinecone_namespace="",
        embedding_model="text-embedding-3-large",
        elasticsearch_index="historical-tenders"
    )
    
    from minerva.tasks.services.historical_tender_service import HistoricalTenderService
    
    return HistoricalTenderService(config=historical_config)

@router.post("/fetch-and-embed-historical")
async def fetch_and_embed_historical_tenders(request: HistoricalExtractionRequest) -> Dict:
    try:
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Please use YYYY-MM-DD format."
            )

        historical_service = _create_historical_service()

        inputs = {
            'start_date': request.start_date,
            'end_date': request.end_date,
            'max_pages': request.max_pages
        }

        result = await historical_service.process_historical_tenders(inputs)
        
        metadata = result.get("metadata")
        if metadata:
            total_tenders = metadata.total_tenders if hasattr(metadata, 'total_tenders') else 0
            pages_scraped = metadata.pages_scraped if hasattr(metadata, 'pages_scraped') else 0
        else:
            total_tenders = 0
            pages_scraped = 0
        
        return {
            "result": result,
            "summary": {
                "historical_tenders_found": total_tenders,
                "pages_scraped": pages_scraped,
                "pinecone_processed": result.get("embedding_result", {}).get("processed_count", 0),
                "elasticsearch_processed": result.get("elasticsearch_result", {}).get("stored_count", 0),
                "date_range": f"{request.start_date} to {request.end_date}"
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting historical tenders: {str(e)}")

@router.post("/query-historical")
async def query_historical_multipart_tenders(search_request: SearchRequest):
    """
    Query historical tenders specifically filtering for multi-part tenders
    """
    try:
        historical_service = _create_historical_service()
        
        result = await historical_service.query_multipart_tenders(
            query=search_request.query,
            top_k=search_request.top_k,
            embedding_model=search_request.embedding_model,
            score_threshold=search_request.score_threshold
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying multi-part historical tenders: {str(e)}")
    

@router.post("/query-historical-by-initiation-date")
async def query_historical_by_initiation_date(
    request: HistoricalDateQueryRequest
):
    """
    Query all historical tenders with a given initiation_date.
    """
    try:
        historical_service = _create_historical_service()
        
        result = await historical_service.query_by_initiation_date(
            initiation_date=request.initiation_date,
            top_k=request.top_k,
            embedding_model=request.embedding_model,
            score_threshold=request.score_threshold
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying historical tenders by initiation_date: {str(e)}")

@router.post("/query-historical-by-initiation-date-and-update-finished-id")
async def query_historical_by_initiation_date_and_update_finished_id(
    request: HistoricalDateQueryRequest
):
    """
    Query all historical tenders with a given initiation_date, and for each result, find the corresponding
    tender_analysis_results in MongoDB by tender_url (matching original_tender_url), and set finished_id to Pinecone object id.
    """
    try:
        historical_service = _create_historical_service()
        
        result = await historical_service.query_by_initiation_date_and_update_finished_id(
            initiation_date=request.initiation_date,
            top_k=request.top_k,
            embedding_model=request.embedding_model,
            score_threshold=request.score_threshold
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying and updating historical tenders: {str(e)}"
        )

@router.post("/historical-tender-by-pinecone-id")
async def get_historical_tender_by_pinecone_id(request: PineconeIdRequest):
    """
    Return all data from Pinecone for a finished tender by its Pinecone id.
    """
    try:
        historical_service = _create_historical_service()
        
        result = await historical_service.get_by_pinecone_id(
            pinecone_id=request.pinecone_id,
            embedding_model=request.embedding_model
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tender from Pinecone: {str(e)}")