import asyncio

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from fraude_incapacidades.api.dependencies import (
    analysis_service,
    crew_runner,
    report_service,
)
from fraude_incapacidades.application.analysis_service import api_key_error
from fraude_incapacidades.application.job_service import (
    JOBS,
    create_job as create_job_use_case,
    job_status,
    retry_job as create_retry_job,
    run_job,
)
from fraude_incapacidades.application.report_service import AnalysisResponse

router = APIRouter()


@router.post("/api/validate")
async def validate_file(file: UploadFile = File(...)):
    content = await file.read()
    validation, _ = analysis_service.validate_and_store(
        file.filename or "documento", content
    )
    return validation


@router.post("/api/jobs")
async def create_job(file: UploadFile = File(...)):
    content = await file.read()
    validation, path = analysis_service.validate_and_store(
        file.filename or "documento", content
    )
    if path is None:
        raise HTTPException(
            status_code=422,
            detail={
                "mensaje": "; ".join(validation["errores"]),
                "validacion": validation,
            },
        )
    if error := api_key_error():
        raise HTTPException(
            status_code=503,
            detail={"mensaje": error, "validacion": validation},
        )
    job_id = create_job_use_case(validation, path)
    asyncio.create_task(run_job(job_id, crew_runner))
    return {"job_id": job_id}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    status = job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return status


@router.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    if JOBS.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    new_job_id = create_retry_job(job_id)
    if new_job_id is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    asyncio.create_task(run_job(new_job_id, crew_runner))
    return {"job_id": new_job_id}


@router.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_certificate(file: UploadFile = File(...)):
    try:
        content = await file.read()
        validation, path = analysis_service.validate_and_store(
            file.filename or "documento", content
        )
        if path is None:
            return AnalysisResponse(
                status="error",
                error="; ".join(validation["errores"]),
                validacion=validation,
            )
        return await analysis_service.analyze_document(path, validation)
    except Exception as exc:  # noqa: BLE001
        return AnalysisResponse(status="error", error=str(exc))


@router.post("/api/export/pdf")
async def export_pdf(request: Request):
    payload = await request.json()
    pdf = report_service.export_pdf(payload)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="dictamen.pdf"'},
    )
