import os
import tempfile
from uuid import uuid4
from dotenv import load_dotenv
from minerva.api.routes.retrieval_routes import sanitize_id
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, EmbeddingTool
from minerva.core.services.vectorstore.text_chunks import ChunkingConfig, TextChunker
import pandas as pd
import io
from pathlib import Path
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from fastapi import UploadFile, HTTPException
from bson import ObjectId
from openai import OpenAI

load_dotenv()

openai = OpenAI()

async def handle_file_upload(
    file: UploadFile,
    owner_id: str,
    db: object,
    assistant_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Handles file upload for both regular files and Excel files.
    Returns a dictionary with OpenAI file ID and attachment configuration.
    """
    try:
        # Handle Excel files
        if file.filename.endswith(('.xls', '.xlsx')):
            return await handle_excel_upload(file, owner_id, db, assistant_id)
        
        # Handle regular files
        return await handle_regular_upload(file, owner_id, db, assistant_id)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling file upload: {str(e)}")

async def handle_regular_upload(
    file: UploadFile,
    owner_id: str,
    db: object,
    assistant_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Handles upload of regular files to OpenAI and creates database record.
    """
    try:
        content = await file.read()
        
        # Upload to OpenAI
        in_memory_file = io.BytesIO(content)
        in_memory_file.name = file.filename

        openai_file = openai.files.create(
            file=in_memory_file,
            purpose="assistants"
        )

        # Create database record
        file_data = {
            "filename": file.filename,
            "bytes": len(content),
            "owner_id": owner_id,
            "openai_file_id": openai_file.id,
            "type": file.filename.split('.')[-1],
            "shared_with": [],
            "created_at": datetime.utcnow()
        }
        
        await db["files"].insert_one(file_data)
        
        await file.seek(0)
        
        return {
            "file_id": openai_file.id,
            "tools": [{"type": "file_search"}]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

async def handle_excel_upload(
    file: UploadFile,
    owner_id: str,
    db: object,
    assistant_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Handles Excel file upload by converting to JSON and uploading to OpenAI.
    """
    try:
        content = await file.read()
        excel_file = pd.ExcelFile(io.BytesIO(content))
        all_sheets_data = []
        
        for sheet_name in excel_file.sheet_names:
            # Convert sheet to JSON
            excel_data = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name)
            
            # Convert column headers to strings to avoid datetime keys
            excel_data.columns = [str(col) for col in excel_data.columns]
            
            # Convert datetime columns to string format
            for column in excel_data.select_dtypes(include=['datetime64[ns]']).columns:
                excel_data[column] = excel_data[column].dt.strftime('%Y-%m-%dT%H:%M:%S')
            
            sheet_data = excel_data.replace({pd.NA: None}).to_dict(orient='records')
            all_sheets_data.append({
                "sheet_name": sheet_name,
                "data": sheet_data
            })
        
        # Convert all sheets to a single JSON file
        json_content = json.dumps(
            {"sheets": all_sheets_data},
            indent=2,
            ensure_ascii=False
        ).encode('utf-8')
        
        # Upload as a single file
        in_memory_file = io.BytesIO(json_content)
        in_memory_file.name = f"{file.filename.rsplit('.', 1)[0]}.json"

        openai_file = openai.files.create(
            file=in_memory_file,
            purpose="assistants"
        )

        # Create database record
        file_data = {
            "filename": in_memory_file.name,
            "bytes": len(json_content),
            "owner_id": owner_id,
            "openai_file_id": openai_file.id,
            "type": "xls",
            "shared_with": [],
            "created_at": datetime.utcnow()
        }
        
        await db["files"].insert_one(file_data)
        await file.seek(0)
        
        return {
            "file_id": openai_file.id,
            "tools": [{"type": "file_search"}]
        }

    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="The Excel file appears to be empty")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Excel file: {str(e)}")