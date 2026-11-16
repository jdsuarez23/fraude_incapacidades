# Guía técnica del backend

## Alcance

Este documento describe el backend Python que se encuentra en `backend/`: su
API, el flujo de análisis de incapacidades, los agentes CrewAI, las
herramientas, el motor de reglas, el laboratorio sintético y los archivos de
ejecución y prueba. Se documenta el comportamiento observado en el código;
las instrucciones de agentes y tareas son objetivos del sistema, no garantías
de que un modelo siempre los cumpla.

El backend está construido con FastAPI y CrewAI. Usa PyMuPDF para leer y
renderizar PDF, OpenAI para análisis visual y generación del dictamen, y
conectores locales o externos para contrastar información. El análisis es
orientativo: el dictamen incluye un aviso de que no constituye una decisión
administrativa.

## Arquitectura por capas implementada

Se organizó como un monolito modular, manteniendo FastAPI y los contratos HTTP
existentes. No se introdujeron microservicios ni se reescribió el historial de
Git.

```text
api/
  server.py                 composición de FastAPI y montaje de routers
  dependencies.py           composición e inyección de adaptadores
  routers/                  controladores HTTP de análisis y benchmark
application/
  analysis_service.py       casos de uso de validación/análisis
  job_service.py            ciclo de vida de trabajos y progreso
  benchmark_service.py      lotes con agentes y documentos propios
  report_service.py         normalización y enriquecimiento del dictamen
  ports.py                  contratos para persistencia, PDF, Crew y exportación
  runtime.py                coordinación del recurso Crew compartido
domain/
  scoring.py                reglas deterministas y veredictos
  upload_validation.py      reglas de aceptación de cargas
  cie10_catalog.py          catálogo de referencia CIE-10
infrastructure/
  crewai_runner.py          adaptador de ejecución CrewAI
  pdf_exporter.py           adaptador de exportación PDF
  upload_storage.py         almacenamiento local de cargas
  pdf_analysis.py           adaptador de análisis PDF con PyMuPDF
tools/                      adaptadores CrewAI para verificaciones y visión
```

La dirección prevista es `api → application → domain`; la aplicación consume
contratos definidos en `application/ports.py`, y `api/dependencies.py` conecta
las implementaciones de `infrastructure/`, incluido el ejecutor CrewAI. Las fachadas
`scoring.py` y `validation.py` en la raíz siguen disponibles para preservar
imports anteriores. Algunos módulos históricos de forense y benchmark aún
combinan reglas y acceso a archivos; quedan como deuda para extraer en una
siguiente fase, sin cambiar ahora su comportamiento.

## Recorrido principal de una solicitud

1. El archivo entra por `/api/validate`, `/api/jobs` o `/api/analyze`.
2. `validate_upload` comprueba extensión PDF, tamaño máximo de 5 MB, firma
   `%PDF-` y número máximo de dos páginas. Calcula SHA-256.
3. El servidor guarda el archivo en el directorio temporal configurado y
   `analyze_pdf` obtiene metadatos y datos forenses deterministas.
4. El `Crew` ejecuta secuencialmente tres tareas:
   - extraer datos del documento y validar CIE-10;
   - contrastar EPS, RETHUS, ADRES y OSINT;
   - redactar el dictamen JSON.
5. El servidor intenta normalizar la salida JSON, anonimizar ciertos campos
   del paciente y añadir el control del motor de reglas.
6. La API devuelve el informe directamente o guarda el avance en memoria para
   que el cliente consulte el trabajo. El informe también se puede exportar a
   PDF.

Las rutas de validación técnica no necesitan un LLM. `/api/jobs` y
`/api/analyze` sí requieren `OPENAI_API_KEY`; el modo agente del laboratorio
también consume llamadas al modelo.

## API y composición de `src/fraude_incapacidades/api/`

### Inicialización y modelos

- `server.py`: inicializa entorno y logging, crea `FastAPI`, configura CORS y
  monta los routers. Conserva algunos nombres importados para compatibilidad.
