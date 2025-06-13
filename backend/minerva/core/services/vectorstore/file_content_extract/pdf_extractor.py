# pdf_extractor.py
#
# Minimal, CLIP-powered extractor that decides —
#   "OCR or skip?" — by classifying the **first page image**
#   as either a technical drawing (skip) or a normal document (OCR).

import io
import itertools
import logging
import os
import re
import statistics
import threading
import time
from pathlib import Path
from typing import Generator, List, Literal

import gc
import pytesseract
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from pypdf import PdfReader
from transformers import pipeline

from .base import BaseFileExtractor, FileContent

# --------------------------------------------------------------------------- #
#                       GLOBAL CONFIG, LOGGER & MODELS                        #
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)
OCR_SEMAPHORE = threading.Semaphore(int(os.getenv("OCR_PARALLELISM", "4")))

logger.info("Loading CLIP model (CPU)…")
_CLIP = pipeline(
    "zero-shot-image-classification",
    model="openai/clip-vit-base-patch32",
    device=-1,  # force CPU
    use_fast=True
)
_CLIP_LABELS = [
    "a technical drawing, blueprint or CAD schematic",
    "a normal page of text or scanned document",
]
logger.info("CLIP model ready.")

# --------------------------------------------------------------------------- #
#                              TEXT NORMALISATION                             #
# --------------------------------------------------------------------------- #
def clean_and_normalize_text(text: str) -> str:
    import unicodedata

    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "ł": "ł", "Ł": "Ł", "ą": "ą", "ć": "ć", "ę": "ę", "ń": "ń",
        "ó": "ó", "ś": "ś", "ź": "ź", "ż": "ż",
        "¿": "ż", "¶": "ś", "³": "ł", "¹": "ą", "œ": "ś",
        "¼": "ź", "¾": "ż",
        "â€™": "'", "â€œ": '"', "â€": '"', "â€¦": "…",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(
        r"[^\w\s\-.,;:!?()[\]{}\"'\/\\+=*&%$#@~`|<>ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]",
        "",
        text,
    )
    return text


def _is_valid_pdf(pdf_bytes: bytes) -> bool:
    """Check if the file is actually a valid PDF by examining the header."""
    if len(pdf_bytes) < 8:
        return False
    
    # PDF files must start with %PDF-
    header = pdf_bytes[:8]
    if not header.startswith(b'%PDF-'):
        logger.warning("Invalid PDF header detected: %s", header[:20])
        return False
    
    return True


def _might_be_text_file(pdf_bytes: bytes) -> bool:
    """Check if this 'PDF' might actually be a text file."""
    if len(pdf_bytes) < 100:
        return False
    
    # Sample first 500 bytes to check if it's mostly text
    sample = pdf_bytes[:500]
    try:
        # Try to decode as text
        text_sample = sample.decode('utf-8', errors='ignore')
        # If most characters are printable, it's likely a text file
        printable_ratio = sum(1 for c in text_sample if c.isprintable() or c.isspace()) / len(text_sample)
        return printable_ratio > 0.8
    except:
        return False


# --------------------------------------------------------------------------- #
#                         FIRST-PAGE CLASSIFICATION HELPER                    #
# --------------------------------------------------------------------------- #
def _first_page_is_drawing(pdf_bytes: bytes, *, dpi: int = 150) -> bool:
    """Return True if CLIP thinks the first page is a technical drawing."""
    # Render first page
    page_imgs = convert_from_bytes(
        pdf_bytes, first_page=1, last_page=1, dpi=dpi, thread_count=2
    )
    if not page_imgs:
        raise ValueError("Empty PDF or pdf2image failure")

    pil_img: Image.Image = page_imgs[0].convert("RGB")
    outputs = _CLIP(pil_img, candidate_labels=_CLIP_LABELS)
    top = outputs[0]  # highest-prob label

    label: Literal["drawing", "document"] = (
        "drawing"
        if "drawing" in top["label"] or "blueprint" in top["label"]
        else "document"
    )
    logger.info("CLIP result – %s (score %.3f)", label, top["score"])
    return label == "drawing"


