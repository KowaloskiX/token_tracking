from pathlib import Path
from typing import Generator, List

from .base import BaseFileExtractor, FileContent

class TextFileExtractor(BaseFileExtractor):
    SUPPORTED_EXTENSIONS = [
        '.c', '.cpp', '.cs', '.css', '.go', '.html',
        '.java', '.js', '.json', '.md', '.php', '.py', '.rb',
        '.sh', '.ts', '.txt'
    ]

    def supported_extensions(self) -> List[str]:
        """Return all file extensions supported by this extractor."""
        return self.SUPPORTED_EXTENSIONS

    def extract_text_as_string(self, file_path: Path) -> str:
        """
        Extract all text from the file as a single string.
        Tries to read with UTF-8 encoding first and falls back to Latin-1 on failure.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError as e:
            self.logger.warning(
                f"UTF-8 decoding failed for {file_path}: {e}. Trying Latin-1 encoding."
            )
            with open(file_path, 'r', encoding='latin1') as f:
                return f.read()

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        text = self.extract_text_as_string(file_path).strip()
        if text:
            yield FileContent(
                content=text,
                metadata={
                    "extractor": self.__class__.__name__,
                    "source_type": "text",
                    "filename": file_path.name,
                    "original_extension": file_path.suffix.lower(),
                    "preview_chars": text[:self.NUM_OF_PREVIEW_CHARS]
                }
            )