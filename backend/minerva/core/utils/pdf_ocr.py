from fastapi import UploadFile, HTTPException
from pdf2image import convert_from_bytes
import pytesseract

import pdfplumber
import io
    

def extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
    total_text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            total_text.append(page_text)
    return "\n".join(total_text)

def run_ocr(pdf_bytes: bytes) -> str:
    images = convert_from_bytes(pdf_bytes)
    extracted_text = []
    for image in images:
        text = pytesseract.image_to_string(image)
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