# --------------------------------------------------------------------------- #
#                               MAIN EXTRACTOR                                #
# --------------------------------------------------------------------------- #
class PDFFileExtractor(BaseFileExtractor):
    """Extracts text from PDFs while *skipping* obvious technical drawings."""

    def __init__(self):
        super().__init__()
        self.tender_context = None  # Will store tender URL for logging context

    def set_tender_context(self, tender_url: str = None, tender_id: str = None):
        """Set tender context for logging purposes."""
        if tender_url:
            self.tender_context = f"[{tender_url}]"
        elif tender_id:
            self.tender_context = f"[{tender_id}]"
        else:
            self.tender_context = None

    def supported_extensions(self) -> List[str]:
        return [".pdf"]

    # ----------------------------- single-string --------------------------- #
    def extract_text_as_string(self, file_path: Path) -> str:
        self.logger.info("⇢ extract_text_as_string(%s)", file_path)
        pdf_bytes = file_path.read_bytes()

        # 0) Check if it's actually a valid PDF
        if not _is_valid_pdf(pdf_bytes):
            self.logger.warning("%s: Invalid PDF detected, checking if it's a text file", file_path.name)
            if _might_be_text_file(pdf_bytes):
                try:
                    # Try to extract as plain text
                    text_content = pdf_bytes.decode('utf-8', errors='ignore')
                    self.logger.info("%s: Extracted as plain text file (masquerading as PDF)", file_path.name)
                    return clean_and_normalize_text(text_content.strip())
                except Exception as exc:
                    self.logger.warning("Text extraction failed: %s", exc)
            # Fall through to OCR as last resort

        # 1) embedded text first — free!
        embedded = self._extract_embedded_text(pdf_bytes)
        if len(embedded.strip()) > 50:
            self.logger.debug("Embedded text found ⇒ no OCR needed.")
            return clean_and_normalize_text(embedded.strip())

        # 2) CLIP says "drawing"? → return special marker instead of empty string
        try:
            if _first_page_is_drawing(pdf_bytes):
                self.logger.info("%s identified as drawing – OCR skipped.", file_path.name)
                return "__TECHNICAL_DRAWING_SKIP_OCR__"
        except Exception as exc:
            self.logger.warning("First-page classification failed: %s", exc)

        # 3) Fallback OCR
        self.logger.info("%s: running OCR…", file_path.name)
        with OCR_SEMAPHORE:
            ocr_text = self._run_ocr(pdf_bytes)
        return ocr_text.strip()

    # ------------------------------ generator ------------------------------ #
    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        self.logger.info("⇢ extract_file_content(%s)", file_path)
        pdf_bytes = file_path.read_bytes()

        # 0) Check if it's actually a valid PDF
        if not _is_valid_pdf(pdf_bytes):
            self.logger.warning("%s: Invalid PDF detected, checking if it's a text file", file_path.name)
            if _might_be_text_file(pdf_bytes):
                try:
                    # Try to extract as plain text
                    text_content = pdf_bytes.decode('utf-8', errors='ignore')
                    cleaned = clean_and_normalize_text(text_content.strip())
                    self.logger.info("%s: Extracted as plain text file (masquerading as PDF)", file_path.name)
                    yield FileContent(
                        content=cleaned,
                        metadata={
                            "extractor": self.__class__.__name__,
                            "source_type": "text_file_as_pdf",
                            "filename": file_path.name,
                            "original_extension": file_path.suffix.lower(),
                            "preview_chars": cleaned[: self.NUM_OF_PREVIEW_CHARS],
                            "is_invalid_pdf": True,
                        },
                    )
                    return
                except Exception as exc:
                    self.logger.warning("Text extraction failed: %s", exc)
            # Fall through to OCR as last resort

        # 1) embedded text
        embedded = self._extract_embedded_text(pdf_bytes)
        if len(embedded.strip()) > 50:
            cleaned = clean_and_normalize_text(embedded.strip())
            yield FileContent(
                content=cleaned,
                metadata={
                    "extractor": self.__class__.__name__,
                    "source_type": "pdf",
                    "filename": file_path.name,
                    "original_extension": file_path.suffix.lower(),
                    "preview_chars": cleaned[: self.NUM_OF_PREVIEW_CHARS],
                },
            )
            return

        # 2) CLIP drawing check - yield special marker instead of returning empty
        try:
            if _first_page_is_drawing(pdf_bytes):
                self.logger.info("%s identified as drawing – OCR skipped.", file_path.name)
                yield FileContent(
                    content="__TECHNICAL_DRAWING_SKIP_OCR__",
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "pdf_technical_drawing",
                        "filename": file_path.name,
                        "original_extension": file_path.suffix.lower(),
                        "preview_chars": "Technical drawing - OCR skipped",
                        "is_technical_drawing": True,
                    },
                )
                return
        except Exception as exc:
            self.logger.warning("First-page classification failed: %s", exc)

        # 3) OCR & yield
        self.logger.info("%s: performing OCR (generator)…", file_path.name)
        with OCR_SEMAPHORE:
            ocr_text = self._run_ocr(pdf_bytes)
        if ocr_text.strip():
            yield FileContent(
                content=ocr_text.strip(),
                metadata={
                    "extractor": self.__class__.__name__,
                    "source_type": "pdf_ocr",
                    "filename": file_path.name,
                    "original_extension": file_path.suffix.lower(),
                    "preview_chars": ocr_text[: self.NUM_OF_PREVIEW_CHARS],
                },
            )

    # ------------------------------- helpers ------------------------------ #
    def _extract_embedded_text(self, pdf_bytes: bytes) -> str:
        out = []
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                out.append(page.extract_text() or "")
        except Exception as exc:
            # More specific logging for invalid PDFs
            if "invalid pdf header" in str(exc).lower() or "stream has ended unexpectedly" in str(exc).lower():
                self.logger.debug("PdfReader failure (likely invalid PDF): %s", exc)
            else:
                self.logger.error("PdfReader failure: %s", exc)
        return "\n".join(out)

    # ------------------------------ OCR stuff ------------------------------ #
    def _run_ocr(self, pdf_bytes: bytes, *, confidence_threshold: float = 60.0) -> str:
        t0 = time.perf_counter()
        texts = []
        
        for idx, img in enumerate(self._iter_pdf_pages(pdf_bytes)):
            bin_img, gray = self.preprocess_pil(img)
            psm = self._pick_psm(bin_img)
            txt1, conf1 = self._tess_data(bin_img, psm)
            if conf1 < confidence_threshold:
                psm2 = "4" if psm != "4" else "6"
                txt2, conf2 = self._tess_data(gray, psm2)
                txt = txt2 if conf2 > conf1 else txt1
            else:
                txt = txt1
            texts.append(txt)
            
            if idx and idx % 5 == 0:
                self.logger.debug("… OCR page %d done (%d chars): %s", 
                                idx + 1, len(txt), txt[:200] + "..." if len(txt) > 200 else txt)
            if idx and idx % 10 == 0:
                gc.collect()
                
        res = "\n\n".join(texts)
        total_time = time.perf_counter() - t0
        
        context_str = f"{self.tender_context} " if self.tender_context else ""
        self.logger.info(f"{context_str}OCR finished: %d pages in %.1fs (%.1f kchars)",
                         len(texts), total_time, len(res) / 1000)
        
        
        return res

    # ---------- image preprocessing & Tesseract helpers (unchanged) -------- #
    def preprocess_pil(self, img: Image.Image) -> tuple[Image.Image, Image.Image]:
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        gray = self._fix_orientation(gray)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if (bw == 0).mean() > 0.75:
            bw = cv2.bitwise_not(bw)
        bw = self._deskew_small(bw)
        return Image.fromarray(bw), Image.fromarray(gray)

    # ---------- rotation / deskew / tess helpers (unchanged) --------------- #
    def _fix_orientation(self, gray: np.ndarray) -> np.ndarray:
        try:
            rot = pytesseract.image_to_osd(gray, output_type=pytesseract.Output.DICT)["rotate"]
        except pytesseract.TesseractError:
            rot = 0
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE) if rot == 270 else \
               cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE) if rot == 90 else gray

    def _deskew_small(self, bw: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(bw == 0))
        if coords.size == 0:
            return bw
        angle = cv2.minAreaRect(coords)[-1]
        angle = angle + 90 if angle < -45 else angle
        if abs(angle) < 1 or abs(angle) > 15:
            return bw
        h, w = bw.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(bw, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    def _pick_psm(self, img: Image.Image) -> str:
        w, h = img.size
        aspect = h / w
        return "4" if aspect < 0.7 else "6" if aspect > 1.4 else "3"

    def _tess_data(self, img: Image.Image, psm: str,
                   lang: str = "pol+eng") -> tuple[str, float]:
        cfg = f"--oem 3 --dpi 300 --psm {psm}"
        data = pytesseract.image_to_data(
            img, lang=lang, config=cfg, output_type=pytesseract.Output.DICT
        )
        rows = [
            (w, l, float(c))
            for w, l, c in zip(data["text"], data["line_num"], data["conf"])
            if w.strip() and c != "-1"
        ]
        if not rows:
            return "", 0.0
        grouped = itertools.groupby(rows, key=lambda r: r[1])
        page_text = "\n".join(" ".join(w for w, *_ in grp) for _, grp in grouped)
        mean_conf = statistics.fmean(c for *_, c in rows)
        return page_text, mean_conf

    def _iter_pdf_pages(self, pdf_bytes: bytes, dpi: int = 300) -> Generator[Image.Image, None, None]:
        info = pdfinfo_from_bytes(pdf_bytes)
        for p in range(1, info["Pages"] + 1):
            yield from convert_from_bytes(
                pdf_bytes, first_page=p, last_page=p, dpi=dpi, thread_count=2
            )
