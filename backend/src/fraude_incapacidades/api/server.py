import io
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

SRC_PATH = Path(__file__).resolve().parents[2]
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace"
    )

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

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
try:
    from dotenv import load_dotenv

    load_dotenv(_ENV_PATH, override=True)
except ImportError:
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

from fraude_incapacidades.api.dependencies import analysis_service
from fraude_incapacidades.application.benchmark_service import AGENT_RUNS
from fraude_incapacidades.application.job_service import JOBS, STAGES
from fraude_incapacidades.application.report_service import (
    AnalysisResponse,
    StructuredReport,
    anonymize as _anonymize,
    enrich_report as _enrich,
    forensic_prompt as _forense_prompt,
    normalize_report as _normalize_report,
    parse_crew_result as _parse_crew_result,
)
from fraude_incapacidades.application.runtime import CREW_LOCK as _CREW_LOCK
from fraude_incapacidades.api.routers.analysis import router as analysis_router
from fraude_incapacidades.api.routers.benchmark import router as benchmark_router

UPLOAD_DIR = analysis_service.storage.upload_dir

app = FastAPI(
    title="Fraude Incapacidades API",
    description="API para procesar certificados médicos usando CrewAI",
    version="2.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analysis_router)
app.include_router(benchmark_router)


@app.get("/")
def read_root():
    return {
        "message": (
            "API de Fraude Incapacidades v2.1 funcionando. "
            "Endpoints: /api/validate, /api/jobs, /api/benchmark/run"
        )
    }


__all__ = [
    "AGENT_RUNS",
    "AnalysisResponse",
    "JOBS",
    "STAGES",
    "StructuredReport",
    "UPLOAD_DIR",
    "_CREW_LOCK",
    "_anonymize",
    "_enrich",
    "_forense_prompt",
    "_normalize_report",
    "_parse_crew_result",
    "app",
]
