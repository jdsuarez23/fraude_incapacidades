import json
import re
from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel

from fraude_incapacidades.domain.scoring import (
    evaluate,
    signals_from_report,
    verdict_for,
)

from .ports import PdfExporter


class StructuredReport(BaseModel):
    puntaje_veracidad: int | None = 0
    hallazgos_medicos: str = ""
    analisis_forense: str = ""
    verificacion_entidades: str = ""
    alertas: list[str] = []
    veredicto: str = "Indeterminado"
    datos_extraidos: dict = {}
    desglose: list[dict] = []
    verificadores: list[dict] = []
    verificacion_externa_pendiente: list[str] = []
    forense: dict[str, object] = {}
    control_reglas: dict = {}
    aviso_legal: str = (
        "Orientación técnica preliminar: no constituye decisión administrativa definitiva. "
        "Cualquier medida requiere confirmación del analista de Gestión Humana."
    )


class AnalysisResponse(BaseModel):
    status: str
    report: StructuredReport | None = None
    raw_report: str = ""
    error: str | None = None
    validacion: dict | None = None


def _forense_mapping(value: object | None) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("forense debe ser un objeto de tipo mapping")
    mapping = cast(Mapping[object, object], value)
    return {str(key): item for key, item in mapping.items()}


class ReportService:
    def __init__(self, pdf_exporter: PdfExporter):
        self.pdf_exporter = pdf_exporter

    def export_pdf(self, payload: dict) -> bytes:
        return self.pdf_exporter.export(payload)


def _mask_name(value) -> str:
    parts = [p for p in re.split(r"\s+", str(value).strip()) if p]
    return " ".join(p[0] + "***" for p in parts)


def _mask_id(value) -> str:
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 8:
        return "*" * max(len(digits), 3)
    return f"{digits[:1]}.{digits[1:4]}.***.***"


def anonymize(datos: dict) -> dict:
    out = dict(datos or {})
    paciente = out.get("paciente")
    if isinstance(paciente, dict):
        paciente = dict(paciente)
        if paciente.get("nombre"):
            paciente["nombre"] = _mask_name(paciente["nombre"])
        for key in ("numero", "cedula", "documento"):
            if paciente.get(key):
                paciente[key] = _mask_id(paciente[key])
        out["paciente"] = paciente
    return out


def normalize_report(data: dict) -> StructuredReport:
    puntaje = data.get("puntaje_veracidad")
    veredicto = str(data.get("veredicto", "Indeterminado"))
    if "inconclus" in veredicto.lower() or "procesable" in veredicto.lower() or puntaje is None:
        veredicto, puntaje = "Inconcluso / No Procesable", None
    else:
        puntaje = max(0, min(100, int(puntaje)))
        veredicto = verdict_for(puntaje)
    return StructuredReport(
        puntaje_veracidad=puntaje,
        hallazgos_medicos=str(data.get("hallazgos_medicos", "")),
        analisis_forense=str(data.get("analisis_forense", "")),
        verificacion_entidades=str(data.get("verificacion_entidades", "")),
        alertas=[str(alerta) for alerta in data.get("alertas", [])],
        veredicto=veredicto,
        datos_extraidos=anonymize(data.get("datos_extraidos", {})),
        desglose=[item for item in data.get("desglose", []) if isinstance(item, dict)],
        verificadores=[
            item for item in data.get("verificadores", []) if isinstance(item, dict)
        ],
        verificacion_externa_pendiente=[
            str(item) for item in data.get("verificacion_externa_pendiente", [])
        ],
    )


def parse_crew_result(result) -> tuple[StructuredReport | None, str]:
    if isinstance(result, str):
        raw_text = result
    elif hasattr(result, "raw"):
        raw_text = str(result.raw)
    elif hasattr(result, "output"):
        raw_text = str(result.output)
    else:
        raw_text = str(result)

    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if json_match:
        try:
            return normalize_report(json.loads(json_match.group())), raw_text
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return None, raw_text


def enrich_report(
    report: StructuredReport | None, forense: object | None
) -> None:
    if report is None:
        return
    forense_data = _forense_mapping(forense)
    report.forense = forense_data or {}
    if report.puntaje_veracidad is None:
        return
    rules = evaluate(signals_from_report(report.model_dump(), forense_data))
    if rules.puntaje is None:
        return
    report.control_reglas = {
        "puntaje": rules.puntaje,
        "veredicto": rules.veredicto,
        "desglose": rules.desglose,
        "verificacion_externa_pendiente": rules.verificacion_externa_pendiente,
        "diferencia": report.puntaje_veracidad - rules.puntaje,
        "coincide_veredicto": rules.veredicto == report.veredicto,
    }


def forensic_prompt(forense: object | None) -> str:
    forense_data = _forense_mapping(forense)
    if not forense_data:
        return "No disponible"
    keys = (
        "estado",
        "creador",
        "productor",
        "fecha_creacion",
        "fecha_modificacion",
        "dias_entre_creacion_y_modificacion",
        "alertas",
    )
    return json.dumps(
        {key: forense_data.get(key) for key in keys}, ensure_ascii=False
    )