- `dependencies.py`: crea `AnalysisService` y conecta `LocalUploadStorage` con
  `PyMuPDFAnalysis`, `CrewAiRunner` y `PyMuPDFReportExporter`.
- `routers/analysis.py`: controladores HTTP para validación, análisis, progreso
  de trabajos, reintento y exportación PDF.
- `routers/benchmark.py`: controladores HTTP para benchmarks, caché y
  documentos de prueba.
- `StructuredReport` y `AnalysisResponse`: modelos Pydantic definidos en
  `application/report_service.py`, usados como formato de salida.
- `STAGES` y `JOBS`: estado de trabajos en `application/job_service.py`;
  `AGENT_RUNS` se mantiene en `application/benchmark_service.py`.
- `CREW_LOCK`: bloqueo de `application/runtime.py` que serializa usos del
  objeto Crew compartido dentro de un proceso.

### Anonimización y normalización

- `_mask_name`, `_mask_id` y `anonymize`: funciones de
  `application/report_service.py` para enmascarar datos estructurados del
  paciente.
- `normalize_report`: limita el puntaje, deriva el veredicto y construye
  `StructuredReport`.
- `parse_crew_result`: extrae JSON de la respuesta del agente y conserva texto
  crudo si no se puede normalizar.
- `enrich_report`: añade el resultado forense y el control independiente de
  reglas.
- `forensic_prompt`: serializa los metadatos forenses que se entregan al Crew.

### Trabajos asíncronos

- `job_service.create_job`, `set_stage`, `run_job`, `job_status` y `retry_job`:
  crean y actualizan trabajos, coordinan etapas del Crew y entregan estado al
  controlador.
- `AnalysisService.api_key_error`: verifica la configuración requerida para
  llamadas al modelo.
- `AnalysisService.validate_and_store`: aplica validación de dominio y delega
  almacenamiento y análisis PDF a los adaptadores inyectados.

### Rutas HTTP

| Ruta | Handler | Comportamiento |
|---|---|---|
| `POST /api/validate` | `analysis.validate_file` | Devuelve la validación técnica del PDF; no ejecuta el Crew. |
| `POST /api/jobs` | `analysis.create_job` | Valida y encola un análisis; responde con `job_id`. |
| `GET /api/jobs/{job_id}` | `analysis.get_job` | Devuelve estado, etapas, validación e informe, sin revelar la ruta local del archivo. |
| `POST /api/jobs/{job_id}/retry` | `analysis.retry_job` | Crea un trabajo nuevo con el mismo archivo. |
| `POST /api/analyze` | `analyze_certificate` | Ejecuta y espera el análisis completo en una sola respuesta. |
| `POST /api/export/pdf` | `export_pdf` | Convierte el JSON recibido en un PDF descargable. |
| `POST /api/benchmark/run` | `benchmark_run` | Ejecuta el benchmark local basado en reglas, normalmente sin LLM. |
| `GET /api/benchmark/cache` | `benchmark_cache` | Devuelve resultados de reglas guardados, si existen. |
| `POST /api/benchmark/regenerate` | `benchmark_regenerate` | Regenera el conjunto de PDFs sintéticos y su registro simulado. |
| `GET /api/benchmark/pdf/{sint_id}` | `benchmark_pdf` | Sirve un PDF sintético cuyo identificador tenga formato válido. |
| `POST /api/benchmark/agent` | `benchmark_agent_start` | Ejecuta el Crew en una muestra estratificada de documentos sintéticos. |
| `GET /api/benchmark/agent/{run_id}` | `benchmark_agent_status` | Devuelve el avance y las métricas de una ejecución de benchmark. |
| `POST /api/benchmark/custom` | `benchmark_custom` | Evalúa hasta 30 PDFs aportados por el usuario frente a etiquetas declaradas. |
| `POST /api/benchmark/agent/{run_id}/cancel` | `benchmark_agent_cancel` | Marca la ejecución para que se detenga antes del siguiente documento. |
| `GET /` | `read_root` | Devuelve un mensaje de disponibilidad y algunas rutas principales. |

