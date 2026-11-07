import { useRef, useState } from "react";
import { Badge } from "../components/ui.jsx";
import { stageLabel, stageTone } from "../lib/status.js";
import { fmtMB, MAX_PAGES } from "../lib/validation.js";

export default function PanelView({
  file,
  validation,
  job,
  error,
  busy,
  onPick,
  onStart,
  onReset,
  onRetry,
  onContinue,
  ackWarning,
  goFicha,
}) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const pick = (f) => f && onPick(f);
  const copySha = () =>
    navigator.clipboard?.writeText(validation?.sha256 || "").catch(() => {});
  const running = job && ["en_cola", "en_curso"].includes(job.estado);

  return (
    <>
      <h1 className="sg-title">
        Panel de trabajo{" "}
        <small>
          Carga, validación técnica y flujo por etapas · HU-01, HU-07, HU-08
        </small>
      </h1>
      <div className="sg-grid2">
        <section className="glass sg-card" aria-labelledby="h-upload">
          <h3 id="h-upload">Cargar archivo</h3>
          <button
            type="button"
            className={`sg-drop ${drag ? "active" : ""}`}
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              pick(e.dataTransfer.files?.[0]);
            }}
          >
            <strong>Arrastrar y soltar archivo aquí</strong>
            <div className="sg-muted" style={{ marginTop: 6 }}>
              o haz clic para seleccionar · PDF · máx. 5 MB · hasta {MAX_PAGES}{" "}
              páginas
            </div>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            hidden
            onChange={(e) => pick(e.target.files?.[0])}
          />

          {file && validation && (
            <div className={`sg-file ${validation.valido ? "" : "invalid"}`}>
              <div className="sg-file-head">
                <div className="sg-thumb" aria-hidden="true">
                  PDF
                </div>
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: 700,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {file.name}
                  </div>
                  {validation.valido ? (
                    <Badge tone="ok">✓ Validado</Badge>
                  ) : (
                    <Badge tone="bad">✕ No válido</Badge>
                  )}
                </div>
              </div>
              <dl className="sg-kv">
                <dt>Tamaño</dt>
                <dd>{fmtMB(validation.tamano)} / Máx 5 MB</dd>
                <dt>Formato</dt>
                <dd>{validation.formato}</dd>
                <dt>Páginas</dt>
                <dd>
                  {validation.paginas
                    ? `${validation.paginasProcesadas} de ${validation.paginas} procesadas (máx. ${MAX_PAGES})`
                    : "No determinadas"}
                </dd>
                <dt>SHA-256</dt>
                <dd className="sg-mono">
                  {validation.sha256.slice(0, 10)}…{validation.sha256.slice(-8)}{" "}
                  <button
                    type="button"
                    className="sg-btn sm ghost"
                    onClick={copySha}
                    aria-label="Copiar huella SHA-256"
                  >
                    Copiar
                  </button>
                </dd>
              </dl>
              {!validation.valido && (
                <ul
                  style={{
                    margin: 0,
                    padding: "0 14px 14px 32px",
                    color: "var(--bad)",
                    fontSize: ".84rem",
                  }}
                >
                  {validation.errores.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div
            style={{
              display: "flex",
              gap: 10,
              marginTop: 16,
              flexWrap: "wrap",
            }}
          >
            <button
              type="button"
              className="sg-btn primary"
              disabled={!validation?.valido || busy}
              onClick={onStart}
            >
              {running ? "Analizando…" : "Iniciar auditoría forense"}
            </button>
            {file && !running && (
              <button type="button" className="sg-btn ghost" onClick={onReset}>
                Elegir otro archivo
              </button>
            )}
          </div>
          <p className="sg-muted" style={{ marginTop: 12 }}>
            Tiempo objetivo: &lt; 30 s por documento. Los datos del paciente se
            enmascaran en el servidor antes de mostrarse (Ley 1581).
          </p>
        </section>

        <section
          className="glass sg-card"
          aria-labelledby="h-flow"
          aria-live="polite"
        >
          <h3 id="h-flow">Flujo de procesamiento en tiempo real</h3>
          {error && (
            <div className="sg-alert b-bad" role="alert">
              {error}
            </div>
          )}
          {!job && !error && (
            <p className="sg-muted">
              Carga un certificado válido e inicia la auditoría para ver el
              avance de cada etapa.
            </p>
          )}
          {job?.etapas.map((et, i) => {
            const warn = et.estado === "advertencia" && i === 2 && !ackWarning;
            return (
              <div
                key={et.id}
                className={`sg-stage ${et.estado === "advertencia" ? "s-warn" : et.estado === "error" ? "s-error" : ""}`}
              >
                <div className="sg-stage-head">
                  <span>
                    {et.id}. {et.nombre}
                  </span>
                  <Badge tone={stageTone[et.estado]}>
                    {et.estado === "en_curso" && (
                      <span className="sg-spin" aria-hidden="true" />
                    )}
                    {stageLabel[et.estado]}
                  </Badge>
                </div>
                {et.nota && <p className="sg-stage-note">{et.nota}</p>}
                {warn && (
                  <div
                    style={{
                      display: "flex",
                      gap: 8,
                      marginTop: 10,
                      flexWrap: "wrap",
                    }}
                  >
                    <button
                      type="button"
                      className="sg-btn sm"
                      onClick={onRetry}
                    >
                      Reintentar
                    </button>
                    <button
                      type="button"
                      className="sg-btn sm"
                      onClick={onContinue}
                    >
                      Continuar sin penalizar
                    </button>
                  </div>
                )}
                {et.estado === "advertencia" && i === 2 && ackWarning && (
                  <p className="sg-stage-note">
                    Continuado: la fuente queda como “Verificación externa
                    pendiente”, 0 pts de penalización.
                  </p>
                )}
                {et.estado === "error" && (
                  <div style={{ marginTop: 10 }}>
                    <button
                      type="button"
                      className="sg-btn sm"
                      onClick={onRetry}
                    >
                      Reintentar análisis
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          {job?.estado === "completado" && (
            <button type="button" className="sg-btn primary" onClick={goFicha}>
              Análisis terminado: revisar ficha de datos →
            </button>
          )}
        </section>
      </div>
    </>
  );
}
