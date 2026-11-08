from fraude_incapacidades.synthetic import SYNTH_DIR, generate as generate_synthetic
from fraude_incapacidades.export_pdf import build_pdf
from fraude_incapacidades.forensics import analyze_pdf
from fraude_incapacidades import benchmark as bench
from fraude_incapacidades.scoring import verdict_for, evaluate, signals_from_report
from fraude_incapacidades.validation import validate_upload
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
import os
import sys
import io
import json
import re
import asyncio
import uuid
import time
import tempfile
from pathlib import Path

# Agregar src a sys.path para que no dependa de poetry para encontrar 'fraude_incapacidades'
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# Parche estricto para Windows: Forzar que Uvicorn y Python impriman Emojis sin crashear CrewAI
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding='utf-8', errors='replace')

# Redirigir stdout/stderr para diagnosticar bloqueos de CrewAI.
# En Vercel no siempre existe un filesystem persistente, así que usamos /tmp como fallback.
try:
    log_dir = Path(__file__).resolve().parents[3] / ".venv" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "crewai_debug.log"
    sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout
except OSError:
    temp_dir = Path(tempfile.gettempdir()) / "fraude_incapacidades"
    temp_dir.mkdir(parents=True, exist_ok=True)
    log_file = temp_dir / "crewai_debug.log"
    sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout


# Cargar variables de entorno desde .env
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH, override=True)
except ImportError:
    # Fallback manual si python-dotenv no está instalado
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

app = FastAPI(
    title="Fraude Incapacidades API",
    description="API para procesar certificados médicos usando CrewAI",
    version="2.1.0"
)

# Configurar CORS para permitir acceso desde nuestro frontend en Vite (puertos 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción debe ser la URL del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta donde se guardarán temporalmente los archivos subidos.
# En Vercel se debe usar el directorio temporal de la ejecución; no es seguro escribir en tests/.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", Path(tempfile.gettempdir()) / "fraude_incapacidades" / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class StructuredReport(BaseModel):
    puntaje_veracidad: int | None = 0
    hallazgos_medicos: str = ""
    analisis_forense: str = ""
    verificacion_entidades: str = ""
    alertas: list[str] = []
    veredicto: str = "Indeterminado"
    # Ampliaciones (HU-02, HU-03, HU-05, HU-06, HU-08)
    datos_extraidos: dict = {}
    desglose: list[dict] = []
    verificadores: list[dict] = []
    verificacion_externa_pendiente: list[str] = []
    forense: dict = {}
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


# ─── Anonimización (HU-07): se aplica en el servidor antes de responder ───
def _mask_name(value) -> str:
    parts = [p for p in re.split(r"\s+", str(value).strip()) if p]
    return " ".join(p[0] + "***" for p in parts)


def _mask_id(value) -> str:
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 8:
        return "*" * max(len(digits), 3)
    return f"{digits[:1]}.{digits[1:4]}.***.***"


def _anonymize(datos: dict) -> dict:
    out = dict(datos or {})
    paciente = out.get("paciente")
    if isinstance(paciente, dict):
        paciente = dict(paciente)
        if paciente.get("nombre"):
            paciente["nombre"] = _mask_name(paciente["nombre"])
        for k in ("numero", "cedula", "documento"):
            if paciente.get(k):
                paciente[k] = _mask_id(paciente[k])
        out["paciente"] = paciente
    return out


def _normalize_report(data: dict) -> StructuredReport:
    puntaje = data.get("puntaje_veracidad")
    veredicto = str(data.get("veredicto", "Indeterminado"))
    if "inconclus" in veredicto.lower() or "procesable" in veredicto.lower() or puntaje is None:
        veredicto, puntaje = "Inconcluso / No Procesable", None
    else:
        puntaje = max(0, min(100, int(puntaje)))
        # umbrales del Entregable 1: 80 / 41 / 0
        veredicto = verdict_for(puntaje)
    return StructuredReport(
        puntaje_veracidad=puntaje,
        hallazgos_medicos=str(data.get("hallazgos_medicos", "")),
        analisis_forense=str(data.get("analisis_forense", "")),
        verificacion_entidades=str(data.get("verificacion_entidades", "")),
        alertas=[str(a) for a in data.get("alertas", [])],
        veredicto=veredicto,
        datos_extraidos=_anonymize(data.get("datos_extraidos", {})),
        desglose=[d for d in data.get("desglose", []) if isinstance(d, dict)],
        verificadores=[v for v in data.get(
            "verificadores", []) if isinstance(v, dict)],
        verificacion_externa_pendiente=[str(x) for x in data.get(
            "verificacion_externa_pendiente", [])],
    )


