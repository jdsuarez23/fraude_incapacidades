from __future__ import annotations

import os
import json
import base64
from pathlib import Path
import fitz  # PyMuPDF
from crewai.tools import BaseTool

# We'll use OpenAI's API directly inside this tool to parse the messy PDF explicitly
import openai

class PDFForensicExtractTool(BaseTool):
    name: str = "Extraccion Forense y Estructuracion PDF"
    description: str = (
        "Extrae el texto, imágenes de logos y metadatos de un PDF. "
        "Luego utiliza un LLM internamente para ordenar todo el texto en un "
        "JSON estructurado (paciente, cédula, médico, registro, eps, fechas, códigos CIE). "
        "Recibe la ruta absoluta del documento y retorna el JSON estructurado + análisis pericial."
    )

    def _run(self, file_path: str) -> str:
        try:
            path = Path(file_path.strip().strip("'\""))
            if not path.exists():
                return json.dumps({"error": f"Archivo no encontrado: {file_path}"}, ensure_ascii=False)

            doc = fitz.open(str(path))

            full_text = ""
            images_found = 0
            # Extraer texto y contar imágenes (potenciales logos)
            for page in doc:
                full_text += page.get_text("text") + "\n"
                images_found += len(page.get_images(full=True))

            # --- Metadata & Forensic extraction ---
            raw_meta = doc.metadata or {}
            metadata = {
                "creador_software": raw_meta.get("creator", ""),
                "productor_software": raw_meta.get("producer", ""),
                "fecha_creacion": raw_meta.get("creationDate", ""),
                "fecha_modificacion": raw_meta.get("modDate", ""),
            }

            fonts_found = set()
            for page in doc:
                for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]:
                    if block.get("type") == 0:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                fonts_found.add(span.get("font", "unknown"))

            alertas_forenses = []
            creator = metadata["creador_software"].lower()
            if any(kw in creator for kw in ["canva", "adobe", "word", "writer", "photoshop"]):
                alertas_forenses.append(f"Software sospechoso: creado con {creator} (no es un HIS de salud).")
            if metadata["fecha_creacion"] and metadata["fecha_modificacion"] and metadata["fecha_creacion"] != metadata["fecha_modificacion"]:
                alertas_forenses.append("Fecha de creación distinta a fecha de modificación (posible edición posterior).")
            if len(fonts_found) > 4:
                alertas_forenses.append(f"Demasiadas tipografías detectadas ({len(fonts_found)}). Posible montaje por capas.")
            if images_found == 0:
                alertas_forenses.append("Sin logo detectado (0 imágenes). Formato inusual.")

            doc.close()

            # --- LLM Structured Extraction ---
            # Instead of passing messy text to the Crew Agent, we use OpenAI here to extract accurate structured data
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return json.dumps({"error": "OPENAI_API_KEY no encontrada. Requerida para estructuración inteligente."}, ensure_ascii=False)
            
            client = openai.OpenAI(api_key=api_key)

            system_prompt = (
                "Eres un extrator experto de certificados médicos colombianos. "
                "Lee el siguiente texto crudo y extrae EXACTAMENTE estos datos en formato JSON. "
                "Responde SOLAMENTE el JSON, sin formato markdown extra ni preámbulos. "
                "Estructura esperada: "
                "{"
                '"paciente_nombre": "", '
                '"paciente_cedula": "", '
                '"medico_nombre": "", '
                '"medico_registro": "", '
                '"eps_o_ips_logo_mencion": "", '
                '"codigo_cie10": "", '
                '"dias_incapacidad": 0'
                "}"
            )

            response = client.chat.completions.create(
                model="gpt-4o",  # we enforce strict json matching
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"TEXTO CRUDO:\n{full_text}"}
                ],
                temperature=0.0
            )

            llm_result_text = response.choices[0].message.content or "{}"
            llm_result_text = llm_result_text.strip("`").replace("json\n", "")

            try:
                structured_data = json.loads(llm_result_text)
            except json.JSONDecodeError:
                structured_data = {
                    "error_extraccion_llm": "El LLM no devolvió formato JSON válido.",
                    "texto_crudo": full_text[:500] + "..."
                }

            # --- Final Assembly ---
            final_report = {
                "datos_estructurados": structured_data,
                "hallazgos_forenses_visuales": {
                    "cantidad_logos_o_imagenes": images_found,
                    "software_creador": metadata["creador_software"],
                    "alertas_forenses_automaticas": alertas_forenses,
                },
                "texto_completo_para_referencia": full_text
            }

            return json.dumps(final_report, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error procesando archivo PDF: {str(e)}"}, ensure_ascii=False)
