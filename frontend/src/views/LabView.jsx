import { useEffect, useRef, useState } from "react";
import { Badge } from "../components/ui.jsx";
import {
  cancelAgentBatch,
  getAgentBatch,
  getBenchmarkCache,
  regenerateSynthetic,
  runBenchmark,
  startAgentBatch,
  startCustomBatch,
  syntheticPdfUrl,
} from "../lib/api.js";
import { fmtMB, validateFile } from "../lib/validation.js";

const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
const fit = (c) =>
  c === null
    ? ["idle", "Sin datos"]
    : c
      ? ["ok", "Cumple"]
      : ["bad", "No cumple"];
const MATCH_TONE = {
  Correcto: "ok",
  "Derivado a Revisión Manual": "info",
  "Derivado a revisión (no esperado)": "warn",
  "Falso Positivo": "bad",
  "Falso Negativo": "warn",
  "Error de puerta OCR": "bad",
  "Error del agente": "bad",
};
const MATCH_LABEL = {
  Correcto: "Coincide",
  "Derivado a Revisión Manual": "Revisión manual (esperado)",
  "Derivado a revisión (no esperado)": "Revisión manual (no esperado)",
  "Falso Positivo": "Falso positivo",
  "Falso Negativo": "Falso negativo",
  "Error de puerta OCR": "No lo detectó ilegible",
  "Error del agente": "No se pudo analizar",
};
const MATCH_TEXT = {
  Correcto: "La IA llegó a la misma conclusión que la etiqueta.",
  "Derivado a Revisión Manual":
    "El documento es ilegible y la IA lo envió a revisión manual, como se esperaba.",
  "Derivado a revisión (no esperado)":
    "La IA no pudo procesar el documento y lo envió a revisión manual; no cuenta como acierto ni como error.",
  "Falso Positivo":
    "Falso positivo: la etiqueta decía íntegro, pero la IA lo marcó como sospechoso o fraudulento.",
  "Falso Negativo":
    "Falso negativo: la etiqueta decía adulterado, pero la IA lo dio por válido.",
  "Error de puerta OCR":
    "La etiqueta decía ilegible, pero la IA le asignó un puntaje en lugar de enviarlo a revisión manual.",
  "Error del agente": "No se pudo completar el análisis de este documento.",
};
const REAL_LABEL = {
  Íntegro: "Íntegro",
  Adulterado: "Adulterado",
  Ilegible: "Ilegible",
};
const FZ_LABEL = {
  ok: "Sin hallazgos",
  aplanados: "Aplanados",
  editor_grafico: "Editor gráfico",
};
const KPIS = [
  ["sensibilidad", "Sensibilidad (adulterados detectados)", "≥"],
  ["precision", "Precisión (alertas acertadas)", "≥"],
  ["falsos_negativos", "Falsos negativos", "≤"],
  ["falsos_positivos", "Falsos positivos", "≤"],
];
const netMsg = (e) =>
  e.message === "Failed to fetch"
    ? "No se pudo conectar con el servidor. Verifica que esté en ejecución."
    : e.message;

function PreviewDrawer({ row, url, onClose }) {
  const closeRef = useRef(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div
        className="sg-drawer-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="sg-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Vista previa de ${row.id}`}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 8,
            alignItems: "center",
          }}
        >
          <h3>
            {row.id} · {row.tipo}
          </h3>
          <button
            ref={closeRef}
            type="button"
            className="sg-btn sm"
            onClick={onClose}
          >
            Cerrar
          </button>
        </div>
        {url ? (
          <iframe
            title={`Vista previa de ${row.id}`}
            src={`${url}#toolbar=0&navpanes=0`}
          />
        ) : (
          <p className="sg-muted">Sin vista previa disponible.</p>
        )}
        {url && (
          <a className="sg-link" href={url} target="_blank" rel="noreferrer">
            Abrir en pestaña nueva
          </a>
        )}
        <div className="glass sg-card">
          <p style={{ margin: "0 0 8px" }}>
            <b>Etiqueta:</b>{" "}
            {REAL_LABEL[row.etiqueta_real] || row.etiqueta_real} ·{" "}
            <b>Resultado de la IA:</b> {row.veredicto_completo}
            {row.puntaje != null ? ` (${row.puntaje}/100)` : ""}
          </p>
          <Badge tone={MATCH_TONE[row.coincidencia] || "idle"}>
            {MATCH_LABEL[row.coincidencia] || row.coincidencia}
          </Badge>
          <p className="sg-muted" style={{ margin: "8px 0 0" }}>
            {MATCH_TEXT[row.coincidencia]}
            {row.error ? ` (${row.error})` : ""}
          </p>
          {(row.desglose || []).length > 0 && (
            <ul className="sg-list" style={{ marginTop: 10 }}>
              {row.desglose.map((d, i) => (
                <li key={i}>
                  <span>{d.detalle || d.regla}</span>
                  <Badge tone="bad">{d.puntos} pts</Badge>
                </li>
              ))}
            </ul>
          )}
          {row.forense && (
            <p className="sg-muted" style={{ margin: "8px 0 0" }}>
              Metadatos del PDF: {FZ_LABEL[row.forense.estado]}
            </p>
          )}
          {row.control_reglas && (
            <p className="sg-muted" style={{ margin: "8px 0 0" }}>
              Control con las reglas automáticas: {row.control_reglas.puntaje}
              /100 ({row.control_reglas.veredicto}).
            </p>
          )}
        </div>
      </aside>
    </>
  );
}