def _parse_crew_result(result) -> tuple[StructuredReport | None, str]:
    """Parsea el resultado del crew intentando extraer JSON estructurado."""
    if isinstance(result, str):
        raw_text = result
    elif hasattr(result, "raw"):
        raw_text = str(result.raw)
    elif hasattr(result, "output"):
        raw_text = str(result.output)
    else:
        raw_text = str(result)

    json_match = re.search(r'\{[\s\S]*\}', raw_text)
    if json_match:
        try:
            return _normalize_report(json.loads(json_match.group())), raw_text
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return None, raw_text  # Respaldo: texto crudo (HU-06 / HU-08)


def _enrich(report: StructuredReport | None, forense: dict | None) -> None:
    """Añade el forense determinista de metadatos y el control con las reglas del Entregable 1."""
    if report is None:
        return
    report.forense = forense or {}
    if report.puntaje_veracidad is None:
        return
    d = evaluate(signals_from_report(report.model_dump(), forense))
    if d.puntaje is None:
        return
    report.control_reglas = {
        "puntaje": d.puntaje, "veredicto": d.veredicto, "desglose": d.desglose,
        "verificacion_externa_pendiente": d.verificacion_externa_pendiente,
        "diferencia": report.puntaje_veracidad - d.puntaje, "coincide_veredicto": d.veredicto == report.veredicto,
    }


def _forense_prompt(forense: dict | None) -> str:
    if not forense:
        return "No disponible"
    keys = ("estado", "creador", "productor", "fecha_creacion",
            "fecha_modificacion", "dias_entre_creacion_y_modificacion", "alertas")
    return json.dumps({k: forense.get(k) for k in keys}, ensure_ascii=False)


# ─── Jobs con progreso por etapa (HU-08: visibilidad del estado) ───
STAGES = [
    {"id": 1, "nombre": "Extracción OCR y Metadatos"},
    {"id": 2, "nombre": "Validación Clínica CIE-10"},
    {"id": 3, "nombre": "Consultas RETHUS / ADRES"},
    {"id": 4, "nombre": "Dictamen IA Explicable"},
]
JOBS: dict[str, dict] = {}
_CREW_LOCK = asyncio.Lock()  # el crew es un singleton: un análisis a la vez
_UNAVAILABLE = re.compile(
    r"captcha|timeout|no responde|no disponible|fallos? t[eé]cnic", re.I)


def _new_job(validacion: dict, path: Path) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "id": job_id, "estado": "en_cola", "validacion": validacion, "archivo": str(path),
        "etapas": [{**s, "estado": "pendiente", "nota": "", "t": None} for s in STAGES],
        "report": None, "raw_report": "", "error": None, "creado": time.time(),
    }
    JOBS[job_id]["etapas"][0].update(estado="en_curso", t=time.time())
    return job_id


def _set_stage(job: dict, idx: int, estado: str, nota: str = "") -> None:
    job["etapas"][idx].update(estado=estado, nota=nota, t=time.time())


