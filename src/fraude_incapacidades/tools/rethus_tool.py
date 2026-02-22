from __future__ import annotations

import json
from crewai.tools import BaseTool


class RETHUSVerificationTool(BaseTool):
    name: str = "Verificacion RETHUS SISPRO"
    description: str = (
        "Verifica si un profesional de salud está registrado en el RETHUS "
        "(Registro Único Nacional del Talento Humano en Salud) del SISPRO Colombia. "
        "Recibe como input un JSON string con: 'tipo_documento' (CC, CE, PA, etc.) "
        "y 'numero_documento' del profesional. "
        "Consulta el servicio web público del SISPRO y retorna los resultados (https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx)."
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

            # Map document types to SISPRO codes
            tipo_map = {"CC": "1", "CE": "2", "PA": "3", "TI": "4", "RC": "5"}
            tipo_code = tipo_map.get(tipo_doc, "1")

            try:
                import requests
                
                # SISPRO RETHUS public consultation endpoint
                url = "https://web.sispro.gov.co/THS/Api/ConsultaPublica/BuscarTHSxIdentificacion"
                
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx",
                    "Origin": "https://web.sispro.gov.co",
                }

                payload = {
                    "TipoIdentificacion": tipo_code,
                    "NumeroIdentificacion": numero_doc,
                }

                response = requests.post(url, json=payload, headers=headers, timeout=15)

                if response.status_code == 200:
                    result_data = response.json()
                    if result_data and isinstance(result_data, list) and len(result_data) > 0:
                        profesional = result_data[0]
                        return json.dumps({
                            "verificado": True,
                            "fuente": "RETHUS/SISPRO",
                            "url_consulta": "https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx",
                            "datos": {
                                "nombre": profesional.get("NombreCompleto", "No disponible"),
                                "profesion": profesional.get("Profesion", "No disponible"),
                                "estado_registro": profesional.get("EstadoRegistro", "No disponible"),
                                "numero_registro": profesional.get("NumeroRegistro", "No disponible"),
                            },
                            "riesgo": "BAJO" if profesional.get("EstadoRegistro", "").upper() == "ACTIVO" else "ALTO"
                        }, ensure_ascii=False, indent=2)
                    else:
                        return json.dumps({
                            "verificado": False,
                            "fuente": "RETHUS/SISPRO",
                            "url_consulta": "https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx",
                            "alerta": f"Profesional con {tipo_doc} {numero_doc} NO encontrado en RETHUS. "
                                      "Puede ser documento incorrecto o profesional no registrado.",
                            "riesgo": "ALTO"
                        }, ensure_ascii=False, indent=2)
                else:
                    return json.dumps({
                        "verificado": None,
                        "fuente": "RETHUS/SISPRO",
                        "alerta": f"Servicio SISPRO respondió con código {response.status_code}. "
                                  "El servicio puede estar temporalmente no disponible.",
                        "recomendacion": f"Verificar manualmente en: https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx",
                        "riesgo": "INDETERMINADO"
                    }, ensure_ascii=False, indent=2)

            except ImportError:
                return json.dumps({
                    "verificado": None,
                    "alerta": "Módulo 'requests' no instalado. No se puede consultar RETHUS.",
                    "recomendacion": f"Verificar manualmente en: https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx con {tipo_doc} {numero_doc}",
                    "riesgo": "INDETERMINADO"
                }, ensure_ascii=False, indent=2)

            except requests.exceptions.Timeout:
                return json.dumps({
                    "verificado": None,
                    "alerta": "Timeout al consultar SISPRO. Servicio no disponible o muy lento.",
                    "recomendacion": f"Verificar manualmente en: https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx",
                    "riesgo": "INDETERMINADO"
                }, ensure_ascii=False, indent=2)

            except Exception as e:
                return json.dumps({
                    "verificado": None,
                    "alerta": f"Error conectando con SISPRO: {str(e)}",
                    "recomendacion": f"Verificar manualmente en: https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx",
                    "riesgo": "INDETERMINADO"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error en verificación RETHUS: {str(e)}"}, ensure_ascii=False)
