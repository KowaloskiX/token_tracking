from datetime import datetime
import io
import logging
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis, TenderToAnalyseDescription
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig
from minerva.tasks.services.search_service import get_saved_search_results
from minerva.tasks.services.tender_description_filtering_service import perform_description_filtering
from minerva.tasks.services.tender_file_extraction_service import perform_file_extraction
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from pydantic import BaseModel
from playwright.async_api import async_playwright
from fastapi.responses import JSONResponse
from PIL import Image
import torch
from transformers import pipeline
from typing import Literal

router = APIRouter()
logger = logging.getLogger(__name__)

class TenderExtractionRequest(BaseModel):
    tender_id: Optional[str] = None
    search_id: Optional[str] = None
    tender: Optional[Dict[str, Any]] = None
    rag_index_name: str
    embedding_model: str
    analysis_id: Optional[str] = None
    save_results: Optional[bool] = False
    use_elasticsearch: Optional[bool] = False
    check_existing_analysis: Optional[bool] = False

class TenderExtractionResponse(BaseModel):
    status: str
    extraction_id: Optional[str] = None
    tender_id: Optional[str] = None
    tender_name: Optional[str] = None
    details_url: Optional[str] = None
    processed_files: Optional[Dict[str, Any]] = None
    tender_pinecone_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


@router.post("/tender-extraction", response_model=TenderExtractionResponse)
async def extract_tender_files(
    request: TenderExtractionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Extract files from a tender's details page.
    """
    try:
        # Get tender data
        if request.tender_id and request.search_id:
            # Get from saved search results
            search_results = await get_saved_search_results(request.search_id)
            if not search_results:
                raise HTTPException(status_code=404, detail=f"Search results with ID {request.search_id} not found")
                
            tender = None
            for match in search_results["all_tender_matches"]:
                if match["id"] == request.tender_id:
                    tender = match
                    break
                    
            if not tender:
                raise HTTPException(status_code=404, detail=f"Tender {request.tender_id} not found in search results")
                
        elif request.tender:
            # Use provided data
            tender = request.tender
        else:
            raise HTTPException(status_code=400, detail="Either search_id with tender_id or tender with combined_search_matches must be provided")
        
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)

        embedding_config = EmbeddingConfig(
            index_name=request.rag_index_name,
            namespace="",
            embedding_model=request.embedding_model
        )
        source_manager = TenderSourceManager(embedding_config)
                
        extraction_result = await perform_file_extraction(
            playwright_browser=browser,
            source_manager=source_manager,
            tender=tender,
            rag_index_name=request.rag_index_name,
            embedding_model=request.embedding_model,
            analysis_id=request.analysis_id,
            current_user=current_user,
            save_results=request.save_results,
            use_elasticsearch=request.use_elasticsearch,
            check_existing_analysis=request.check_existing_analysis
        )
        
        if extraction_result["status"] == "error":
            raise HTTPException(status_code=400, detail=extraction_result["reason"])
            
        return extraction_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in tender extraction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error in tender extraction: {str(e)}"
        )


@router.get("/tender-extraction/{extraction_id}", response_model=TenderExtractionResponse)
async def get_extraction_results(
    extraction_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve saved extraction results.
    """
    try:
        # Check if the ID is a valid ObjectId
        try:
            extraction_doc = await db.tender_extraction_results.find_one({"_id": ObjectId(extraction_id)})
        except:
            # If not a valid ObjectId, try as extraction_id field
            extraction_doc = await db.tender_extraction_results.find_one({"extraction_id": extraction_id})
            
        if not extraction_doc:
            raise HTTPException(status_code=404, detail=f"Extraction results with ID {extraction_id} not found")
            
        return {
            "status": "success",
            "extraction_id": extraction_id,
            "tender_id": extraction_doc.get("tender_id"),
            "tender_name": extraction_doc.get("tender_name"),
            "details_url": extraction_doc.get("details_url"),
            "processed_files": extraction_doc.get("processed_files"),
            "tender_pinecone_id": extraction_doc.get("tender_pinecone_id"),
            "created_at": extraction_doc.get("created_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving extraction results: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving extraction results: {str(e)}"
        )
    
@router.get("/test-ocr")
async def test_ocr():
    try:
        from minerva.core.services.vectorstore.file_content_extract.pdf_extractor import PDFFileExtractor
        from pathlib import Path
        
        results = []
        extractor = PDFFileExtractor()

        file_paths = [
            "/workspaces/minerva/backend/temp_downloads/przedmiar.pdf",
            "/workspaces/minerva/backend/temp_downloads/rzut.pdf"
        ]
        
        for file_path in file_paths:
            pdf_path = Path(file_path)
            
            if not pdf_path.exists():
                results.append({
                    "file_path": str(pdf_path),
                    "status": "error",
                    "error": "File not found"
                })
                continue
                
            try:
                extracted_text = extractor.extract_text_as_string(pdf_path)
                results.append({
                    "file_path": str(pdf_path),
                    "status": "success",
                    "extracted_text": extracted_text,
                    "text_length": len(extracted_text)
                })
            except Exception as e:
                results.append({
                    "file_path": str(pdf_path),
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "results": results,
            "total_files": len(file_paths),
            "successful_files": sum(1 for r in results if r["status"] == "success")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDFs: {str(e)}"
        )

# classifier = pipeline(
#     "zero-shot-image-classification",
#     model="openai/clip-vit-base-patch32",
#     device=-1,                         # -1 ➜ force CPU
# )

# CANDIDATES = [
#     "a technical drawing, blueprint or CAD schematic",
#     "a normal page of text or scanned document",
# ]



# @router.post("/classify-img")
# async def classify(file: UploadFile = File(...)):
#     logger.info(f"Received file: {file.filename} (content_type={file.content_type})")

#     if file.content_type not in {"image/png", "image/jpeg"}:
#         logger.warning("Unsupported file type")
#         raise HTTPException(415, "Upload PNG or JPEG only.")

#     try:
#         contents = await file.read()
#         logger.info(f"Read {len(contents)} bytes")
#         image = Image.open(io.BytesIO(contents)).convert("RGB")
#         logger.info("Image decoded successfully")
#     except Exception as e:
#         logger.error(f"Image decode error: {e}")
#         raise HTTPException(400, "Cannot decode the image file.")

#     logger.info("Running classification...")
#     outputs = classifier(image, candidate_labels=CANDIDATES)
#     logger.info(f"Model output: {outputs}")

#     top = outputs[0]
#     result: Literal["drawing", "document"] = (
#         "drawing" if "drawing" in top["label"] or "blueprint" in top["label"]
#         else "document"
#     )

#     logger.info(f"Final result: {result} (score: {top['score']:.4f})")
#     return JSONResponse({"result": result, "score": round(top["score"], 4)})