async def _run_job(job_id: str) -> None:
    job = JOBS[job_id]
    async with _CREW_LOCK:
        job["estado"] = "en_curso"
        try:
            from fraude_incapacidades.crew import crew

            done = {"n": 0}

            def on_task(output) -> None:  # tareas del crew: 1→etapas 1-2, 2→etapa 3, 3→etapa 4
                done["n"] += 1
                text = str(getattr(output, "raw", output))
                if done["n"] == 1:
                    _set_stage(job, 0, "completado",
                               "Documento leído por visión + metadatos")
                    _set_stage(job, 1, "completado",
                               "Código CIE-10 contrastado con catálogo")
                    _set_stage(job, 2, "en_curso")
                elif done["n"] == 2:
                    if _UNAVAILABLE.search(text):
                        _set_stage(
                            job, 2, "advertencia", "Una fuente externa no respondió. No es evidencia de fraude.")
                    else:
                        _set_stage(job, 2, "completado",
                                   "Fuentes externas consultadas")
                    _set_stage(job, 3, "en_curso")

            crew.task_callback = on_task
            result = await crew.kickoff_async(inputs={"file_path": job["archivo"], "metadatos_forenses": _forense_prompt(job["validacion"].get("forense"))})
            report, raw = _parse_crew_result(result)
            _enrich(report, job["validacion"].get("forense"))
            job.update(report=report.model_dump() if report else None,
                       raw_report=raw, estado="completado")
            for i in (0, 1, 3):
                if job["etapas"][i]["estado"] != "completado":
                    _set_stage(job, i, "completado")
            if job["etapas"][2]["estado"] in ("pendiente", "en_curso"):
                _set_stage(job, 2, "completado")
            if report is None:
                _set_stage(job, 3, "advertencia",
                           "Respuesta no estructurada: se conserva el texto crudo de respaldo.")
        except Exception as e:  # noqa: BLE001
            job.update(estado="error", error=str(e))
            for et in job["etapas"]:
                if et["estado"] == "en_curso":
                    et.update(estado="error", nota=str(e)[:200])


def _require_api_key() -> str | None:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return "Configura OPENAI_API_KEY en el archivo .env para analizar documentos."
    return None


async def _save_validated(file: UploadFile) -> tuple[dict, Path | None]:
    content = await file.read()
    val = validate_upload(file.filename or "documento", content)
    if not val.valido:
        return val.to_dict(), None
    path = UPLOAD_DIR / f"{val.sha256[:12]}_{Path(val.nombre).name}"
    path.write_bytes(content)
    out = val.to_dict()
    try:
        # metadatos PDF: determinista, sin LLM
        out["forense"] = analyze_pdf(content)
    except Exception as exc:  # noqa: BLE001
        out["forense"] = {"estado": "ok", "alertas": [
            {"nivel": "leve", "texto": f"No se pudieron leer los metadatos: {exc}"}]}
    return out, path


