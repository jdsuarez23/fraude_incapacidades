import asyncio
import os
import uuid
from pathlib import Path

from fraude_incapacidades import benchmark as bench
from fraude_incapacidades.synthetic import (
    SYNTH_DIR,
    generate as generate_synthetic,
)

from .analysis_service import AnalysisService, api_key_error
from .ports import CrewRunner, PdfAnalysis
from fraude_incapacidades.infrastructure.pii_redaction import (
    sanitized_pdf_for_analysis,
)
from .report_service import enrich_report, forensic_prompt, parse_crew_result
from .runtime import CREW_LOCK

AGENT_RUNS: dict[str, dict] = {}
_LABELS_OK = {
    "integro": "Íntegro",
    "adulterado": "Adulterado",
    "ilegible": "Ilegible",
}


def run_rules_benchmark(use_cache: bool = True, force: bool = False) -> dict:
    return bench.run_benchmark(use_cache=use_cache, force=force)


def read_rules_cache() -> dict | None:
    return bench.read_cache()


def regenerate_synthetic() -> int:
    return len(generate_synthetic(force=True))


def synthetic_pdf_path(sint_id: str) -> Path | None:
    generate_synthetic()
    path = SYNTH_DIR / f"{sint_id}.pdf"
    return path if path.exists() else None


async def _run_agent_batch(
    run_id: str,
    items: list[dict],
    use_cache: bool,
    pdf_analysis: PdfAnalysis,
    crew_runner: CrewRunner,
) -> None:
    run = AGENT_RUNS[run_id]
    async with CREW_LOCK:
        os.environ["FRAUDE_MOCK_REGISTRY"] = "1"
        try:
            for item in items:
                if run["cancelar"]:
                    break
                run["actual"] = item["id"]
                row = bench.agent_cache_get(item) if use_cache else None
                if row:
                    row = {**row, "desde_cache": True}
                else:
                    try:
                        path = SYNTH_DIR / item["archivo"]
                        forense = pdf_analysis.analyze(
                            path, check_signature_region=True
                        )
                        result = await crew_runner.run(
                            {
                                "file_path": str(path),
                                "metadatos_forenses": forensic_prompt(forense),
                            },
                            task_callback=None,
                        )
                        report, _raw = parse_crew_result(result)
                        enrich_report(report, forense)
                        row = bench.agent_row(
                            item,
                            report.model_dump() if report else None,
                            None if report else "Respuesta no estructurada",
                        )
                        bench.agent_cache_put(item, row)
                    except Exception as exc:  # noqa: BLE001
                        row = bench.agent_row(item, None, str(exc)[:200])
                run["detalle"].append(row)
            run["estado"] = "cancelado" if run["cancelar"] else "completado"
        except Exception as exc:  # noqa: BLE001
            run.update(estado="error", error=str(exc))
        finally:
            os.environ.pop("FRAUDE_MOCK_REGISTRY", None)
            run["actual"] = None


async def start_agent_run(
    n: int,
    use_cache: bool,
    pdf_analysis: PdfAnalysis,
    crew_runner: CrewRunner,
) -> dict:
    if error := api_key_error():
        raise ValueError(error)
    items = bench.sample_manifest(max(1, min(n, 30)))
    run_id = uuid.uuid4().hex[:10]
    AGENT_RUNS[run_id] = {
        "id": run_id,
        "estado": "en_curso",
        "total": len(items),
        "detalle": [],
        "actual": None,
        "error": None,
        "cancelar": False,
    }
    asyncio.create_task(
        _run_agent_batch(run_id, items, use_cache, pdf_analysis, crew_runner)
    )
    return {"run_id": run_id, "total": len(items)}


def agent_run_status(run_id: str) -> dict | None:
    run = AGENT_RUNS.get(run_id)
    if run is None:
        return None
    valid_rows = [
        row for row in run["detalle"] if row["coincidencia"] != "Error del agente"
    ]
    return {
        **{key: value for key, value in run.items() if key != "cancelar"},
        "modo": "agente",
        **bench.compute_metrics(valid_rows),
        "llamadas_llm": sum(
            1 for row in run["detalle"] if not row.get("desde_cache")
        ),
        "desde_cache_n": sum(
            1 for row in run["detalle"] if row.get("desde_cache")
        ),
    }


async def _run_custom_batch(
    run_id: str, items: list[dict], crew_runner: CrewRunner
) -> None:
    run = AGENT_RUNS[run_id]
    async with CREW_LOCK:
        try:
            for item in items:
                if run["cancelar"]:
                    break
                run["actual"] = item["id"]
                if item.get("error"):
                    row = bench.agent_row(item, None, item["error"])
                else:
                    try:
                        with sanitized_pdf_for_analysis(Path(item["path"])) as safe_path:
                            result = await crew_runner.run(
                                {
                                    "file_path": str(safe_path),
                                    "metadatos_forenses": forensic_prompt(
                                        item["forense"]
                                    ),
                                },
                                task_callback=None,
                            )
                        report, _raw = parse_crew_result(result)
                        enrich_report(report, item["forense"])
                        row = bench.agent_row(
                            item,
                            report.model_dump() if report else None,
                            None
                            if report
                            else "La IA no devolvió un dictamen estructurado",
                        )
                    except Exception as exc:  # noqa: BLE001
                        row = bench.agent_row(item, None, str(exc)[:200])
                run["detalle"].append(row)
            run["estado"] = "cancelado" if run["cancelar"] else "completado"
        except Exception as exc:  # noqa: BLE001
            run.update(estado="error", error=str(exc))
        finally:
            run["actual"] = None


def prepare_custom_items(
    documents: list[tuple[str, bytes]],
    labels: list[str],
    analysis_service: AnalysisService,
) -> list[dict]:
    if len(labels) != len(documents) or any(label not in _LABELS_OK for label in labels):
        raise ValueError("Cada documento necesita una etiqueta válida")
    if len(documents) > 30:
        raise ValueError("Máximo 30 documentos por prueba")

    items = []
    for number, ((filename, content), label) in enumerate(
        zip(documents, labels), start=1
    ):
        validation, path = analysis_service.validate_and_store(filename, content)
        items.append(
            {
                "id": f"DOC-{number:03d}",
                "archivo": filename or f"documento{number}.pdf",
                "tipo": filename or "Documento propio",
                "etiqueta_real": _LABELS_OK[label],
                "path": path,
                "forense": validation.get("forense"),
                "error": None
                if path
                else "; ".join(validation.get("errores", [])),
            }
        )
    return items


async def start_custom_run(items: list[dict], crew_runner: CrewRunner) -> dict:
    if error := api_key_error():
        raise ValueError(error)
    run_id = uuid.uuid4().hex[:10]
    AGENT_RUNS[run_id] = {
        "id": run_id,
        "estado": "en_curso",
        "total": len(items),
        "detalle": [],
        "actual": None,
        "error": None,
        "cancelar": False,
    }
    asyncio.create_task(_run_custom_batch(run_id, items, crew_runner))
    return {"run_id": run_id, "total": len(items)}


def cancel_agent_run(run_id: str) -> bool:
    run = AGENT_RUNS.get(run_id)
    if run is None:
        return False
    run["cancelar"] = True
    return True
