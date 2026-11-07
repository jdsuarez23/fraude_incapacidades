# Fraude en incapacidades

Sistema basado en inteligencia artificial para evaluar la autenticidad de incapacidades médicas en Colombia. El proyecto combina análisis documental, validación de reglas y revisión automatizada de fuentes relevantes para identificar posibles inconsistencias o fraudes.

La solución está separada en dos capas principales:
- `backend/`: API en Python con FastAPI y lógica de IA.
- `frontend/`: interfaz web en React con Vite.

## Estructura del repositorio

```text
fraude_incapacidades/
├── .gitignore
├── README.md
├── backend/
│   ├── .env.example
│   ├── .venv/   (entorno virtual local, no versionado)
│   ├── docs/
│   │   └── Proyecto-software-Entregable-1.pdf
│   ├── logs/
│   │   ├── crew_direct_log.txt
│   │   ├── crewai_debug.log
│   │   ├── debug_env.txt
│   │   ├── error_crew.log
│   │   ├── log.txt
│   │   └── push_log.txt
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── scripts/
│   │   └── manual/
│   │       ├── analyze_pdf.py
│   │       ├── test_adres_bypass.py
│   │       ├── test_adres_pw.py
│   │       ├── test_adres_pw2.py
│   │       ├── test_rethus_bypass.py
│   │       └── test_rethus_pw.py
│   ├── src/
│   │   └── fraude_incapacidades/
│   │       ├── api/
│   │       │   └── server.py
│   │       ├── config/
│   │       │   ├── agents.yaml
│   │       │   └── tasks.yaml
│   │       ├── tools/
│   │       │   ├── adres_tool.py
│   │       │   ├── cie10_tool.py
│   │       │   ├── eps_tool.py
│   │       │   ├── ocr_tool.py
│   │       │   ├── rethus_tool.py
│   │       │   └── search_tool.py
│   │       ├── benchmark.py
│   │       ├── crew.py
│   │       ├── export_pdf.py
│   │       ├── forensics.py
│   │       ├── init.py
│   │       ├── main.py
│   │       ├── mock_registry.py
│   │       ├── model_config.py
│   │       ├── scoring.py
│   │       ├── synthetic.py
│   │       └── validation.py
│   └── tests/
│       ├── artifacts/
│       │   ├── adres_page.html
│       │   ├── adres_page2.html
│       │   ├── adres_page3.html
│       │   ├── pdf_output.txt
│       │   ├── pdf_output_utf8.txt
│       │   ├── pdf_result.txt
│       │   └── rethus_page.html
│       ├── fixtures/
│       │   ├── dummy.pdf
│       │   ├── ejemplo_incapacidad.pdf
│       │   └── test_doc.pdf
│       ├── synthetic/
│       │   ├── manifest.json
│       │   ├── registro_mock.json
│       │   └── SINT-001.pdf ... SINT-030.pdf
│       └── test_model_config.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── eslint.config.js
│   ├── public/
│   │   └── vite.svg
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       ├── lab.css
│       ├── main.jsx
│       ├── shell.css
│       ├── assets/
│       │   └── react.svg
│       ├── components/
│       │   └── ui.jsx
│       ├── lib/
│       │   ├── api.js
│       │   ├── status.js
│       │   └── validation.js
│       └── views/
│           ├── DictamenView.jsx
│           ├── FichaView.jsx
│           ├── LabView.jsx
│           └── PanelView.jsx
```

### Descripción de carpetas

- `backend/`: lógica del sistema, API REST, agentes, validaciones y pruebas del motor de análisis.
  - `backend/.venv/`: entorno virtual local del backend; no se versiona.
  - `backend/src/fraude_incapacidades/`: código principal del backend.
  - `backend/tests/`: fixtures, documentos sintéticos y artefactos de prueba.
  - `backend/scripts/manual/`: scripts de validación manual o exploración externa.
  - `backend/logs/`: registros y diagnósticos del sistema.
- `frontend/`: interfaz de usuario para cargar documentos y visualizar resultados.
- `README.md`: guía general del proyecto.

---

## Requisitos previos

- Python 3.10 o superior
- Node.js 18+ y npm
- Chromium/Playwright para validación documental y scraping de portales
- Variable de entorno `OPENAI_API_KEY` en el backend

---

## Inicio rápido

### 1) Backend (Python / FastAPI)

Desde la raíz del proyecto:

```powershell
cd .\backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Dentro de `backend/`, crea el archivo `.env` si aún no existe:

```powershell
Copy-Item .env.example .env
```

Si no existe `.env.example`, crea manualmente `backend/.env` con las variables mínimas necesarias, por ejemplo:

```env
OPENAI_API_KEY=tu_clave_aqui
OPENAI_MODEL=gpt-4o
```

Inicia el servidor:

```powershell
cd .\backend
$env:PYTHONDONTWRITEBYTECODE="1"
$env:PYTHONPATH="$PWD\src"
.\.venv\Scripts\python.exe -m uvicorn src.fraude_incapacidades.api.server:app --reload --host 127.0.0.1 --port 8000
```

La API quedará disponible en `http://localhost:8000`.

> Nota: el backend carga las variables desde `backend/.env`. Los logs de diagnóstico del entorno virtual se guardan en `backend/.venv/logs/`.

### 2) Frontend (React / Vite)

En otra terminal:

```powershell
cd .\frontend
npm ci
npm run dev
```

La interfaz quedará disponible en `http://localhost:5173`.

---

## Flujo de uso

1. Levanta el backend y el frontend.
2. Abre la app en `http://localhost:5173`.
3. Sube un PDF o imagen de una incapacidad.
4. El sistema valida la documentación, compara la información con reglas y fuentes de referencia, y devuelve un diagnóstico con puntaje y hallazgos.

---

## Convenciones del flujo actual

- Los scripts manuales en `backend/scripts/manual/` no forman parte del flujo principal y se usan para validación o pruebas puntuales.
- Los archivos generados por ejecución local (logs, uploads, cachés y entornos virtuales) quedan fuera del control de versiones y deben mantenerse en la estructura del proyecto, no en la raíz del repositorio.
- El backend se ejecuta desde `backend/`, no desde la raíz del repo, para preservar rutas relativas y la carga correcta de `.env` y `src`.