### Procesamiento de lotes de benchmark

- `benchmark_service.start_agent_run`, `_run_agent_batch` y
  `agent_run_status`: gestionan ejecución por agentes, caché y métricas.
- `prepare_custom_items`, `start_custom_run` y `_run_custom_batch`: preparan y
  ejecutan pruebas con PDFs aportados por el usuario.
- `cancel_agent_run`: solicita detener un lote antes del siguiente documento.
- Las rutas del benchmark determinista siguen delegando en `benchmark.py`.
- `read_root`, en `server.py`, responde en `/` con un mensaje informativo.

## Agentes y tareas CrewAI

### `src/fraude_incapacidades/crew.py`

- `_load_yaml(path)`: lee configuración YAML.
- `_build_agents(cfg)`: carga `.env`, crea el LLM si encuentra `OPENAI_API_KEY`,
  instancia las herramientas y asigna herramientas por rol. La delegación entre
  agentes está desactivada.
- `_build_tasks(cfg, agents)`: crea las tareas y falla con `ValueError` si una
  tarea referencia un agente inexistente.
- `crew`: instancia una ejecución `Process.sequential` con tres agentes y tres
  tareas, en el orden de configuración.

### Agentes declarados en `config/agents.yaml`

| Identificador | Responsabilidad | Herramientas asignadas |
|---|---|---|
| `auditor_medico_forense` | Extraer información, revisar señales documentales y contrastar CIE-10. | `PDFForensicExtractTool`, `CIE10ValidationTool` |
| `investigador_osint` | Contrastar médico, afiliación y entidades, distinguiendo ausencia de resultados de fallos técnicos. | `EPSValidationTool`, `RETHUSVerificationTool`, `ADRESVerificationTool`, `OSINTSearchTool` |
| `redactor_dictamen` | Consolidar los resultados en JSON con puntaje, verificadores y aviso legal. | Ninguna herramienta directa |

Cada agente tiene `role`, `goal` y `backstory` en YAML. Estos campos orientan
al modelo; no sustituyen validaciones deterministas.

### Tareas declaradas en `config/tasks.yaml`

1. `extract_and_validate_task`: extrae datos mediante visión, solicita la
   verificación CIE-10 y resume hallazgos documentales.
2. `search_and_verify_task`: valida EPS y solicita comprobaciones RETHUS,
   ADRES y OSINT.
3. `generate_final_report_task`: produce el esquema JSON final, las alertas,
   el desglose de puntos y los verificadores.

Las tareas reciben `file_path` y `metadatos_forenses` como variables de entrada.

## Herramientas (`src/fraude_incapacidades/tools/`)

- `ocr_tool.py` — `PDFForensicExtractTool._run(file_path)`: abre el PDF,
  renderiza hasta dos páginas, recopila texto, metadatos, imágenes y fuentes,
  y llama al modelo de visión OpenAI para estructurar los campos y evaluar el
  aspecto visual. A pesar del nombre del módulo, el texto de respaldo se
  obtiene de la capa de texto del PDF; no implementa OCR local con
  Tesseract. También acepta algunos formatos de imagen/documento, aunque la
  validación HTTP de cargas solo admite PDF.
- `cie10_tool.py` — `CIE10ValidationTool._run(input_data)` busca el código
  exacto o por prefijo y compara los días otorgados con el catálogo de dominio
  en `domain/cie10_catalog.py`.
- `eps_tool.py` — `EPS_COLOMBIA` contiene nombres y variaciones.  
  `EPSValidationTool._run(eps_name)` realiza una comparación textual
  aproximada; es un catálogo interno, no una consulta oficial en tiempo real.
