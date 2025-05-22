# xml_extractor.py
from pathlib import Path
from typing import Generator, List
import xml.etree.ElementTree as ET
import gc

from .base import BaseFileExtractor, FileContent

class XMLFileExtractor(BaseFileExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.xml']

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        try:
            text = self.extract_text_as_string(file_path)
            if text.strip():
                yield FileContent(
                    content=text,
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "xml",
                        "filename": file_path.name,
                        "original_extension": file_path.suffix.lower(),
                        "preview_chars": text[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                text = None
                gc.collect()
        except Exception as e:
            self.logger.error(f"Error extracting XML file {file_path}: {str(e)}")
            raise

    def extract_text_as_string(self, file_path: Path) -> str:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            all_lines = []
            
            # Recursively process all elements
            self._process_element(root, all_lines, parent_path="")
            
            # Add a short summary
            total_elements = self._count_elements(root)
            all_lines.append(f"\nXML Summary:")
            all_lines.append(f"Root Element: {root.tag}")
            all_lines.append(f"Total Elements: {total_elements}")
            all_lines.append(f"Root Attributes: {root.attrib if root.attrib else 'None'}")

            output_text = "\n".join(all_lines)
            tree = None
            root = None
            all_lines = None
            gc.collect()
            return output_text
        except Exception as e:
            raise ValueError(f"Failed to parse XML: {str(e)}")
    
    def _process_element(self, element: ET.Element, lines: List[str], parent_path: str):
        path = f"{parent_path}/{element.tag}" if parent_path else element.tag
        
        line_parts = [f"Element Path: {path}"]
        if element.attrib:
            line_parts.append(f"Attributes: {element.attrib}")
        if element.text and element.text.strip():
            line_parts.append(f"Text: {element.text.strip()}")
        
        if len(line_parts) > 1:
            lines.append("\n".join(line_parts))

        # Recursively process children
        for child in element:
            self._process_element(child, lines, path)
    
    def _count_elements(self, element: ET.Element) -> int:
        count = 1
        for child in element:
            count += self._count_elements(child)
        return count
