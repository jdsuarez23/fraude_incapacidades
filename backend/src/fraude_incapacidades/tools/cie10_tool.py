from __future__ import annotations

import json
from crewai.tools import BaseTool

from fraude_incapacidades.domain.cie10_catalog import CIE10_DATABASE


class CIE10ValidationTool(BaseTool):
    name: str = "Validacion CIE-10"
    description: str = (
        "Valida un código CIE-10 contra la base de datos de diagnósticos colombianos. "
        "Recibe como input un JSON string con los campos: "
        "'codigo' (ej: 'J06'), 'diagnostico_texto' (descripción del médico), "
        "'dias_incapacidad' (número de días otorgados). "
        "Retorna la validación con coherencia de días y alertas."
    )

    def _run(self, input_data: str) -> str:
        try:
            # Parse input - accept flexible formats
            try:
                data = json.loads(input_data)
            except json.JSONDecodeError:
                # Try to extract from natural language
                return json.dumps({
                    "error": "El input debe ser un JSON con campos: codigo, diagnostico_texto, dias_incapacidad",
                    "ejemplo": '{"codigo": "J06", "diagnostico_texto": "Infección respiratoria", "dias_incapacidad": 5}'
                }, ensure_ascii=False, indent=2)

            codigo = data.get("codigo", "").upper().strip()
            dias = data.get("dias_incapacidad", 0)
            diagnostico_texto = data.get("diagnostico_texto", "")

            # Search by exact match first, then by prefix
            codigo = codigo.replace(".", "").replace(" ", "")
            entry = CIE10_DATABASE.get(codigo) or CIE10_DATABASE.get(codigo[:3])

            if not entry:
                return json.dumps({
                    "codigo": codigo,
                    "encontrado_en_base": False,
                    "alerta": f"Código CIE-10 '{codigo}' NO encontrado en la base de datos. Puede ser un código inválido, obsoleto o extremadamente raro.",
                    "riesgo": "ALTO"
                }, ensure_ascii=False, indent=2)

            # Validate days coherence
            alertas = []
            riesgo = "BAJO"

            if isinstance(dias, (int, float)) and dias > 0:
                if dias < entry["dias_min"]:
                    alertas.append(f"Días de incapacidad ({dias}) INFERIORES al mínimo esperado ({entry['dias_min']} días) para {entry['desc']}.")
                    riesgo = "MEDIO"
                elif dias > entry["dias_max"]:
                    alertas.append(f"Días de incapacidad ({dias}) SUPERIORES al máximo esperado ({entry['dias_max']} días) para {entry['desc']}. Posible exceso.")
                    riesgo = "ALTO"
                else:
                    alertas.append(f"Días de incapacidad ({dias}) dentro del rango esperado ({entry['dias_min']}-{entry['dias_max']} días).")

            return json.dumps({
                "codigo": codigo,
                "encontrado_en_base": True,
                "descripcion_oficial": entry["desc"],
                "diagnostico_medico": diagnostico_texto,
                "dias_incapacidad": dias,
                "rango_esperado_dias": f"{entry['dias_min']}-{entry['dias_max']}",
                "alertas": alertas,
                "riesgo": riesgo,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Error en validación CIE-10: {str(e)}"}, ensure_ascii=False)
