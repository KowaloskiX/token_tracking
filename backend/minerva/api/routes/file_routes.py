# file_routes.py
from datetime import datetime
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import List, Optional
from minerva.core.helpers.s3_upload import (
    upload_file_to_s3,
    delete_file_from_s3
)
from minerva.core.models.file import File as FileModel
from fastapi import APIRouter, HTTPException, UploadFile, Form, File
from bson import ObjectId
from minerva.core.database.database import db
from minerva.core.models.folder import Folder
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.utils.pdf_ocr import maybe_ocr_pdf
from minerva.tasks.services.analyze_tender_files import RAGManager
from openai import OpenAI
import pandas as pd
from pydantic import BaseModel
from fastapi.responses import Response
import httpx
from urllib.parse import unquote
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService

openai = OpenAI()
router = APIRouter()

@router.post("/", response_model=FileModel)
async def create_file(
    file: UploadFile,
    owner_id: str = Form(...),
    parent_folder_id: str = Form(None),
    file_type: str = Form(None),
    assistant_id: str = Form(None)
):
    try:
        # Ensure filename is not None
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        
        # Read file content once and reuse it
        file_bytes_content = await file.read()

        # Upload to S3
        try:
            s3_url = upload_file_to_s3(file.filename, file_bytes_content)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to S3: {str(e)}"
            )

        # Attach file to your vector store if you have an assistant_id
        file_pinecone_config = None
        file_preview_chars = None
        if assistant_id:
            assistant = await db["assistants"].find_one({"_id": ObjectId(assistant_id)})
            if assistant:
                if assistant.get('pinecone_config', None):
                    uploaded_files_pinecone_id = assistant.get('uploaded_files_pinecone_id', None)
                    pinecone_config_dict = assistant.get('pinecone_config', None)
                    
                    rag_manager = RAGManager(
                        index_name=pinecone_config_dict['index_name'],
                        namespace=pinecone_config_dict['namespace'],
                        embedding_model=pinecone_config_dict['embedding_model'],
                        tender_pinecone_id=uploaded_files_pinecone_id,
                        use_elasticsearch=pinecone_config_dict.get('use_elasticsearch', False),
                        es_config=pinecone_config_dict.get('es_config', None),
                        language=pinecone_config_dict.get('language', None)
                    )
                    
                    if pinecone_config_dict.get('use_elasticsearch', False):
                        await rag_manager.ensure_elasticsearch_index_initialized()
                    
                    # --- Extract text content using the same extraction pipeline utilised across the codebase ---
                    # Reuse the file_bytes_content we already read

                    # Write the uploaded bytes to a temporary file so that our extraction
                    # service can process it just like in tender extraction flows.
                    # Safely get file suffix, defaulting to empty string if no extension
                    file_suffix = Path(file.filename).suffix if file.filename else ""
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
                        tmp_file.write(file_bytes_content)
                        tmp_file.flush()
                        temp_path = Path(tmp_file.name)

                    extraction_service = FileExtractionService()

                    try:
                        # Async wrapper so we don't block the event loop
                        extracted_results = await extraction_service.process_file_async(temp_path)

                        # Fall back to raw UTF-8 decode if extractors returned nothing
                        if not extracted_results:
                            extracted_results = [(file_bytes_content, file.filename, "", file_bytes_content, file.filename)]

                        # Upload each extracted chunk to Pinecone, keeping the config from the first
                        file_pinecone_config = None
                        file_preview_chars = None
                        for i, (extracted_bytes, extracted_filename, _preview, _orig_bytes, _orig_name) in enumerate(extracted_results):
                            cfg = await rag_manager.upload_file_content(extracted_bytes, extracted_filename)
                            if file_pinecone_config is None:
                                file_pinecone_config = cfg
                            if file_preview_chars is None:
                                file_preview_chars = _preview  # Use preview from first extraction result
                    finally:
                        # Clean up temp file
                        try:
                            os.remove(temp_path)
                        except Exception as cleanup_error:
                            pass
                    
                    rag_manager.clean_up()

        # If no assistant_id or no vector processing, still extract preview for file metadata
        if file_preview_chars is None:
            file_suffix = Path(file.filename).suffix if file.filename else ""
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
                tmp_file.write(file_bytes_content)
                tmp_file.flush()
                temp_path = Path(tmp_file.name)

            extraction_service = FileExtractionService()

            try:
                # Extract just for preview, don't process for vector store
                extracted_results = await extraction_service.process_file_async(temp_path)
                if extracted_results:
                    # Use preview from first extraction result
                    _, _, file_preview_chars, _, _ = extracted_results[0]
            finally:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except Exception as cleanup_error:
                    pass

        # Create a FileModel record in your database
        file_model = FileModel(
            filename=file.filename,
            bytes=len(file_bytes_content),  # Use the actual file content length
            owner_id=owner_id,
            parent_folder_id=parent_folder_id,
            blob_url=s3_url,
            type=file_type,
            file_pinecone_config=file_pinecone_config,
            preview_chars=file_preview_chars,  # Add the preview from extraction
            user_file=True,
            shared_with=[]  # Initialize empty shared_with list
        )

        # Insert into MongoDB
        result = await db["files"].insert_one(file_model.dict(by_alias=True))
        
        # If there's a parent folder, link the file to that folder
        if parent_folder_id:
            await db["folders"].update_one(
                {"_id": ObjectId(parent_folder_id)},
                {"$push": {"files": str(result.inserted_id)}}
            )
        
        created_file = await db["files"].find_one({"_id": result.inserted_id})
        return FileModel(**created_file)

    except Exception as e:
        print(f"Error creating file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating file: {str(e)}"
        )

