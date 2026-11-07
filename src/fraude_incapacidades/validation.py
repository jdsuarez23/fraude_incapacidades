"""Validación técnica de archivos cargados (HU-01).

Los límites siguen el Entregable 1: PDF, tamaño máximo 5 MB, hasta 2 páginas.
El mismo contrato se replica en el frontend (frontend/src/lib/validation.js).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict

MAX_SIZE_BYTES = 5 * 1024 * 1024          # Entregable 1: 5 MB
MAX_PAGES = 2                              # Entregable 1: hasta 2 páginas
ALLOWED_EXTENSIONS = {".pdf"}              # Entregable 1: formato PDF
PDF_MAGIC = b"%PDF-"


@dataclass
class UploadValidation:
    valido: bool
    nombre: str
    tamano_bytes: int
    formato: str
    sha256: str
    paginas: int | None
    paginas_procesadas: int | None
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def count_pdf_pages(content: bytes) -> int | None:
    """Cuenta páginas con PyMuPDF; si no está disponible, usa una heurística."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(stream=content, filetype="pdf") as doc:
            return doc.page_count
    except Exception:
        pass
    matches = re.findall(rb"/Type\s*/Page(?![s\w])", content)
    return len(matches) or None


def validate_upload(filename: str, content: bytes) -> UploadValidation:
    errores: list[str] = []
    advertencias: list[str] = []
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    sha = hashlib.sha256(content).hexdigest()
    paginas: int | None = None

    if ext not in ALLOWED_EXTENSIONS:
        errores.append(f"Formato no soportado ({ext or 'sin extensión'}). Solo se admite PDF.")
    if len(content) == 0:
        errores.append("El archivo está vacío.")
    if len(content) > MAX_SIZE_BYTES:
        errores.append(
            f"El archivo pesa {len(content) / 1024 / 1024:.1f} MB y supera el máximo de "
            f"{MAX_SIZE_BYTES // 1024 // 1024} MB."
        )
    if ext == ".pdf" and content and not content.startswith(PDF_MAGIC):
        errores.append("El contenido no corresponde a un PDF real (firma de archivo inválida).")
    elif ext == ".pdf" and content:
        paginas = count_pdf_pages(content)
        if paginas is None:
            advertencias.append("No fue posible contar las páginas del PDF.")
        elif paginas > MAX_PAGES:
            errores.append(f"El PDF tiene {paginas} páginas; el máximo permitido es {MAX_PAGES}.")

    return UploadValidation(
        valido=not errores,
        nombre=filename,
        tamano_bytes=len(content),
        formato=ext.lstrip(".").upper() or "?",
        sha256=sha,
        paginas=paginas,
        paginas_procesadas=min(paginas, MAX_PAGES) if paginas else None,
        errores=errores,
        advertencias=advertencias,
    )
