# zip_extractor.py (formerly archive_extractor.py)
import zipfile
import tempfile
import os
from pathlib import Path
from typing import List, Generator
import gc

import py7zr
import rarfile

from .base import BaseFileExtractor, FileContent, ExtractorRegistry

class ZipFileExtractor(BaseFileExtractor):
    """
    Extracts files from ZIP (.zip), 7-Zip (.7z), and RAR (.rar) archives.
    For each file inside the archive:
      - Always use the registered extractor for the file type and yield text chunks.
      - Never yield base64 or pass_through chunks.
    """

    def supported_extensions(self) -> List[str]:
        return ['.zip', '.7z', '.rar']

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        ext = file_path.suffix.lower()
        self.logger.info(f"Extracting archive: {file_path}")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract based on file type
            try:
                if ext == '.zip':
                    self.logger.info(f"Processing ZIP archive: {file_path}")
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                elif ext == '.7z':
                    self.logger.info(f"Processing 7Z archive: {file_path}")
                    with py7zr.SevenZipFile(file_path, mode='r') as archive:
                        archive.extractall(path=temp_dir)
                elif ext == '.rar':
                    self.logger.info(f"Processing RAR archive: {file_path}")
                    with rarfile.RarFile(file_path) as rar_ref:
                        rar_ref.extractall(temp_dir)
                else:
                    raise ValueError(f"Unsupported archive format: {ext}")
            except Exception as e:
                self.logger.warning(
                            f"Failed to process archive '{file_path}': {str(e)}"
                        )

            # Process extracted files (same for all archive types)
            for root, _, files in os.walk(temp_dir):
                for filename in files:
                    extracted_path = Path(root) / filename
                    try:
                        file_ext = extracted_path.suffix.lower()
                        registry = ExtractorRegistry()
                        extractor = registry.get(file_ext)
                        if extractor:
                            self.logger.info(
                                f"Extracting '{extracted_path.name}' inside archive with '{extractor.__class__.__name__}'."
                            )
                            for content in extractor.extract_file_content(extracted_path):
                                if content.metadata is None:
                                    content.metadata = {}
                                # Always keep the inner extractor’s own fields
                                content.metadata.setdefault("filename", extracted_path.name)
                                content.metadata.setdefault("inner_temp_path", str(extracted_path))
                                content.metadata.setdefault("original_filename", extracted_path.name)

                                # Add archive provenance (these are new keys, so setdefault not required)
                                content.metadata["archive_source"] = file_path.name
                                content.metadata["archive_type"]   = ext[1:]     
                                yield content
                                # We can safely delete the extracted file after it has been yielded;
                                # FileExtractionService will have copied the bytes by the time the
                                # generator advances again.
                                gc.collect()
                        else:
                            self.logger.warning(
                                f"No extractor found for extension '{file_ext}' inside archive file '{extracted_path.name}'. Skipping."
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to process file '{extracted_path.name}' inside archive: {str(e)}"
                        )

    def extract_text_as_string(self, file_path: Path) -> str:
        """
        For archives, we return a simple message rather than trying to extract all text.
        """
        ext = file_path.suffix.lower()
        if ext == '.zip':
            return f"ZIP archive: {file_path.name}"
        elif ext == '.7z':
            return f"7Z archive: {file_path.name}"
        elif ext == '.rar':
            return f"RAR archive: {file_path.name}"
        else:
            return f"Archive file: {file_path.name}"