- `rethus_tool.py` — `RETHUSVerificationTool._run(input_data)` valida la forma
  de entrada, prioriza el registro simulado cuando está habilitado y, de otro
  modo, intenta consultar el portal externo mediante automatización del
  navegador. Si la consulta no puede determinar un resultado, devuelve un
  estado indeterminado/no aplicable. La implementación actual automatiza el
  portal gubernamental y requiere revisión de cumplimiento antes de cualquier
  uso real; esta guía no detalla mecanismos para eludir controles del portal.
- `adres_tool.py` — `ADRESVerificationTool._run(input_data)` usa primero el
  registro simulado y, en modo real, intenta endpoints HTTP; si no puede
  obtener una respuesta estructurada, informa que la verificación queda
  pendiente y sugiere revisión manual.
- `search_tool.py` — `OSINTSearchTool._run(query)` intenta dos consultas web
  con DuckDuckGo, filtra duplicados y clasifica resultados; la falta de
  resultados o un error se expresa como no concluyente, no como prueba de
  fraude.

Todas estas clases heredan `BaseTool` de CrewAI. Sus métodos `_run` devuelven
texto, normalmente JSON, para consumo del agente.

## Reglas, validación y análisis documental

### `domain/upload_validation.py`

- `UploadValidation`: dataclass con validez, nombre, tamaño, formato, hash,
  cantidad de páginas, páginas procesables, errores y advertencias.
- `to_dict()`: convierte el dataclass a diccionario.
- `count_pdf_pages(content)`: intenta contar páginas con PyMuPDF; si falla,
  usa una búsqueda heurística de objetos de página PDF.
- `validate_upload(filename, content)`: aplica las restricciones de carga y
  calcula SHA-256. El máximo es 5 MiB y dos páginas; solo se permite `.pdf`.
- `validation.py`, en la raíz del paquete, reexporta estos símbolos para
  conservar imports existentes.

### `forensics.py`

- `EDITORES_GRAFICOS` y `UMBRAL_MODIFICACION_DIAS`: catálogo de palabras de
  editores y umbral temporal de un día.
- `parse_pdf_date(value)`: interpreta fechas PDF a `datetime` sin conservar la
  zona horaria.
- `analyze_metadata(meta)`: compara creador/productor y fechas; devuelve estado,
  fechas, posibles editores y alertas. Metadatos aplanados se califican como
  informativos por esta función.
- `detect_signature(page, region, min_ink)`: estima tinta oscura en una región
  fija de una página. Es un detector geométrico simple, no valida una firma
  criptográfica ni su autenticidad.
- `analyze_pdf(source, check_signature_region)`: lee el PDF, calcula estado
  forense, texto nativo y número de páginas; opcionalmente calcula presencia de
  tinta en la región de firma de la primera página.

### `domain/scoring.py`

- `OCR_MIN_CONFIDENCE`, `PENALTIES` y `VEREDICTOS`: definen umbral de lectura,
  ponderaciones y nombres de veredictos.
- `verdict_for(score)`: asigna `Válido` (80+), `Sospechoso` (41–79) o
  `Potencialmente Fraudulento` (0–40).
- `Dictamen`: dataclass para veredicto, puntaje, desglose, verificaciones
  pendientes y motivo; `to_dict()` lo serializa.
- `evaluate(doc)`: si recibe manuscrito u OCR menor que 70%, devuelve
  inconcluso sin puntaje. De lo contrario parte de 100 y aplica como máximo
  una penalización por regla: RETHUS/OSINT −45; forense −35; clínica −25;
  ADRES/EPS −20; formales −10. Las consultas externas no disponibles quedan
  pendientes sin penalización.
- `_norm_cie(code)`: normaliza un código para búsqueda.
- `cie10_standard_days(code)`: obtiene `dias_max` del catálogo CIE-10 por
  código exacto o prefijo.
- `arithmetic_ok(inicio, fin, dias)`: compara fechas ISO y días inclusivos;
  devuelve `None` si no puede calcular.
- `signals_from_report(report, forense)`: transforma parte del informe del
  agente y el análisis forense en señales consumibles por `evaluate`.
