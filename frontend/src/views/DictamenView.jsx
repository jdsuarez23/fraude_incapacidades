import { useState } from "react";
import { Badge, ScoreRing } from "../components/ui.jsx";
import { download, exportPdf } from "../lib/api.js";
import { VERDICTS } from "../lib/status.js";

const SOURCE_TONE = (estado = "") => {
  const e = estado.toLowerCase();
  if (/no disponible|pendiente/.test(e)) return "warn";
  if (/alerta|inactiv|no encontrado|hallazgo/.test(e)) return "bad";
  if (/verificado|sin hallazgos/.test(e)) return "ok";
  return "idle";
};

const FZ_TONE = { ok: "ok", aplanados: "warn", editor_grafico: "bad" };
const FZ_LABEL = {
  ok: "Sin hallazgos",
  aplanados: "Aplanados (alerta leve)",
  editor_grafico: "Editor gráfico detectado",
};
const LEVEL_TONE = { alta: "bad", media: "warn", leve: "idle" };

function ForenseCard({ forense }) {
  return (
    <section className="glass sg-card c6" aria-labelledby="h-fz">
      <div className="sg-card-head">
        <h3 id="h-fz">Metadatos del PDF (forense determinista)</h3>
        <Badge tone={FZ_TONE[forense.estado]}>{FZ_LABEL[forense.estado]}</Badge>
      </div>
      <ul className="sg-list">
        <li>
          <span className="sg-muted">Creador</span>
          <span>{forense.creador || "—"}</span>
        </li>
        <li>
          <span className="sg-muted">Productor</span>
          <span>{forense.productor || "—"}</span>
        </li>
        <li>
          <span className="sg-muted">CreationDate</span>
          <span>{forense.fecha_creacion || "—"}</span>
        </li>
        <li>
          <span className="sg-muted">ModDate</span>
          <span>{forense.fecha_modificacion || "—"}</span>
        </li>
        <li>
          <span className="sg-muted">Días entre ambas</span>
          <span>{forense.dias_entre_creacion_y_modificacion ?? "—"}</span>
        </li>
      </ul>
      {(forense.alertas || []).map((a, i) => (
        <p key={i} style={{ margin: "8px 0 0", fontSize: ".82rem" }}>
          <Badge tone={LEVEL_TONE[a.nivel] || "idle"}>{a.nivel}</Badge>{" "}
          {a.texto}
        </p>
      ))}
    </section>
  );
}

function ControlCard({ report }) {
  const c = report.control_reglas;
  const same = c.coincide_veredicto;
  return (
    <section className="glass sg-card c6" aria-labelledby="h-ctrl">
      <div className="sg-card-head">
        <h3 id="h-ctrl">Control con las reglas del Entregable 1</h3>
        <Badge tone={same ? "ok" : "warn"}>
          {same ? "Mismo veredicto" : "Veredicto distinto"}
        </Badge>
      </div>
      <ul className="sg-list">
        <li>
          <span className="sg-muted">Puntaje del agente</span>
          <b>{report.puntaje_veracidad}</b>
        </li>
        <li>
          <span className="sg-muted">Puntaje por reglas (determinista)</span>
          <b>{c.puntaje}</b>
        </li>
        <li>
          <span className="sg-muted">Veredicto por reglas</span>
          <span>{c.veredicto}</span>
        </li>
        <li>
          <span className="sg-muted">Diferencia</span>
          <Badge tone={c.diferencia === 0 ? "ok" : "warn"}>
            {c.diferencia > 0 ? "+" : ""}
            {c.diferencia} pts
          </Badge>
        </li>
      </ul>
      {c.desglose?.map((d, i) => (
        <p key={i} className="sg-muted" style={{ margin: "6px 0 0" }}>
          {d.puntos} pts · {d.detalle}
        </p>
      ))}
      <p className="sg-muted" style={{ margin: "8px 0 0" }}>
        El agente puede diferir (p. ej. por OSINT o criterio visual); la reglas
        solo ven los datos estructurados y los metadatos. Una diferencia grande
        indica que conviene revisar el caso.
      </p>
    </section>
  );
}

