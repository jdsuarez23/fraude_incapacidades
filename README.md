# Sistema IA para Evaluación de Autenticidad de Incapacidades Médicas

Este proyecto es un sistema basado en Inteligencia Artificial (CrewAI) que permite analizar certificados de incapacidad médica en Colombia para identificar posibles inconsistencias, fraudes o alteraciones en los documentos.

El sistema se compone de dos partes:
1. **Backend**: Desarrollado en Python, utilizando FastAPI y CrewAI. Gestionado con Poetry.
2. **Frontend**: Desarrollado en React con Vite y TailwindCSS.

---

## 📋 Requisitos Previos

Asegúrate de tener instalado en tu sistema:
- **Python** 3.10 o superior.
- **Poetry** (Gestor de dependencias de Python).
- **Node.js** (v18 o superior) y **npm**.
- Una clave de API de OpenAI válida (`OPENAI_API_KEY`).

---

## 🚀 Guía de Inicio Rápido

### 1. Configuración del Backend (Python / FastAPI)

El backend expone una API REST para procesar los documentos y se encarga de ejecutar la lógica de los agentes de IA.

1. Abre una terminal en la raíz del proyecto (`d:\proyectos_tech\fraude_incapacidades`).
2. Instala las dependencias del proyecto usando Poetry:
   ```bash
   poetry install
   ```
3. Crea un archivo `.env` en la raíz del proyecto (si no existe) y agrega tu clave de OpenAI:
   ```env
   OPENAI_API_KEY=tu_clave_api_aqui
   ```
4. Inicia el servidor de FastAPI. Como el proyecto usa dependencias locales sin instalación global de Poetry, usa el siguiente comando en la terminal de **VS Code** o **Antigravity** (PowerShell):
   ```powershell
   $env:PYTHONPATH="$PWD\src"; .\.venv\Scripts\python.exe -m uvicorn src.fraude_incapacidades.api.server:app --reload --port 8000
   ```
   *El backend estará disponible en `http://localhost:8000`.*

### 2. Configuración del Frontend (React / Vite)

El frontend proporciona una interfaz de usuario en modo oscuro para adjuntar documentos y ver el análisis detallado.

1. Abre una **nueva ventana/pestaña** en la terminal y navega hasta el directorio del frontend:
   ```bash
   cd frontend
   ```
2. Instala las dependencias de Node.js:
   ```bash
   npm install
   ```
4. Inicia el servidor de desarrollo de Vite (puedes abrir una nueva terminal en VS Code con el botón `+`):
   ```powershell
   npm run dev
   ```
   *El frontend estará disponible en `http://localhost:5173`.*

---

## 🧪 Uso del Sistema

1. Con ambos servidores (Backend y Frontend) en ejecución.
2. Abre tu navegador e ingresa a `http://localhost:5173`.
3. Sube un archivo PDF o imagen de un certificado de incapacidad médica.
4. El sistema, a través de los agentes de CrewAI, extraerá la información, validará con la normativa colombiana y buscará el registro médico/IPS, devolviendo un reporte detallado con un puntaje de riesgo de fraude.
