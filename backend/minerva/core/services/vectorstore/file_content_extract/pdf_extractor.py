# pdf_extractor.py
from pathlib import Path
import time
from typing import Generator, List
import logging
import io
import base64
import gc
import asyncio
import threading
import os

import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfReader

from .base import BaseFileExtractor, FileContent

# Configurable OCR concurrency
OCR_SEMAPHORE = threading.Semaphore(int(os.getenv("OCR_PARALLELISM", "4")))

class PDFFileExtractor(BaseFileExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.pdf']
    
    def extract_text_as_string(self, file_path: Path) -> str:
        self.logger.info(f"Extracting text from PDF: {file_path}")
        try:
            pdf_bytes = file_path.read_bytes()
            # Quick guard: if PDF is gigantic (>25MB) and likely scanned, skip with warning
            if file_path.stat().st_size > 36 * 1024 * 1024:  # 25 MB
                self.logger.warning(f"PDF {file_path.name} is very large ({file_path.stat().st_size/1024/1024:.1f} MB); skipping OCR-heavy processing to avoid slowdown.")
                return ""
            # 1) Attempt normal text extraction
            embedded_text = self._extract_embedded_text(pdf_bytes)
            if len(embedded_text.strip()) > 50:
                return embedded_text.strip()
            else:
                # 2) Otherwise, run OCR
                self.logger.info(
                    f"PDF {file_path.name} seems scanned or has little text; performing OCR..."
                )
                with OCR_SEMAPHORE:
                    ocr_text = self._run_ocr(pdf_bytes)
                # Force cleanup after OCR which might use a lot of memory
                gc.collect()
                if ocr_text.strip():
                    return ocr_text.strip()
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            raise
        
    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        self.logger.info(f"Extracting PDF: {file_path}")
        try:
            pdf_bytes = file_path.read_bytes()
            # Quick guard: if PDF is gigantic (>25MB) and likely scanned, skip with warning
            if file_path.stat().st_size > 25 * 1024 * 1024:  # 25 MB
                self.logger.warning(f"PDF {file_path.name} is very large ({file_path.stat().st_size/1024/1024:.1f} MB); skipping OCR-heavy processing to avoid slowdown.")
                return
            embedded_text = self._extract_embedded_text(pdf_bytes)
            if len(embedded_text.strip()) > 50:
                yield FileContent(
                    content=embedded_text.strip(),
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "pdf",
                        "filename": file_path.name,
                        "original_extension": file_path.suffix.lower(),
                        "preview_chars": embedded_text[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                # Release memory for this chunk
                embedded_text = None
                gc.collect()
            else:
                self.logger.info(
                    f"PDF {file_path.name} seems scanned or has little text; performing OCR..."
                )
                with OCR_SEMAPHORE:
                    ocr_text = self._run_ocr(pdf_bytes)
                # Force cleanup after OCR which might use a lot of memory    
                gc.collect()
                if ocr_text.strip():
                    yield FileContent(
                        content=ocr_text.strip(),
                        metadata={
                            "extractor": self.__class__.__name__,
                            "source_type": "pdf_ocr",
                            "filename": file_path.name,
                            "original_extension": file_path.suffix.lower(),
                            "preview_chars": ocr_text[:self.NUM_OF_PREVIEW_CHARS]
                        }
                    )
                    # Release OCR text memory
                    ocr_text = None
                    gc.collect()
        except Exception as e:
            self.logger.error(f"Error extracting PDF {file_path}: {str(e)}")
            raise

    def _extract_embedded_text(self, pdf_bytes: bytes) -> str:
        """Extract embedded text from a PDF using pypdf (no OCR)."""
        text_buffer = []
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text_buffer.append(page_text)
            # Clean up reader resources
            reader = None
        except Exception as e:
            self.logger.error(f"Error reading PDF with PdfReader: {str(e)}")
        return "\n".join(text_buffer)

    def _run_ocr(self, pdf_bytes: bytes) -> str:
        """Convert PDF to images and run Tesseract OCR, with duration logging."""
        start_time = time.monotonic()
        try:
            # Lower the DPI to speed up OCR and reduce memory usage
            images = convert_from_bytes(pdf_bytes, dpi=150)
        except Exception as e:
            self.logger.error(f"Error converting PDF to images for OCR: {str(e)}")
            return ""
        
        extracted = []
        for i, img in enumerate(images):
            txt = pytesseract.image_to_string(img)
            extracted.append(txt)
            # Release the image object to free memory
            img = None
            # For large documents, force gc after processing some pages
            if i > 0 and i % 10 == 0:
                gc.collect()
                
        ocr_text = "\n".join(extracted)
        end_time = time.monotonic()
        duration = end_time - start_time
        self.logger.info(f"OCR completed in {duration:.2f} seconds for PDF ({len(images)} pages).")
        
        # Clean up images array to release memory
        images = None
        gc.collect()
        
        return ocr_text