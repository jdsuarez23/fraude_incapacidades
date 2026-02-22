import os
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass

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
