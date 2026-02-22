import os
import sys
import io
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Parche estricto para Windows: Forzar que Uvicorn y Python impriman Emojis sin crashear CrewAI
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding.lower() != 'utf-8':
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
    version="1.0.0"
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

class AnalysisResponse(BaseModel):
    status: str
    report: str
    error: str | None = None

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_certificate(file: UploadFile = File(...)):
    """
    Endpoint para subir un certificado (PDF/Imagen) y ejecutar el pipeline de CrewAI.
    """
    try:
        # Guardar archivo temporal en test/uploads/
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Debugging the environment variable at runtime
        api_key = os.environ.get("OPENAI_API_KEY")
        print(f"[DEBUG] OPENAI_API_KEY present: {api_key is not None}")
        if api_key:
            print(f"[DEBUG] OPENAI_API_KEY length: {len(api_key)}, starts with: {api_key[:5]}")
        else:
            print("[DEBUG] OPENAI_API_KEY IS MISSING IN WORKER PROCESS!")
            
        # Ejecutar el CrewAI con la ruta del archivo
        result = crew.kickoff(inputs={
            "file_path": str(file_path)
        })
        
        return AnalysisResponse(
            status="success",
            report=str(result),
            error=None
        )
        
    except Exception as e:
        return AnalysisResponse(
            status="error",
            report="",
            error=str(e)
        )

@app.get("/")
def read_root():
    return {"message": "API de Fraude Incapacidades funcionando correctamente. Endpoint: POST /api/analyze"}
