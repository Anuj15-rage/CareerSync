import hashlib
import io
import re
from pathlib import Path
from typing import Tuple

import docx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

# 5 MB limit in bytes
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize the uploaded filename to prevent directory traversal
    and remove unsafe characters while preserving the extension.
    """
    if not filename:
        return "uploaded_resume"
    # Take basename only to defeat path traversal attempts
    base_name = Path(filename).name
    # Remove any characters other than alphanumeric, dots, hyphens, and underscores
    sanitized = re.sub(r"[^\w.\-]", "_", base_name)
    # Ensure maximum length of 255 characters (database schema limit)
    return sanitized[:255] if len(sanitized) > 255 else sanitized


def compute_file_hash(content: bytes) -> str:
    """Compute the SHA-256 hexadecimal hash of the file bytes."""
    return hashlib.sha256(content).hexdigest()


def validate_file_signature(content: bytes, ext: str) -> bool:
    """
    Verify magic header bytes to ensure the file format actually matches
    its declared extension.
    - PDF: starts with b"%PDF-"
    - DOCX: starts with b"PK\x03\x04" (ZIP archive header)
    """
    if not content:
        return False

    normalized_ext = ext.lower().strip()
    if normalized_ext == ".pdf":
        return content.startswith(b"%PDF-")
    elif normalized_ext == ".docx":
        return content.startswith(b"PK\x03\x04")
    return False


def extract_text_from_pdf(content: bytes) -> Tuple[str, bool, str]:
    """
    Extract readable text from PDF bytes using pypdf.
    Returns: (extracted_text, success_boolean, message)
    """
    try:
        reader = PdfReader(io.BytesIO(content))

        # Check for encrypted or password-protected PDFs
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
                if decrypted == 0:
                    return (
                        "",
                        False,
                        "PDF is password-protected and cannot be read without a password.",
                    )
            except Exception:
                return (
                    "",
                    False,
                    "PDF is password-protected and cannot be decrypted.",
                )

        extracted_pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(page_text.strip())

        full_text = "\n\n".join(extracted_pages).strip()

        if not full_text:
            return (
                "",
                False,
                "No readable text found. (Scanned or image-only PDFs require OCR, which is not supported).",
            )

        return (full_text, True, "Text extracted successfully.")

    except PdfReadError as pre:
        return ("", False, f"Malformed or corrupted PDF file: {str(pre)}")
    except Exception as e:
        return ("", False, f"Unable to parse PDF document: {str(e)}")


def extract_text_from_docx(content: bytes) -> Tuple[str, bool, str]:
    """
    Extract readable text from DOCX bytes using python-docx.
    Returns: (extracted_text, success_boolean, message)
    """
    try:
        doc = docx.Document(io.BytesIO(content))
        lines = []

        # Extract text from standard body paragraphs
        for p in doc.paragraphs:
            if p.text and p.text.strip():
                lines.append(p.text.strip())

        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    lines.append(" | ".join(row_cells))

        full_text = "\n\n".join(lines).strip()

        if not full_text:
            return ("", False, "Empty DOCX document: No readable text found.")

        return (full_text, True, "Text extracted successfully.")

    except Exception as e:
        return ("", False, f"Malformed or corrupted DOCX document: {str(e)}")
