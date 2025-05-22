# csv_extractor.py
from pathlib import Path
from typing import Generator, List
import logging
import pandas as pd
import gc

from .base import BaseFileExtractor, FileContent

class CSVFileExtractor(BaseFileExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.csv']

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        """
        Reads the entire CSV file into a single string, including:
        - Column names
        - Row data
        - Simple summary
        Yields one FileContent if successful.
        """
        try:
            text = self.extract_text_as_string(file_path)
            if text.strip():
                yield FileContent(
                    content=text,
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "csv",
                        "preview_chars": text.strip()[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                text = None
                gc.collect()
        except Exception as e:
            self.logger.error(f"Error extracting CSV file {file_path}: {str(e)}")
            raise

    def extract_text_as_string(self, file_path: Path) -> str:
        df = self._read_csv_with_encoding(file_path)
        if df is None:
            raise ValueError("Could not read CSV file with any supported encoding")

        lines = []
        
        # 1) Column names
        columns_line = f"Columns: {', '.join(df.columns)}"
        lines.append(columns_line)
        
        # 2) Row data
        for idx, row in df.iterrows():
            row_str = f"Row {idx+1} -> " + ", ".join(f"{col}={val}" 
                                   for col, val in row.items() if pd.notna(val))
            if row_str.strip():
                lines.append(row_str)
        
        # 3) Summary
        lines.append(f"\nSummary:")
        lines.append(f"Total Rows: {len(df)}")
        lines.append(f"Total Columns: {len(df.columns)}")

        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if not numeric_cols.empty:
            lines.append("Numeric Columns Stats:")
            for col in numeric_cols:
                stats = df[col].describe()
                lines.append(f"\nColumn: {col}")
                lines.append(f"Mean: {stats['mean']:.2f}")
                lines.append(f"Min: {stats['min']:.2f}")
                lines.append(f"Max: {stats['max']:.2f}")

        text_output = "\n".join(lines)
        df = None
        lines = None
        gc.collect()
        return text_output

    def _read_csv_with_encoding(self, file_path: Path):
        encodings = ['utf-8', 'latin1', 'iso-8859-1']
        for encoding in encodings:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        return None
