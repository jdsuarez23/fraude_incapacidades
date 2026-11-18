from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import fitz


class PiiRedactionError(ValueError):
    """Raised when a PDF cannot be safely prepared for an AI analysis."""


_FIELD_BOUNDARY = (
    r"(?=\s*(?:[|;]\s*|$)|\s+(?:"
    r"paciente|nombre(?:s)?|c\.?\s*c\.?|c[eé]dula|documento|identificaci[oó]n|"
    r"tel[eé]fono|celular|m[oó]vil|direcci[oó]n|domicilio|residencia|"
    r"diagn[oó]stico|cie(?:-?10)?|fecha|eps|ips"
    r")\s*[:#\-])"
)
_NAME_LABEL = re.compile(
    r"\b(?:paciente|nombre(?:s)?(?:\s+completo)?(?:\s+y\s+apellidos)?"
    r"(?:\s+(?:del?|de)\s+(?:paciente|m[eé]dico|profesional|titular))?"
    r"|m[eé]dico|doctor(?:a)?|profesional(?:\s+emisor)?)"
    r"(?:\s*[:#\-]\s*|\s+)(.+?)" + _FIELD_BOUNDARY,
    re.IGNORECASE,
)
_NAME_LABEL_ONLY = re.compile(
    r"\b(?:paciente|nombre(?:s)?(?:\s+completo)?(?:\s+y\s+apellidos)?"
    r"(?:\s+(?:del?|de)\s+(?:paciente|m[eé]dico|profesional|titular))?"
    r"|m[eé]dico|doctor(?:a)?|profesional(?:\s+emisor)?)"
    r"\s*[:#\-]?\s*$",
    re.IGNORECASE,
)
_ID_LABEL = re.compile(
    r"\b(?:c[eé]dula|documento(?:\s+(?:de\s+)?identidad)?|"
    r"identificaci[oó]n|c\.?\s*c\.?)\s*"
    r"(?:n(?:u|ú)mero|n[°ºo.]*)?\s*[:#\-]?\s*"
    r"(\d[\d .\-]{4,16}\d)",
    re.IGNORECASE,
)
_ID_LABEL_ONLY = re.compile(
    r"\b(?:c[eé]dula|documento(?:\s+(?:de\s+)?identidad)?|"
    r"identificaci[oó]n|c\.?\s*c\.?)\s*"
    r"(?:n(?:u|ú)mero|n[°ºo.]*)?\s*[:#\-]?\s*$",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_LABEL = re.compile(
    r"\b(?:tel[eé]fono|celular|m[oó]vil|phone|contacto)\s*[:#\-]?\s*"
    r"(\+?[\d ()\-\.]{7,20}\d)",
    re.IGNORECASE,
)
_PHONE_LABEL_ONLY = re.compile(
    r"\b(?:tel[eé]fono|celular|m[oó]vil|phone|contacto)\s*[:#\-]?\s*$",
    re.IGNORECASE,
)
_ADDRESS_LABEL = re.compile(
    r"\b(?:direcci[oó]n(?:\s+(?:(?:del?|de)\s+)?paciente)?|"
    r"domicilio|residencia|address)\s*[:#\-]?\s*(.+?)" + _FIELD_BOUNDARY,
    re.IGNORECASE,
)
_ADDRESS_LABEL_ONLY = re.compile(
    r"\b(?:direcci[oó]n(?:\s+(?:(?:del?|de)\s+)?paciente)?|"
    r"domicilio|residencia|address)\s*[:#\-]?\s*$",
    re.IGNORECASE,
)
_COLOMBIAN_PHONE = re.compile(
    r"(?<!\d)(?:\+?57[\s.\-]?)?(?:3\d{2}|60[1-8])[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"
)
_DETECTION_PATTERNS = (
    _EMAIL,
    _PHONE_LABEL,
    _COLOMBIAN_PHONE,
    _ID_LABEL,
    _ADDRESS_LABEL,
)
_LABEL_ONLY_PATTERNS = (
    _NAME_LABEL_ONLY,
    _ID_LABEL_ONLY,
    _PHONE_LABEL_ONLY,
    _ADDRESS_LABEL_ONLY,
)


def _line_matches(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in _DETECTION_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span(1) if match.lastindex else match.span()
            spans.append((start, end))

    name = _NAME_LABEL.search(text)
    if name:
        spans.append(name.span(1))

    return spans


def _word_lines(words: list[tuple]) -> list[list[tuple]]:
    grouped: dict[tuple[int, int], list[tuple]] = {}
    for word in words:
        grouped.setdefault((word[5], word[6]), []).append(word)
    return sorted(
        (sorted(line, key=lambda word: word[7]) for line in grouped.values()),
        key=lambda line: (line[0][1], line[0][0]),
    )


def _sensitive_rectangles(page: fitz.Page) -> list[fitz.Rect]:
    words = page.get_text("words", sort=True)
    lines = _word_lines(words)
    rectangles: list[fitz.Rect] = []
    mask_next_line = False

    for line in lines:
        text_parts: list[str] = []
        offsets: list[tuple[int, int, tuple]] = []
        cursor = 0
        for word in line:
            value = word[4]
            if text_parts:
                cursor += 1
            start = cursor
            text_parts.append(value)
            cursor += len(value)
            offsets.append((start, cursor, word))
        line_text = " ".join(text_parts)

        if mask_next_line:
            rectangles.extend(fitz.Rect(word[:4]) for word in line)
            mask_next_line = False
            continue

        spans = _line_matches(line_text)
        if any(pattern.search(line_text) for pattern in _LABEL_ONLY_PATTERNS):
            mask_next_line = True

        for start, end in spans:
            rectangles.extend(
                fitz.Rect(word[:4])
                for word_start, word_end, word in offsets
                if word_start < end and word_end > start
            )

    return rectangles


def redact_pdf_for_analysis(source: Path, destination: Path) -> None:
    """Create a PDF copy with direct identifiers and all embedded images removed."""
    try:
        doc = fitz.open(source)
    except Exception as exc:
        raise PiiRedactionError("No se pudo abrir el PDF para anonimizarlo.") from exc

    try:
        if not doc.page_count:
            raise PiiRedactionError("El PDF no contiene páginas para anonimizar.")

        for page in doc:
            if not page.get_text("text").strip():
                raise PiiRedactionError(
                    "No se puede analizar este PDF escaneado de forma segura: "
                    "requiere OCR local antes de enviarlo al agente."
                )

            rectangles = _sensitive_rectangles(page)
            for widget in list(page.widgets() or ()):
                page.delete_widget(widget)
            for annotation in list(page.annots() or ()):
                page.delete_annot(annotation)
            for image in page.get_images(full=True):
                page.delete_image(image[0])

            for rectangle in rectangles:
                page.add_redact_annot(rectangle, fill=(0, 0, 0), cross_out=False)
            if rectangles:
                page.apply_redactions(images=2)

        metadata = doc.metadata
        for key in (
            "title",
            "author",
            "subject",
            "keywords",
            "creator",
            "producer",
            "creationDate",
            "modDate",
            "trapped",
        ):
            metadata[key] = ""
        doc.set_metadata(metadata)
        doc.save(destination, garbage=4, deflate=True)
    finally:
        doc.close()


@contextmanager
def sanitized_pdf_for_analysis(source: Path) -> Iterator[Path]:
    """Yield a temporary, locally redacted PDF and remove it after analysis."""
    with tempfile.TemporaryDirectory(prefix="fraude_pii_") as directory:
        sanitized = Path(directory) / "documento_anonimizado.pdf"
        redact_pdf_for_analysis(source, sanitized)
        yield sanitized