@router.get("/{file_id}", response_model=FileModel)
async def get_file(file_id: str):
    file = await db["files"].find_one({"_id": ObjectId(file_id)})
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileModel(**file)


@router.get("/by-filename/{filename}", response_model=FileModel)
async def get_file_by_filename(filename: str):
    """Find a file by its filename."""
    try:
        # URL-decode the filename
        decoded_filename = unquote(filename)
        
        # First try exact match
        file = await db["files"].find_one({"filename": decoded_filename})
        
        # If not found, try a partial match
        if not file:
            # Use a regex to find filenames containing the provided string
            file = await db["files"].find_one({"filename": {"$regex": f".*{decoded_filename}.*", "$options": "i"}})
        
        if not file:
            raise HTTPException(status_code=404, detail=f"File with name '{decoded_filename}' not found")
        
        return FileModel(**file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding file: {str(e)}")

@router.get("/by-single-id/{file_id}", response_model=FileModel)
async def get_file_by_single_id(file_id: str):
    # First try to find the file by openai_file_id
    file = await db["files"].find_one({"openai_file_id": file_id})
    
    # If not found, try looking up by MongoDB _id
    if not file:
        try:
            file = await db["files"].find_one({"_id": ObjectId(file_id)})
            print(file)
        except:
            # If ObjectId conversion fails, it's not a valid MongoDB id
            pass
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileModel(**file)

@router.put("/{file_id}", response_model=FileModel)
async def update_file(file_id: str, file_update: dict):
    result = await db["files"].update_one(
        {"_id": ObjectId(file_id)},
        {"$set": file_update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="File not found")
    updated_file = await db["files"].find_one({"_id": ObjectId(file_id)})
    return FileModel(**updated_file)

@router.delete("/{file_id}")
async def delete_file(file_id: str):
    file = await db["files"].find_one({"_id": ObjectId(file_id)})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file.get("user_file", False):
        raise HTTPException(status_code=500, detail="Not User File cannot be")
    if file["openai_file_id"]:
        openai.files.delete(file["openai_file_id"])

    if file['blob_url']:
        delete_file_from_s3(file['blob_url'])

    if file['file_pinecone_config']:
        index_name =  file['file_pinecone_config']['query_config']['index_name']
        namespace =  file['file_pinecone_config']['query_config']['namespace']
        embedding_model = file['file_pinecone_config']['query_config']['embedding_model']
        pinecone_unique_id_prefix = file['file_pinecone_config']['pinecone_unique_id_prefix']

        query_tool = QueryTool(QueryConfig(index_name=index_name, namespace=namespace, embedding_model=embedding_model))

        query_tool.delete_from_pinecone_by_id_prefix(pinecone_unique_id_prefix)

    if file.get("parent_folder_id"):
        await db["folders"].update_one(
            {"_id": ObjectId(file["parent_folder_id"])},
            {"$pull": {"files": file_id}}
        )
    
    result = await db["files"].delete_one({"_id": ObjectId(file_id)})
    return {"message": "File deleted"}

@router.get("/", response_model=List[FileModel])
async def get_all_files():
    files = await db["files"].find().to_list(length=None)
    return [FileModel(**file) for file in files]

@router.get("/folder/{folder_id}/files", response_model=List[FileModel])
async def get_files_in_folder(folder_id: str):
    files = await db["files"].find({"parent_folder_id": folder_id}).to_list(length=None)
    return [FileModel(**file) for file in files]

@router.patch("/{file_id}/rename", response_model=FileModel)
async def rename_file(file_id: str, new_name: str):
    """Rename a file"""
    file = await db["files"].find_one({"_id": ObjectId(file_id)})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update filename
    result = await db["files"].update_one(
        {"_id": ObjectId(file_id)},
        {"$set": {"filename": new_name}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="File rename failed")
        
    updated_file = await db["files"].find_one({"_id": ObjectId(file_id)})
    return FileModel(**updated_file)


@router.post("/excel-upload")
async def transform_excel_to_txt(file: UploadFile = File(...)):
    """
    Endpoint to transform an Excel file (xls or xlsx) with multiple sheets into separate text files.
    Returns a list of generated text files, one for each worksheet.
    """
    # Ensure filename is not None and is Excel format
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")
    
    if not (file.filename.endswith('.xls') or file.filename.endswith('.xlsx')):
        raise HTTPException(status_code=400, detail="File must be an .xls or .xlsx Excel file")
    
    try:
        # Read the Excel file
        content = await file.read()
        
        # Create output directory if it doesn't exist
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Read all sheets from the Excel file
        excel_file = pd.ExcelFile(io.BytesIO(content))
        sheet_names = excel_file.sheet_names
        
        output_files = []
        
        # Process each sheet
        for sheet_name in sheet_names:
            # Read the specific sheet
            excel_data = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name)
            
            # Replace `nan` values with `-` or empty string
            excel_data = excel_data.fillna("-")  # Use "" instead of "-" if you prefer empty strings
            
            # Convert the Excel data into a readable text format
            readable_text = excel_data.to_markdown(index=False)
            
            # Create a safe filename from the sheet name
            safe_sheet_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in sheet_name)
            output_file = output_dir / f"{safe_sheet_name}.txt"
            
            # Save the result as a .txt file
            with open(output_file, "w", encoding='utf-8') as txt_file:
                txt_file.write(f"Sheet: {sheet_name}\n")
                txt_file.write("="*50 + "\n\n")
                txt_file.write(readable_text)
            
            output_files.append(str(output_file))
        
        return {
            "message": "Files transformed successfully!",
            "sheet_count": len(sheet_names),
            "sheets_processed": sheet_names,
            "output_files": output_files
        }
    
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="The Excel file appears to be empty")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    


