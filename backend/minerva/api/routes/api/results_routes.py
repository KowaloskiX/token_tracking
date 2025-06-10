# backend/minerva/api/routes/api/results.py
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from bson import ObjectId

from minerva.core.middleware.auth.api_key import get_current_user_or_api_key
from minerva.core.models.user import User
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from minerva.core.database.database import db

router = APIRouter()
logger = logging.getLogger(__name__)

# Request/Response Models
class ResultsRequest(BaseModel):
    analysis_id: str
    date_from: Optional[str] = None  # YYYY-MM-DD format
    date_to: Optional[str] = None    # YYYY-MM-DD format
    status: Optional[str] = None     # active, inactive, archived
    limit: Optional[int] = Field(default=100, le=1000)
    offset: Optional[int] = Field(default=0, ge=0)
    include_historical: Optional[bool] = False

class BasicTenderResult(BaseModel):
    id: str = Field(alias="_id")
    tender_name: Optional[str] = None
    organization: Optional[str] = None
    tender_url: Optional[str] = None
    tender_score: Optional[float] = None
    status: Optional[str] = "active"
    submission_deadline: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ResultsResponse(BaseModel):
    results: List[BasicTenderResult]
    total: int
    has_more: bool

class CriteriaAnalysisResponse(BaseModel):
    result_id: str
    criteria_analysis: List[Dict[str, Any]]
    tender_score: Optional[float] = None
    created_at: Optional[datetime] = None

class FileInfo(BaseModel):
    filename: str
    blob_url: Optional[str] = None
    file_size: Optional[int] = None
    content_preview: Optional[str] = None

class FilesResponse(BaseModel):
    result_id: str
    files: List[FileInfo]
    total_files: int

async def check_analysis_access(analysis_id: str, current_user: User) -> bool:
    """Check if user has access to the analysis"""
    try:
        analysis_oid = ObjectId(analysis_id)
    except:
        return False
    
    # Check if user has access to this analysis
    query = {
        "_id": analysis_oid,
        "$or": [
            {"user_id": current_user.id},  # User is creator
            {"assigned_users": {"$in": [str(current_user.id)]}}  # User is assigned
        ]
    }
    
    # If user has org_id, also check org access
    if current_user.org_id and current_user.org_id.strip():
        query["$or"].append({"org_id": current_user.org_id})
    
    analysis = await db.tender_analysis.find_one(query)
    return analysis is not None

async def check_result_access(result_id: str, current_user: User) -> bool:
    """Check if user has access to the specific result"""
    try:
        result_oid = ObjectId(result_id)
    except:
        return False
    
    # First get the result to find its analysis_id
    result = await db.tender_analysis_results.find_one({"_id": result_oid})
    if not result:
        return False
    
    # Check access to the parent analysis
    analysis_id = str(result.get("tender_analysis_id"))
    return await check_analysis_access(analysis_id, current_user)