function Results({ data, shown, partial, urlFor }) {
  const [preview, setPreview] = useState(null);
  const m = data.metricas,
    mx = data.matriz;
  return (
    <div aria-live="polite">
      <p className="sg-muted" style={{ margin: "0 0 10px" }}>
        {partial ? (
          <Badge tone="info">
            {data.detalle.length} de {data.total} documentos analizados ·
            resultados parciales
          </Badge>
        ) : data.aprobado ? (
          <Badge tone="ok">Lote aprobado</Badge>
        ) : (
          <Badge tone="bad">Lote no aprobado</Badge>
        )}{" "}
        {data.modo === "reglas" &&
          (data.desde_cache
            ? "Resultados guardados de una ejecución anterior"
            : `Evaluado en ${data.duracion_ms} ms`)}
        {data.modo === "agente" &&
          `${data.llamadas_llm} análisis nuevos · ${data.desde_cache_n} reutilizados`}
      </p>
      <div className="sg-kpis">
        {KPIS.map(([k, label, op]) => (
          <div
            key={k}
            className={`glass sg-card sg-kpi ${fit(m[k].cumple)[0]}`}
          >
            <span className="sg-muted">{label}</span>
            <b>{pct(m[k].valor)}</b>
            <span className="sg-muted">
              Meta {op} {pct(m[k].meta_web)}{" "}
              <Badge tone={fit(m[k].cumple)[0]}>{fit(m[k].cumple)[1]}</Badge>
            </span>
            <div
              className="sg-muted"
              style={{ fontSize: ".7rem", marginTop: 4 }}
            >
              Meta del proyecto completo: {op} {pct(m[k].meta_entregable)}
            </div>
          </div>
        ))}
        <div
          className={`glass sg-card sg-kpi ${fit(m.ilegibles_derivados.cumple)[0]}`}
        >
          <span className="sg-muted">Ilegibles enviados a revisión manual</span>
          <b>{pct(m.ilegibles_derivados.valor)}</b>
          <span className="sg-muted">
            {m.ilegibles_derivados.derivados}/{m.ilegibles_derivados.total}{" "}
            <Badge tone={fit(m.ilegibles_derivados.cumple)[0]}>
              {fit(m.ilegibles_derivados.cumple)[1]}
            </Badge>
          </span>
        </div>
      </div>

      <div className="sg-lab">
        <section className="glass sg-card" aria-labelledby="h-mx">
          <h3 id="h-mx">
            Matriz de confusión: etiqueta vs. resultado de la IA
          </h3>
          <div className="sg-matrix">
            <span />
            <span className="sg-axis">IA: sospechoso</span>
            <span className="sg-axis">IA: válido</span>
            <span className="sg-axis" style={{ writingMode: "vertical-rl" }}>
              Adulterado
            </span>
            <div className="sg-cell m-vp">
              Acierto: detectó el adulterado<b>{mx.vp}</b>
            </div>
            <div className="sg-cell m-fn">
              Falso negativo: lo dio por válido<b>{mx.fn}</b>
            </div>
            <span className="sg-axis" style={{ writingMode: "vertical-rl" }}>
              Íntegro
            </span>
            <div className="sg-cell m-fp">
              Falso positivo: acusó a un íntegro<b>{mx.fp}</b>
            </div>
            <div className="sg-cell m-vn">
              Acierto: aceptó el íntegro<b>{mx.vn}</b>
            </div>
          </div>
          <p className="sg-muted" style={{ marginTop: 10 }}>
            Los ilegibles enviados a revisión manual no entran en la matriz.
          </p>
        </section>

        <section className="glass sg-card" aria-labelledby="h-dt">
          <h3 id="h-dt">Detalle por documento</h3>
          <div className="sg-table-wrap">
            <table className="sg-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Documento</th>
                  <th>Etiqueta</th>
                  <th>Resultado IA</th>
                  <th>Puntaje</th>
                  <th>Coincidencia</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.detalle.slice(0, shown).map((r) => (
                  <tr key={r.id}>
                    <td className="sg-mono">{r.id}</td>
                    <td>{r.tipo}</td>
                    <td>{REAL_LABEL[r.etiqueta_real] || r.etiqueta_real}</td>
                    <td>{r.veredicto_ia}</td>
                    <td>{r.puntaje ?? "—"}</td>
                    <td>
                      <Badge tone={MATCH_TONE[r.coincidencia] || "idle"}>
                        {MATCH_LABEL[r.coincidencia] || r.coincidencia}
                      </Badge>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="sg-btn sm"
                        onClick={() => setPreview(r)}
                      >
                        Ver
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      {preview && (
        <PreviewDrawer
          row={preview}
          url={urlFor(preview)}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}

function CustomForm({ busy, running, onRun }) {
  const [items, setItems] = useState([]);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);
  const urls = useRef([]);
  useEffect(
    () => () => urls.current.forEach((u) => URL.revokeObjectURL(u)),
    [],
  );

  const add = async (fileList) => {
    const added = [];
    for (const f of Array.from(fileList)) {
      const v = await validateFile(f);
      const url = URL.createObjectURL(f);
      urls.current.push(url);
      added.push({ file: f, url, v, label: "" });
    }
    setItems((cur) => [...cur, ...added].slice(0, 30));
  };
  const setLabel = (i, label) =>
    setItems((cur) => cur.map((it, k) => (k === i ? { ...it, label } : it)));
  const remove = (i) => setItems((cur) => cur.filter((_, k) => k !== i));
  const valid = items.filter((it) => it.v.valido);
  const ready = valid.length > 0 && valid.every((it) => it.label);

  return (
    <div className="glass sg-card" style={{ marginBottom: 14 }}>
      <h3>Prueba con tus propios documentos</h3>
      <p className="sg-muted" style={{ marginTop: 0 }}>
        Sube certificados en PDF y marca qué esperas de cada uno (íntegro,
        adulterado o ilegible). La IA los analiza sin saber la etiqueta y luego
        se compara: coincide, falso positivo o falso negativo. Usa solo
        documentos sintéticos o anonimizados.
      </p>
      <button
        type="button"
        className={`sg-drop-files ${drag ? "active" : ""}`}
        disabled={running}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          add(e.dataTransfer.files);
        }}
      >
        <strong>Arrastra los PDF aquí</strong>{" "}
        <span className="sg-muted">
          o haz clic para elegirlos · máx. 5 MB y 2 páginas cada uno · hasta 30
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        hidden
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />

      {items.length > 0 && (
        <div className="sg-doclist">
          {items.map((it, i) => (
            <div
              key={`${it.file.name}-${i}`}
              className={`sg-docrow ${it.v.valido ? "" : "invalid"}`}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 600,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {it.file.name}
                </div>
                <div className="sg-muted">
                  {fmtMB(it.v.tamano)}
                  {it.v.paginas ? ` · ${it.v.paginas} pág.` : ""}
                  {!it.v.valido && (
                    <span style={{ color: "var(--bad)" }}>
                      {" "}
                      · {it.v.errores[0]}
                    </span>
                  )}
                </div>
              </div>
              <select
                className="sg-select"
                aria-label={`Etiqueta de ${it.file.name}`}
                value={it.label}
                disabled={!it.v.valido || running}
                onChange={(e) => setLabel(i, e.target.value)}
              >
                <option value="">Elige la etiqueta…</option>
                <option value="integro">Íntegro (auténtico)</option>
                <option value="adulterado">Adulterado</option>
                <option value="ilegible">Ilegible / manuscrito</option>
              </select>
              <a
                className="sg-link"
                href={it.url}
                target="_blank"
                rel="noreferrer"
              >
                Ver
              </a>
              <button
                type="button"
                className="sg-btn sm ghost"
                disabled={running}
                onClick={() => remove(i)}
                aria-label={`Quitar ${it.file.name}`}
              >
                Quitar
              </button>
            </div>
          ))}
        </div>
      )}
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          className="sg-btn primary"
          disabled={!ready || busy || running}
          onClick={() =>
            onRun(
              valid.map((it) => it.file),
              valid.map((it) => it.label),
              valid.map((it) => it.url),
            )
          }
        >
          Evaluar con la IA
        </button>
        <span className="sg-muted">
          {items.length === 0
            ? "Aún no has subido documentos."
            : ready
              ? `${valid.length} documento(s) listos. Cada uno cuesta un análisis completo de la IA.`
              : "Falta elegir la etiqueta de todos los documentos válidos."}
        </span>
      </div>
    </div>
  );
}

export default function LabView() {
  const [mode, setMode] = useState("rapida");
  const [data, setData] = useState(null);
  const [shown, setShown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [n, setN] = useState(6);
  const [useCache, setUseCache] = useState(true);
  const [run, setRun] = useState(null);
  const customUrls = useRef([]);
  const timer = useRef(null);
  const poll = useRef(null);

  useEffect(
    () => () => {
      clearInterval(timer.current);
      clearInterval(poll.current);
    },
    [],
  );

  const reveal = (d) => {
    clearInterval(timer.current);
    setData(d);
    setShown(0);
    let k = 0;
    timer.current = setInterval(() => {
      k += 2;
      setShown(k);
      if (k >= d.detalle.length) clearInterval(timer.current);
    }, 40);
  };
  const guard = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(netMsg(e));
    } finally {
      setBusy(false);
    }
  };
  const runRules = (opts, loader = runBenchmark) =>
    guard(async () => reveal(await loader(opts)));
  const regenerate = () =>
    guard(async () => {
      await regenerateSynthetic();
      reveal(await runBenchmark({ useCache: false, force: true }));
    });

  const watch = (run_id) => {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const s = await getAgentBatch(run_id);
        setRun(s);
        setData(s);
        setShown(s.detalle.length);
        if (s.estado !== "en_curso") clearInterval(poll.current);
      } catch (e) {
        clearInterval(poll.current);
        setError(netMsg(e));
      }
    }, 2000);
  };
  const startAI = () =>
    guard(async () => {
      const { run_id, total } = await startAgentBatch({ n, useCache });
      setData(null);
      setRun({ id: run_id, estado: "en_curso", total, detalle: [] });
      watch(run_id);
    });
  const startCustom = (files, labels, urls) =>
    guard(async () => {
      const { run_id, total } = await startCustomBatch(files, labels);
      customUrls.current = urls;
      setData(null);
      setRun({ id: run_id, estado: "en_curso", total, detalle: [] });
      watch(run_id);
    });
  const cancel = () => run && cancelAgentBatch(run.id).catch(() => {});
  const switchMode = (m) => {
    setMode(m);
    setData(null);
    setError(null);
    setRun(null);
    clearInterval(poll.current);
    clearInterval(timer.current);
  };
  const running = run?.estado === "en_curso";
  const urlFor = (row) =>
    mode === "mios"
      ? customUrls.current[Number(row.id.slice(4)) - 1]
      : syntheticPdfUrl(row.id);

  const Progress = () =>
    run && (
      <div style={{ marginTop: 10 }}>
        <div
          className="sg-progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={run.total}
          aria-valuenow={run.detalle.length}
        >
          <i style={{ width: `${(run.detalle.length / run.total) * 100}%` }} />
        </div>
        <span className="sg-muted">
          {run.detalle.length}/{run.total} ·{" "}
          {running ? `analizando ${run.actual || "…"}` : run.estado}
          {run.error ? ` · ${run.error}` : ""}
        </span>
        {running && (
          <button
            type="button"
            className="sg-btn sm"
            style={{ marginLeft: 10 }}
            onClick={cancel}
          >
            Cancelar
          </button>
        )}
      </div>
    );

  return (
    <>
      <h1 className="sg-title">
        Laboratorio de validación{" "}
        <small>HU-09 · comprueba si la IA llega a la conclusión esperada</small>
      </h1>
      <div className="sg-tabs" role="tablist" aria-label="Tipo de prueba">
        <button
          type="button"
          role="tab"
          className="sg-tab"
          aria-selected={mode === "rapida"}
          onClick={() => switchMode("rapida")}
        >
          Prueba rápida · sin costo
        </button>
        <button
          type="button"
          role="tab"
          className="sg-tab"
          aria-selected={mode === "ia"}
          onClick={() => switchMode("ia")}
        >
          Prueba con IA completa
        </button>
        <button
          type="button"
          role="tab"
          className="sg-tab"
          aria-selected={mode === "mios"}
          onClick={() => switchMode("mios")}
        >
          Mis documentos
        </button>
      </div>

      {mode === "rapida" && (
        <div
          className="glass sg-banner b-ok"
          style={{
            marginBottom: 14,
            display: "flex",
            gap: 12,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <span>
            <strong>30 certificados de prueba, sin costo de IA.</strong> Se
            revisan con las reglas automáticas: metadatos del archivo, fechas,
            días de incapacidad, firma y consultas simuladas de RETHUS/ADRES.
          </span>
          <span
            style={{
              marginLeft: "auto",
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <button
              type="button"
              className="sg-btn primary sm"
              disabled={busy}
              onClick={() => runRules({ useCache: false, force: true })}
            >
              Ejecutar lote de prueba
            </button>
            <button
              type="button"
              className="sg-btn sm"
              disabled={busy}
              onClick={() => runRules({}, getBenchmarkCache)}
            >
              Cargar resultados guardados
            </button>
            <button
              type="button"
              className="sg-btn sm ghost"
              disabled={busy}
              onClick={regenerate}
              title="Vuelve a crear los 30 PDFs de prueba"
            >
              Regenerar PDFs de prueba
            </button>
          </span>
        </div>
      )}

      {mode === "ia" && (
        <div className="glass sg-banner b-warn" style={{ marginBottom: 14 }}>
          <div
            style={{
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <span>
              <strong>
                La IA analiza los certificados de prueba como si fueran
                documentos reales.
              </strong>{" "}
              Tarda más y tiene un costo por documento; los resultados se
              guardan para no repetir el gasto.
            </span>
            <span
              style={{
                marginLeft: "auto",
                display: "flex",
                gap: 8,
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <label className="sg-muted">
                Documentos a evaluar{" "}
                <select
                  className="sg-select"
                  value={n}
                  onChange={(e) => setN(+e.target.value)}
                  disabled={running}
                >
                  {[3, 6, 10, 15, 30].map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label className="sg-muted">
                <input
                  type="checkbox"
                  checked={useCache}
                  onChange={(e) => setUseCache(e.target.checked)}
                  disabled={running}
                />{" "}
                Reutilizar análisis guardados
              </label>
              <button
                type="button"
                className="sg-btn primary sm"
                disabled={busy || running}
                onClick={startAI}
              >
                Ejecutar con IA
              </button>
            </span>
          </div>
          <Progress />
        </div>
      )}

      {mode === "mios" && (
        <>
          <CustomForm busy={busy} running={running} onRun={startCustom} />
          <Progress />
        </>
      )}

      {error && (
        <div className="sg-alert b-bad" role="alert">
          {error}
        </div>
      )}
      {!data && !error && mode !== "mios" && !run && (
        <div className="glass sg-card">
          <p className="sg-muted">
            {mode === "rapida"
              ? "Aún no hay resultados. Ejecuta el lote para revisar los 30 certificados SINT-001 a SINT-030, o carga los resultados de la última ejecución."
              : "Elige cuántos certificados evaluar (una muestra equilibrada de íntegros, adulterados e ilegibles) y ejecútalo."}
          </p>
        </div>
      )}
      {data && data.detalle.length > 0 && (
        <>
          <ul className="sg-legend" aria-label="Cómo leer los resultados">
            <li>
              <Badge tone="ok">Coincide</Badge> la IA llegó a tu etiqueta
            </li>
            <li>
              <Badge tone="bad">Falso positivo</Badge> era íntegro y la IA
              sospechó
            </li>
            <li>
              <Badge tone="warn">Falso negativo</Badge> era adulterado y la IA
              lo dio por válido
            </li>
          </ul>
          <Results
            data={data}
            shown={shown}
            partial={mode !== "rapida"}
            urlFor={urlFor}
          />
        </>
      )}
    </>
  );
}
