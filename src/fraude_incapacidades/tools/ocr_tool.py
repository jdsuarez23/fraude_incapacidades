from __future__ import annotations

import os
import json
import base64
from pathlib import Path
import fitz  # PyMuPDF
from crewai.tools import BaseTool
import openai


class PDFForensicExtractTool(BaseTool):
    name: str = "Extraccion Forense y Estructuracion PDF"
    description: str = (
        "Analiza un archivo PDF de incapacidad médica usando visión artificial (GPT-4o Vision). "
        "Renderiza las páginas como imágenes de alta resolución y las envía al modelo de visión "
        "para extraer: logos, nombre y documento del paciente, nombre y registro del médico, "
        "EPS/IPS, código CIE-10, días de incapacidad, fechas, y una evaluación visual del documento. "
        "También extrae metadatos forenses (software creador, fuentes tipográficas). "
        "Recibe la ruta absoluta del archivo."
    )

    def _run(self, file_path: str) -> str:
        try:
            path = Path(file_path.strip().strip("'\""))
            if not path.exists():
                return json.dumps({"error": f"Archivo no encontrado: {file_path}"}, ensure_ascii=False)

            file_ext = path.suffix.lower()
            page_images_b64 = []
            full_text = ""
            images_found = 0
            metadata = {
                "creador_software": "",
                "productor_software": "",
                "fecha_creacion": "",
                "fecha_modificacion": "",
            }
            fonts_found = set()
            alertas_forenses = []

            if file_ext == '.pdf':
                doc = fitz.open(str(path))
                raw_meta = doc.metadata or {}
                metadata.update({
                    "creador_software": raw_meta.get("creator", ""),
                    "productor_software": raw_meta.get("producer", ""),
                    "fecha_creacion": raw_meta.get("creationDate", ""),
                    "fecha_modificacion": raw_meta.get("modDate", ""),
                })
                for i, page in enumerate(doc):
                    if i >= 3: break
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat)
                    page_images_b64.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
                    full_text += page.get_text("text") + "\n"
                    images_found += len(page.get_images(full=True))
                    
                    for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", []):
                        if block.get("type") == 0:
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    fonts_found.add(span.get("font", "unknown"))
                doc.close()
                
                creator = metadata["creador_software"].lower()
                producer = metadata.get("productor_software", "").lower()
                if any(kw in creator or kw in producer for kw in ["canva", "photoshop", "illustrator", "figma", "gimp"]):
                    alertas_forenses.append(f"⚠️ Software de DISEÑO GRÁFICO detectado: '{metadata['creador_software']}'. Sugiere fabricación manual.")
                if len(fonts_found) > 8:
                    alertas_forenses.append(f"⚠️ Exceso de tipografías ({len(fonts_found)} fuentes). Posible manipulación por capas.")
                if images_found == 0:
                    alertas_forenses.append("⚠️ Sin logo ni imagen detectada (0 imágenes). Los certificados oficiales suelen tener logos.")

            elif file_ext in ['.png', '.jpg', '.jpeg']:
                with open(str(path), "rb") as img_file:
                    page_images_b64.append(base64.b64encode(img_file.read()).decode("utf-8"))
                images_found = 1
                metadata["creador_software"] = "Imagen directa"
                
            elif file_ext in ['.docx', '.doc']:
                try:
                    import docx2txt
                    full_text = docx2txt.process(str(path))
                    metadata["creador_software"] = "Microsoft Word / Procesador de texto"
                except Exception as e:
                    full_text = f"Error extrayendo DOCX: {e}"
                    alertas_forenses.append("Error procesando formato DOCX.")
            else:
                return json.dumps({"error": f"Formato no soportado: {file_ext}"}, ensure_ascii=False)

            # ── 4. GPT-4o Vision Analysis ──
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return json.dumps({"error": "OPENAI_API_KEY no encontrada."}, ensure_ascii=False)

            client = openai.OpenAI(api_key=api_key)

            vision_prompt = (
                "Eres un perito forense especialista en documentos médicos colombianos. "
                "Analiza visualmente este certificado de incapacidad médica.\n\n"
                "EXTRAE la siguiente información en formato JSON estricto:\n"
                "{\n"
                '  "paciente_nombre": "nombre completo del paciente",\n'
                '  "paciente_cedula": "número de cédula/documento del paciente",\n'
                '  "medico_nombre": "nombre completo del médico",\n'
                '  "medico_cedula": "cédula o registro profesional del médico",\n'
                '  "eps_o_ips": "nombre de la EPS o IPS que aparece en el documento o logo",\n'
                '  "codigo_cie10": "código CIE-10 si aparece",\n'
                '  "diagnostico_texto": "descripción del diagnóstico",\n'
                '  "dias_incapacidad": número de días,\n'
                '  "fecha_inicio": "fecha de inicio de la incapacidad",\n'
                '  "fecha_fin": "fecha fin de la incapacidad",\n'
                '  "logo_detectado": "descripción del logo que ves (ej: Logo de Sanitas, Logo de Sura, etc.)",\n'
                '  "tiene_firma": true/false,\n'
                '  "tiene_sello": true/false,\n'
                '  "evaluacion_visual": "tu evaluación profesional del aspecto visual del documento: '
                '¿parece un formato institucional real? ¿El logo corresponde a la EPS/IPS mencionada? '
                '¿Hay señales de edición visual (parches, texto superpuesto, alineación rota)?"\n'
                "}\n\n"
                "Si no puedes leer algún dato, escribe 'No legible' o 'No presente'.\n"
                "Responde SOLAMENTE el JSON, sin markdown ni preámbulos."
            )

            # Build the messages with image content
            content_parts = [{"type": "text", "text": vision_prompt}]
            for i, img_b64 in enumerate(page_images_b64):
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}",
                        "detail": "high"
                    }
                })

            # Also include the raw text as backup in case Vision misses something
            if full_text.strip():
                content_parts.append({
                    "type": "text",
                    "text": f"\n\nTEXTO EXTRAÍDO POR OCR (referencia adicional):\n{full_text[:3000]}"
                })

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content_parts}],
                max_tokens=2000,
                temperature=0.0
            )

            llm_result_text = response.choices[0].message.content or "{}"
            # Clean markdown fences if present
            llm_result_text = llm_result_text.strip()
            if llm_result_text.startswith("```"):
                llm_result_text = llm_result_text.split("\n", 1)[1] if "\n" in llm_result_text else llm_result_text
            if llm_result_text.endswith("```"):
                llm_result_text = llm_result_text[:-3]
            llm_result_text = llm_result_text.strip()

            try:
                structured_data = json.loads(llm_result_text)
            except json.JSONDecodeError:
                structured_data = {
                    "error_extraccion_vision": "GPT-4o Vision no devolvió JSON válido.",
                    "respuesta_cruda": llm_result_text[:500],
                    "texto_ocr_backup": full_text[:1000]
                }

            # ── 5. Final Assembly ──
            final_report = {
                "datos_estructurados": structured_data,
                "hallazgos_forenses": {
                    "cantidad_imagenes_en_pdf": images_found,
                    "software_creador": metadata["creador_software"] or "No especificado",
                    "productor": metadata["productor_software"] or "No especificado",
                    "fecha_creacion_pdf": metadata["fecha_creacion"],
                    "fecha_modificacion_pdf": metadata["fecha_modificacion"],
                    "fuentes_tipograficas": sorted(list(fonts_found)),
                    "alertas_forenses_automaticas": alertas_forenses,
                },
                "paginas_analizadas_por_vision": len(page_images_b64),
            }

            return json.dumps(final_report, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error procesando archivo PDF: {str(e)}"}, ensure_ascii=False)