export default function DictamenView({
  report,
  rawReport,
  edits,
  validation,
  forense,
  manual,
  setManual,
  onRetry,
  goPanel,
}) {
  const [showRaw, setShowRaw] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  if (!report && !rawReport) {
    return (
      <>
        <h1 className="sg-title">
          Informe forense <small>Dictamen explicable · HU-03 a HU-08</small>
        </h1>
        <div className="glass sg-card">
          <p className="sg-muted">
            Aún no hay dictamen. Analiza un certificado desde el Panel.
          </p>
          <button type="button" className="sg-btn primary" onClick={goPanel}>
            Ir al Panel
          </button>
        </div>
      </>
    );
  }

  const payload = {
    exportado: new Date().toISOString(),
    validacion: validation && {
      nombre: validation.nombre,
      sha256: validation.sha256,
    },
    correcciones_analista: edits,
    validacion_manual: manual,
    informe: report,
    forense,
    raw_report: report ? undefined : rawReport,
  };
  const stem = `dictamen_${(validation?.sha256 || "caso").slice(0, 8)}`;
  const exportJson = () =>
    download(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }),
      `${stem}.json`,
    );
  const exportAsPdf = async () => {
    setExporting(true);
    setExportError(null);
    try {
      download(await exportPdf(payload), `${stem}.pdf`);
    } catch (e) {
      setExportError(
        e.message === "Failed to fetch"
          ? "No se pudo conectar con la API."
          : e.message,
      );
    } finally {
      setExporting(false);
    }
  };

  const v = report
    ? VERDICTS[report.veredicto] || VERDICTS["Sospechoso"]
    : null;
  const pending = report?.verificacion_externa_pendiente || [];
  const verificadores = report?.verificadores || [];

  return (
    <>
      <h1 className="sg-title">
        Informe forense{" "}
        <small>
          Dictamen explicable, estados por verificador y gestión de fallas
        </small>
      </h1>

      {!report && (
        <div className="glass sg-card" style={{ marginBottom: 14 }}>
          <Badge tone="warn">Respuesta no estructurada</Badge>
          <p className="sg-muted">
            El análisis no pudo convertirse al formato estructurado. Se conserva
            el texto recibido como respaldo.
          </p>
          <pre className="sg-pre">{rawReport}</pre>
        </div>
      )}

      {report && (
        <div className="sg-bento">
          <section
            className="glass sg-card c5"
            aria-labelledby="h-score"
            style={{
              display: "flex",
              gap: 18,
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <div>
              <h3 id="h-score">Puntaje de veracidad</h3>
              <ScoreRing score={report.puntaje_veracidad} />
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <h3>Desglose (base 100)</h3>
              <ul className="sg-list">
                {report.desglose.length === 0 && (
                  <li className="sg-muted">
                    {report.puntaje_veracidad == null
                      ? "Sin puntaje: documento inconcluso."
                      : "Sin descuentos reportados."}
                  </li>
                )}
                {report.desglose.map((d, i) => (
                  <li key={i}>
                    <span>{d.regla}</span>
                    <Badge tone={d.puntos < 0 ? "bad" : "idle"}>
                      {d.puntos} pts
                    </Badge>
                  </li>
                ))}
                {pending.map((p) => (
                  <li key={p}>
                    <span>{p} no disponible</span>
                    <Badge tone="idle">0 pts · no penaliza</Badge>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section
            className="glass sg-card c7 sg-verdict"
            style={{
              borderColor: v.color,
              background: `color-mix(in srgb, ${v.color} 10%, transparent)`,
            }}
            aria-live="polite"
          >
            <h2 style={{ color: v.color }}>{v.text}</h2>
            <strong>
              {manual ? "Marcado para validación manual" : v.hint}
            </strong>
            <span className="sg-muted">{report.aviso_legal}</span>
          </section>

          {(verificadores.length ? verificadores : []).map((s) => (
            <section key={s.fuente} className="glass sg-card c4 sg-src">
              <h4>{s.fuente}</h4>
              <div>
                <Badge tone={SOURCE_TONE(s.estado)}>{s.estado}</Badge>
              </div>
              <span className="sg-muted">{s.detalle}</span>
              {/disponible/i.test(s.estado) && (
                <div>
                  <button type="button" className="sg-btn sm" onClick={onRetry}>
                    Reintentar
                  </button>
                  <p className="sg-muted" style={{ margin: "6px 0 0" }}>
                    CAPTCHA/timeout no es evidencia de fraude.
                  </p>
                </div>
              )}
            </section>
          ))}
          {verificadores.length === 0 && (
            <section className="glass sg-card c12">
              <span className="sg-muted">
                El análisis no devolvió el estado individual de cada fuente.
              </span>
            </section>
          )}

          <section className="glass sg-card c4">
            <h3>Hallazgos médicos</h3>
            <p className="sg-muted" style={{ whiteSpace: "pre-wrap" }}>
              {report.hallazgos_medicos || "No disponible"}
            </p>
          </section>
          <section className="glass sg-card c4">
            <h3>Análisis forense digital</h3>
            <p className="sg-muted" style={{ whiteSpace: "pre-wrap" }}>
              {report.analisis_forense || "No disponible"}
            </p>
          </section>
          <section className="glass sg-card c4">
            <h3>Alertas de riesgo ({report.alertas.length})</h3>
            {report.alertas.length ? (
              <ul className="sg-list">
                {report.alertas.map((a, i) => (
                  <li key={i}>
                    <span>⚠ {a}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="sg-muted">Sin alertas de riesgo real.</p>
            )}
            {pending.length > 0 && (
              <>
                <h3 style={{ marginTop: 14 }}>Limitaciones técnicas</h3>
                <p className="sg-muted">
                  Verificación externa pendiente: {pending.join(", ")}. No
                  constituye evidencia de fraude.
                </p>
              </>
            )}
          </section>
          {forense && <ForenseCard forense={forense} />}
          {report.control_reglas?.puntaje !== undefined && (
            <ControlCard report={report} />
          )}
          <section className="glass sg-card c12">
            <h3>Verificación de entidades</h3>
            <p className="sg-muted" style={{ whiteSpace: "pre-wrap" }}>
              {report.verificacion_entidades || "No disponible"}
            </p>
          </section>
        </div>
      )}

      {report && rawReport && (
        <label
          className="sg-muted"
          style={{
            display: "flex",
            gap: 8,
            margin: "14px 0 6px",
            alignItems: "center",
          }}
        >
          <input
            type="checkbox"
            checked={showRaw}
            onChange={(e) => setShowRaw(e.target.checked)}
          />{" "}
          Ver texto crudo de respaldo (raw_report)
        </label>
      )}
      {showRaw && <pre className="sg-pre">{rawReport}</pre>}

      <div className="sg-actionbar">
        <button
          type="button"
          className="sg-btn primary"
          onClick={exportAsPdf}
          disabled={exporting || !report}
        >
          {exporting ? "Generando PDF…" : "Exportar dictamen (PDF)"}
        </button>
        <button type="button" className="sg-btn" onClick={exportJson}>
          Exportar JSON
        </button>
        {exportError && (
          <span
            className="sg-muted"
            role="alert"
            style={{ color: "var(--bad)" }}
          >
            {exportError}
          </span>
        )}
        <button
          type="button"
          className="sg-btn"
          aria-pressed={manual}
          onClick={() => setManual((m) => !m)}
        >
          {manual
            ? "✓ Marcado para validación manual"
            : "Marcar para validación manual"}
        </button>
      </div>
    </>
  );
}
