"""Reglas de dominio para puntuar la veracidad de una incapacidad.

Parte de 100 puntos y descuenta por hallazgo. Las consultas externas no
disponibles (CAPTCHA/timeout) NO penalizan: quedan como "Verificación externa
pendiente". Este módulo es determinista (no consume tokens de LLM) y lo usa el
laboratorio de benchmark (HU-09).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, asdict
from typing import TypedDict, cast

OCR_MIN_CONFIDENCE = 70  # % — por debajo, el documento es Inconcluso / No Procesable

# (clave, puntos, descripción) — pesos del Entregable 1
PENALTIES: dict[str, tuple[int, str]] = {
    "rethus_osint": (45, "Profesional inexistente/inhabilitado o IPS apócrifa (RETHUS/OSINT)"),
    "forense": (35, "Adulteración digital en regiones críticas o rastros de edición gráfica"),
    "clinica": (25, "Días fuera de rango CIE-10 (>100% del estándar) o error aritmético de fechas"),
    "adres": (20, "Afiliación inactiva o EPS discordante con la entidad emisora (ADRES)"),
    "formales": (10, "Metadatos aplanados/eliminados o firma/sello no visible"),
}

VEREDICTOS = ("Válido", "Sospechoso", "Potencialmente Fraudulento",
              "Inconcluso / No Procesable")


class RuleSignals(TypedDict, total=False):
    ocr_confianza: int | float
    manuscrito: bool
    rethus: str
    osint_ips_apocrifa: bool
    adulteracion_ela: bool
    metadatos: str
    dias_otorgados: int | None
    dias_estandar_cie10: int | None
    aritmetica_fechas_ok: bool
    adres: str
    eps_coincide: bool | None
    firma_visible: bool


class RuleFinding(TypedDict):
    regla: str
    puntos: int
    detalle: str


def _new_findings() -> list[RuleFinding]:
    return []


def _new_pending_checks() -> list[str]:
    return []


def verdict_for(score: int) -> str:
    if score >= 80:
        return "Válido"
    if score >= 41:
        return "Sospechoso"
    return "Potencialmente Fraudulento"


@dataclass
class Dictamen:
    veredicto: str
    puntaje: int | None
    desglose: list[RuleFinding] = field(default_factory=_new_findings)
    verificacion_externa_pendiente: list[str] = field(default_factory=_new_pending_checks)
    motivo: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate(doc: RuleSignals) -> Dictamen:
    """Evalúa un registro de extracción estructurada (real o sintético).

    Campos esperados (todos opcionales salvo lo indicado por defecto):
      ocr_confianza (0-100), manuscrito (bool),
      rethus: verificado|no_encontrado|inhabilitado|no_disponible,
      osint_ips_apocrifa (bool), adulteracion_ela (bool),
      metadatos: ok|aplanados|editor_grafico,
      dias_otorgados, dias_estandar_cie10, aritmetica_fechas_ok (bool),
      adres: activo|inactivo|no_disponible, eps_coincide (bool), firma_visible (bool)
    """
    # Puerta de legibilidad: antes de cualquier consumo de LLM (HU-09 criterio 4)
    if doc.get("manuscrito") or doc.get("ocr_confianza", 100) < OCR_MIN_CONFIDENCE:
        return Dictamen(
            veredicto=VEREDICTOS[3],
            puntaje=None,
            motivo="Manuscrito o lectura OCR < 70%: derivado a revisión manual sin puntaje.",
        )

    desglose: list[RuleFinding] = []
    pendientes: list[str] = []

    def hit(key: str, detalle: str) -> None:
        pts, _ = PENALTIES[key]
        desglose.append({"regla": key, "puntos": -pts, "detalle": detalle})

    rethus = doc.get("rethus", "verificado")
    if rethus in ("no_encontrado", "inhabilitado"):
        hit("rethus_osint", f"RETHUS: profesional {rethus.replace('_', ' ')}")
    elif doc.get("osint_ips_apocrifa"):
        hit("rethus_osint", "OSINT: IPS emisora apócrifa")
    elif rethus == "no_disponible":
        pendientes.append("RETHUS")

    meta = doc.get("metadatos", "ok")
    if doc.get("adulteracion_ela") or meta == "editor_grafico":
        hit("forense", "ELA en región crítica" if doc.get(
            "adulteracion_ela") else "Metadatos con software de edición gráfica")

    dias, estandar = doc.get("dias_otorgados"), doc.get("dias_estandar_cie10")
    fuera_rango = dias is not None and estandar and dias > 2 * estandar
    if fuera_rango or doc.get("aritmetica_fechas_ok") is False:
        hit("clinica",
            f"Días otorgados {dias} vs estándar {estandar}" if fuera_rango else "Error aritmético entre fechas y días")

    adres = doc.get("adres", "activo")
    if adres == "inactivo" or doc.get("eps_coincide") is False:
        hit("adres", "Afiliación inactiva" if adres ==
            "inactivo" else "EPS discordante con la emisora")
    elif adres == "no_disponible":
        pendientes.append("ADRES")

    if meta == "aplanados" or doc.get("firma_visible") is False:
        hit("formales", "Metadatos aplanados" if meta ==
            "aplanados" else "Firma/sello no visible")

    puntaje = max(0, 100 + sum(d["puntos"] for d in desglose))
    return Dictamen(
        veredicto=verdict_for(puntaje),
        puntaje=puntaje,
        desglose=desglose,
        verificacion_externa_pendiente=pendientes,
    )


# ─── Control de reglas para el flujo real (compara contra el puntaje del agente) ───
def _norm_cie(code: str | None) -> str:
    return (code or "").upper().replace(".", "").replace(" ", "")


def cie10_standard_days(code: str | None) -> int | None:
    """Días de referencia (máximo orientativo) del catálogo embebido, o None si el código no está."""
    from .cie10_catalog import CIE10_DATABASE
    c = _norm_cie(code)
    entry = CIE10_DATABASE.get(c) or CIE10_DATABASE.get(c[:3])
    return entry["dias_max"] if entry else None


def arithmetic_ok(inicio: object, fin: object, dias: object) -> bool | None:
    from datetime import date
    try:
        if not isinstance(dias, (int, float, str)):
            return None
        d = (date.fromisoformat(str(fin)[:10]) -
             date.fromisoformat(str(inicio)[:10])).days + 1
        return d == int(dias)
    except (TypeError, ValueError):
        return None  # fechas no interpretables: no se puede afirmar error


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(key): item for key, item in mapping.items()}


def _as_object_list(value: object) -> list[object] | None:
    if isinstance(value, list):
        return cast(list[object], value)
    return None


def signals_from_report(
    report: Mapping[str, object], forense: Mapping[str, object] | None
) -> RuleSignals:
    """Traduce el informe del agente + forense determinista a campos para `evaluate`."""
    datos = _as_mapping(report.get("datos_extraidos"))
    inc = _as_mapping(datos.get("incapacidad"))
    estados: dict[str, str] = {}
    verificadores = _as_object_list(report.get("verificadores"))
    if verificadores is not None:
        for item in verificadores:
            verifier = _as_mapping(item)
            fuente = verifier.get("fuente", "")
            estado = verifier.get("estado", "")
            estados[str(fuente)] = str(estado).lower()

    def state(prefix: str) -> str:
        return next((e for k, e in estados.items() if k.lower().startswith(prefix)), "")

    rethus_s, adres_s = state("rethus"), state("adres")
    forensic_data = forense or {}
    doc: RuleSignals = {
        "metadatos": str(forensic_data.get("estado", "ok"))
    }
    doc["rethus"] = ("no_disponible" if "disponible" in rethus_s or "pendiente" in rethus_s
                     else "no_encontrado" if "no encontrado" in rethus_s or "inhabilit" in rethus_s
                     else "verificado")
    doc["adres"] = ("no_disponible" if "disponible" in adres_s or "pendiente" in adres_s
                    else "inactivo" if "inactiv" in adres_s else "activo")
    dias = inc.get("dias_otorgados")
    if isinstance(dias, (int, float, str)):
        try:
            doc["dias_otorgados"] = int(dias)
            codigo = inc.get("codigo_cie10")
            doc["dias_estandar_cie10"] = cie10_standard_days(
                codigo if isinstance(codigo, str) else None
            )
        except (TypeError, ValueError):
            pass
    ar = arithmetic_ok(
        inc.get("fecha_inicio"),
        inc.get("fecha_fin"),
        inc.get("dias_otorgados"),
    )
    if ar is not None:
        doc["aritmetica_fechas_ok"] = ar
    entidad = _as_mapping(datos.get("entidad"))
    firma = str(entidad.get("firma_sello", "")).lower()
    if firma:
        doc["firma_visible"] = not (
            "ausente" in firma or "no legible" in firma)
    return doc