@app.post("/api/validate")
async def validate_file(file: UploadFile = File(...)):
    """Validación técnica sin consumir LLM: formato real, peso, páginas y SHA-256 (HU-01)."""
    val, _ = await _save_validated(file)
    return val


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...)):
    """Inicia un análisis en segundo plano y devuelve el id para consultar el progreso por etapa."""
    val, path = await _save_validated(file)
    if path is None:
        raise HTTPException(status_code=422, detail={
                            "mensaje": "; ".join(val["errores"]), "validacion": val})
    if err := _require_api_key():
        raise HTTPException(status_code=503, detail={
                            "mensaje": err, "validacion": val})
    job_id = _new_job(val, path)
    asyncio.create_task(_run_job(job_id))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Consulta el estado, el progreso y el resultado de un análisis."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return {k: v for k, v in job.items() if k != "archivo"}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """Reintenta el análisis completo con el mismo archivo (HU-08)."""
    old = JOBS.get(job_id)
    if not old:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    new_id = _new_job(old["validacion"], Path(old["archivo"]))
    asyncio.create_task(_run_job(new_id))
    return {"job_id": new_id}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_certificate(file: UploadFile = File(...)):
    """Valida el archivo y espera el informe completo del crew en la misma respuesta."""
    try:
        val, path = await _save_validated(file)
        if path is None:
            return AnalysisResponse(status="error", error="; ".join(val["errores"]), validacion=val)
        if err := _require_api_key():
            return AnalysisResponse(status="error", error=err, validacion=val)
        from fraude_incapacidades.crew import crew

        async with _CREW_LOCK:
            crew.task_callback = None
            result = await crew.kickoff_async(inputs={"file_path": str(path), "metadatos_forenses": _forense_prompt(val.get("forense"))})
        report, raw_text = _parse_crew_result(result)
        _enrich(report, val.get("forense"))
        return AnalysisResponse(status="success", report=report, raw_report=raw_text, validacion=val)
    except Exception as e:  # noqa: BLE001
        return AnalysisResponse(status="error", error=str(e))


# ─── Exportación a PDF ───
@app.post("/api/export/pdf")
async def export_pdf(request: Request):
    """Genera y devuelve un PDF a partir del dictamen recibido en formato JSON."""
    payload = await request.json()
    pdf = build_pdf(payload)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="dictamen.pdf"'})


# ─── Laboratorio Ground Truth (HU-09) ───
@app.post("/api/benchmark/run")
def benchmark_run(use_cache: bool = True, force: bool = False):
    """Modo reglas: evalúa los 30 PDFs sintéticos con forense + reglas (sin LLM)."""
    return bench.run_benchmark(use_cache=use_cache, force=force)


@app.get("/api/benchmark/cache")
def benchmark_cache():
    """Devuelve los resultados del benchmark guardados en caché, si existen."""
    cached = bench.read_cache()
    if cached is None:
        raise HTTPException(
            status_code=404, detail="No hay resultados en caché")
    return cached


@app.post("/api/benchmark/regenerate")
def benchmark_regenerate():
    """Vuelve a crear los 30 PDFs sintéticos y su registro simulado."""
    return {"total": len(generate_synthetic(force=True))}


@app.get("/api/benchmark/pdf/{sint_id}")
def benchmark_pdf(sint_id: str):
    """Devuelve el PDF sintético correspondiente al identificador solicitado."""
    if not re.fullmatch(r"SINT-\d{3}", sint_id):
        raise HTTPException(status_code=404, detail="Id inválido")
    generate_synthetic()
    path = SYNTH_DIR / f"{sint_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{sint_id}.pdf"'})


AGENT_RUNS: dict[str, dict] = {}


async def _run_agent_batch(run_id: str, items: list[dict], use_cache: bool) -> None:
    run = AGENT_RUNS[run_id]
    async with _CREW_LOCK:
        # RETHUS/ADRES/OSINT simulados: solo documentos sintéticos
        os.environ["FRAUDE_MOCK_REGISTRY"] = "1"
        try:
            from fraude_incapacidades.crew import crew

            crew.task_callback = None
            for it in items:
                if run["cancelar"]:
                    break
                run["actual"] = it["id"]
                row = bench.agent_cache_get(it) if use_cache else None
                if row:
                    row = {**row, "desde_cache": True}
                else:
                    try:
                        path = SYNTH_DIR / it["archivo"]
                        forense = analyze_pdf(
                            path, check_signature_region=True)
                        res = await crew.kickoff_async(inputs={"file_path": str(path), "metadatos_forenses": _forense_prompt(forense)})
                        report, _raw = _parse_crew_result(res)
                        _enrich(report, forense)
                        row = bench.agent_row(it, report.model_dump(
                        ) if report else None, None if report else "Respuesta no estructurada")
                        bench.agent_cache_put(it, row)
                    except Exception as exc:  # noqa: BLE001
                        row = bench.agent_row(it, None, str(exc)[:200])
                run["detalle"].append(row)
            run["estado"] = "cancelado" if run["cancelar"] else "completado"
        except Exception as exc:  # noqa: BLE001
            run.update(estado="error", error=str(exc))
        finally:
            os.environ.pop("FRAUDE_MOCK_REGISTRY", None)
            run["actual"] = None


@app.post("/api/benchmark/agent")
async def benchmark_agent_start(n: int = 6, use_cache: bool = True):
    """Modo agente (consume tokens): ejecuta el crew sobre una muestra estratificada de n PDFs sintéticos."""
    if err := _require_api_key():
        raise HTTPException(status_code=503, detail={"mensaje": err})
    n = max(1, min(n, 30))
    items = bench.sample_manifest(n)
    run_id = uuid.uuid4().hex[:10]
    AGENT_RUNS[run_id] = {"id": run_id, "estado": "en_curso", "total": len(
        items), "detalle": [], "actual": None, "error": None, "cancelar": False}
    asyncio.create_task(_run_agent_batch(run_id, items, use_cache))
    return {"run_id": run_id, "total": len(items)}


@app.get("/api/benchmark/agent/{run_id}")
def benchmark_agent_status(run_id: str):
    """Consulta el progreso y las métricas de una ejecución del laboratorio."""
    run = AGENT_RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    ok = [r for r in run["detalle"] if r["coincidencia"] != "Error del agente"]
    return {
        **{k: v for k, v in run.items() if k != "cancelar"}, "modo": "agente", **bench.compute_metrics(ok),
        "llamadas_llm": sum(1 for r in run["detalle"] if not r.get("desde_cache")),
        "desde_cache_n": sum(1 for r in run["detalle"] if r.get("desde_cache")),
    }


# ─── Pruebas con documentos propios (el usuario aporta la etiqueta esperada) ───
_LABELS_OK = {"integro": "Íntegro",
              "adulterado": "Adulterado", "ilegible": "Ilegible"}


async def _run_custom_batch(run_id: str, items: list[dict]) -> None:
    run = AGENT_RUNS[run_id]
    async with _CREW_LOCK:
        try:
            from fraude_incapacidades.crew import crew

            crew.task_callback = None
            for it in items:
                if run["cancelar"]:
                    break
                run["actual"] = it["id"]
                if it.get("error"):
                    row = bench.agent_row(it, None, it["error"])
                else:
                    try:
                        res = await crew.kickoff_async(inputs={"file_path": str(it["path"]), "metadatos_forenses": _forense_prompt(it["forense"])})
                        report, _raw = _parse_crew_result(res)
                        _enrich(report, it["forense"])
                        row = bench.agent_row(it, report.model_dump(
                        ) if report else None, None if report else "La IA no devolvió un dictamen estructurado")
                    except Exception as exc:  # noqa: BLE001
                        row = bench.agent_row(it, None, str(exc)[:200])
                run["detalle"].append(row)
            run["estado"] = "cancelado" if run["cancelar"] else "completado"
        except Exception as exc:  # noqa: BLE001
            run.update(estado="error", error=str(exc))
        finally:
            run["actual"] = None


@app.post("/api/benchmark/custom")
async def benchmark_custom(files: list[UploadFile] = File(...), etiquetas: str = Form(...)):
    """Evalúa documentos reales subidos por el usuario contra la etiqueta que él indicó (consume IA)."""
    if err := _require_api_key():
        raise HTTPException(status_code=503, detail={"mensaje": err})
    try:
        labels = json.loads(etiquetas)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail={
                            "mensaje": "Etiquetas inválidas"})
    if len(labels) != len(files) or any(l not in _LABELS_OK for l in labels):
        raise HTTPException(status_code=422, detail={
                            "mensaje": "Cada documento necesita una etiqueta válida"})
    if len(files) > 30:
        raise HTTPException(status_code=422, detail={
                            "mensaje": "Máximo 30 documentos por prueba"})
    items = []
    for n, (f, lab) in enumerate(zip(files, labels), start=1):
        val, path = await _save_validated(f)
        items.append({
            "id": f"DOC-{n:03d}", "archivo": f.filename or f"documento{n}.pdf", "tipo": f.filename or "Documento propio",
            "etiqueta_real": _LABELS_OK[lab], "path": path, "forense": val.get("forense"),
            "error": None if path else "; ".join(val["errores"]),
        })
    run_id = uuid.uuid4().hex[:10]
    AGENT_RUNS[run_id] = {"id": run_id, "estado": "en_curso", "total": len(
        items), "detalle": [], "actual": None, "error": None, "cancelar": False}
    asyncio.create_task(_run_custom_batch(run_id, items))
    return {"run_id": run_id, "total": len(items)}


@app.post("/api/benchmark/agent/{run_id}/cancel")
def benchmark_agent_cancel(run_id: str):
    """Solicita cancelar una ejecución del laboratorio antes del siguiente documento."""
    if run_id in AGENT_RUNS:
        AGENT_RUNS[run_id]["cancelar"] = True
    return {"ok": True}


@app.get("/")
def read_root():
    """Devuelve un mensaje de disponibilidad y las rutas principales de la API."""
    return {"message": "API de Fraude Incapacidades v2.1 funcionando. Endpoints: /api/validate, /api/jobs, /api/benchmark/run"}
