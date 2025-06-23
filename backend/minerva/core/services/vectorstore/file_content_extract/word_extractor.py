# word_extractor.py
"""Advanced Word text extractor.

This extractor is designed for production use where accuracy is critical and must
support both modern ``.docx`` and legacy ``.doc`` files coming from public‑tender
workflows.  Strategies per format:

* *.docx* – primary: ``docx2python`` (captures headers, footers, lists, foot‑
  notes, comments, etc.); fallback: LibreOffice/soffice headless conversion; final
  fallback: python‑docx (already installed in most environments).
* *.doc*  – primary: LibreOffice/soffice headless conversion (much higher
  fidelity than antiword); fallback: antiword (fast, but lossy); 

All methods are invoked through small helpers so the public interface (`extract_file_content`/
extract_text_as_string) is unchanged.

Dependencies (Ubuntu/Debian examples):

```bash
apt-get update && apt-get install -y libreoffice-core libreoffice-writer \
                                   unoconv antiword default-jre-headless
pip install docx2python python-docx

"""
from __future__ import annotations

import gc
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Generator, List

from docx import Document  # fallback only!
from docx.opc.exceptions import PackageNotFoundError
from docx2python import docx2python  # primary for .docx

from .base import BaseFileExtractor, FileContent

logger = logging.getLogger(__name__)


def _run_subprocess(cmd: list[str | Path], timeout: int = 60) -> str:
    """Run cmd and return stdout (raise on error).

    All stderr output is captured for diagnostics.  ``timeout`` prevents hangs
    (LibreOffice occasionally freezes on malformed files).
    """
    proc = subprocess.run(
        [str(c) for c in cmd],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with code {proc.returncode}:\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        )
    return proc.stdout

class WordFileExtractor(BaseFileExtractor):

    def supported_extensions(self) -> List[str]:
        return [".doc", ".docx"]

    def extract_file_content(self, file_path: Path) -> Generator[FileContent, None, None]:
        self.logger.info("Extracting Word file: %s", file_path)
        ext = file_path.suffix.lower()
        try:
            text = self.extract_text_as_string(file_path)
            if text and text.strip():
                yield FileContent(
                    content=text.strip(),
                    metadata={
                        "extractor": self.__class__.__name__,
                        "source_type": "word",
                        "filename": file_path.name,
                        "original_extension": ext,
                        "preview_chars": text[: self.NUM_OF_PREVIEW_CHARS],
                    },
                )
                text = None
                gc.collect()
            else:
                self.logger.warning("No text extracted from %s (empty output)", file_path)
        except Exception as exc:
            self.logger.error("Error extracting %s: %s", file_path, exc, exc_info=True)
            raise

    def extract_text_as_string(self, file_path: Path, use_soffice_only = False) -> str:
        """Try several methods appropriate for the file extension and return text.

        Stops at the first successful extraction that returns non‑empty text.
        Raises ``ValueError`` if all methods fail.
        """
        ext = file_path.suffix.lower()
        is_docx = ext == ".docx"
        is_doc = ext == ".doc"

        methods: list[tuple[str, "WordFileExtractor._Extractor"]] = []

        # NB: Method order = preference order
        if is_docx:
            if use_soffice_only:
                methods.extend(
                [
                    ("soffice-txt", self._extract_with_soffice_txt),
                    ("python-docx", self._extract_with_python_docx),
                ]
                )
            else:
                methods.extend(
                    [
                        ("docx2python", self._extract_with_docx2python),
                        ("soffice-txt", self._extract_with_soffice_txt),
                        ("python-docx", self._extract_with_python_docx),
                    ]
                )
        elif is_doc:
            methods.extend(
                [
                    ("soffice-txt", self._extract_with_soffice_txt),
                    ("antiword", self._extract_with_antiword),
                ]
            )
        else:
            raise ValueError(f"Unsupported extension: {ext}")

        errors: list[str] = []
        for name, func in methods:
            try:
                text = func(file_path)
                if text and text.strip():
                    self.logger.info("%s succeeded on %s (extracted %d chars)", name, file_path, len(text))
                    return text
                self.logger.warning("%s returned empty output for %s", name, file_path)
            except FileNotFoundError as fe:  # missing dependency: not a fatal error, try next method
                self.logger.warning("%s dependency unavailable: %s", name, fe)
                errors.append(f"{name}: tool not found")
            except subprocess.TimeoutExpired:
                msg = f"{name} timed out"
                self.logger.warning("%s on %s", msg, file_path)
                errors.append(msg)
            except Exception as exc:
                msg = f"{name}: {exc}"
                self.logger.debug("Extractor %s failed: %s", name, exc, exc_info=True)
                errors.append(msg)

        raise ValueError(
            f"Unable to extract text from {file_path} after trying {len(methods)} methods.\n"
            f"Errors: {'; '.join(errors)}"
        )

    def _extract_with_docx2python(self, file_path: Path) -> str:
        """Primary extractor for .docx using docx2python."""
        if file_path.suffix.lower() != ".docx":
            raise ValueError("docx2python only supports .docx")
        try:
            with docx2python(file_path, html=False) as doc:
                # .text contains headers, footers, footnotes, comments, lists w/ numbers
                text = doc.text.replace("\u000b", "\n")  # strip vertical‑tab char for cleanliness
            return text
        except PackageNotFoundError as pnf:  # malformed docx (not a zip)
            raise ValueError(f"Malformed .docx file: {pnf}") from pnf

    def _extract_with_soffice_txt(self, file_path: Path) -> str:
        """Use LibreOffice headless to export to plain text (works for .doc and .docx).

        Requires ``soffice`` (LibreOffice) in PATH.  If the environment variable
        ``WORD_EXTRACTOR_DISABLE_SOFFICE`` is set to a truthy value, this method
        raises FileNotFoundError so that the caller proceeds to the next fallback.
        """
        if os.getenv("WORD_EXTRACTOR_DISABLE_SOFFICE"):
            raise FileNotFoundError("soffice intentionally disabled via env")

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "soffice",
                "--headless",
                "--convert-to",
                "txt:Text",
                "--outdir",
                tmpdir,
                file_path,
            ]
            _run_subprocess(cmd, timeout=120)  # LibreOffice can be slow on big docs

            txt_file = Path(tmpdir) / f"{file_path.stem}.txt"
            if not txt_file.exists():
                raise RuntimeError("LibreOffice did not produce expected TXT file")

            return txt_file.read_text(errors="replace")

    def _extract_with_python_docx(self, file_path: Path) -> str:
        """Fallback extractor using python‑docx – will miss headers/footers."""
        if file_path.suffix.lower() != ".docx":
            raise ValueError("python-docx only supports .docx")
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(paragraphs)

    def _extract_with_antiword(self, file_path: Path) -> str:
        """Legacy extractor for .doc using antiword."""
        if file_path.suffix.lower() != ".doc":
            raise ValueError("antiword only supports .doc")
        cmd = ["antiword", file_path]
        return _run_subprocess(cmd)