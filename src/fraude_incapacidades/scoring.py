"""Motor de reglas de puntaje de veracidad (Entregable 1, sección Dashboard).

Parte de 100 puntos y descuenta por hallazgo. Las consultas externas no
disponibles (CAPTCHA/timeout) NO penalizan: quedan como "Verificación externa
pendiente". Este módulo es determinista (no consume tokens de LLM) y lo usa el
laboratorio de benchmark (HU-09).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

OCR_MIN_CONFIDENCE = 70  # % — por debajo, el documento es Inconcluso / No Procesable

# (clave, puntos, descripción) — pesos del Entregable 1
PENALTIES = {
    "rethus_osint": (45, "Profesional inexistente/inhabilitado o IPS apócrifa (RETHUS/OSINT)"),
    "forense": (35, "Adulteración digital en regiones críticas o rastros de edición gráfica"),
    "clinica": (25, "Días fuera de rango CIE-10 (>100% del estándar) o error aritmético de fechas"),
    "adres": (20, "Afiliación inactiva o EPS discordante con la entidad emisora (ADRES)"),
    "formales": (10, "Metadatos aplanados/eliminados o firma/sello no visible"),
}

VEREDICTOS = ("Válido", "Sospechoso", "Potencialmente Fraudulento",
              "Inconcluso / No Procesable")


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
    desglose: list[dict] = field(default_factory=list)
    verificacion_externa_pendiente: list[str] = field(default_factory=list)
    motivo: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(doc: dict) -> Dictamen:
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

    desglose: list[dict] = []
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
    from .tools.cie10_tool import CIE10_DATABASE
    c = _norm_cie(code)
    entry = CIE10_DATABASE.get(c) or CIE10_DATABASE.get(c[:3])
    return entry["dias_max"] if entry else None


def arithmetic_ok(inicio: str | None, fin: str | None, dias) -> bool | None:
    from datetime import date
    try:
        d = (date.fromisoformat(str(fin)[:10]) -
             date.fromisoformat(str(inicio)[:10])).days + 1
        return d == int(dias)
    except (TypeError, ValueError):
        return None  # fechas no interpretables: no se puede afirmar error


def signals_from_report(report: dict, forense: dict | None) -> dict:
    """Traduce el informe del agente + forense determinista a campos para `evaluate`."""
    datos = report.get("datos_extraidos") or {}
    inc = datos.get("incapacidad") or {}
    estados = {v.get("fuente", ""): str(v.get("estado", "")).lower()
               for v in report.get("verificadores") or []}

    def state(prefix: str) -> str:
        return next((e for k, e in estados.items() if k.lower().startswith(prefix)), "")

    rethus_s, adres_s = state("rethus"), state("adres")
    doc: dict = {"metadatos": (forense or {}).get("estado", "ok")}
    doc["rethus"] = ("no_disponible" if "disponible" in rethus_s or "pendiente" in rethus_s
                     else "no_encontrado" if "no encontrado" in rethus_s or "inhabilit" in rethus_s
                     else "verificado")
    doc["adres"] = ("no_disponible" if "disponible" in adres_s or "pendiente" in adres_s
                    else "inactivo" if "inactiv" in adres_s else "activo")
    try:
        doc["dias_otorgados"] = int(inc.get("dias_otorgados"))
        doc["dias_estandar_cie10"] = cie10_standard_days(
            inc.get("codigo_cie10"))
    except (TypeError, ValueError):
        pass
    ar = arithmetic_ok(inc.get("fecha_inicio"), inc.get(
        "fecha_fin"), inc.get("dias_otorgados"))
    if ar is not None:
        doc["aritmetica_fechas_ok"] = ar
    firma = str((datos.get("entidad") or {}).get("firma_sello", "")).lower()
    if firma:
        doc["firma_visible"] = not (
            "ausente" in firma or "no legible" in firma)
    return doc
