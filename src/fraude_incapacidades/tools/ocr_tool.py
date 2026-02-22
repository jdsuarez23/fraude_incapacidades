from __future__ import annotations

import json
import fitz  # PyMuPDF
from pathlib import Path
from crewai.tools import BaseTool


class PDFForensicTool(BaseTool):
    name: str = "Extraccion Forense PDF"
    description: str = (
        "Extrae texto, metadatos forenses (creador, software, fechas), "
        "fuentes tipográficas y cantidad de páginas desde un archivo PDF. "
        "Recibe la ruta absoluta del archivo. Retorna un JSON con toda la información."
    )

    def _run(self, file_path: str) -> str:
        try:
            path = Path(file_path.strip().strip("'\""))
            if not path.exists():
                return json.dumps({"error": f"Archivo no encontrado: {file_path}"}, ensure_ascii=False)

            doc = fitz.open(str(path))

            # --- Text extraction ---
            full_text = ""
            for page in doc:
                full_text += page.get_text("text")

            # --- Metadata extraction ---
            raw_meta = doc.metadata or {}
            metadata = {
                "titulo": raw_meta.get("title", ""),
                "autor": raw_meta.get("author", ""),
                "creador_software": raw_meta.get("creator", ""),
                "productor_software": raw_meta.get("producer", ""),
                "fecha_creacion": raw_meta.get("creationDate", ""),
                "fecha_modificacion": raw_meta.get("modDate", ""),
                "formato": raw_meta.get("format", ""),
                "encriptado": raw_meta.get("encryption", ""),
            }

            # --- Font detection (forensic) ---
            fonts_found = set()
            for page in doc:
                for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]:
                    if block.get("type") == 0:  # text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                font_name = span.get("font", "unknown")
                                font_size = span.get("size", 0)
                                fonts_found.add(f"{font_name} ({font_size:.1f}pt)")

            # --- Anomaly pre-check ---
            alertas_forenses = []
            creator = metadata["creador_software"].lower()
            producer = metadata["productor_software"].lower()

            if "adobe" in creator or "adobe" in producer:
                alertas_forenses.append("Software Adobe detectado en metadatos - verificar si es edición o creación")
            if "canva" in creator or "canva" in producer:
                alertas_forenses.append("Canva detectado como creador - podría indicar diseño manual del documento")
            if any(kw in creator or kw in producer for kw in ["word", "libreoffice", "writer", "docs"]):
                alertas_forenses.append("Procesador de texto detectado como creador - NO es un sistema hospitalario típico")
            if metadata["fecha_creacion"] and metadata["fecha_modificacion"]:
                if metadata["fecha_creacion"] != metadata["fecha_modificacion"]:
                    alertas_forenses.append("Fecha de creación y modificación DIFIEREN - posible edición posterior")
            if len(fonts_found) > 4:
                alertas_forenses.append(f"{len(fonts_found)} fuentes distintas detectadas - posible manipulación tipográfica")

            doc.close()

            result = {
                "texto_extraido": full_text.strip(),
                "metadatos": metadata,
                "fuentes_detectadas": sorted(list(fonts_found)),
                "numero_paginas": doc.page_count if hasattr(doc, 'page_count') else len(doc),
                "alertas_forenses_automaticas": alertas_forenses,
            }

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error procesando archivo: {str(e)}"}, ensure_ascii=False)
