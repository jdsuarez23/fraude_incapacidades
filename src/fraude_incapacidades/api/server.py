import os
import sys
import io
import json
import re
from pathlib import Path

# Agregar src a sys.path para que no dependa de poetry para encontrar 'fraude_incapacidades'
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Parche estricto para Windows: Forzar que Uvicorn y Python impriman Emojis sin crashear CrewAI
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Redirigir stdout/stderr para diagnosticar bloqueos de CrewAI
log_file = Path(__file__).resolve().parents[3] / "src" / "crewai_debug.log"
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

# Importamos el Crew para ejecutar la lógica de la IA
from fraude_incapacidades.crew import crew

app = FastAPI(
    title="Fraude Incapacidades API",
    description="API para procesar certificados médicos usando CrewAI",
    version="2.0.0"
)

# Configurar CORS para permitir acceso desde nuestro frontend en Vite (puertos 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción debe ser la URL del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta donde se guardarán temporalmente los archivos subidos
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "test" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class StructuredReport(BaseModel):
    puntaje_veracidad: int = 0
    hallazgos_medicos: str = ""
    analisis_forense: str = ""
    verificacion_entidades: str = ""
    alertas: list[str] = []
    veredicto: str = "Indeterminado"


class AnalysisResponse(BaseModel):
    status: str
    report: StructuredReport | None = None
    raw_report: str = ""
    error: str | None = None


def _parse_crew_result(result) -> tuple[StructuredReport | None, str]:
    """Parsea el resultado del crew intentando extraer JSON estructurado."""
    raw_text = ""
    if isinstance(result, str):
        raw_text = result
    elif hasattr(result, "raw"):
        raw_text = str(result.raw)
    elif hasattr(result, "output"):
        raw_text = str(result.output)
    else:
        raw_text = str(result)

    # Try to extract JSON from the text (it may be wrapped in markdown code blocks)
    json_match = re.search(r'\{[\s\S]*\}', raw_text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            report = StructuredReport(
                puntaje_veracidad=int(data.get("puntaje_veracidad", 0)),
                hallazgos_medicos=str(data.get("hallazgos_medicos", "")),
                analisis_forense=str(data.get("analisis_forense", "")),
                verificacion_entidades=str(data.get("verificacion_entidades", "")),
                alertas=data.get("alertas", []),
                veredicto=str(data.get("veredicto", "Indeterminado")),
            )
            return report, raw_text
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Fallback: return as raw text
    return None, raw_text


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_certificate(file: UploadFile = File(...)):
    """
    Endpoint para subir un certificado (PDF/Imagen) y ejecutar el pipeline de CrewAI.
    Retorna un informe estructurado con puntaje, hallazgos, análisis forense y veredicto.
    """
    try:
        # Guardar archivo temporal en test/uploads/
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Ejecutar el CrewAI con la ruta del archivo
        result = crew.kickoff(inputs={
            "file_path": str(file_path)
        })
        
        # Parse structured report
        report, raw_text = _parse_crew_result(result)
        
        return AnalysisResponse(
            status="success",
            report=report,
            raw_report=raw_text,
            error=None
        )
        
    except Exception as e:
        return AnalysisResponse(
            status="error",
            report=None,
            raw_report="",
            error=str(e)
        )

@app.get("/")
def read_root():
    return {"message": "API de Fraude Incapacidades v2.0 funcionando correctamente. Endpoint: POST /api/analyze"}
