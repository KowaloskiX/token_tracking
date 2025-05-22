from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis, TenderToAnalyseDescription
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.tasks.services.tender_description_filtering_service import perform_description_filtering
from pydantic import BaseModel
import json
from bson import json_util


router = APIRouter()
logger = logging.getLogger(__name__)

class TenderDescriptionFilterRequest(BaseModel):
    analysis_id: str
    tender_results: List[TenderToAnalyseDescription]
    ai_batch_size: Optional[int] = 20
    save_results: Optional[bool] = False

class TenderDescriptionFilterResponse(BaseModel):
    status: str
    description_filter_id: Optional[str] = None
    filtered_tenders: Optional[List[Union[Dict[str, Any], TenderToAnalyseDescription]]] = None
    filtered_out_tenders: Optional[List[Union[Dict[str, Any], TenderToAnalyseDescription]]] = None
    total_filtered: Optional[int] = None
    total_filtered_out: Optional[int] = None
    created_at: Optional[datetime] = None

@router.post("/tender-description-filter", response_model=TenderDescriptionFilterResponse)
async def filter_by_description(
    request: TenderDescriptionFilterRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Filter tenders based on their descriptions.
    """
    try:
        # Get tender analysis configuration
        tender_analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(request.analysis_id)})
        if not tender_analysis_doc:
            raise HTTPException(status_code=404, detail="Tender analysis configuration not found")
            
        tender_analysis = TenderAnalysis(**tender_analysis_doc)
        
        # Get tender results
        if not request.tender_results:
            raise HTTPException(status_code=400, detail="Tender results must be provided")
        
        # Perform description filtering
        filter_results = await perform_description_filtering(
            tender_analysis=tender_analysis,
            tender_results=request.tender_results,
            analysis_id=request.analysis_id,
            current_user=current_user,
            ai_batch_size=request.ai_batch_size,
            save_results=request.save_results
        )
        
        if filter_results["status"] == "error":
            raise HTTPException(status_code=400, detail=filter_results["reason"])
            
        return filter_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in description filtering: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in description filtering: {str(e)}"
        )


@router.get("/tender-description-filter/{description_filter_id}", response_model=TenderDescriptionFilterResponse)
async def get_description_filter_results(
    description_filter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve saved description filter results.
    """
    try:
        filter_doc = await db.tender_description_filter_results.find_one({"_id": ObjectId(description_filter_id)})
        if not filter_doc:
            raise HTTPException(status_code=404, detail=f"Description filter results with ID {description_filter_id} not found")

        class MongoJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, ObjectId):
                    return str(obj)
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
        
        # Manual conversion through JSON serialization with custom encoder
        serialized = json.dumps(filter_doc, cls=MongoJSONEncoder)
        filter_doc = json.loads(serialized)
        
        # Now construct the response with properly serialized data
        return TenderDescriptionFilterResponse(
            status="success",
            description_filter_id=description_filter_id,
            total_filtered=filter_doc.get("total_filtered", 0),
            total_filtered_out=filter_doc.get("total_filtered_out", 0),
            filtered_tenders=filter_doc.get("filtered_tenders", []),
            filtered_out_tenders=filter_doc.get("filtered_out_tenders", []),
            created_at=datetime.fromisoformat(filter_doc.get("created_at")) if filter_doc.get("created_at") else None
        )
        
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving description filter results: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving description filter results: {str(e)}"
        )