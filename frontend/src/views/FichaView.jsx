import { useState } from "react";
import { Badge } from "../components/ui.jsx";

const MISSING = /^(|no legible.*|dato ausente|ausente|n\/a|null|undefined)$/i;
const missing = (v) => v == null || MISSING.test(String(v).trim());

const SECTIONS = [
  {
    key: "paciente",
    title: "Paciente (protegido)",
    fields: [
      ["nombre", "Nombre"],
      ["tipo_doc", "Tipo doc."],
      ["numero", "Número"],
    ],
    tag: "Anonimizado",
  },
  {
    key: "profesional",
    title: "Profesional emisor",
    fields: [
      ["nombre", "Nombre"],
      ["cedula", "Cédula"],
      ["registro_medico", "Registro médico"],
    ],
  },
  {
    key: "entidad",
    title: "Entidad y apariencia",
    fields: [
      ["eps_ips", "EPS / IPS"],
      ["logo", "Logo"],
      ["firma_sello", "Firma / sello"],
    ],
  },
  {
    key: "incapacidad",
    title: "Incapacidad y diagnóstico",
    fields: [
      ["consecutivo", "Consecutivo"],
      ["codigo_cie10", "Código CIE-10"],
      ["fecha_inicio", "Fecha inicio"],
      ["fecha_fin", "Fecha fin"],
      ["dias_otorgados", "Días otorgados"],
    ],
  },
];

function outOfRange(days, rango) {
  const m = String(rango || "").match(/(\d+)\s*[-–a]\s*(\d+)/);
  if (!m || days == null || isNaN(+days)) return false;
  return +days > +m[2] * 2; // regla del Entregable: > 100% del estándar
}

export default function FichaView({
  report,
  fileUrl,
  edits,
  setEdits,
  onConfirm,
  goPanel,
}) {
  const datos = report?.datos_extraidos;
  const [editing, setEditing] = useState(false);
  const [showDoc, setShowDoc] = useState(false);
  const url = fileUrl;

  if (!datos || !Object.keys(datos).length) {
    return (
      <>
        <h1 className="sg-title">
          Ficha de datos extraídos <small>HU-02 · HU-07</small>
        </h1>
        <div className="glass sg-card">
          <p className="sg-muted">
            Aún no hay datos extraídos. Analiza un certificado desde el Panel
            {report
              ? " (este análisis no devolvió campos estructurados; revisa el texto crudo en el Dictamen)"
              : ""}
            .
          </p>
          <button type="button" className="sg-btn primary" onClick={goPanel}>
            Ir al Panel
          </button>
        </div>
      </>
    );
  }

  const get = (sec, k) => edits[`${sec}.${k}`] ?? datos?.[sec]?.[k];
  const set = (sec, k, v) => setEdits((e) => ({ ...e, [`${sec}.${k}`]: v }));
  const rango = datos?.incapacidad?.rango_cie10;

  return (
    <>
      <h1 className="sg-title">
        Ficha de datos extraídos y confirmación del analista{" "}
        <small>HU-02 · HU-07</small>
      </h1>
      <div
        className="sg-grid2"
        style={{ gridTemplateColumns: "minmax(0,.9fr) minmax(0,1.3fr)" }}
      >
        <section className="glass sg-card" aria-labelledby="h-doc">
          <h3 id="h-doc">Certificado cargado</h3>
          <div className="sg-viewer">
            {showDoc && url ? (
              <iframe
                title="Certificado original"
                src={`${url}#toolbar=0&navpanes=0`}
              />
            ) : (
              <div>
                <p className="sg-muted">
                  El documento original contiene datos personales y sensibles;
                  permanece oculto por defecto (Ley 1581).
                </p>
                <button
                  type="button"
                  className="sg-btn"
                  onClick={() => setShowDoc(true)}
                  disabled={!url}
                >
                  Mostrar documento original
                </button>
              </div>
            )}
          </div>
          {showDoc && (
            <div
              style={{
                display: "flex",
                gap: 10,
                marginTop: 8,
                alignItems: "center",
              }}
            >
              <button
                type="button"
                className="sg-btn sm ghost"
                onClick={() => setShowDoc(false)}
              >
                Ocultar documento
              </button>
              <a
                className="sg-link"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                Abrir en pestaña nueva
              </a>
            </div>
          )}
        </section>

        <section
          aria-label="Datos extraídos"
          style={{ display: "grid", gap: 14 }}
        >
          <div className="sg-fields">
            {SECTIONS.map((s) => (
              <div key={s.key} className="glass sg-card">
                <div className="sg-card-head">
                  <h3>{s.title}</h3>
                  {s.tag && <Badge tone="info">{s.tag}</Badge>}
                </div>
                {s.fields.map(([k, label]) => {
                  const v = get(s.key, k);
                  const edited = edits[`${s.key}.${k}`] !== undefined;
                  const absent = missing(v);
                  const rangeWarn =
                    s.key === "incapacidad" &&
                    k === "dias_otorgados" &&
                    outOfRange(v, rango);
                  const readonly =
                    s.key === "paciente" && (k === "nombre" || k === "numero"); // PII: no se edita enmascarado
                  return (
                    <div className="sg-field" key={k}>
                      <label htmlFor={`f-${s.key}-${k}`}>{label}</label>
                      <div
                        style={{
                          display: "flex",
                          gap: 6,
                          alignItems: "center",
                          flexWrap: "wrap",
                        }}
                      >
                        {editing && !readonly ? (
                          <input
                            id={`f-${s.key}-${k}`}
                            className="sg-input"
                            value={v ?? ""}
                            onChange={(e) => set(s.key, k, e.target.value)}
                          />
                        ) : (
                          <span id={`f-${s.key}-${k}`}>
                            {absent ? "—" : String(v)}
                          </span>
                        )}
                        {absent ? (
                          <Badge tone="warn">Dato ausente</Badge>
                        ) : edited ? (
                          <Badge tone="info">Editado</Badge>
                        ) : rangeWarn ? (
                          <Badge tone="bad">Fuera de rango</Badge>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
                {s.key === "incapacidad" && rango && (
                  <p className="sg-muted" style={{ margin: "8px 0 0" }}>
                    Rango orientativo CIE-10: {rango}
                  </p>
                )}
              </div>
            ))}
          </div>
          <p className="sg-muted">
            Las correcciones se aplican sobre esta ficha y se incluyen al
            exportar el dictamen; el motor no recalcula el puntaje con ellas
            (pendiente).
          </p>
        </section>
      </div>
      <div className="sg-actionbar">
        <button
          type="button"
          className="sg-btn"
          onClick={() => setEditing((e) => !e)}
          aria-pressed={editing}
        >
          {editing ? "Terminar edición" : "Corregir / editar campos"}
        </button>
        <button
          type="button"
          className="sg-btn primary"
          style={{ marginLeft: "auto" }}
          onClick={onConfirm}
        >
          Confirmar datos y ver dictamen →
        </button>
      </div>
    </>
  );
}
