import sys
from pathlib import Path

# Asegurar que el layout src/ esté en sys.path si se ejecuta como script
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Cargar variables de entorno desde .env (OPENAI_API_KEY, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()  # carga .env en el cwd
except Exception:
    pass

from fraude_incapacidades.crew import crew

if __name__ == "__main__":
    # Ruta absoluta al PDF en la carpeta test
    pdf_path = (Path(__file__).resolve().parents[2] / "test" / "ejemplo_incapacidad.pdf").as_posix()
    result = crew.kickoff(inputs={
        "file_path": pdf_path
    })
    print(result)