class ExcelUploadResponse(BaseModel):
    message: str
    created_files: List[FileModel]

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }

@router.post("/excel-upload-json", response_model=ExcelUploadResponse)
async def transform_excel_to_json(
    file: UploadFile = File(...),
    owner_id: str = Form(...),
    parent_folder_id: str = Form(None),
    file_type: str = Form(None),
    assistant_id: str = Form(None)
):
    """
    Endpoint to transform an Excel file (xls or xlsx) with multiple sheets into JSON files.
    Each sheet is converted to a JSON file and uploaded to OpenAI.
    """
    # Ensure filename is not None and is Excel format
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")
    
    if not (file.filename.endswith('.xls') or file.filename.endswith('.xlsx')):
        raise HTTPException(status_code=400, detail="File must be an .xls or .xlsx Excel file")
    
    try:
        content = await file.read()
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        excel_file = pd.ExcelFile(io.BytesIO(content))
        sheet_names = excel_file.sheet_names
        created_files = []
        
        for sheet_name in sheet_names:
            # Process Excel sheet to JSON
            excel_data = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name)
            
            # Convert column headers to strings to avoid datetime keys
            excel_data.columns = [str(col) for col in excel_data.columns]
            
            # Convert datetime columns to string format
            for column in excel_data.select_dtypes(include=['datetime64[ns]']).columns:
                excel_data[column] = excel_data[column].dt.strftime('%Y-%m-%dT%H:%M:%S')
            
            sheet_data = excel_data.replace({pd.NA: None}).to_dict(orient='records')
            
            # Create JSON file
            safe_sheet_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in sheet_name)
            output_file = output_dir / f"{safe_sheet_name}.json"
            
            with open(output_file, "w", encoding='utf-8') as json_file:
                json.dump(
                    {"data": sheet_data}, 
                    json_file, 
                    indent=2,
                    ensure_ascii=False
                )
            
            # Create file model and upload to OpenAI
            with open(output_file, "rb") as json_file:
                file_content = json_file.read()
                in_memory_file = io.BytesIO(file_content)
                in_memory_file.name = f"{safe_sheet_name}.json"

                openai_file = openai.files.create(
                    file=in_memory_file,
                    purpose="assistants"
                )

                if assistant_id:
                    assistant = await db["assistants"].find_one({"_id": ObjectId(assistant_id)})
                    if assistant and assistant.get("openai_vectorstore_id"):
                        openai.vector_stores.files.create(
                            vector_store_id=assistant["openai_vectorstore_id"],
                            file_id=openai_file.id
                        )

                # Prepare FileModel instance
                file_model = FileModel(
                    filename=f"{safe_sheet_name}_{file.filename}",
                    bytes=os.path.getsize(output_file),
                    owner_id=owner_id,
                    parent_folder_id=parent_folder_id,
                    openai_file_id=openai_file.id,
                    type="xls",
                    shared_with=[],
                    user_file=True
                )
                
                # Insert into database
                result = await db["files"].insert_one(file_model.dict(by_alias=True))
                
                # Fetch the inserted document
                created_doc = await db["files"].find_one({"_id": result.inserted_id})
                if created_doc:
                    # Let Pydantic handle ObjectId fields via PyObjectId
                    created_files.append(FileModel(**created_doc))
        
        return ExcelUploadResponse(
            message="Files transformed successfully!",
            created_files=created_files
        )
    
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="The Excel file appears to be empty")
    except Exception as e:
        print(f"Error processing Excel file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating file: {str(e)}"
        )
    

