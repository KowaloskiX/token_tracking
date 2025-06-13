from datetime import datetime
import logging
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.tasks.services.tender_description_generation_service import generate_tender_description
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

class TenderDescriptionRequest(BaseModel):
    tender_pinecone_id: str
    rag_index_name: str
    embedding_model: str
    analysis_id: Optional[str] = None
    save_results: Optional[bool] = False    
    language: Optional[str] = "polish"

class TenderDescriptionResponse(BaseModel):
    status: str
    description_id: Optional[str] = None
    tender_pinecone_id: str
    tender_description: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

@router.post("/tender-description", response_model=TenderDescriptionResponse)
async def generate_description(
    request: TenderDescriptionRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        description_result = await generate_tender_description(
            tender_pinecone_id=request.tender_pinecone_id,
            rag_index_name=request.rag_index_name,
            embedding_model=request.embedding_model,
            analysis_id=request.analysis_id,
            current_user=current_user,
            save_results=request.save_results,
            language=request.language
        )
        
        return description_result
        
    except Exception as e:
        logger.error(f"Error in description generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in description generation: {str(e)}"
        )


@router.get("/tender-description/{description_id}", response_model=TenderDescriptionResponse)
async def get_description_results(
    description_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        description_doc = await db.tender_description_generation_results.find_one({"_id": ObjectId(description_id)})
            
        if not description_doc:
            raise HTTPException(status_code=404, detail=f"Description results with ID {description_id} not found")
            
        return {
            "status": "success",
            "description_id": description_id,
            "tender_pinecone_id": description_doc.get("tender_pinecone_id"),
            "tender_description": description_doc.get("tender_description"),
            "created_at": description_doc.get("created_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving description results: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving description results: {str(e)}"
        )