from __future__ import annotations

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import importlib

try:  # Carga dinámica para evitar warnings de Pylance si no está instalado
    tool = importlib.import_module("langchain_core.tools").tool  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - fallback
    try:
        tool = importlib.import_module("langchain.tools").tool  # type: ignore[attr-defined]
    except Exception:
        # Fallback sin dependencias: decorador no-op compatible con @tool o @tool("desc")
        def tool(arg=None):  # type: ignore[misc]
            if callable(arg):
                return arg

            def _wrap(func):
                return func

            return _wrap


@tool("Extraer texto desde archivo PDF o imagen")
def ocr_tool(file_path: str) -> str:
    """
    Extrae texto desde un PDF o imagen usando OCR y PyMuPDF.
    Retorna el texto extraído.
    """
    try:
        if file_path.endswith(".pdf"):
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        elif file_path.lower().endswith((".jpg", ".png", ".jpeg")):
            img = Image.open(file_path)
            return pytesseract.image_to_string(img, lang="spa")
        else:
            return "Formato de archivo no soportado"
    except Exception as e:
        return f"Error procesando el archivo: {e}"
