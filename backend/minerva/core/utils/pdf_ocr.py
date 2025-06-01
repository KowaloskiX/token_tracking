from fastapi import UploadFile, HTTPException
from pdf2image import convert_from_bytes
import pytesseract

import pdfplumber
import io
import unicodedata
import re
    

def extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
    total_text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            total_text.append(page_text)
    return "\n".join(total_text)

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
        'l': 'ł',   # Sometimes l is misread as ł in context
        '¿': 'ż',   # Common OCR mistake
        '¶': 'ś',   # Common OCR mistake
        '³': 'ł',   # Common OCR mistake
        '¹': 'ą',   # Common OCR mistake
        '¿': 'ż',   # Common OCR mistake
        'œ': 'ś',   # Common OCR mistake
        '¼': 'ź',   # Common OCR mistake
        '¾': 'ż',   # Common OCR mistake
    }
    
    # Apply replacements carefully - only if the context suggests it's a Polish word
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
    
    # Remove any remaining problematic characters that might cause encoding issues
    text = re.sub(r'[^\w\s\-.,;:!?()[\]{}"\'/\\+=*&%$#@~`|<>ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', '', text)
    
    return text

def run_ocr(pdf_bytes: bytes) -> str:
    images = convert_from_bytes(pdf_bytes)
    extracted_text = []
    
    # Configure Tesseract for Polish language with better character recognition
    custom_config = r'--oem 3 --psm 6 -l pol+eng'
    
    for image in images:
        text = pytesseract.image_to_string(
            image,
            lang="pol+eng",           # Polish first; add English for mixed headers
            config="--psm 3 --oem 1"
        )
        extracted_text.append(text)

    return "\n".join(extracted_text)

async def maybe_ocr_pdf(file: UploadFile) -> str:
    pdf_bytes = await file.read()
    
    text_extracted = extract_text_with_pdfplumber(pdf_bytes)
    
    # Arbitrary threshold: if the PDF already has >= ~50 chars, assume no OCR needed
    if len(text_extracted.strip()) > 50:
        return text_extracted
    else:
        return run_ocr(pdf_bytes)

async def maybe_ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    
    text_extracted = extract_text_with_pdfplumber(pdf_bytes)
    
    # Arbitrary threshold: if the PDF already has >= ~50 chars, assume no OCR needed
    if len(text_extracted.strip()) > 50:
        return text_extracted
    else:
        return run_ocr(pdf_bytes)