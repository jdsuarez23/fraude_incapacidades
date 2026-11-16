import json
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from fraude_incapacidades.api.dependencies import (
    analysis_service,
    crew_runner,
    pdf_analysis,
)
from fraude_incapacidades.application import benchmark_service
from fraude_incapacidades.application.analysis_service import api_key_error

router = APIRouter()


@router.post("/api/benchmark/run")
def benchmark_run(use_cache: bool = True, force: bool = False):
    return benchmark_service.run_rules_benchmark(use_cache=use_cache, force=force)


@router.get("/api/benchmark/cache")
def benchmark_cache():
    cached = benchmark_service.read_rules_cache()
    if cached is None:
        raise HTTPException(status_code=404, detail="No hay resultados en caché")
    return cached


@router.post("/api/benchmark/regenerate")
def benchmark_regenerate():
    return {"total": benchmark_service.regenerate_synthetic()}


@router.get("/api/benchmark/pdf/{sint_id}")
def benchmark_pdf(sint_id: str):
    if not re.fullmatch(r"SINT-\d{3}", sint_id):
        raise HTTPException(status_code=404, detail="Id inválido")
    path = benchmark_service.synthetic_pdf_path(sint_id)
    if path is None:
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{sint_id}.pdf"'},
    )


@router.post("/api/benchmark/agent")
async def benchmark_agent_start(n: int = 6, use_cache: bool = True):
    if error := api_key_error():
        raise HTTPException(status_code=503, detail={"mensaje": error})
    return await benchmark_service.start_agent_run(
        n, use_cache, pdf_analysis, crew_runner
    )


@router.get("/api/benchmark/agent/{run_id}")
def benchmark_agent_status(run_id: str):
    status = benchmark_service.agent_run_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return status


@router.post("/api/benchmark/custom")
async def benchmark_custom(
    files: list[UploadFile] = File(...), etiquetas: str = Form(...)
):
    if error := api_key_error():
        raise HTTPException(status_code=503, detail={"mensaje": error})
    try:
        labels = json.loads(etiquetas)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail={"mensaje": "Etiquetas inválidas"})
    if len(files) > 30:
        raise HTTPException(
            status_code=422,
            detail={"mensaje": "Máximo 30 documentos por prueba"},
        )
    try:
        documents = [
            (file.filename or f"documento{number}.pdf", await file.read())
            for number, file in enumerate(files, start=1)
        ]
        items = benchmark_service.prepare_custom_items(
            documents, labels, analysis_service
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"mensaje": str(exc)}) from exc
    try:
        return await benchmark_service.start_custom_run(items, crew_runner)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"mensaje": str(exc)}) from exc


@router.post("/api/benchmark/agent/{run_id}/cancel")
def benchmark_agent_cancel(run_id: str):
    benchmark_service.cancel_agent_run(run_id)
    return {"ok": True}
