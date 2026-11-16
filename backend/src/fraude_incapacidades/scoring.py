"""Compatibilidad para imports históricos del motor de reglas."""

from .domain.scoring import (
    OCR_MIN_CONFIDENCE,
    PENALTIES,
    VEREDICTOS,
    Dictamen,
    arithmetic_ok,
    cie10_standard_days,
    evaluate,
    signals_from_report,
    verdict_for,
)

__all__ = [
    "OCR_MIN_CONFIDENCE",
    "PENALTIES",
    "VEREDICTOS",
    "Dictamen",
    "arithmetic_ok",
    "cie10_standard_days",
    "evaluate",
    "signals_from_report",
    "verdict_for",
]
