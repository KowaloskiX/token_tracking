# routes.py
from fastapi import APIRouter, HTTPException
from minerva.tasks.services.monitoring_service import get_updates_for_tenders
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging
from minerva.core.database.database import db
from bson import ObjectId
from datetime import datetime
from minerva.core.models.utils import PyObjectId
from minerva.core.models.file import File

router = APIRouter()

class UpdateRequest(BaseModel):
    date: str

class TenderUpdateResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    tender_analysis_result_id: PyObjectId
    updated_files: List[File]
    update_date: datetime
    update_link: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

@router.post("/tenders/updates", response_model=Dict[str, Any])
async def updates_endpoint(request: UpdateRequest) -> Dict[str, Any]:
    try:
        result = await get_updates_for_tenders(request.date)
        return {
            "status": result["status"],
            "updates": result["updates"]
        }
    except Exception as e:
        logging.error(f"Error running get_updates_for_tenders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tender updates: {str(e)}")

@router.get("/tender-updates/{update_id}", response_model=TenderUpdateResponse)
async def get_tender_update(update_id: str):
    try:
        if not ObjectId.is_valid(update_id):
            raise HTTPException(status_code=400, detail="Invalid update ID format")

        update = await db.tender_analysis_updates.find_one({"_id": ObjectId(update_id)})
        if update is None:
            raise HTTPException(status_code=404, detail="Update not found")

        return update
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error fetching tender update {update_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching the tender update.")
    
@router.get("/tenders/{tender_id}/updates", response_model=List[Dict[str, Any]])
async def get_tender_updates_summary(tender_id: str):
    try:
        if not ObjectId.is_valid(tender_id):
            raise HTTPException(status_code=400, detail="Invalid tender ID format")
        
        # Get updates for this specific tender
        updates_cursor = db.tender_analysis_updates.find({"tender_analysis_result_id": ObjectId(tender_id)})
        updates = await updates_cursor.to_list(length=None)
        
        if not updates:
            return []
        
        # Format and return the update summaries
        result = []
        for update in updates:
            result.append({
                "tender_id": str(update["tender_analysis_result_id"]),
                "update_id": str(update["_id"]),
                "files_uploaded": [f["filename"] for f in update.get("updated_files", [])],
                "file_summaries": update.get("file_summaries", []),
                "overall_summary": update.get("overall_summary", ""),
                "update_date": update.get("update_date", None)
            })
            
        # Sort by update date, newest first
        result.sort(key=lambda x: x.get("update_date", ""), reverse=True)
        return result
        
    except Exception as e:
        logging.error(f"Error fetching updates for tender {tender_id}: {str(e)}")
        raise HTTPException(status_code=500, 
                           detail=f"Failed to fetch updates for tender: {str(e)}")