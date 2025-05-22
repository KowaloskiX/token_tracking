# odt_extractor.py
from pathlib import Path
from typing import Generator, List
import logging
import gc

from odf.opendocument import load
from odf.text import P
from odf.teletype import extractText

from .base import BaseFileExtractor, ExtractorRegistry, FileContent

class OpenOfficeOdtFileExtractor(BaseFileExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.odt']

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        self.logger.info(f"Extracting OpenOffice file: {file_path}")
        try:
            text = self.extract_text_as_string(file_path)
            if text.strip():
                yield FileContent(
                    content=text.strip(),
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "odt",
                        "filename": file_path.name,
                        "original_extension": file_path.suffix.lower(),
                        "preview_chars": text[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                text = None
                gc.collect()
            else:
                self.logger.warning(f"No text extracted from {file_path}")
        except Exception as e:
            self.logger.error(f"Error extracting OpenOffice file {file_path}: {str(e)}")
            raise

    def extract_text_as_string(self, file_path: Path) -> str:
        """Extract text from ODT file and return the full text as a single string."""
        if file_path.suffix.lower() != '.odt':
            raise ValueError("This extractor only supports .odt files")

        methods = [
            (self._extract_with_odfpy, "odfpy library"),
            (self._extract_with_odt2txt, "odt2txt command line")
        ]

        errors = []
        for method, method_desc in methods:
            try:
                text = method(file_path)
                if text.strip():
                    self.logger.info(f"Successfully extracted text from {file_path} using {method.__name__}")
                    return text
                else:
                    errors.append(f"{method.__name__} ({method_desc}): Returned empty text")
            except Exception as e:
                errors.append(f"{method.__name__} ({method_desc}): {str(e)}")
                continue

        error_msg = f"Unable to extract text from {file_path}. Errors: {'; '.join(errors)}"
        self.logger.error(error_msg)
        raise ValueError(error_msg)

    def _extract_with_odfpy(self, file_path: Path) -> str:
        """Extract text using odfpy library."""
        try:
            doc = load(str(file_path))
            paragraphs = []
            # Extract text from all paragraph elements
            for paragraph in doc.getElementsByType(P):
                text = extractText(paragraph)
                if text.strip():
                    paragraphs.append(text.strip())
            
            result_text = "\n".join(paragraphs)
            doc = None
            paragraphs = None
            gc.collect()
            return result_text
        except Exception as e:
            raise ValueError(f"odfpy extraction failed: {str(e)}")

    def _extract_with_odt2txt(self, file_path: Path) -> str:
        """Extract text using odt2txt command line tool (requires odt2txt installed)."""
        import subprocess
        try:
            # Extract text with odt2txt
            result = subprocess.run(
                ['odt2txt', str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            output_text = result.stdout
            result = None
            gc.collect()
            return output_text
        except FileNotFoundError:
            raise ValueError("odt2txt not found. Please install it with 'brew install odt2txt' on macOS or 'apt-get install odt2txt' on Linux.")
        except subprocess.CalledProcessError as e:
            raise ValueError(f"odt2txt failed: {e.stderr or e.stdout}") from e