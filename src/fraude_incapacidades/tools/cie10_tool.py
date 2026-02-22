from __future__ import annotations

import json
from crewai.tools import BaseTool

# Base de datos embebida con los códigos CIE-10 más frecuentes en incapacidades
# colombianas, con rangos típicos de días según protocolos de medicina laboral.
CIE10_DATABASE: dict[str, dict] = {
    # --- Enfermedades infecciosas ---
    "A09": {"desc": "Diarrea y gastroenteritis de presunto origen infeccioso", "dias_min": 1, "dias_max": 5},
    "A90": {"desc": "Fiebre del dengue (dengue clásico)", "dias_min": 5, "dias_max": 14},
    "A91": {"desc": "Fiebre del dengue hemorrágico", "dias_min": 7, "dias_max": 21},
    "B34": {"desc": "Enfermedad viral no especificada", "dias_min": 3, "dias_max": 7},
    # --- Neoplasias ---
    "C50": {"desc": "Tumor maligno de la mama", "dias_min": 30, "dias_max": 180},
    "D25": {"desc": "Leiomioma del útero", "dias_min": 15, "dias_max": 60},
    # --- Enfermedades endocrinas ---
    "E11": {"desc": "Diabetes mellitus tipo 2", "dias_min": 3, "dias_max": 30},
    "E66": {"desc": "Obesidad", "dias_min": 3, "dias_max": 15},
    # --- Trastornos mentales ---
    "F32": {"desc": "Episodio depresivo", "dias_min": 7, "dias_max": 90},
    "F33": {"desc": "Trastorno depresivo recurrente", "dias_min": 15, "dias_max": 90},
    "F41": {"desc": "Otros trastornos de ansiedad", "dias_min": 5, "dias_max": 30},
    "F43": {"desc": "Reacciones a estrés grave y trastornos de adaptación", "dias_min": 5, "dias_max": 30},
    # --- Sistema nervioso ---
    "G43": {"desc": "Migraña", "dias_min": 1, "dias_max": 5},
    "G44": {"desc": "Otros síndromes de cefalea", "dias_min": 1, "dias_max": 3},
    "G56": {"desc": "Mononeuropatías del miembro superior (túnel carpiano)", "dias_min": 15, "dias_max": 60},
    # --- Enfermedades del ojo ---
    "H10": {"desc": "Conjuntivitis", "dias_min": 2, "dias_max": 7},
    # --- Enfermedades del oído ---
    "H66": {"desc": "Otitis media supurativa y la no especificada", "dias_min": 3, "dias_max": 7},
    # --- Sistema circulatorio ---
    "I10": {"desc": "Hipertensión esencial (primaria)", "dias_min": 3, "dias_max": 15},
    "I20": {"desc": "Angina de pecho", "dias_min": 7, "dias_max": 30},
    "I63": {"desc": "Infarto cerebral", "dias_min": 30, "dias_max": 180},
    "I64": {"desc": "Accidente vascular encefálico agudo no especificado", "dias_min": 30, "dias_max": 180},
    # --- Sistema respiratorio ---
    "J00": {"desc": "Rinofaringitis aguda (resfriado común)", "dias_min": 1, "dias_max": 3},
    "J01": {"desc": "Sinusitis aguda", "dias_min": 3, "dias_max": 7},
    "J02": {"desc": "Faringitis aguda", "dias_min": 2, "dias_max": 5},
    "J03": {"desc": "Amigdalitis aguda", "dias_min": 3, "dias_max": 7},
    "J06": {"desc": "Infecciones agudas de las vías respiratorias superiores", "dias_min": 3, "dias_max": 7},
    "J11": {"desc": "Influenza con virus no identificado", "dias_min": 5, "dias_max": 10},
    "J18": {"desc": "Neumonía organismo no especificado", "dias_min": 7, "dias_max": 21},
    "J20": {"desc": "Bronquitis aguda", "dias_min": 5, "dias_max": 10},
    "J45": {"desc": "Asma", "dias_min": 3, "dias_max": 14},
    # --- Sistema digestivo ---
    "K21": {"desc": "Enfermedad de reflujo gastroesofágico", "dias_min": 3, "dias_max": 7},
    "K25": {"desc": "Úlcera gástrica", "dias_min": 5, "dias_max": 15},
    "K29": {"desc": "Gastritis y duodenitis", "dias_min": 2, "dias_max": 7},
    "K35": {"desc": "Apendicitis aguda", "dias_min": 10, "dias_max": 30},
    "K40": {"desc": "Hernia inguinal", "dias_min": 15, "dias_max": 30},
    "K80": {"desc": "Colelitiasis", "dias_min": 10, "dias_max": 30},
    # --- Enfermedades de la piel ---
    "L02": {"desc": "Absceso cutáneo, furúnculo y ántrax", "dias_min": 3, "dias_max": 10},
    "L03": {"desc": "Celulitis", "dias_min": 5, "dias_max": 14},
    # --- Sistema musculoesquelético ---
    "M23": {"desc": "Trastorno interno de la rodilla", "dias_min": 15, "dias_max": 60},
    "M25": {"desc": "Otros trastornos articulares", "dias_min": 5, "dias_max": 30},
    "M54": {"desc": "Dorsalgia (dolor de espalda)", "dias_min": 3, "dias_max": 15},
    "M54.5": {"desc": "Lumbago no especificado", "dias_min": 3, "dias_max": 15},
    "M65": {"desc": "Sinovitis y tenosinovitis", "dias_min": 7, "dias_max": 21},
    "M75": {"desc": "Lesiones del hombro", "dias_min": 10, "dias_max": 45},
    "M79": {"desc": "Otros trastornos de los tejidos blandos", "dias_min": 3, "dias_max": 15},
    # --- Sistema genitourinario ---
    "N30": {"desc": "Cistitis (infección urinaria)", "dias_min": 2, "dias_max": 5},
    "N39": {"desc": "Otros trastornos del sistema urinario", "dias_min": 2, "dias_max": 7},
    "N76": {"desc": "Otras afecciones inflamatorias de la vagina y de la vulva", "dias_min": 3, "dias_max": 7},
    # --- Embarazo ---
    "O20": {"desc": "Hemorragia precoz del embarazo", "dias_min": 7, "dias_max": 30},
    "O21": {"desc": "Vómitos excesivos en el embarazo", "dias_min": 5, "dias_max": 15},
    "O47": {"desc": "Falso trabajo de parto", "dias_min": 2, "dias_max": 7},
    "O80": {"desc": "Parto único espontáneo", "dias_min": 56, "dias_max": 126},
    "O82": {"desc": "Parto único por cesárea", "dias_min": 56, "dias_max": 126},
    # --- Periodo perinatal ---
    "P07": {"desc": "Trastornos relacionados con duración corta de la gestación", "dias_min": 30, "dias_max": 90},
    # --- Malformaciones ---
    # --- Traumatismos ---
    "S02": {"desc": "Fractura de huesos del cráneo y de la cara", "dias_min": 15, "dias_max": 60},
    "S32": {"desc": "Fractura de columna lumbar y de la pelvis", "dias_min": 30, "dias_max": 90},
    "S42": {"desc": "Fractura del hombro y del brazo", "dias_min": 30, "dias_max": 90},
    "S52": {"desc": "Fractura del antebrazo", "dias_min": 30, "dias_max": 90},
    "S62": {"desc": "Fractura a nivel de la muñeca y de la mano", "dias_min": 21, "dias_max": 60},
    "S72": {"desc": "Fractura del fémur", "dias_min": 45, "dias_max": 120},
    "S82": {"desc": "Fractura de la pierna incluso el tobillo", "dias_min": 30, "dias_max": 90},
    "S83": {"desc": "Luxación esguince y torcedura de articulaciones de la rodilla", "dias_min": 7, "dias_max": 45},
    "S93": {"desc": "Luxación esguince y torcedura de articulaciones del tobillo", "dias_min": 5, "dias_max": 30},
    "T14": {"desc": "Traumatismo de regiones del cuerpo no especificadas", "dias_min": 3, "dias_max": 15},
    # --- Factores de salud / contacto con el servicio de salud ---
    "Z34": {"desc": "Supervisión de embarazo normal", "dias_min": 1, "dias_max": 3},
    "Z76": {"desc": "Personas en contacto con los servicios de salud en otras circunstancias", "dias_min": 1, "dias_max": 5},
}


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
            entry = CIE10_DATABASE.get(codigo)
            if not entry:
                # Try prefix match (e.g., "J06.9" -> "J06")
                prefix = codigo.split(".")[0]
                entry = CIE10_DATABASE.get(prefix)

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
