# word_extractor.py
import base64
from pathlib import Path
from typing import Generator, List
import subprocess
import logging
import gc

from docx import Document

from .base import BaseFileExtractor, ExtractorRegistry, FileContent

class WordFileExtractor(BaseFileExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.doc', '.docx']

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        self.logger.info(f"Extracting Word file: {file_path}")
        try:
            ext = file_path.suffix.lower()
            text = self.extract_text_as_string(file_path)
            if text and text.strip():
                yield FileContent(
                    content=text.strip(),
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "word",
                        "filename": file_path.name,
                        "original_extension": ext,
                        "preview_chars": text[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                # Release memory for extracted text
                text = None
                gc.collect()
            elif not text:
                self.logger.warning(f"No text could be extracted from Word file {file_path} by any method.")
            else:
                self.logger.warning(f"Extracted text from Word file {file_path} is empty or whitespace only.")

        except Exception as e:
            self.logger.error(f"Error extracting Word file {file_path}: {str(e)}")
            if not isinstance(e, ValueError) or "Unable to extract text from" not in str(e):
                raise

    def extract_text_as_string(self, file_path: Path) -> str:
        """Attempt multiple fallback methods; return the full text as a single string."""
        is_doc = file_path.suffix.lower() == '.doc'
        is_docx = file_path.suffix.lower() == '.docx'

        methods = []
        if is_docx:
            methods.append((self._extract_with_python_docx, "python-docx (.docx)"))
            methods.append((self._extract_with_antiword, "antiword (fallback for .docx)"))
        elif is_doc:
            methods.append((self._extract_with_antiword, "antiword (.doc only)"))

        if not methods:
            error_msg = f"No extraction methods applicable for file: {file_path} (suffix: {file_path.suffix.lower()})"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        errors = []
        for method, method_desc in methods:
            try:
                text = method(file_path)
                if text and text.strip():
                    self.logger.info(f"Successfully extracted text from {file_path} using {method.__name__} ({method_desc})")
                    return text
                else:
                    empty_msg = f"{method.__name__} ({method_desc}): Returned empty text or None"
                    self.logger.warning(f"For file {file_path}, {empty_msg}")
                    errors.append(empty_msg)
            except Exception as e:
                error_entry = f"{method.__name__} ({method_desc}): {str(e)}"
                self.logger.warning(f"For file {file_path}, extraction with {method.__name__} failed: {error_entry}")
                errors.append(error_entry)
                continue

        error_msg = f"Unable to extract text from {file_path} after trying all methods. Errors: {'; '.join(errors)}"
        self.logger.error(error_msg)
        raise ValueError(error_msg)

    def _extract_with_python_docx(self, file_path: Path) -> str:
        """Extract text using python-docx (for .docx files only)."""
        if file_path.suffix.lower() != '.docx':
            raise ValueError("python-docx only supports .docx files")
        doc = Document(file_path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)

    def _extract_with_antiword(self, file_path: Path) -> str:
        """Extract text using antiword (for .doc and as fallback for .docx files; requires antiword installed)."""
        try:
            result = subprocess.run(
                ['antiword', str(file_path)],
                capture_output=True,
                text=True,
                check=True,
                errors='replace'
            )
            return result.stdout
        except FileNotFoundError:
            msg = "antiword not found. Please install it (e.g., 'sudo apt-get install antiword' or 'brew install antiword'). It is used for .doc files and as a fallback for .docx."
            self.logger.error(f"{msg} (File: {file_path})")
            raise ValueError(msg) from None
        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.strip() if e.stderr and isinstance(e.stderr, str) else ""
            stdout_output = e.stdout.strip() if e.stdout and isinstance(e.stdout, str) else ""
            error_detail = stderr_output or stdout_output or "No specific error output from antiword."
            msg = f"antiword failed for {file_path}. Details: {error_detail}"
            self.logger.error(msg)
            raise ValueError(msg) from e