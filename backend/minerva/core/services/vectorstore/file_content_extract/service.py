# minerva/core/services/vectorstore/file_content_extract/service.py (append or separate file)
import asyncio
import concurrent.futures
import base64
import atexit
from pathlib import Path
import logging
from typing import List, Tuple
from datetime import datetime
import os
import gc

from minerva.core.services.vectorstore.file_content_extract.odt_extractor import OpenOfficeOdtFileExtractor

from .base import ExtractorRegistry
from .zip_extractor import ZipFileExtractor
from .word_extractor import WordFileExtractor
from .pdf_extractor import PDFFileExtractor
from .excel_extractor import ExcelFileExtractor
from .xml_extractor import XMLFileExtractor
from .csv_extractor import CSVFileExtractor
logger = logging.getLogger(__name__)

class FileExtractionService:
    _instance = None
    
    # Class-level logger
    logger = logging.getLogger(__name__)
    
    # Create a thread pool executor for CPU/IO-bound extractor tasks
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
    # Register shutdown on exit
    atexit.register(lambda: FileExtractionService.executor.shutdown(wait=False))
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.registry = ExtractorRegistry()
            cls._instance._register_extractors()
        return cls._instance
    
    def _register_extractors(self):
        # Ensure we always have an event loop available – during synchronous
        # imports (e.g. FastAPI route module import) there is no loop running
        # yet, so ``get_running_loop`` would raise ``RuntimeError``.
        # Nothing here should rely on a specific event loop instance.  We
        # register the extractors once, but defer choosing the asyncio event
        # loop until work is executed (see ``process_file_async``).  This
        # avoids the "attached to a different loop" error that occurred when
        # a loop captured during import time was later used inside a running
        # async application loop.
        extractors = [
            PDFFileExtractor(),
            WordFileExtractor(),
            OpenOfficeOdtFileExtractor(),
            ExcelFileExtractor(),
            XMLFileExtractor(),
            CSVFileExtractor(),
            ZipFileExtractor()
        ]
        for extractor in extractors:
            self.registry.register(extractor)
            logger.info(f"Registered {extractor.__class__.__name__}")

    def process_file(self, file_path: Path) -> List[Tuple[bytes, str, str, bytes, str]]:
        """
        Returns a list of tuples:
        (extracted_text_bytes, extracted_filename, preview_chars, original_file_bytes, original_filename)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Processing file: {file_path}")
        extension = file_path.suffix.lower() or '.doc'  # Fallback to .doc if no extension

        extractor = self.registry.get(extension)
        if not extractor:
            raise ValueError(f"No extractor registered for file type: {extension}")

        all_chunks = list(extractor.extract_file_content(file_path))
        if not all_chunks:
            logger.warning(f"No content extracted from {file_path}")
            # Explicitly release extractor if it was created and no chunks found
            extractor = None
            gc.collect()
            return []

        processed_files: List[Tuple[bytes, str, str, bytes, str]] = []
        # original_bytes = file_path.read_bytes() # MODIFIED: Remove eager loading
        original_filename = file_path.name
        original_bytes_top_level = None  # MODIFIED: Initialize to None
        read_top_level_bytes_once = False # MODIFIED: Flag to read only once

        for chunk in all_chunks:
            extracted_filename = chunk.metadata.get("filename", original_filename) # Use original_filename as fallback
            preview_chars = chunk.metadata.get("preview_chars", "")
            extracted_bytes = chunk.content.encode("utf-8", errors="replace")
            
            # MODIFIED: Lazy load original_bytes_top_level
            per_file_bytes = chunk.metadata.get("original_bytes")
            if per_file_bytes is None:
                # Check if extractor provided a temp path for lazy loading (e.g., ZipFileExtractor)
                inner_path = chunk.metadata.pop("inner_temp_path", None)
                if inner_path and os.path.exists(inner_path):
                    try:
                        per_file_bytes = Path(inner_path).read_bytes()
                    except Exception as read_err:
                        logger.error(f"Failed to read inner temp file bytes from {inner_path}: {read_err}")
                        per_file_bytes = b""
                    finally:
                        # Delete the temp file immediately after reading to save disk and RAM
                        try:
                            os.remove(inner_path)
                        except Exception:
                            pass
                else:
                    # Fallback to reading top-level bytes lazily (non-archive case)
                    if not read_top_level_bytes_once:
                        if file_path.exists():
                            original_bytes_top_level = file_path.read_bytes()
                        else:
                            logger.error(f"Original file path {file_path} no longer exists when trying to read its bytes lazily.")
                            original_bytes_top_level = b""
                        read_top_level_bytes_once = True
                    per_file_bytes = original_bytes_top_level if original_bytes_top_level is not None else b""

            per_file_name = chunk.metadata.get("original_filename", extracted_filename)
            
            processed_files.append((
                extracted_bytes,
                extracted_filename,
                preview_chars,
                per_file_bytes,
                per_file_name
            ))

        logger.info(f"Returning {len(processed_files)} file(s) from top-level file: {file_path.name}")

        # Explicitly release heavy vars
        all_chunks = None
        extractor = None
        if read_top_level_bytes_once: # MODIFIED: Clear if it was read
            original_bytes_top_level = None
        gc.collect()
        return processed_files

    # New async wrapper
    async def process_file_async(self, file_path: Path) -> List[Tuple[bytes, str, str, bytes, str]]:
        """Runs the synchronous process_file in a thread pool executor."""
        # Always schedule the CPU-bound work on the *current* running loop so
        # the returned Future belongs to the same loop that is awaiting it.
        # Using an old/stale loop captured during import leads to
        # "attached to a different loop" runtime errors inside Playwright
        # callbacks.
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor, self.process_file, file_path
        )
        
    @classmethod
    def shutdown(cls):
        """Explicitly shutdown the executor"""
        if cls.executor:
            cls.executor.shutdown(wait=False)
            cls.logger.info("FileExtractionService executor shutdown")