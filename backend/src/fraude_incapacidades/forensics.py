"""Análisis forense determinista de metadatos de PDF (Entregable 1, vector 1).

Compara CreationDate y ModDate e identifica rastros de software de edición
gráfica (Photoshop, Illustrator, Canva, editores PDF en línea). Si los
metadatos están ausentes o aplanados por escaneo, registra una alerta
informativa leve SIN calificar el archivo como adulterado.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

EDITORES_GRAFICOS = (
    "photoshop", "illustrator", "canva", "figma", "gimp", "coreldraw", "affinity",
    "inkscape", "pixlr", "ilovepdf", "smallpdf", "sejda", "pdfescape", "pdf24",
    "soda pdf", "sodapdf", "pdffiller", "dochub",
)
# ModDate posterior a CreationDate por más de 1 día → hallazgo informativo
UMBRAL_MODIFICACION_DIAS = 1


def parse_pdf_date(value: str | None) -> datetime | None:
    """Convierte 'D:YYYYMMDDHHmmSS+hh'mm'' a datetime (sin zona)."""
    if not value:
        return None
    m = re.match(
        r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", value.strip())
    if not m:
        return None
    parts = [int(g) if g else d for g, d in zip(
        m.groups(), (0, 1, 1, 0, 0, 0))]
    try:
        return datetime(*parts)
    except ValueError:
        return None


def analyze_metadata(meta: dict | None) -> dict:
    meta = meta or {}
    creador = (meta.get("creator") or "").strip()
    productor = (meta.get("producer") or "").strip()
    creacion = parse_pdf_date(meta.get("creationDate"))
    modif = parse_pdf_date(meta.get("modDate"))
    alertas: list[dict] = []

    editor = next(
        (e for e in EDITORES_GRAFICOS if e in f"{creador} {productor}".lower()), None)
    aplanados = (not creador and not productor) or creacion is None

    dias_mod = None
    if creacion and modif:
        dias_mod = (modif - creacion).total_seconds() / 86400
        if dias_mod > UMBRAL_MODIFICACION_DIAS:
            alertas.append(
                {"nivel": "media", "texto": f"ModDate es {dias_mod:.0f} días posterior a CreationDate: el archivo fue modificado después de crearse."})
        elif dias_mod < -UMBRAL_MODIFICACION_DIAS:
            alertas.append(
                {"nivel": "media", "texto": "ModDate es anterior a CreationDate (inconsistencia de fechas)."})

    if editor:
        alertas.insert(
            0, {"nivel": "alta", "texto": f"Rastro de software de edición gráfica o manipulación: '{creador or productor}' (coincide con '{editor}')."})
        estado = "editor_grafico"
    elif aplanados:
        alertas.append(
            {"nivel": "leve", "texto": "Metadatos ausentes o aplanados por escaneo. Alerta informativa: no califica el archivo como adulterado."})
        estado = "aplanados"
    else:
        estado = "ok"

    return {
        "estado": estado,
        "creador": creador or None,
        "productor": productor or None,
        "fecha_creacion": creacion.isoformat(sep=" ") if creacion else None,
        "fecha_modificacion": modif.isoformat(sep=" ") if modif else None,
        "dias_entre_creacion_y_modificacion": round(dias_mod, 1) if dias_mod is not None else None,
        "editor_detectado": editor,
        "alertas": alertas,
    }


def detect_signature(page, region=(0.08, 0.80, 0.50, 0.95), min_ink=0.004) -> bool:
    """Segmentación simple: proporción de píxeles oscuros en la región esperada de firma/sello.

    Solo se usa con plantillas de ubicación conocida (certificados sintéticos).
    """
    import fitz

    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY)
    w, h = pix.width, pix.height
    x0, y0, x1, y1 = int(region[0] * w), int(region[1]
                                             * h), int(region[2] * w), int(region[3] * h)
    data = pix.samples
    dark = total = 0
    for y in range(y0, y1):
        row = data[y * w + x0: y * w + x1]
        dark += sum(1 for v in row if v < 110)
        total += len(row)
    return total > 0 and dark / total >= min_ink


def analyze_pdf(source: bytes | str, check_signature_region: bool = False) -> dict:
    """Devuelve metadatos analizados y, opcionalmente, la presencia de firma en la región de plantilla."""
    import fitz

    doc = fitz.open(stream=source, filetype="pdf") if isinstance(
        source, (bytes, bytearray)) else fitz.open(source)
    try:
        out = analyze_metadata(doc.metadata)
        text = "".join(p.get_text("text") for p in doc)
        out["texto_nativo"] = len(text.strip()) > 20
        out["paginas"] = doc.page_count
        if check_signature_region and doc.page_count:
            out["firma_visible"] = detect_signature(doc[0])
        return out
    finally:
        doc.close()
