"""Compatibilidad para imports históricos de validación de cargas."""

from .domain.upload_validation import (
    ALLOWED_EXTENSIONS,
    MAX_PAGES,
    MAX_SIZE_BYTES,
    PDF_MAGIC,
    UploadValidation,
    count_pdf_pages,
    validate_upload,
)

__all__ = [
    "ALLOWED_EXTENSIONS",
    "MAX_PAGES",
    "MAX_SIZE_BYTES",
    "PDF_MAGIC",
    "UploadValidation",
    "count_pdf_pages",
    "validate_upload",
]