- `scoring.py`, en la raíz del paquete, reexporta estos símbolos por
  compatibilidad.

**Observación sobre reglas:** el texto de tareas habla de exceder en más de
100% el estándar, y `evaluate` implementa `dias_otorgados > 2 * dias_estandar`.
Además, `cie10_standard_days` usa el máximo del catálogo, por lo que la
condición resulta ser más de dos veces ese máximo, no simplemente superar el
rango recomendado. También `signals_from_report` no transfiere actualmente
los campos de manuscrito ni confianza OCR al motor de control; por ello ese
control adicional no aplica necesariamente la puerta de legibilidad que sí
existe en `evaluate`.

### `export_pdf.py`

- `_rows(pairs)`: convierte pares clave/valor en filas HTML escapadas.
- `build_html(payload)`: crea el HTML del dictamen, incluyendo puntaje,
  validación, reglas, fuentes externas, forense, hallazgos y datos extraídos.
  Los valores de `correcciones_analista` se muestran, pero el puntaje no se
  recalcula.
- `build_pdf(payload)`: usa PyMuPDF Story y DocumentWriter para paginar el HTML
  y devolver un PDF A4.

## Aplicación e infraestructura

### Capa de aplicación

- `application/analysis_service.py` — `AnalysisService` valida y coordina el
  guardado y análisis de una carga. `api_key_error()` comprueba la clave
  requerida.
- `application/ports.py` — `UploadStorage`, `PdfAnalysis` y `CrewRunner`
  definen contratos para almacenamiento, análisis documental y ejecución IA.
- `application/job_service.py` — gestiona estados y ejecución asíncrona de
  trabajos; conserva estado en memoria.
- `application/benchmark_service.py` — coordina los lotes de benchmark con
  agentes y los documentos propios.
- `application/report_service.py` — define los DTO Pydantic y transforma
  resultados del Crew al formato de salida; `ReportService` delega la
  exportación mediante el puerto `PdfExporter`.
- `application/runtime.py` — contiene el bloqueo compartido para serializar el
  uso de Crew dentro de un proceso.

### Adaptadores de infraestructura

- `infrastructure/upload_storage.py` — `LocalUploadStorage` guarda archivos
  localmente, bajo `UPLOAD_DIR` o el directorio temporal por defecto.
- `infrastructure/pdf_analysis.py` — `PyMuPDFAnalysis` adapta `analyze_pdf`
  al puerto de análisis PDF.
- `infrastructure/pdf_exporter.py` — `PyMuPDFReportExporter` adapta el
  generador de dictámenes PDF.
- `api/dependencies.py` — composición raíz que instancia la implementación
  local de almacenamiento y el adaptador PyMuPDF y los inyecta a la aplicación.
- `tools/`, `crew.py`, `mock_registry.py` y `model_config.py` siguen siendo
  adaptadores/integraciones históricas. Su organización física puede
  normalizarse en otra fase conservando los imports existentes.

## Laboratorio sintético y registros mock

### `synthetic.py`

Define 30 escenarios ficticios: casos íntegros, adulterados e ilegibles.
`SYNTH_DIR` apunta a `tests/synthetic/`.

- `_build_order()`: orden determinista de escenarios.
- `_fields(n, case)`: construye campos del certificado.
- `_draw(page, fields, firma, visible)`: escribe texto del certificado.
- `_signature(page)`: dibuja una firma/sello de prueba.
- `_scribbles(page, seed)`: dibuja trazos para casos manuscritos.
- `_to_scan(src_doc, blur, noise)`: rasteriza y degrada una página para simular
  escaneo.
- `_metadata(meta)`: genera valores de metadatos de los casos.
- `build_pdf(fields, case)`: crea un PDF nativo, escaneado, ilegible o
  manuscrito según el escenario.
- `generate(force)`: crea los PDFs, `manifest.json` y `registro_mock.json`;
  si el manifiesto ya existe, no regenera salvo `force=True`.

### `mock_registry.py`