class FileOpenAIRequest(BaseModel):
    filename: str
    openai_file_id: Optional[str] = None
    blob_url: Optional[str] = None
    type: Optional[str] = None
    bytes: Optional[int] = None

class BatchFileCreateRequest(BaseModel):
    files: List[FileOpenAIRequest]
    owner_id: str
    assistant_id: Optional[str] = None
    parent_folder_id: Optional[str] = None

@router.post("/upload-existing-openai-files", response_model=List[FileModel])
async def create_files_with_openai_id(request: BatchFileCreateRequest):
    try:
        created_files = []
        default_folder = None

        # Get assistant and create default folder if needed
        if request.assistant_id:
            assistant = await db["assistants"].find_one({"_id": ObjectId(request.assistant_id)})
            if not assistant:
                raise HTTPException(status_code=404, detail="Assistant not found")
            
            default_folder = await get_or_create_default_folder(
                owner_id=request.owner_id,
                assistant_id=request.assistant_id
            )

        folder_id = request.parent_folder_id or (default_folder.id if default_folder else None)

        # Process files in batches to handle potential failures
        for file_data in request.files:
            try:
                # Try to add to vector store if assistant exists
                vector_store_success = True
                if file_data.openai_file_id:
                    if assistant and assistant.get("openai_vectorstore_id"):
                        try:
                            vector_store_success = await add_to_vector_store(
                                vector_store_id=assistant["openai_vectorstore_id"],
                                file_id=file_data.openai_file_id
                            )
                        except Exception as e:
                            # Log the error but continue processing the file
                            print(f"Vector store error for file {file_data.filename}: {str(e)}")
                            vector_store_success = False
                else:
                    vector_store_success = False
                
                # Create file record even if vector store operation failed
                file_model = await create_file_record(
                    file_data=file_data,
                    owner_id=request.owner_id,
                    folder_id=folder_id,
                )
                
                created_files.append(file_model)

            except Exception as e:
                print(f"Error processing file {file_data.filename}: {str(e)}")
                # Continue processing other files instead of failing completely
                continue

        if created_files:
            return created_files
        else:
            raise HTTPException(
                status_code=500,
                detail="No files were successfully processed"
            )

    except Exception as e:
        print(f"Error in file upload handler: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )

async def get_or_create_default_folder(owner_id: str, assistant_id: str) -> Folder:
    """Get or create the default 'Home' folder for an assistant."""
    existing_folder = await db["folders"].find_one({
        "owner_id": owner_id,
        "assistant_id": assistant_id,
        "name": "Home",
        "parent_folder_id": None
    })
    
    if existing_folder:
        return Folder(**existing_folder)
    
    default_folder = Folder(
        name="Home",
        description="Default home folder",
        owner_id=owner_id,
        assistant_id=assistant_id,
        parent_folder_id=None,
        files=[],
        subfolders=[]
    )
    
    result = await db["folders"].insert_one(default_folder.dict(by_alias=True))
    created_folder = await db["folders"].find_one({"_id": result.inserted_id})
    return Folder(**created_folder)

async def add_to_vector_store(vector_store_id: str, file_id: str) -> bool:
    """Add a file to the OpenAI vector store.
    Returns True if successful, False if failed."""
    try:
        response = openai.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        return True
    except Exception as e:
        if "404" in str(e):
            print(f"File {file_id} not found in vector store {vector_store_id}")
        else:
            print(f"Error adding file to vector store: {str(e)}")
        return False

async def create_file_record(
    file_data, 
    owner_id: str, 
    folder_id: str = None,
) -> FileModel:
    """Create a file record in the database."""
    # Safely determine file type
    file_type = file_data.type
    if not file_type and file_data.filename:
        if '.' in file_data.filename:
            file_type = file_data.filename.split('.')[-1].lower()
        else:
            file_type = 'unknown'
    elif not file_type:
        file_type = 'unknown'
    
    file_model = FileModel(
        filename=file_data.filename,
        bytes=file_data.bytes,
        owner_id=owner_id,
        blob_url=file_data.blob_url,
        parent_folder_id=str(folder_id) if folder_id else None,
        openai_file_id=file_data.openai_file_id,
        type=file_type,
        shared_with=[],
        user_file=True
    )
    
    result = await db["files"].insert_one(file_model.dict(by_alias=True))
    
    if folder_id:
        await db["folders"].update_one(
            {"_id": folder_id},
            {"$push": {"files": str(result.inserted_id)}}
        )
    
    created_file = await db["files"].find_one({"_id": result.inserted_id})
    return FileModel(**created_file)




@router.post("/convert-to-pdf")
async def convert_docx(file: UploadFile):
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Determine file extension from uploaded file
        original_filename = file.filename or "input"
        file_ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "docx"
        input_path = Path(temp_dir) / f"input.{file_ext}"
        output_path = Path(temp_dir) / "output.pdf"
        
        # Write uploaded file to disk
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        try:
            # Use LibreOffice to convert
            cmd = [
                'soffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', temp_dir,
                str(input_path)
            ]
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=30
            )
            
            if process.returncode != 0:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Conversion failed: {process.stderr.decode()}"
                )
            
            # Read the PDF file (LibreOffice names it based on input)
            pdf_path = Path(temp_dir) / f"input.pdf"
            if not pdf_path.exists():
                raise HTTPException(status_code=500, detail="PDF file not created")
                
            with open(pdf_path, "rb") as pdf_file:
                pdf_content = pdf_file.read()
            
            # Return PDF
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=converted.pdf"}
            )
            
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=500, detail="Conversion timeout")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")
        


