"""Registro simulado (Mock API con caché local) de RETHUS, ADRES y entidades.

El Entregable 1 prevé este conector porque los portales oficiales usan CAPTCHA.
Solo se activa para certificados sintéticos: laboratorio con `FRAUDE_MOCK_REGISTRY=1`
o consultas explícitas desde `benchmark.py`. Nunca responde por personas reales.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve(
).parents[2] / "tests" / "synthetic" / "registro_mock.json"


def enabled() -> bool:
    return os.environ.get("FRAUDE_MOCK_REGISTRY") == "1" and REGISTRY_PATH.exists()


def load() -> dict:
    if not REGISTRY_PATH.exists():
        return {"rethus": {}, "adres": {}, "entidades": {}}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def lookup_rethus(numero: str) -> dict | None:
    return load()["rethus"].get(str(numero).strip())


def lookup_adres(numero: str) -> dict | None:
    return load()["adres"].get(str(numero).strip())


def lookup_entidad(nombre: str) -> dict | None:
    return load()["entidades"].get(str(nombre).strip().upper())


def tool_response(kind: str, data: dict) -> str | None:
    """Respuesta tipo herramienta para el agente cuando el modo simulado está activo; None si no aplica."""
    if not enabled():
        return None
    numero = str(data.get("numero_documento", "")).strip()
    if kind == "rethus":
        r = lookup_rethus(numero)
        if r is None or r["estado"] == "no_encontrado":
            return json.dumps({"fuente": "RETHUS (simulado)", "encontrado": False, "riesgo": "ALTO",
                               "nota": "El profesional no figura en el registro simulado."}, ensure_ascii=False)
        if r["estado"] == "no_disponible":
            return json.dumps({"fuente": "RETHUS (simulado)", "disponible": False,
                               "nota": "Timeout simulado: verificación externa pendiente. No es evidencia de fraude."}, ensure_ascii=False)
        return json.dumps({"fuente": "RETHUS (simulado)", "encontrado": True, "vigente": r["estado"] == "activo",
                           "estado_habilitacion": r["estado"], "riesgo": "BAJO" if r["estado"] == "activo" else "ALTO"}, ensure_ascii=False)
    if kind == "adres":
        a = lookup_adres(numero)
        if a is None or a["estado"] == "no_disponible":
            return json.dumps({"fuente": "ADRES (simulado)", "disponible": False,
                               "nota": "Timeout simulado: verificación externa pendiente. No es evidencia de fraude."}, ensure_ascii=False)
        return json.dumps({"fuente": "ADRES (simulado)", "estado_afiliacion": a["estado"].upper(), "eps": a["eps"]}, ensure_ascii=False)
    if kind == "osint":
        e = lookup_entidad(data.get("consulta", ""))
        txt = "Sin hallazgos adversos específicos." if e is None or e.get(
            "registrada", True) else "La entidad no aparece registrada y hay reportes de que es apócrifa."
        return json.dumps({"fuente": "OSINT (simulado)", "resultado": txt}, ensure_ascii=False)
    return None