@router.post("/results", response_model=ResultsResponse)
async def get_results(
    request: ResultsRequest,
    current_user: User = Depends(get_current_user_or_api_key)
):
    """
    Fetch tender analysis results with basic information.
    Returns key information without heavy data like files or criteria.
    """
    try:
        # Check access to analysis
        if not await check_analysis_access(request.analysis_id, current_user):
            raise HTTPException(
                status_code=404,
                detail="Analysis not found or access denied"
            )
        
        # Build query
        query = {"tender_analysis_id": ObjectId(request.analysis_id)}
        
        # Add date filtering if provided
        if request.date_from or request.date_to:
            date_filter = {}
            if request.date_from:
                date_filter["$gte"] = request.date_from
            if request.date_to:
                date_filter["$lte"] = request.date_to
            query["tender_metadata.initiation_date"] = date_filter
        
        # Add status filtering
        if request.status:
            query["status"] = request.status
        elif not request.include_historical:
            # Default to active results unless explicitly requesting historical
            query["status"] = {"$ne": "archived"}
        
        # Get total count
        total = await db.tender_analysis_results.count_documents(query)
        
        # Build aggregation pipeline for projection and pagination
        pipeline = [
            {"$match": query},
            {
                "$project": {
                    "_id": 1,
                    "tender_name": "$tender_metadata.name",
                    "organization": "$tender_metadata.organization", 
                    "tender_url": 1,
                    "tender_score": 1,
                    "status": 1,
                    "submission_deadline": "$tender_metadata.submission_deadline",
                    "location": "$tender_metadata.location",
                    "created_at": 1,
                    "opened_at": 1
                }
            },
            {"$sort": {"created_at": -1}},
            {"$skip": request.offset},
            {"$limit": request.limit}
        ]
        
        # Execute aggregation
        raw_results = await db.tender_analysis_results.aggregate(pipeline).to_list(None)
        
        # Convert to response models
        results = []
        for result in raw_results:
            # Convert ObjectId to string
            if isinstance(result.get("_id"), ObjectId):
                result["_id"] = str(result["_id"])
            results.append(BasicTenderResult(**result))
        
        has_more = (request.offset + request.limit) < total
        
        return ResultsResponse(
            results=results,
            total=total,
            has_more=has_more
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching results: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching results: {str(e)}"
        )

@router.get("/results/{result_id}/criteria", response_model=CriteriaAnalysisResponse)
async def get_result_criteria(
    result_id: str,
    current_user: User = Depends(get_current_user_or_api_key)
):
    """
    Fetch criteria analysis for a specific tender analysis result.
    """
    try:
        # Check access to result
        if not await check_result_access(result_id, current_user):
            raise HTTPException(
                status_code=404,
                detail="Result not found or access denied"
            )
        
        # Fetch the result with criteria
        result = await db.tender_analysis_results.find_one(
            {"_id": ObjectId(result_id)},
            {
                "criteria_analysis": 1,
                "tender_score": 1,
                "created_at": 1
            }
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        
        return CriteriaAnalysisResponse(
            result_id=result_id,
            criteria_analysis=result.get("criteria_analysis", []),
            tender_score=result.get("tender_score"),
            created_at=result.get("created_at")
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching criteria for result {result_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching criteria: {str(e)}"
        )

@router.get("/results/{result_id}/files", response_model=FilesResponse)
async def get_result_files(
    result_id: str,
    include_preview: bool = Query(default=False, description="Include content preview"),
    current_user: User = Depends(get_current_user_or_api_key)
):
    """
    Fetch file information for a specific tender analysis result.
    """
    try:
        # Check access to result
        if not await check_result_access(result_id, current_user):
            raise HTTPException(
                status_code=404,
                detail="Result not found or access denied"
            )
        
        # Fetch the result with files - FIXED field names
        projection = {
            "uploaded_files.filename": 1,
            "uploaded_files.blob_url": 1,
            "uploaded_files.bytes": 1,  # CHANGED: Use 'bytes' instead of 'file_size'
        }
        
        if include_preview:
            projection["uploaded_files.preview_chars"] = 1
        
        result = await db.tender_analysis_results.find_one(
            {"_id": ObjectId(result_id)},
            projection
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        
        # Process files
        files = []
        uploaded_files = result.get("uploaded_files", [])
        
        for file_doc in uploaded_files:
            file_info = FileInfo(
                filename=file_doc.get("filename", ""),
                blob_url=file_doc.get("blob_url"),
                file_size=file_doc.get("bytes")  # CHANGED: Use 'bytes' field
            )
            
            if include_preview:
                preview_text = file_doc.get("preview_chars", "")
                if preview_text:
                    file_info.content_preview = preview_text[:500]
            
            files.append(file_info)
        
        return FilesResponse(
            result_id=result_id,
            files=files,
            total_files=len(files)
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching files for result {result_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching files: {str(e)}"
        )