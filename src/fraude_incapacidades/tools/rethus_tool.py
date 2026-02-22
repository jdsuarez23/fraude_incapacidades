from __future__ import annotations

import json
from crewai.tools import BaseTool
import time


class RETHUSVerificationTool(BaseTool):
    name: str = "Verificacion RETHUS SISPRO"
    description: str = (
        "Verifica si un profesional de salud está registrado en el RETHUS "
        "(Registro Único Nacional del Talento Humano en Salud) del SISPRO Colombia. "
        "Recibe como input un JSON string con: 'tipo_documento' (CC, CE, PA, etc.) "
        "y 'numero_documento' del profesional. "
        "Intenta acceder a la página web real mediante Playwright y bypass del CAPTCHA."
    )

    def _run(self, input_data: str) -> str:
        try:
            try:
                data = json.loads(input_data)
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Input debe ser JSON con campos: tipo_documento, numero_documento",
                    "ejemplo": '{"tipo_documento": "CC", "numero_documento": "12345678"}'
                }, ensure_ascii=False, indent=2)

            tipo_doc = data.get("tipo_documento", "CC").upper().strip()
            numero_doc = str(data.get("numero_documento", "")).strip()

            if not numero_doc:
                return json.dumps({"error": "Número de documento vacío"}, ensure_ascii=False)

            # Map to RETHUS dropdown values
            tipo_map = {"CC": "CC", "CE": "CE", "PA": "PA", "TI": "TI", "PE": "PE", "PT": "PT"}
            tipo_val = tipo_map.get(tipo_doc, "CC")

            # Múltiples reintentos con Playwright
            try:
                from playwright.sync_api import sync_playwright
                
                with sync_playwright() as p:
                    # Usar chromium headless
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        viewport={"width": 1280, "height": 800}
                    )
                    page = context.new_page()
                    try:
                        # 1. Navegar a la página
                        page.goto("https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx", timeout=30000)
                        page.wait_for_selector("input#ctl00_cntContenido_txtNumeroIdentificacion", timeout=15000)
                        
                        # 2. Leer CAPTCHA client-side variable bypass
                        captcha_val = page.evaluate("window.tc")
                        
                        # 3. Llenar formulario
                        page.select_option("select#ctl00_cntContenido_ddlTipoIdentificacion", tipo_val)
                        page.fill("input#ctl00_cntContenido_txtNumeroIdentificacion", numero_doc)
                        page.fill("input#ctl00_cntContenido_txtCatpchaConfirmation", str(captcha_val))
                        
                        # 4. Enviar
                        page.click("input#ctl00_cntContenido_btnVerificarIdentificacion")
                        
                        # 5. Esperar resultados o mensajes
                        time.sleep(4) # Esperar a que el UpdatePanel responda
                        
                        # 6. Extraer resultados
                        page_text = page.inner_text("body").lower()
                        html_content = page.content()
                        
                        # Si encuentra 'no se encontraron registros'
                        if "no se han encontrado resultados" in page_text or "no se encontrar" in page_text:
                             return json.dumps({
                                "verificado": False,
                                "fuente": "RETHUS/SISPRO (Raspado Web Automatizado)",
                                "alerta": f"Profesional con {tipo_doc} {numero_doc} NO encontrado en RETHUS. Esto es MUY SOSPECHOSO.",
                                "riesgo": "ALTO"
                            }, ensure_ascii=False, indent=2)
                        
                        # Si encuentra la tabla de resultados
                        elif "nombres y apellidos" in page_text and "profesión" in page_text:
                            # Buscar elementos de la tabla usando CSS
                            try:
                                nombre = page.locator("table#ctl00_cntContenido_grdResultadosBasicos tr:nth-child(2) td:nth-child(2)").inner_text().strip()
                                profesion = page.locator("table#ctl00_cntContenido_grdResultadosBasicos tr:nth-child(2) td:nth-child(3)").inner_text().strip()
                                estado = page.locator("table#ctl00_cntContenido_grdResultadosAcademicos tr:nth-child(2) td:nth-child(4)").inner_text().strip()
                            except:
                                nombre = "Presente en tabla"
                                profesion = "Presente en tabla"
                                estado = "Presente en tabla"
                                
                            return json.dumps({
                                "verificado": True,
                                "fuente": "RETHUS/SISPRO (Raspado Web Automatizado)",
                                "datos": {
                                    "nombre": nombre,
                                    "profesion": profesion,
                                    "estado": estado
                                },
                                "riesgo": "BAJO"
                            }, ensure_ascii=False, indent=2)
                            
                        else:
                            # Caso indeterminado, tal vez falló la consulta temporalmente
                            return json.dumps({
                                "verificado": None,
                                "fuente": "RETHUS/SISPRO",
                                "nota": "El servicio RETHUS respondió pero el resultado fue ambiguo. No se penalizará.",
                                "recomendacion": f"Verificar manualmente en: https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx con documento {tipo_doc} {numero_doc}",
                                "detalle_tecnico": "Texto extraído: " + page_text[:200],
                                "riesgo": "NO_APLICA"
                            }, ensure_ascii=False, indent=2)

                    except Exception as e:
                        # Error de Playwright
                        return json.dumps({
                            "verificado": None,
                            "fuente": "RETHUS/SISPRO",
                            "nota": "El portal RETHUS presentó fallos técnicos temporales (timeout).",
                            "detalle_tecnico": str(e),
                            "riesgo": "NO_APLICA"
                        }, ensure_ascii=False, indent=2)
                    finally:
                        browser.close()

            except ImportError:
                return json.dumps({
                    "verificado": None,
                    "nota": "Módulo 'playwright' no instalado para extracción web.",
                    "riesgo": "NO_APLICA"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error crítico en verificación RETHUS: {str(e)}"}, ensure_ascii=False)