@router.post("/enrich-files", response_model=List[FileModel])
async def enrich_files(
    request: BatchFileCreateRequest
):
    try:
        enriched_files = []
        assistant = None
        default_folder = None

        if request.assistant_id:
            assistant = await db["assistants"].find_one({"_id": ObjectId(request.assistant_id)})
            if not assistant:
                raise HTTPException(status_code=404, detail="Assistant not found")
            default_folder = await get_or_create_default_folder(
                owner_id=request.owner_id,
                assistant_id=request.assistant_id
            )

        folder_id = request.parent_folder_id or (default_folder.id if default_folder else None)

        # Collect all file IDs to attach to the vector store
        file_ids_to_attach = []

        for file_data in request.files:
            if file_data.openai_file_id and file_data.openai_file_id.strip():
                # File already has openai_file_id, just create the record
                file_model = await create_file_record(
                    file_data=file_data,
                    owner_id=request.owner_id,
                    folder_id=folder_id,
                )
                enriched_files.append(file_model)
                file_ids_to_attach.append(file_data.openai_file_id)
            elif file_data.blob_url:
                # Fetch file from Vercel Blob Storage
                async with httpx.AsyncClient() as client:
                    response = await client.get(file_data.blob_url)
                    if response.status_code != 200:
                        print(f"Failed to fetch {file_data.blob_url}: {response.status_code}")
                        continue
                    file_content = response.content

                # Upload to OpenAI
                in_memory_file = io.BytesIO(file_content)
                in_memory_file.name = file_data.filename
                openai_file = openai.files.create(
                    file=in_memory_file,
                    purpose="assistants"
                )

                # Update file_data with new openai_file_id
                file_data.openai_file_id = openai_file.id
                file_data.bytes = len(file_content)

                # Create file record
                file_model = await create_file_record(
                    file_data=file_data,
                    owner_id=request.owner_id,
                    folder_id=folder_id,
                )
                enriched_files.append(file_model)
                file_ids_to_attach.append(openai_file.id)
            else:
                print(f"Skipping {file_data.filename}: no openai_file_id or blob_url")
                continue

        # Attach all files to the assistant's vector store if assistant exists
        if assistant and assistant.get("openai_vectorstore_id") and file_ids_to_attach:
            for file_id in file_ids_to_attach:
                try:
                    openai.vector_stores.files.create(
                        vector_store_id=assistant["openai_vectorstore_id"],
                        file_id=file_id
                    )
                except Exception as e:
                    print(f"Failed to attach file {file_id} to vector store: {str(e)}")
                    # Continue even if one fails, but log the error

        if not enriched_files:
            raise HTTPException(status_code=400, detail="No files processed successfully")
        return enriched_files

    except Exception as e:
        print(f"Error enriching files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error enriching files: {str(e)}")