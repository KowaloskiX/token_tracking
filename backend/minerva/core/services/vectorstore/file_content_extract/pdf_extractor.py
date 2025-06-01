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
import unicodedata
import re

import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfReader

from .base import BaseFileExtractor, FileContent

# Configurable OCR concurrency
OCR_SEMAPHORE = threading.Semaphore(int(os.getenv("OCR_PARALLELISM", "4")))

def clean_and_normalize_text(text: str) -> str:
    """Clean and normalize text to handle encoding issues and Polish characters properly."""
    if not text:
        return ""
    
    # Normalize Unicode characters (NFD -> NFC)
    text = unicodedata.normalize('NFC', text)
    
    # Common OCR character replacements for Polish
    replacements = {
        'ł': 'ł',  # Ensure proper ł character
        'Ł': 'Ł',  # Ensure proper Ł character
        'ą': 'ą',  # Ensure proper ą character
        'ć': 'ć',  # Ensure proper ć character
        'ę': 'ę',  # Ensure proper ę character
        'ń': 'ń',  # Ensure proper ń character
        'ó': 'ó',  # Ensure proper ó character
        'ś': 'ś',  # Ensure proper ś character
        'ź': 'ź',  # Ensure proper ź character
        'ż': 'ż',  # Ensure proper ż character
        # Common OCR misreads
        '¿': 'ż',   # Common OCR mistake
        '¶': 'ś',   # Common OCR mistake
        '³': 'ł',   # Common OCR mistake
        '¹': 'ą',   # Common OCR mistake
        'œ': 'ś',   # Common OCR mistake
        '¼': 'ź',   # Common OCR mistake
        '¾': 'ż',   # Common OCR mistake
        # Handle common encoding artifacts
        'â€™': "'",  # Smart quote
        'â€œ': '"',  # Smart quote
        'â€': '"',   # Smart quote
        'â€¦': '...',  # Ellipsis
    }
    
    # Apply replacements
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
    
    # Remove any remaining problematic characters that might cause encoding issues
    # Keep Polish characters and common punctuation
    text = re.sub(r'[^\w\s\-.,;:!?()[\]{}"\'/\\+=*&%$#@~`|<>ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', '', text)
    
    return text

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
                # Clean and normalize even embedded text
                return clean_and_normalize_text(embedded_text.strip())
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
                # Clean and normalize embedded text
                cleaned_text = clean_and_normalize_text(embedded_text.strip())
                yield FileContent(
                    content=cleaned_text,
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "pdf",
                        "filename": file_path.name,
                        "original_extension": file_path.suffix.lower(),
                        "preview_chars": cleaned_text[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                # Release memory for this chunk
                embedded_text = None
                cleaned_text = None
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
        """Convert PDF to images and run Tesseract OCR with Polish language support."""
        start_time = time.monotonic()
        try:
            # Lower the DPI to speed up OCR and reduce memory usage
            images = convert_from_bytes(pdf_bytes, dpi=150)
        except Exception as e:
            self.logger.error(f"Error converting PDF to images for OCR: {str(e)}")
            return ""
        
        # Configure Tesseract for Polish language with better character recognition
        custom_config = r'--oem 3 --psm 6 -l pol+eng'
        
        extracted = []
        for i, img in enumerate(images):
            txt =  pytesseract.image_to_string(
                img,
                lang="pol+eng",           # Polish first; add English for mixed headers
                config="--psm 3 --oem 1"
            )
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