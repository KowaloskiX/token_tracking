from minerva.core.services.vectorstore.helpers import ChunkingConfig
import tiktoken
from nltk.tokenize import sent_tokenize
from typing import List, Optional
from pydantic import BaseModel
import re
import logging
logger = logging.getLogger(__name__)

class BZPDocumentChunker:
    """Specialized chunker for Polish BZP (Biuletyn Zamówień Publicznych) documents."""
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.tokenizer = tiktoken.get_encoding(self.config.tokenizer_name)
    
    @staticmethod
    def is_bzp_document(text: str) -> bool:
        """Detect if a document is a BZP (Polish public tender announcement)."""
        if not text or len(text) < 100:
            return False
            
        # Convert to lowercase for case-insensitive matching
        text_lower = text.lower()
        
        # Log content preview for BZP detection
        text_preview = text[:200].replace('\n', ' ').replace('\r', ' ').strip()
        
        # Specific BZP section headers (exact format)
        required_sections = [
            r'sekcja\s+i\s*[-–]\s*zamawiający',
            r'sekcja\s+ii\s*[-–]\s*informacje\s+podstawowe', 
            r'sekcja\s+iii\s*[-–]\s*udostępnianie\s+dokumentów',
            r'sekcja\s+iv\s*[-–]\s*przedmiot\s+zamówienia'
        ]
        
        # Count how many standard sections are present
        sections_found = 0
        found_section_names = []
        for i, section_pattern in enumerate(required_sections):
            if re.search(section_pattern, text_lower):
                sections_found += 1
                section_names = ["SEKCJA I", "SEKCJA II", "SEKCJA III", "SEKCJA IV"]
                found_section_names.append(section_names[i])
        
        # Look for the specific BZP numbering format (X.Y.) followed by content
        # Examples: "2.1.) Ogłoszenie dotyczy:", "2.5.) Numer ogłoszenia:", etc.
        bzp_numbering_pattern = r'\d+\.\d+\.\)\s*[A-ZĄĆĘŁŃÓŚŹŻ]'
        bzp_numbering_matches = len(re.findall(bzp_numbering_pattern, text))
        
        # Look for "Ogłoszenie o zamówieniu" header (should be at the beginning)
        has_announcement_header = bool(re.search(r'ogłoszenie\s+o\s+zamówieniu', text_lower))
        
        # Look for BZP number format: "YYYY/BZP XXXXXXXX"
        bzp_number_pattern = r'\d{4}/bzp\s+\d{8}'
        has_bzp_number = bool(re.search(bzp_number_pattern, text_lower))
        
        # Precise scoring system for BZP documents
        score = 0
        
        # Must have the announcement header
        if has_announcement_header:
            score += 3
            
        # Points for standard sections (need at least 2 out of 4 main sections)
        score += sections_found * 2
        
        # Points for BZP-style numbering (need several instances)
        if bzp_numbering_matches >= 5:
            score += 4
        elif bzp_numbering_matches >= 3:
            score += 2
        elif bzp_numbering_matches >= 1:
            score += 1
            
        # Points for official BZP number
        if has_bzp_number:
            score += 2
            
        is_bzp = score >= 8
        
        # If not BZP, log specific reasons why
        if not is_bzp:
            reasons = []
            if not has_announcement_header:
                reasons.append("Missing 'Ogłoszenie o zamówieniu' header")
            if sections_found < 2:
                reasons.append(f"Only {sections_found} standard sections found (need at least 2)")
            if bzp_numbering_matches < 1:
                reasons.append("No BZP numbering pattern (X.Y.) found")
            if not has_bzp_number:
                reasons.append("No official BZP number (YYYY/BZP XXXXXXXX) found")
            
            logger.info(f"BZP Detection FAILED - Reasons: {'; '.join(reasons)}")
            
        # Document is BZP if it has:
        # - Announcement header (3 pts)
        # - At least 2 standard sections (4 pts) 
        # - Several BZP numbering instances (2-4 pts)
        # Total threshold: 8 points minimum
        return is_bzp
    
    def create_chunks(self, text: str) -> List[str]:
        """Create chunks from BZP document by sections and subsections."""
        if not text or text.isspace():
            return []
        
        logger.info("Processing document as BZP (Polish public tender announcement)")
        chunks = []
        
        # Split by main sections (SEKCJA I, SEKCJA II, etc.) - robust pattern capturing full section text
        section_pattern = r'(SEKCJA\s+[IVXLC]+\s*[-–].*?)(?=SEKCJA\s+[IVXLC]+\s*[-–]|$)'
        sections = re.findall(section_pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not sections:
            logger.warning("BZP document detected but no sections found, falling back to standard chunking")
            return self._fallback_chunking(text)
        
        logger.info(f"Found {len(sections)} sections in BZP document")
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Check if section is within token limit
            section_tokens = len(self.tokenizer.encode(section))
            
            if section_tokens <= self.config.chunk_size:
                # Section fits in one chunk
                chunks.append(section)
            else:
                # Section too large, split by subsections
                subsection_chunks = self._split_section_by_subsections(section)
                chunks.extend(subsection_chunks)
        
        logger.info(f"BZP document chunked into {len(chunks)} chunks")
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _split_section_by_subsections(self, section: str) -> List[str]:
        """Split a large section by numbered subsections."""
        chunks = []
        
        # Pattern for BZP-style numbered subsections (e.g., "1.1)", "2.3)", "5.11)")
        # This is more specific than the generic pattern
        subsection_pattern = r'(\d+\.\d+(?:\.\d+)*\.\))'
        parts = re.split(subsection_pattern, section)
        
        if len(parts) <= 2:
            # No subsections found, use word-based splitting
            return self._split_by_words(section)
        
        current_chunk = ""
        current_tokens = 0
        
        # Skip first part if it's just the section header
        start_idx = 1 if not parts[0].strip() else 0
        
        i = start_idx
        while i < len(parts):
            if i + 1 < len(parts) and re.match(r'\d+\.\d+(?:\.\d+)*\.\)', parts[i]):
                # This is a subsection number, combine with following content
                subsection = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
                i += 2
            else:
                # This is content without subsection number
                subsection = parts[i]
                i += 1
            
            subsection = subsection.strip()
            if not subsection:
                continue
                
            subsection_tokens = len(self.tokenizer.encode(subsection))
            
            # If adding this subsection would exceed limit, finalize current chunk
            if current_tokens + subsection_tokens > self.config.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = subsection
                current_tokens = subsection_tokens
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + subsection
                    current_tokens += subsection_tokens + 2  # +2 for newlines
                else:
                    current_chunk = subsection
                    current_tokens = subsection_tokens
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_by_words(self, text: str) -> List[str]:
        """Fallback: split text by words when other methods fail."""
        chunks = []
        words = text.split()
        current_chunk = []
        current_tokens = 0
        
        for word in words:
            word_tokens = len(self.tokenizer.encode(word))
            
            if current_tokens + word_tokens > self.config.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_tokens = word_tokens
            else:
                current_chunk.append(word)
                current_tokens += word_tokens
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _fallback_chunking(self, text: str) -> List[str]:
        """Fallback to sentence-based chunking if BZP structure not detected."""
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))
            
            if current_tokens + sentence_tokens > self.config.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks