import asyncio
import re
import time
import uuid
from pathlib import Path

from .ports import CrewRunner
from .report_service import enrich_report, forensic_prompt, parse_crew_result
from .runtime import CREW_LOCK
from fraude_incapacidades.infrastructure.pii_redaction import (
    sanitized_pdf_for_analysis,
)

STAGES = [
    {"id": 1, "nombre": "Extracción OCR y Metadatos"},
    {"id": 2, "nombre": "Validación Clínica CIE-10"},
    {"id": 3, "nombre": "Consultas RETHUS / ADRES"},
    {"id": 4, "nombre": "Dictamen IA Explicable"},
]
JOBS: dict[str, dict] = {}
_UNAVAILABLE = re.compile(
    r"captcha|timeout|no responde|no disponible|fallos? t[eé]cnic", re.I
)


def create_job(validation: dict, path: Path) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "id": job_id,
        "estado": "en_cola",
        "validacion": validation,
        "archivo": str(path),
        "etapas": [
            {**stage, "estado": "pendiente", "nota": "", "t": None}
            for stage in STAGES
        ],
        "report": None,
        "raw_report": "",
        "error": None,
        "creado": time.time(),
    }
    JOBS[job_id]["etapas"][0].update(estado="en_curso", t=time.time())
    return job_id


def set_stage(job: dict, index: int, state: str, note: str = "") -> None:
    job["etapas"][index].update(estado=state, nota=note, t=time.time())


async def run_job(job_id: str, crew_runner: CrewRunner) -> None:
    job = JOBS[job_id]
    async with CREW_LOCK:
        job["estado"] = "en_curso"
        try:
            completed = {"count": 0}

            def on_task(output) -> None:
                completed["count"] += 1
                text = str(getattr(output, "raw", output))
                if completed["count"] == 1:
                    set_stage(job, 0, "completado", "Documento leído por visión + metadatos")
                    set_stage(job, 1, "completado", "Código CIE-10 contrastado con catálogo")
                    set_stage(job, 2, "en_curso")
                elif completed["count"] == 2:
                    if _UNAVAILABLE.search(text):
                        set_stage(
                            job,
                            2,
                            "advertencia",
                            "Una fuente externa no respondió. No es evidencia de fraude.",
                        )
                    else:
                        set_stage(job, 2, "completado", "Fuentes externas consultadas")
                    set_stage(job, 3, "en_curso")

            with sanitized_pdf_for_analysis(Path(job["archivo"])) as safe_path:
                result = await crew_runner.run(
                    {
                        "file_path": str(safe_path),
                        "metadatos_forenses": forensic_prompt(
                            job["validacion"].get("forense")
                        ),
                    },
                    task_callback=on_task,
                )
            report, raw = parse_crew_result(result)
            enrich_report(report, job["validacion"].get("forense"))
            job.update(
                report=report.model_dump() if report else None,
                raw_report=raw,
                estado="completado",
            )
            for index in (0, 1, 3):
                if job["etapas"][index]["estado"] != "completado":
                    set_stage(job, index, "completado")
            if job["etapas"][2]["estado"] in ("pendiente", "en_curso"):
                set_stage(job, 2, "completado")
            if report is None:
                set_stage(
                    job,
                    3,
                    "advertencia",
                    "Respuesta no estructurada: se conserva el texto crudo de respaldo.",
                )
        except Exception as exc:  # noqa: BLE001
            job.update(estado="error", error=str(exc))
            for stage in job["etapas"]:
                if stage["estado"] == "en_curso":
                    stage.update(estado="error", nota=str(exc)[:200])


def job_status(job_id: str) -> dict | None:
    job = JOBS.get(job_id)
    if job is None:
        return None
    return {key: value for key, value in job.items() if key != "archivo"}


def retry_job(job_id: str) -> str | None:
    job = JOBS.get(job_id)
    if job is None:
        return None
    return create_job(job["validacion"], Path(job["archivo"]))


def require_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)
