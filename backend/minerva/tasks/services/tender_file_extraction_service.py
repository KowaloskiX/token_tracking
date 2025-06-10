import asyncio
from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from minerva.api.routes.retrieval_routes import sanitize_id
from minerva.core.helpers.s3_upload import upload_file_to_s3
from minerva.core.models.extensions.tenders.tender_analysis import FilterStage, FilteredTenderAnalysisResult, TenderAnalysis
from minerva.core.models.user import User
from minerva.tasks.services.analyze_tender_files import RAGManager
from minerva.core.database.database import db
from minerva.tasks.sources.source_types import TenderSourceType
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from playwright.async_api import Browser, BrowserContext
import psutil
import gc
import unicodedata
import re

logger = logging.getLogger("minerva.tasks.analysis_tasks")

# Memory logging helper
def log_mem(tag: str = ""):
    try:
        process_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        logger.info(f"[{tag}] Memory usage: {process_mem:.1f} MB")
    except Exception as mem_exc:
        logger.debug(f"Unable to log memory usage for tag '{tag}': {mem_exc}")

# Configurable max parallel file tasks (per tender)
MAX_PARALLEL_FILE_TASKS = int(os.getenv("MAX_PARALLEL_FILE_TASKS", "28"))

# Helper function to sanitize filenames

def safe_filename(filename: str) -> str:
    # Remove accents/diacritics, replace spaces with underscores, remove unsafe chars
    nfkd = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    # Replace sequences of non-alphanumeric (excluding ., _) with a single underscore
    safe_intermediate = re.sub(r'[^A-Za-z0-9._-]+', '_', only_ascii)
    # Remove leading/trailing underscores and ensure it's not empty
    safe = re.sub(r'^_+|_+$', '', safe_intermediate)
    if not safe: # if filename was all unsafe characters
        return "unsafe_filename_" + str(uuid4())[:8]
    return safe

# Helper function to get semaphore based on file size
def get_file_semaphore(size_bytes: Optional[int]) -> asyncio.Semaphore:
    if size_bytes and size_bytes > 10 * 1024 * 1024:  # If file > 10MB
        logger.info(f"Using reduced concurrency (1) for large file of size {size_bytes / 1024 / 1024:.2f} MB")
        return asyncio.Semaphore(1)
    return asyncio.Semaphore(MAX_PARALLEL_FILE_TASKS)