`REGISTRY_PATH` apunta al registro sintético. `enabled()` solo habilita las
respuestas mock cuando existe el registro y `FRAUDE_MOCK_REGISTRY=1`.
`load()`, `lookup_rethus(numero)`, `lookup_adres(numero)` y
`lookup_entidad(nombre)` leen los datos simulados.
`tool_response(kind, data)` crea respuestas JSON simuladas para las
herramientas. No está pensado para verificar personas reales.

### `benchmark.py`

- `UMBRALES_WEB`, `METAS_ENTREGABLE`, `ENGINE_VERSION` y rutas de caché:
  parámetros y localización de resultados.
- `_LABELS`: etiquetas que permiten extraer texto de los PDFs sintéticos.
- `extract_fields(pdf_path)`: extrae campos etiquetados desde la capa de texto.
- `build_signals(pdf_path)`: combina extracción local, registro simulado y
  análisis forense para construir señales de scoring.
- `classify(real, veredicto)`: traduce el resultado a coincidencia, falso
  positivo, falso negativo o revisión manual.
- `_ratio(n, d)` y `_ok(value, limit, sense)`: helpers de métricas.
- `compute_metrics(detalle)`: calcula matriz de confusión, sensibilidad,
  precisión, tasas de error y derivaciones de ilegibles.
- `_fingerprint(manifest, extra)` y `pdf_sha(item)`: generan huellas para
  invalidar o consultar caché.
- `run_benchmark(use_cache, force)`: ejecuta modo reglas sobre el manifiesto,
  sin llamadas al LLM, y persiste el resultado.
- `read_cache()`: obtiene el resultado de reglas en caché.
- `agent_cache_get(item)` y `agent_cache_put(item, row)`: leen/escriben caché
  del modo agente por PDF y versión del motor.
- `agent_row(item, report, error)`: normaliza la fila de un caso procesado por
  agente.
- `sample_manifest(n)`: selecciona casos de manera estratificada y estable.

## Archivos de entrada, configuración y despliegue

- [`api/index.py`](../api/index.py): añade `src/` a `sys.path`, importa la
  instancia FastAPI y la exporta como `app` para Vercel.
- [`src/fraude_incapacidades/main.py`](../src/fraude_incapacidades/main.py):
  punto de ejecución de demostración con el PDF fixture y `crew.kickoff`.
  Importa `crew` antes de añadir `src/` al `sys.path`; puede depender de que el
  paquete ya esté instalado o que `PYTHONPATH` esté preparado.
- [`src/fraude_incapacidades/model_config.py`](../src/fraude_incapacidades/model_config.py):
  `get_openai_model()` devuelve `OPENAI_MODEL` o `gpt-4o` por defecto y rechaza
  un valor vacío.
- [`src/fraude_incapacidades/init.py`](../src/fraude_incapacidades/init.py):
  archivo vacío; no declara inicialización ni una API de paquete.
- [`pyproject.toml`](../pyproject.toml): metadatos Poetry, paquete src-layout,
  dependencias de ejecución y sistema de build.
- [`requirements.txt`](../requirements.txt): dependencias pip del backend.
- [`runtime.txt`](../runtime.txt): especifica Python 3.11 para el proveedor de
  despliegue.
- [`vercel.json`](../vercel.json): configura la función Python en
  `api/index.py` y enruta las solicitudes hacia ella.
- [`Proyecto-software-Entregable-1.pdf`](Proyecto-software-Entregable-1.pdf):
  documento de especificación del proyecto; no es código ejecutable.
- [`.env.example`](../.env.example): plantilla de variables de entorno. La clave
  real debe configurarse fuera del repositorio.

## Pruebas y utilidades manuales

- [`tests/test_model_config.py`](../tests/test_model_config.py) — `ModelConfigTests`:
  comprueba modelo por defecto/configurado, rechazo del modelo vacío,
  propagación de configuración a CrewAI y uso del modelo configurado por la
  herramienta visual.
- [`tests/fixtures/`](../tests/fixtures/): PDFs de ejemplo para pruebas y
  demostración.
