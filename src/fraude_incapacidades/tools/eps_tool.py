from __future__ import annotations

import json
from crewai.tools import BaseTool


# Lista Exhaustiva de EPS autorizadas en Colombia (Régimen Contributivo y Subsidiado)
# Se incluyen variaciones comunes de nombre (siglas, nombres completos).
EPS_COLOMBIA = {
    "SURA": ["sura", "eps suramericana", "suramericana", "eps sura"],
    "SANITAS": ["sanitas", "eps sanitas"],
    "NUEVA EPS": ["nueva eps", "neps"],
    "SALUD TOTAL": ["salud total", "eps salud total", "saludtotal", "salud total eps"],
    "COMPENSAR": ["compensar", "eps compensar", "compensar eps"],
    "FAMISANAR": ["famisanar", "eps famisanar", "cafam", "colsubsidio"],
    "COOMEVA": ["coomeva", "eps coomeva", "coomeva eps"], # En liquidación pero aún aparecen históricas
    "ALIANSALUD": ["aliansalud", "eps aliansalud"],
    "S.O.S": ["sos", "servicio occidental de salud", "s.o.s eps"],
    "MUTUAL SER": ["mutual ser", "mutualser", "eps mutual ser"],
    "ASMET SALUD": ["asmet salud", "asmetsalud", "eps asmet salud"],
    "CAJACOPI": ["cajacopi", "eps cajacopi", "cajacopi eps"],
    "CAPITAL SALUD": ["capital salud", "eps capital salud", "capitalsalud"],
    "COMFAORIENTE": ["comfaoriente", "eps comfaoriente"],
    "SAVIA SALUD": ["savia salud", "eps savia salud", "saviasalud"],
    "EMSSANAR": ["emssanar", "eps emssanar"],
    "MALLAMAS": ["mallamas", "eps mallamas", "mallamas epsi"],
    "AIC": ["aic", "asociacion indigena del cauca", "eps aic"],
    "PIJAOS": ["pijaos", "eps pijaos salud", "pijaos salud"],
    "DUSAKAWI": ["dusakawi", "eps dusakawi"],
    "ANAS WAYUU": ["anas wayuu", "eps anas wayuu", "anaswayuu"],
}


class EPSValidationTool(BaseTool):
    name: str = "Validacion EPS Colombia"
    description: str = (
        "Valida si el nombre de una EPS (Entidad Promotora de Salud) extraída "
        "o un logo mencionado corresponden a una entidad real y legal "
        "del sistema de salud de Colombia (SGSSS). "
        "Recibe como input el nombre o descripción de la EPS (ej: 'Sura', 'eps sanitas'). "
        "Retorna si es válida, el nombre oficial y alertas en caso de no encontrarse."
    )

    def _run(self, eps_name: str) -> str:
        try:
            if not eps_name or eps_name.strip() == "":
                return json.dumps({
                    "error": "El nombre de la EPS a buscar no puede estar vacío."
                }, ensure_ascii=False)

            search_name_clean = eps_name.lower().strip()
            
            # Simple sanitization
            search_name_clean = search_name_clean.replace("s.a.", "").replace("s.a", "").strip()

            eps_oficial_encontrada = None

            # Búsqueda difusa manual
            for eps_oficial, variaciones in EPS_COLOMBIA.items():
                if any(var == search_name_clean or var in search_name_clean or search_name_clean in var for var in variaciones):
                    eps_oficial_encontrada = eps_oficial
                    break

            if eps_oficial_encontrada:
                return json.dumps({
                    "encontrada": True,
                    "eps_buscada": eps_name,
                    "eps_oficial": eps_oficial_encontrada,
                    "alerta": "La EPS mencionada existe en el sistema de salud colombiano y es válida.",
                    "riesgo": "BAJO"
                }, ensure_ascii=False, indent=2)
            else:
                return json.dumps({
                    "encontrada": False,
                    "eps_buscada": eps_name,
                    "alerta": f"ADVERTENCIA CRÍTICA: La entidad '{eps_name}' NO se encuentra en la base de datos "
                              "interna de EPS reales operativas en Colombia. Puede ser un error de OCR, o bien "
                              "el documento usa un nombre de EPS inventado/fachada.",
                    "recomendacion": "Si es una IPS o clínica pequeña (no una EPS), este error puede ignorarse. "
                                     "Pero si el documento afirma ser emitido por esta EPS, "
                                     "es una fuerte señal de fraude.",
                    "riesgo": "ALTO"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error en validación de EPS: {str(e)}"}, ensure_ascii=False)
