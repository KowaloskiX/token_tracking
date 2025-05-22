# base.py
from pathlib import Path
import logging
from typing import List, Generator, Optional
from dataclasses import dataclass

@dataclass
class FileContent:
    content: str
    metadata: dict

class BaseFileExtractor:
    """
    Base class for text extraction from files.
    Now each extractor returns a SINGLE chunk with the entire file text.
    """

    NUM_OF_PREVIEW_CHARS = 250
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def supported_extensions(self) -> List[str]:
        """List of file extensions this extractor supports."""
        raise NotImplementedError
        
    def extract_text_as_string(self, file_path: Path) -> str:
        """
        Extract all text from file as a single string.
        Subclasses should override or use their own logic.
        """
        raise NotImplementedError
    
    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        text = self.extract_text_as_string(file_path).strip()
        if text:
            yield FileContent(
                content=text,
                metadata={
                    "extractor": self.__class__.__name__,
                    "source_type": "generic",
                    "preview_chars": text[:self.NUM_OF_PREVIEW_CHARS]
                }
            )

class ExtractorRegistry:
    """Registry for file type extractors"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.extractors = {}
            cls._instance.logger = logging.getLogger(f"{__name__}.ExtractorRegistry")
        return cls._instance
    
    def register(self, extractor: BaseFileExtractor):
        """Register an extractor for its supported extensions."""
        for ext in extractor.supported_extensions():
            self.extractors[ext] = extractor
            self.logger.info(f"Registered extractor for extension: {ext}")
            
    def get(self, extension: str) -> Optional[BaseFileExtractor]:
        """Get the appropriate extractor for a file extension."""
        return self.extractors.get(extension.lower())