async def perform_file_extraction(
    playwright_browser: Browser,
    source_manager: TenderSourceManager,
    tender: Dict[str, Any],
    rag_index_name: str,
    embedding_model: str,
    analysis_id: str,
    current_user: Optional[User] = None,
    save_results: bool = False,
    check_existing_analysis: bool = False,
    use_elasticsearch: bool = False
) -> Dict[str, Any]:

    context: Optional[BrowserContext] = None
    rag_manager = None
    tender_id_str = tender.get('id', 'UNKNOWN_ID')
    
    try:
        # Memory log at start of extraction per tender
        log_mem(f"{tender_id_str} perform_file_extraction:start")
        if check_existing_analysis:
            existing_analysis = await db.tender_analysis_results.find_one({
                "tender_url": tender_id_str,
            })
            
            if existing_analysis:
                logger.info(f"[{tender_id_str}] Found existing analysis. Reusing file extraction results.")
                
                # Gather the necessary data from the existing analysis
                are_files_ready_to_reuse = True
                successful_files = []
                for file in existing_analysis.get("uploaded_files", []):
                    if file.get("file_pinecone_config").get("query_config").get("index_name") != rag_index_name:
                        logger.info(f"[{tender_id_str}] Skipping files reuse {file.get('filename')} because it is not in the correct pinecone index.")
                        are_files_ready_to_reuse = False
                        break

                    if use_elasticsearch:
                        if not file.get("file_pinecone_config").get("elasticsearch_indexed", False):
                            logger.info(f"[{tender_id_str}] Skipping files reuse {file.get('filename')} because it is not in elastic search index.")
                            are_files_ready_to_reuse = False
                            break
                        
                    successful_files.append({
                        "filename": file.get("filename"),
                        "type": file.get("type"),
                        "url": file.get("url"),
                        "blob_url": file.get("blob_url"),
                        "bytes": file.get("bytes"),
                        "owner_id": str(current_user.id) if current_user else "system",
                        "preview_chars": file.get("preview_chars"),
                        "file_pinecone_config": file.get("file_pinecone_config")
                    })
                
                if are_files_ready_to_reuse:
                    processed_files_summary = {
                        'successful_files': successful_files,
                        'total_processed': len(successful_files),
                        'successful_count': len(successful_files)
                    }
                    
                    result = {
                        "status": "success",
                        "tender_id": tender_id_str,
                        "tender_name": tender.get('name', ""),
                        "details_url": tender_id_str,
                        "processed_files": processed_files_summary,
                        "tender_pinecone_id": existing_analysis.get("tender_pinecone_id"),
                        "original_match": tender,
                        "reused_from_analysis": str(existing_analysis.get("_id"))
                    }
                    
                    # Save results if requested
                    if save_results:
                        extraction_doc = {
                            "analysis_id": analysis_id,
                            "tender_id": tender_id_str,
                            "tender_name": tender.get('name', ""),
                            "created_at": datetime.utcnow(),
                            "user_id": str(current_user.id) if current_user else None,
                            "details_url": tender_id_str,
                            "processed_files": processed_files_summary,
                            "tender_pinecone_id": existing_analysis.get("tender_pinecone_id"),
                            "reused_from_analysis": str(existing_analysis.get("_id"))
                        }
                        
                        db_result = await db.tender_extraction_results.insert_one(extraction_doc)
                        result["extraction_id"] = str(db_result.inserted_id)
                        logger.info(f"[{tender_id_str}] Saved reused extraction results with ID: {result['extraction_id']}")
                    
                    # Memory log after successful extraction and upload
                    log_mem(f"{tender_id_str} perform_file_extraction:end")
                    return result
        context = await playwright_browser.new_context()
        
        logger.info(f"[{tender_id_str}] Started file extraction process.")
        
            
        # Get details URL
        details_url = tender_id_str
        if not details_url or details_url == "UNKNOWN_ID":
            logger.warning(f"[{tender_id_str}] No details URL found.")
            return {"status": "error", "reason": "No details URL found", "tender_id": tender_id_str}
            
        # Initialize extractor
        source_type_str = tender.get("source_type", "")
        
        try:
            source_type = TenderSourceType(source_type_str)
            source_config = source_manager.source_configs.get(source_type)
            if not source_config:
                logger.error(f"[{tender_id_str}] No configuration found for source type: {source_type}")
                return {"status": "error", "reason": f"No configuration for source: {source_type}", "tender_id": tender_id_str}
                
            # Handle special case for ezamawiajacy
            if source_type == TenderSourceType.EZAMAWIAJACY:
                ez_extractor = (
                    source_config.extractor_class(**source_config.organization_config)
                    if source_config.organization_config
                    else source_config.extractor_class()
                )
                tender_extractor = ez_extractor
                
                # Handle login
                username = os.getenv("ONEPLACE_EMAIL")
                password = os.getenv("ONEPLACE_PASSWORD")
                if username and password:
                    login_page = await context.new_page()
                    try:
                        logger.info(f"[{tender_id_str}] Attempting login for source {source_type_str}")
                        await ez_extractor.login(login_page, username, password)
                        logger.info(f"[{tender_id_str}] Login successful.")
                        await login_page.close()
                    except Exception as login_err:
                        logger.warning(f"[{tender_id_str}] Login failed: {login_err}. Proceeding without login.")
                        await login_page.close()
                else:
                    logger.warning(f"[{tender_id_str}] Missing credentials for ezamawiajacy login.")
            else:
                tender_extractor = (
                    source_config.extractor_class(**source_config.organization_config)
                    if source_config.organization_config
                    else source_config.extractor_class()
                )
                
        except ValueError:
            logger.error(f"[{tender_id_str}] Unknown tender source type: {source_type_str}")
            return {"status": "error", "reason": f"Unknown source type: {source_type_str}", "tender_id": tender_id_str}
        except Exception as config_err:
            logger.error(f"[{tender_id_str}] Error configuring extractor: {config_err}")
            return {"status": "error", "reason": f"Error configuring extractor: {str(config_err)}", "tender_id": tender_id_str}
            
        if not tender_extractor:
            logger.error(f"[{tender_id_str}] Tender extractor not initialized.")
            return {"status": "error", "reason": "Extractor not initialized", "tender_id": tender_id_str}
            
        # Initialize RAG manager
        namespace = ""
        tender_name = tender.get('name', "")
        tender_pinecone_id = f"{sanitize_id(tender_name)}_{uuid4()}"
        rag_manager = RAGManager(rag_index_name, namespace, embedding_model, tender_pinecone_id, use_elasticsearch=use_elasticsearch, tender_url=tender_id_str)
        await rag_manager.ensure_elasticsearch_index_initialized()
        
        # Extract files
        logger.info(f"[{tender_id_str}] Starting file extraction from {details_url}")
        processed_files = await tender_extractor.extract_files_from_detail_page(
            context=context,
            details_url=details_url
        )
        # Memory log after files extracted (raw)
        log_mem(f"{tender_id_str} perform_file_extraction:after_file_download")
        
        if not processed_files:
            logger.warning(f"[{tender_id_str}] No files successfully processed.")
            filtered_tender = FilteredTenderAnalysisResult(
                            tender_id=tender_id_str,
                            tender_name=getattr(tender, 'name', ""),
                            organization=getattr(tender, 'organization', None),
                            location=getattr(tender, 'location', None),
                            analysis_id=str(analysis_id),
                            filter_stage=FilterStage.FILE_EXTRACTION,
                            filter_reason="No files successfully processed or error during processing",
                            search_phrase=getattr(tender, 'search_phrase', None),
                            source=getattr(tender, 'source', None),
                            details_url=details_url,
                            user_id=str(current_user.id) if current_user else None
                        )
            await db.filtered_tender_analysis_results.insert_one(filtered_tender.dict(by_alias=True))
            logger.warning(f"Saved filtered tender (no files) to database: {tender_id_str}")
            return {
                "status": "no_files",
                "reason": "No files successfully processed",
                "tender_id": tender_id_str,
                "details_url": details_url,
                "original_match": tender
            }
            
        # Process files
        # Semaphore will now be created per file inside process_one_file based on its size
        # file_semaphore = asyncio.Semaphore(MAX_PARALLEL_FILE_TASKS) # Removed global semaphore here

        async def process_one_file(file_tuple):
            file_content, filename, url, preview_chars, original_bytes = file_tuple
            
            # ------------------------------------------------------------
            # 1.  Skip uploading archives – we already extracted the files
            # ------------------------------------------------------------
            archive_exts = {".zip", ".7z", ".rar"}
            # Use os.path.splitext for robust extension checking
            if os.path.splitext(filename)[1].lower() in archive_exts:
                logger.info(
                    f"[{tender_id_str}] Skipping S3 upload for archive '{filename}' – "
                    "its contents are processed separately."
                )
                return None                       # Do not create an uploaded_files record
            # ------------------------------------------------------------
            
            # Calculate size now then release content asap
            bytes_len = len(original_bytes) if original_bytes else (len(file_content) if file_content else None)

            # Get semaphore based on file size
            file_semaphore = get_file_semaphore(bytes_len)

            async with file_semaphore:
                try:
                    # Embed & upsert
                    file_pinecone_config = await rag_manager.upload_file_content(file_content, filename)

                    # Release raw content
                    file_content = None
                    gc.collect()

                    # Determine file type
                    file_extension = os.path.splitext(filename)[1].lower()
                    file_type = "file" if file_extension else "website"

                    # Use original filename for blob storage to maintain consistency
                    logger.info(f"[{tender_id_str}] Uploading file '{filename}' ({bytes_len} bytes) to S3")
                    blob_url = upload_file_to_s3(filename, original_bytes)

                    # Build record
                    record = {
                        "filename": filename,  # Keep original filename
                        "type": file_type,
                        "url": url,
                        "blob_url": blob_url,
                        "bytes": bytes_len,
                        "owner_id": str(current_user.id) if current_user else "system",
                        "preview_chars": preview_chars,
                        "file_pinecone_config": file_pinecone_config.model_dump()
                    }

                    # Clean up per-file vars
                    original_bytes = None
                    preview_chars = None
                    gc.collect()

                    log_mem(f"{tender_id_str} perform_file_extraction:processed_{filename}")
                    return record
                except Exception as exc:
                    logger.error(f"[{tender_id_str}] Error processing file {filename}: {exc}")
                    return None

        # Launch limited-concurrency tasks
        processed_tasks = [process_one_file(f) for f in processed_files]
        processed_results = await asyncio.gather(*processed_tasks)
        successful_files = [r for r in processed_results if r]

        # ensure semaphore references released (individual semaphores are released by 'async with')
        processed_tasks = None
        processed_results = None
        # file_semaphore = None # Removed as it's now per-task
        gc.collect()
        
        total_processed_count = len(processed_files)
        processed_files = None  # help GC
        processed_files_summary = {
            'successful_files': successful_files,
            'total_processed': total_processed_count,
            'successful_count': len(successful_files)
        }
        
        if not successful_files:
            logger.warning(f"[{tender_id_str}] No files were successfully uploaded after processing.")
            filtered_tender = FilteredTenderAnalysisResult(
                            tender_id=tender_id_str,
                            tender_name=getattr(tender, 'name', ""),
                            organization=getattr(tender, 'organization', None),
                            location=getattr(tender, 'location', None),
                            analysis_id=str(analysis_id),
                            filter_stage=FilterStage.FILE_EXTRACTION,
                            filter_reason="No files were successfully uploaded after processing",
                            search_phrase=getattr(tender, 'search_phrase', None),
                            source=getattr(tender, 'source', None),
                            details_url=details_url,
                            user_id=str(current_user.id) if current_user else None
                        )
            await db.filtered_tender_analysis_results.insert_one(filtered_tender.dict(by_alias=True))
            logger.warning(f"Saved filtered tender (no files) to database: {tender_id_str}")
            return {
                "status": "upload_failed",
                "reason": "No files were successfully uploaded",
                "tender_id": tender_id_str,
                "details_url": details_url,
                "original_match": tender
            }
            
        result = {
            "status": "success",
            "tender_id": tender_id_str,
            "tender_name": tender_name,
            "details_url": details_url,
            "processed_files": processed_files_summary,
            "tender_pinecone_id": tender_pinecone_id,
            "original_match": tender
        }
        
        # Save results if requested
        if save_results:
            extraction_doc = {
                "analysis_id": analysis_id,
                "tender_id": tender_id_str,
                "tender_name": tender_name,
                "created_at": datetime.utcnow(),
                "user_id": str(current_user.id) if current_user else None,
                "details_url": details_url,
                "processed_files": processed_files_summary,
                "tender_pinecone_id": tender_pinecone_id
            }
            
            db_result = await db.tender_extraction_results.insert_one(extraction_doc)
            result["extraction_id"] = str(db_result.inserted_id)
            logger.info(f"[{tender_id_str}] Saved extraction results with ID: {result['extraction_id']}")
            
        # Memory log after successful extraction and upload
        log_mem(f"{tender_id_str} perform_file_extraction:end")
        return result
        
    except Exception as e:
        logger.error(f"[{tender_id_str}] Error during file extraction: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "reason": f"Extraction error: {str(e)}",
            "tender_id": tender_id_str
        }
    finally:
        if context:
            await context.close()
        if rag_manager:
            rag_manager.clean_up()
        # Final memory log in finally block
        log_mem(f"{tender_id_str} perform_file_extraction:finally")