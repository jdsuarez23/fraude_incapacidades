from fraude_incapacidades.crew import crew
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


if __name__ == "__main__":
    # Ruta absoluta al PDF de ejemplo
    pdf_path = (Path(__file__).resolve(
    ).parents[2] / "tests" / "fixtures" / "ejemplo_incapacidad.pdf").as_posix()
    result = crew.kickoff(inputs={
        "file_path": pdf_path
    })
    print(result)
