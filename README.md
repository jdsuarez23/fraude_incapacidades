# Sistema IA para Evaluación de Autenticidad de Incapacidades Médicas

Este proyecto es un sistema basado en Inteligencia Artificial (CrewAI) que permite analizar certificados de incapacidad médica en Colombia para identificar posibles inconsistencias, fraudes o alteraciones en los documentos.

El sistema se compone de dos partes:
1. **Backend**: Desarrollado en Python, utilizando FastAPI y CrewAI. Gestionado con Poetry.
2. **Frontend**: Desarrollado en React con Vite y TailwindCSS.

## Estructura y documentación

- [`docs/diagrams/`](./docs/diagrams/): 
- [`frontend/`](./frontend/): aplicación React con su configuración y código fuente.
- [`src/fraude_incapacidades/`](./src/fraude_incapacidades/): API, agentes y herramientas del backend.
- [`tests/`](./tests/): pruebas automatizadas, archivos de ejemplo en `fixtures/`, resultados manuales en `artifacts/` y archivos cargados en `uploads/`.
- [`scripts/manual/`](./scripts/manual/): scripts de exploración de portales externos. Se ejecutan desde la raíz y dependen de la disponibilidad de los portales; no forman parte del flujo principal de la aplicación.
- [`logs/`](./logs/): registro histórico de publicación.

---

## Requisitos Previos

Asegúrate de tener instalado en tu sistema:
- **Python** 3.11.
- **Node.js** (v18 o superior) y **npm**.
- Una clave de API de OpenAI válida (`OPENAI_API_KEY`).

---

## Guía de Inicio Rápido

### 1. Configuración del Backend (Python / FastAPI)

El backend expone una API REST para procesar los documentos y se encarga de ejecutar la lógica de los agentes de IA.

1. Abre una terminal PowerShell en la raíz del proyecto.
2. Crea el entorno virtual e instala las dependencias:
   ```bash
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m playwright install chromium
   ```
3. Si aún no tienes un archivo `.env`, copia la plantilla desde la raíz del proyecto:
   ```powershell
   Copy-Item .env.example .env
   ```
   Después, agrega tu clave de OpenAI a `OPENAI_API_KEY` en `.env`. No compartas ese archivo.
   `OPENAI_MODEL` configura el modelo de los agentes y el análisis visual. Si se omite, se usa `gpt-4o`; cualquier alternativa debe admitir imágenes y Chat Completions. Reinicia el backend tras cambiarlo.
4. Inicia el servidor de FastAPI:
   ```powershell
   $env:PYTHONDONTWRITEBYTECODE="1"
   $env:PYTHONPATH="$PWD\src"
   .\.venv\Scripts\python.exe -m uvicorn src.fraude_incapacidades.api.server:app --reload --host 127.0.0.1 --port 8000
   ```
   *El backend estará disponible en `http://localhost:8000`. Sin `OPENAI_API_KEY`, la API inicia, pero no procesa análisis.*
   *La consulta automatizada de RETHUS requiere Chromium y depende de la disponibilidad y las restricciones del portal.*

### 2. Configuración del Frontend (React / Vite)

El frontend proporciona una interfaz de usuario en modo oscuro para adjuntar documentos y ver el análisis detallado.

1. Abre una **nueva ventana/pestaña** en la terminal y navega hasta el directorio del frontend:
   ```bash
   cd .\frontend
   ```
2. Instala las dependencias de Node.js:
   ```bash
   npm ci
   ```
3. Inicia el servidor de desarrollo de Vite:
   ```powershell
   npm run dev
   ```
   *El frontend estará disponible en `http://localhost:5173`.*

---

## Uso del Sistema

1. Con ambos servidores (Backend y Frontend) en ejecución.
2. Abre tu navegador e ingresa a `http://localhost:5173`.
3. Sube un archivo PDF o imagen de un certificado de incapacidad médica.
4. El sistema, a través de los agentes de CrewAI, extraerá la información, validará con la normativa colombiana y buscará el registro médico/IPS, devolviendo un reporte detallado con un puntaje de riesgo de fraude.
