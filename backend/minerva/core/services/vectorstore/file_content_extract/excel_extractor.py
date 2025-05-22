# excel_extractor.py
from pathlib import Path
from typing import Generator, List
import logging
import pandas as pd
import gc

from .base import BaseFileExtractor, FileContent

class ExcelFileExtractor(BaseFileExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.xls', '.xlsx', '.xlsm']

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        try:
            text = self.extract_text_as_string(file_path)
            if text.strip():
                yield FileContent(
                    content=text,
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "excel",
                        "filename": file_path.name,
                        "original_extension": file_path.suffix.lower(),
                        "preview_chars": text[:self.NUM_OF_PREVIEW_CHARS]
                    }
                )
                # Free text memory
                text = None
                gc.collect()
        except Exception as e:
            self.logger.error(f"Error extracting Excel file {file_path}: {str(e)}")
            raise

    def extract_text_as_string(self, file_path: Path) -> str:
        lines = []
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        
        for sheet_name in sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                lines.append(f"\n--- Sheet: {sheet_name} ---")
                lines.append(f"Total Rows: {len(df)}, Columns: {', '.join(df.columns)}")

                # Gather row data
                for idx, row in df.iterrows():
                    row_str = f"Row {idx+1} -> " + ", ".join(
                        f"{col}={val}" for col, val in row.items() if pd.notna(val)
                    )
                    if row_str.strip():
                        lines.append(row_str)

                # Summary for numeric cols
                numeric_cols = df.select_dtypes(include=['int64','float64']).columns
                if not numeric_cols.empty:
                    lines.append("Numeric Columns Stats:")
                    for col in numeric_cols:
                        stats = df[col].describe()
                        lines.append(f"\nColumn: {col}")
                        lines.append(f"Mean: {stats['mean']:.2f}")
                        lines.append(f"Min: {stats['min']:.2f}")
                        lines.append(f"Max: {stats['max']:.2f}")
                
                # Clean up df for the current sheet
                df = None
                gc.collect()

            except Exception as e:
                # If one sheet fails, log and continue
                self.logger.error(f"Error processing sheet {sheet_name} in {file_path}: {e}")
                # Ensure df is cleaned up even on error within a sheet
                df = None 
                gc.collect()
                continue
        
        # Clean up ExcelFile object and sheet_names list
        xl = None
        sheet_names = None
        gc.collect()

        result_text = "\n".join(lines)
        # Cleanup lines list
        lines = None
        gc.collect()
        return result_text