- [`tests/synthetic/`](../tests/synthetic/): manifiesto, registro simulado y
  documentos generados para benchmark.
- [`tests/artifacts/`](../tests/artifacts/): capturas HTML y salidas de análisis
  guardadas durante pruebas exploratorias; no son dependencias del flujo
  principal.
- [`scripts/manual/analyze_pdf.py`](../scripts/manual/analyze_pdf.py) —
  `analyze_pdf(pdf_path, out_path)`: extrae metadatos, texto e inventario de
  imágenes a un archivo para inspección local.
- [`scripts/manual/test_adres_pw.py`](../scripts/manual/test_adres_pw.py) —
  `test_adres()`: guarda una captura HTML exploratoria del portal ADRES.
- [`scripts/manual/test_adres_pw2.py`](../scripts/manual/test_adres_pw2.py) —
  `test_adres2()`: segunda exploración/captura del portal ADRES.
- [`scripts/manual/test_adres_bypass.py`](../scripts/manual/test_adres_bypass.py)
  — `test_adres3()`: prueba manual antigua de navegación y envío de formulario.
- [`scripts/manual/test_rethus_pw.py`](../scripts/manual/test_rethus_pw.py) —
  `test_rethus(tipo, doc)`: guarda HTML del portal RETHUS para inspección.
- [`scripts/manual/test_rethus_bypass.py`](../scripts/manual/test_rethus_bypass.py)
  — `test_rethus()`: experimento manual de automatización del portal. Por
  involucrar controles de acceso de un servicio gubernamental, no se describe
  aquí cómo sortearlos; debe revisarse su legalidad y retirarse o reemplazarse
  por un canal de integración autorizado antes de producción.

Los archivos de [`logs/`](../logs/) y `.venv/logs/` son salidas diagnósticas, no
módulos del backend. Los uploads y cachés se crean durante la ejecución; no son
fuente de verdad ni base de datos transaccional.

## Consideraciones operativas y límites observados

1. **Privacidad:** `_anonymize` transforma los campos estructurados del
   paciente, pero `_parse_crew_result` también conserva `raw_report` y otros
   textos generados que podrían contener datos personales. La instrucción de
   anonimización del prompt no sustituye una sanitización de todas las salidas.
2. **CORS y acceso:** el servidor permite todos los orígenes, métodos y
   encabezados, y no implementa autenticación/autorización en estas rutas.
   Revisar antes de exponerlo a Internet.
3. **Datos efímeros:** trabajos y lotes se guardan en diccionarios en memoria;
   se pierden al reiniciar y no se comparten entre instancias serverless.
   Los PDFs cargados tampoco tienen una política de borrado implementada aquí.
4. **Robustez del agente:** extraer JSON desde el primer bloque `{...}` es una
   estrategia textual sencilla; una salida no estructurada queda en
   `raw_report`. El resultado no debe tratarse como verificación certificada.
5. **Herramientas externas:** portales web, CAPTCHA, red, dependencias de
   navegador y cambios de página pueden impedir verificaciones. El código
   intenta expresar esos casos como pendientes, pero los formatos devueltos por
   herramientas no siempre están uniformados.
6. **Pruebas automatizadas:** el único archivo Python de pruebas unitarias
   observado es `test_model_config.py`; no cubre rutas API, reglas, anonimización,
   procesamiento de archivos ni exactitud del benchmark.
7. **Datos clínicos:** los días por CIE-10 son una referencia embebida y
   orientativa; no reemplaza juicio médico ni una fuente clínica oficial
   versionada.

## Comandos de referencia

Desde `backend/`, la API puede ejecutarse con Uvicorn apuntando a
`fraude_incapacidades.api.server:app` y `PYTHONPATH=src`. El README de la raíz
describe la instalación, las variables de entorno y el comando de inicio del
proyecto. Las pruebas unitarias se pueden ejecutar con:

```powershell
python -m unittest discover -s tests
```
