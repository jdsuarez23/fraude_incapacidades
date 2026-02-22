from __future__ import annotations

import json
from crewai.tools import BaseTool


class ADRESVerificationTool(BaseTool):
    name: str = "Verificacion ADRES BDUA"
    description: str = (
        "Verifica si un paciente está afiliado al Sistema General de Seguridad Social "
        "en Salud de Colombia (SGSSS) consultando la BDUA de ADRES. "
        "Recibe como input un JSON string con: 'tipo_documento' (CC, CE, TI, PA, RC, etc.) "
        "y 'numero_documento' del paciente. "
        "Intenta múltiples endpoints de ADRES para máxima compatibilidad."
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

            # Map to ADRES type codes
            tipo_map_adres = {
                "CC": "CC", "CE": "CE", "TI": "TI",
                "PA": "PA", "RC": "RC", "MS": "MS",
            }
            tipo_adres = tipo_map_adres.get(tipo_doc, tipo_doc)

            try:
                import requests

                endpoints = [
                    {
                        "url": "https://aplicaciones.adres.gov.co/BDUA_Internet/Pages/RespuestaConsulta.aspx",
                        "method": "GET",
                        "params": {
                            "tokenId": "",
                            "tipoId": tipo_adres,
                            "txtNumero": numero_doc,
                        },
                    },
                    {
                        "url": "https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA",
                        "method": "GET",
                        "params": {
                            "tipoDocumento": tipo_adres,
                            "numero": numero_doc,
                        },
                    },
                ]

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8",
                }

                last_error = None
                for endpoint in endpoints:
                    try:
                        response = requests.get(
                            endpoint["url"],
                            params=endpoint["params"],
                            headers=headers,
                            timeout=20,
                            verify=True,
                            allow_redirects=True,
                        )

                        if response.status_code == 200:
                            content_type = response.headers.get("Content-Type", "")

                            # Try JSON first
                            if "json" in content_type:
                                try:
                                    result_data = response.json()
                                    if result_data and isinstance(result_data, dict):
                                        estado = result_data.get("estado", result_data.get("Estado", ""))
                                        eps = result_data.get("eps", result_data.get("EPS", result_data.get("entidad", "")))
                                        regimen = result_data.get("regimen", result_data.get("Regimen", ""))

                                        if estado or eps:
                                            return json.dumps({
                                                "verificado": True,
                                                "fuente": "ADRES/BDUA (consulta automatizada)",
                                                "url_consulta": "https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA",
                                                "datos": {
                                                    "estado_afiliacion": estado or "Dato no disponible",
                                                    "eps": eps or "Dato no disponible",
                                                    "regimen": regimen or "Dato no disponible",
                                                },
                                                "riesgo": "BAJO"
                                            }, ensure_ascii=False, indent=2)
                                except (json.JSONDecodeError, ValueError):
                                    pass

                            # If HTML response, check if it contains affiliation data
                            body = response.text[:3000].lower()
                            if "activo" in body and ("contributivo" in body or "subsidiado" in body):
                                return json.dumps({
                                    "verificado": True,
                                    "fuente": "ADRES/BDUA (consulta web)",
                                    "url_consulta": "https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA",
                                    "datos": {
                                        "estado_afiliacion": "Activo (detectado en respuesta HTML)",
                                        "regimen": "Contributivo" if "contributivo" in body else "Subsidiado",
                                    },
                                    "riesgo": "BAJO"
                                }, ensure_ascii=False, indent=2)

                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                        last_error = str(e)
                        continue
                    except Exception as e:
                        last_error = str(e)
                        continue

                # If all endpoints failed or returned unstructured data
                return json.dumps({
                    "verificado": None,
                    "fuente": "ADRES/BDUA",
                    "nota": "El servicio ADRES está protegido por Google reCAPTCHA Enterprise. "
                            "No es posible la consulta automatizada. Es OBLIGATORIO que el validador humano lo consulte.",
                    "recomendacion": f"Verificar manualmente en: https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA "
                                    f"con documento {tipo_doc} {numero_doc}",
                    "riesgo": "NO_APLICA"
                }, ensure_ascii=False, indent=2)

            except ImportError:
                return json.dumps({
                    "verificado": None,
                    "nota": "Módulo 'requests' no instalado.",
                    "riesgo": "NO_APLICA"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error en verificación ADRES: {str(e)}"}, ensure_ascii=False)
