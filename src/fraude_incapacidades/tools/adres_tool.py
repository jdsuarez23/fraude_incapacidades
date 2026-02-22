from __future__ import annotations

import json
from crewai.tools import BaseTool


class ADRESVerificationTool(BaseTool):
    name: str = "Verificacion ADRES BDUA"
    description: str = (
        "Verifica si un paciente/usuario está afiliado al Sistema General de Seguridad Social "
        "en Salud de Colombia (SGSSS) consultando la BDUA de ADRES. "
        "Recibe como input un JSON string con: 'tipo_documento' (CC, CE, TI, PA, RC, etc.) "
        "y 'numero_documento' del paciente. "
        "Retorna el estado de afiliación, EPS y régimen (https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA)."
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

            try:
                import requests

                # ADRES BDUA public consultation
                url = "https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA"

                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA",
                    "Origin": "https://servicios.adres.gov.co",
                }

                # The ADRES BDUA service uses a REST API
                params = {
                    "tipoDocumento": tipo_doc,
                    "numero": numero_doc,
                }

                response = requests.get(url, params=params, headers=headers, timeout=15)

                if response.status_code == 200:
                    try:
                        result_data = response.json()
                        if result_data and isinstance(result_data, dict):
                            estado = result_data.get("estado", result_data.get("Estado", ""))
                            eps = result_data.get("eps", result_data.get("EPS", result_data.get("entidad", "")))
                            regimen = result_data.get("regimen", result_data.get("Regimen", ""))

                            if estado or eps:
                                return json.dumps({
                                    "verificado": True,
                                    "fuente": "ADRES/BDUA",
                                    "url_consulta": "https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA",
                                    "datos": {
                                        "estado_afiliacion": estado or "Dato no disponible",
                                        "eps": eps or "Dato no disponible",
                                        "regimen": regimen or "Dato no disponible",
                                    },
                                    "riesgo": "BAJO"
                                }, ensure_ascii=False, indent=2)
                        
                        # If no structured data returned
                        return json.dumps({
                            "verificado": None,
                            "fuente": "ADRES/BDUA",
                            "alerta": "Servicio ADRES respondió pero sin datos estructurados. "
                                      "El servicio puede requerir interacción manual (CAPTCHA o sesión).",
                            "recomendacion": f"Verificar manualmente en: https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA "
                                            f"con documento {tipo_doc} {numero_doc}",
                            "riesgo": "INDETERMINADO"
                        }, ensure_ascii=False, indent=2)

                    except (json.JSONDecodeError, ValueError):
                        # HTML response - service requires browser interaction
                        return json.dumps({
                            "verificado": None,
                            "fuente": "ADRES/BDUA",
                            "alerta": "Servicio ADRES requiere interacción de navegador (posible CAPTCHA). "
                                      "No se puede consultar de forma automatizada.",
                            "recomendacion": f"Verificar manualmente en: https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA "
                                            f"con documento {tipo_doc} {numero_doc}",
                            "riesgo": "INDETERMINADO"
                        }, ensure_ascii=False, indent=2)
                else:
                    return json.dumps({
                        "verificado": None,
                        "fuente": "ADRES/BDUA",
                        "alerta": f"Servicio ADRES respondió con código {response.status_code}.",
                        "recomendacion": f"Verificar manualmente en: https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA "
                                        f"con documento {tipo_doc} {numero_doc}",
                        "riesgo": "INDETERMINADO"
                    }, ensure_ascii=False, indent=2)

            except ImportError:
                return json.dumps({
                    "verificado": None,
                    "alerta": "Módulo 'requests' no instalado.",
                    "recomendacion": f"Verificar manualmente en: https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA "
                                    f"con documento {tipo_doc} {numero_doc}",
                    "riesgo": "INDETERMINADO"
                }, ensure_ascii=False, indent=2)

            except Exception as e:
                return json.dumps({
                    "verificado": None,
                    "alerta": f"Error conectando con ADRES: {str(e)}",
                    "recomendacion": f"Verificar manualmente en: https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA "
                                    f"con documento {tipo_doc} {numero_doc}",
                    "riesgo": "INDETERMINADO"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error en verificación ADRES: {str(e)}"}, ensure_ascii=False)
