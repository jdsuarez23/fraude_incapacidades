"""Laboratorio de validación Ground Truth (HU-09).

Evalúa el lote de 30 certificados sintéticos EN PDF (`tests/synthetic/SINT-001..030.pdf`, ver
`synthetic.py`). Dos modos:

* **reglas** (sin LLM, 0 tokens): cada PDF pasa por forense de metadatos real, lectura de la capa de
  texto, registro simulado (RETHUS/ADRES/entidades) y el motor de reglas del Entregable 1.
* **agente** (LLM): el crew de CrewAI analiza los PDFs con el registro simulado activo. Consume
  tokens, por eso se ejecuta sobre una muestra y cada resultado se guarda en caché por huella SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import mock_registry
from .forensics import analyze_pdf
from .scoring import PENALTIES, arithmetic_ok, cie10_standard_days, evaluate
from .synthetic import ADULTERADO, ILEGIBLE, SYNTH_DIR, generate

UMBRALES_WEB = {"recall_min": 0.75,
                "precision_min": 0.75, "fn_max": 0.25, "fp_max": 0.25}
METAS_ENTREGABLE = {"recall_min": 0.85,
                    "precision_min": 0.80, "fn_max": 0.15, "fp_max": 0.20}
CACHE_DIR = Path(__file__).resolve().parents[2] / "tests" / "benchmark_cache"
CACHE_RULES = CACHE_DIR / "lote_web_30_reglas.json"
CACHE_AGENT = CACHE_DIR / "agente"
ENGINE_VERSION = 2  # subir al cambiar el pipeline de reglas para invalidar cachés


# ─── Extracción local desde la capa de texto (sin OCR ni LLM) ───
_LABELS = {
    "entidad": "Entidad emisora", "consecutivo": "Consecutivo", "paciente": "Paciente", "tipo_doc": "Tipo de documento",
    "cc_paciente": "Número de documento", "eps": "EPS de afiliación", "cie": "Código CIE-10", "inicio": "Fecha de inicio",
    "fin": "Fecha de fin", "dias": "Días otorgados", "medico": "Médico", "cc_medico": "Cédula del médico", "rm": "Registro médico",
}


def extract_fields(pdf_path: Path) -> dict | None:
    import fitz
    with fitz.open(pdf_path) as doc:
        text = "\n".join(p.get_text("text") for p in doc)
    if len(text.strip()) < 20:
        return None
    out = {}
    for key, label in _LABELS.items():
        m = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, re.M)
        out[key] = m.group(1).strip() if m else None
    return out


def build_signals(pdf_path: Path) -> tuple[dict, dict]:
    """PDF → (señales para el motor de reglas, forense). Sin texto legible ⇒ lectura OCR 0 %."""
    fz = analyze_pdf(pdf_path, check_signature_region=True)
    campos = extract_fields(pdf_path) if fz["texto_nativo"] else None
    if not campos:
        return {"ocr_confianza": 0}, fz
    rethus = mock_registry.lookup_rethus(campos["cc_medico"] or "")
    adres = mock_registry.lookup_adres(campos["cc_paciente"] or "")
    entidad = mock_registry.lookup_entidad(campos["entidad"] or "")
    try:
        dias = int(campos["dias"])
    except (TypeError, ValueError):
        dias = None
    doc = {
        "ocr_confianza": 95,
        "metadatos": fz["estado"],
        "firma_visible": fz.get("firma_visible", True),
        "rethus": (rethus or {"estado": "no_encontrado"})["estado"].replace("activo", "verificado"),
        "osint_ips_apocrifa": bool(entidad and entidad.get("registrada") is False),
        "adres": (adres or {"estado": "no_disponible"})["estado"],
        "eps_coincide": None if not adres else (adres["eps"].upper() == (campos["eps"] or "").upper()),
        "dias_otorgados": dias,
        "dias_estandar_cie10": cie10_standard_days(campos["cie"]),
    }
    ar = arithmetic_ok(campos["inicio"], campos["fin"], campos["dias"])
    if ar is not None:
        doc["aritmetica_fechas_ok"] = ar
    return doc, fz


# ─── Clasificación y métricas ───
def classify(real: str, veredicto: str) -> tuple[str, str]:
    """(veredicto simplificado, coincidencia). Positivo = adulterado; íntegro ⇔ veredicto Válido."""
    if veredicto.startswith("Inconcluso"):
        return "Inconcluso", "Derivado a Revisión Manual" if real == ILEGIBLE else "Derivado a revisión (no esperado)"
    adulterado = veredicto != "Válido"
    ia = "Adulterado" if adulterado else "Íntegro"
    if real == ADULTERADO:
        return ia, "Correcto" if adulterado else "Falso Negativo"
    if real == ILEGIBLE:
        return ia, "Error de puerta OCR"
    return ia, "Falso Positivo" if adulterado else "Correcto"


def _ratio(n: int, d: int) -> float | None:
    """None cuando no hay casos para calcular (p. ej. muestra sin adulterados)."""
    return round(n / d, 4) if d else None


def _ok(value: float | None, limit: float, sense: str) -> bool | None:
    if value is None:
        return None
    return value >= limit if sense == "min" else value <= limit


def compute_metrics(detalle: list[dict]) -> dict:
    vp = sum(r["coincidencia"] == "Correcto" and r["etiqueta_real"]
             == ADULTERADO for r in detalle)
    vn = sum(r["coincidencia"] == "Correcto" and r["etiqueta_real"]
             not in (ADULTERADO, ILEGIBLE) for r in detalle)
    fp = sum(r["coincidencia"] == "Falso Positivo" and r["etiqueta_real"]
             != ILEGIBLE for r in detalle)
    fn = sum(r["coincidencia"] == "Falso Negativo" for r in detalle)
    ileg = [r for r in detalle if r["etiqueta_real"] == ILEGIBLE]
    ileg_ok = sum(r["veredicto_completo"].startswith("Inconcluso")
                  for r in ileg)
    u, mt = UMBRALES_WEB, METAS_ENTREGABLE
    recall, prec = _ratio(vp, vp + fn), _ratio(vp, vp + fp)
    fnr, fpr = _ratio(fn, vp + fn), _ratio(fp, fp + vn)
    metricas = {
        "sensibilidad": {"valor": recall, "meta_web": u["recall_min"], "meta_entregable": mt["recall_min"], "cumple": _ok(recall, u["recall_min"], "min"), "sentido": "min"},
        "precision": {"valor": prec, "meta_web": u["precision_min"], "meta_entregable": mt["precision_min"], "cumple": _ok(prec, u["precision_min"], "min"), "sentido": "min"},
        "falsos_negativos": {"valor": fnr, "meta_web": u["fn_max"], "meta_entregable": mt["fn_max"], "cumple": _ok(fnr, u["fn_max"], "max"), "sentido": "max"},
        "falsos_positivos": {"valor": fpr, "meta_web": u["fp_max"], "meta_entregable": mt["fp_max"], "cumple": _ok(fpr, u["fp_max"], "max"), "sentido": "max"},
        "ilegibles_derivados": {"valor": _ratio(ileg_ok, len(ileg)), "derivados": ileg_ok, "total": len(ileg), "meta_web": 1.0, "cumple": (ileg_ok == len(ileg)) if ileg else None, "sentido": "min"},
    }
    return {"matriz": {"vp": vp, "fp": fp, "fn": fn, "vn": vn}, "metricas": metricas,
            "aprobado": all(m["cumple"] is not False for m in metricas.values())}


def _fingerprint(manifest: list[dict], extra: str = "") -> str:
    h = hashlib.sha256()
    for m in manifest:
        h.update((SYNTH_DIR / m["archivo"]).read_bytes())
        h.update(m["etiqueta_real"].encode())
    h.update(json.dumps({k: v[0] for k, v in PENALTIES.items()}).encode())
    h.update(f"{ENGINE_VERSION}{extra}".encode())
    return h.hexdigest()[:16]


def pdf_sha(item: dict) -> str:
    return hashlib.sha256((SYNTH_DIR / item["archivo"]).read_bytes()).hexdigest()


# ─── Modo reglas ───
def run_benchmark(use_cache: bool = True, force: bool = False) -> dict:
    manifest = generate()
    fp_id = _fingerprint(manifest)
    if use_cache and not force and CACHE_RULES.exists():
        try:
            cached = json.loads(CACHE_RULES.read_text(encoding="utf-8"))
            if cached.get("huella") == fp_id:
                cached["desde_cache"] = True
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    t0 = time.perf_counter()
    detalle = []
    for m in manifest:
        signals, fz = build_signals(SYNTH_DIR / m["archivo"])
        d = evaluate(signals)
        ia, match = classify(m["etiqueta_real"], d.veredicto)
        detalle.append({
            "id": m["id"], "archivo": m["archivo"], "tipo": m["tipo"], "etiqueta_real": m["etiqueta_real"],
            "veredicto_ia": ia, "veredicto_completo": d.veredicto, "puntaje": d.puntaje, "coincidencia": match,
            "desglose": d.desglose, "forense": {"estado": fz["estado"], "alertas": fz["alertas"]},
        })
    result = {
        "modo": "reglas", "huella": fp_id, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "desde_cache": False, "duracion_ms": round((time.perf_counter() - t0) * 1000, 1),
        "tokens_llm": 0, "llamadas_llm": 0, "costo_usd": 0.0,
        "lote": {"total": len(detalle), "integros": sum(d["etiqueta_real"] != ADULTERADO for d in detalle),
                 "adulterados": sum(d["etiqueta_real"] == ADULTERADO for d in detalle)},
        "detalle": detalle, **compute_metrics(detalle),
    }
    CACHE_RULES.parent.mkdir(parents=True, exist_ok=True)
    CACHE_RULES.write_text(json.dumps(
        result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def read_cache() -> dict | None:
    if CACHE_RULES.exists():
        try:
            d = json.loads(CACHE_RULES.read_text(encoding="utf-8"))
            d["desde_cache"] = True
            return d
        except (json.JSONDecodeError, OSError):
            return None
    return None


# ─── Modo agente (caché por huella del PDF) ───
def agent_cache_get(item: dict) -> dict | None:
    p = CACHE_AGENT / f"{pdf_sha(item)}_v{ENGINE_VERSION}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def agent_cache_put(item: dict, row: dict) -> None:
    CACHE_AGENT.mkdir(parents=True, exist_ok=True)
    (CACHE_AGENT / f"{pdf_sha(item)}_v{ENGINE_VERSION}.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")


def agent_row(item: dict, report: dict | None, error: str | None = None) -> dict:
    veredicto = (report or {}).get(
        "veredicto", "Indeterminado") if report else "Indeterminado"
    ia, match = classify(item["etiqueta_real"], veredicto) if report else (
        "Sin dictamen", "Error del agente")
    return {
        "id": item["id"], "archivo": item["archivo"], "tipo": item["tipo"], "etiqueta_real": item["etiqueta_real"],
        "veredicto_ia": ia, "veredicto_completo": veredicto, "puntaje": (report or {}).get("puntaje_veracidad"),
        "coincidencia": match, "desglose": (report or {}).get("desglose", []), "error": error,
        "control_reglas": (report or {}).get("control_reglas"),
    }


def sample_manifest(n: int) -> list[dict]:
    """Muestra estratificada y estable: alterna íntegros, adulterados e ilegibles."""
    manifest = generate()
    groups = {k: [m for m in manifest if m["etiqueta_real"] == k]
              for k in ("Íntegro", ADULTERADO, ILEGIBLE)}
    out, i = [], 0
    while len(out) < min(n, len(manifest)):
        for k in ("Íntegro", ADULTERADO, ILEGIBLE):
            if i < len(groups[k]) and len(out) < n:
                out.append(groups[k][i])
        i += 1
    return out
