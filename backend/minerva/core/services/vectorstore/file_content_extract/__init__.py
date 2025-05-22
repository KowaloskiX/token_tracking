from minerva.core.services.vectorstore.file_content_extract.txt_extractor import TextFileExtractor
from .base import FileContent, BaseFileExtractor, ExtractorRegistry
from .service import FileExtractionService
from .word_extractor import WordFileExtractor
from .pdf_extractor import PDFFileExtractor
from .excel_extractor import ExcelFileExtractor
from .csv_extractor import CSVFileExtractor
from .xml_extractor import XMLFileExtractor
from .zip_extractor import ZipFileExtractor

# Initialize registry and register extractors
registry = ExtractorRegistry()
registry.register(PDFFileExtractor())
registry.register(WordFileExtractor())
registry.register(ExcelFileExtractor())
registry.register(CSVFileExtractor())
registry.register(XMLFileExtractor())
registry.register(ZipFileExtractor())
registry.register(TextFileExtractor())

__all__ = [
    'FileContent',
    'BaseFileExtractor',
    'FileExtractionService',
    'PDFFileExtractor',
    'WordFileExtractor',
    'ExcelFileExtractor',
    'CSVFileExtractor',
    'XMLFileExtractor',
    'ZipFileExtractor',
    'TextFileExtractor'
]