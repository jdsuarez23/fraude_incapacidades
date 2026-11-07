import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "./components/ui.jsx";
import { getJob, retryJob, startJob } from "./lib/api.js";
import { validateFile } from "./lib/validation.js";
import PanelView from "./views/PanelView.jsx";
import FichaView from "./views/FichaView.jsx";
import DictamenView from "./views/DictamenView.jsx";
import LabView from "./views/LabView.jsx";

const NAV = [
  ["panel", "Panel", "⌂"],
  ["ficha", "Ficha de datos", "▤"],
  ["dictamen", "Dictamen", "⚖"],
  ["lab", "Laboratorio", "⚗"],
];

const readTheme = () =>
  document.documentElement.dataset.theme === "light" ? "light" : "dark";
const netMsg = (e) =>
  e.message === "Failed to fetch"
    ? "No se pudo conectar con la API (¿está corriendo en el puerto 8000?)."
    : e.message;

export default function App() {
  const [view, setView] = useState("panel");
  const [theme, setTheme] = useState(readTheme);
  const [file, setFile] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);
  const [validation, setValidation] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [edits, setEdits] = useState({});
  const [manual, setManual] = useState(false);
  const [ackWarning, setAckWarning] = useState(false);
  const poll = useRef(null);
  const urlRef = useRef(null);

  const stopPoll = () => {
    clearInterval(poll.current);
    poll.current = null;
  };
  useEffect(
    () => () => {
      stopPoll();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("sg-theme", next);
    } catch {
      /* sin almacenamiento: no se recuerda */
    }
    setTheme(next);
  };

  // La URL del PDF se crea al elegir el archivo (no en un efecto) para sobrevivir a StrictMode
  const setUrlFor = (f) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = f ? URL.createObjectURL(f) : null;
    setFileUrl(urlRef.current);
  };

  const watch = useCallback((id) => {
    stopPoll();
    poll.current = setInterval(async () => {
      try {
        const j = await getJob(id);
        setJob(j);
        if (["completado", "error"].includes(j.estado)) {
          stopPoll();
          setBusy(false);
          if (j.estado === "error") setError(j.error || "El análisis falló.");
        }
      } catch (e) {
        stopPoll();
        setBusy(false);
        setError(netMsg(e));
      }
    }, 1500);
  }, []);

  const onPick = async (f) => {
    stopPoll();
    setJob(null);
    setError(null);
    setEdits({});
    setManual(false);
    setAckWarning(false);
    setBusy(false);
    setFile(f);
    setUrlFor(f);
    setValidation(null);
    setValidation(await validateFile(f)); // validación en el navegador, antes del envío
  };
  const onReset = () => {
    stopPoll();
    setFile(null);
    setUrlFor(null);
    setValidation(null);
    setJob(null);
    setError(null);
    setEdits({});
    setBusy(false);
  };

  const begin = async (starter) => {
    setBusy(true);
    setError(null);
    setAckWarning(false);
    try {
      const { job_id } = await starter();
      setJob({
        id: job_id,
        estado: "en_cola",
        etapas: [
          "Extracción OCR y Metadatos",
          "Validación Clínica CIE-10",
          "Consultas RETHUS / ADRES",
          "Dictamen IA Explicable",
        ].map((nombre, i) => ({
          id: i + 1,
          nombre,
          estado: i === 0 ? "en_curso" : "pendiente",
          nota: "",
        })),
      });
      watch(job_id);
    } catch (e) {
      setBusy(false);
      setJob(null);
      setError(netMsg(e));
    }
  };
  const onStart = () => begin(() => startJob(file));
  const onRetry = () => job?.id && begin(() => retryJob(job.id));

  const report = job?.report || null;
  const rawReport = job?.raw_report || "";
  const done = job?.estado === "completado";
  const forense = report?.forense?.estado
    ? report.forense
    : job?.validacion?.forense || null;

  return (
    <div className="sg-app">
      <header className="sg-top">
        <div className="sg-brand">
          <span className="sg-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="white">
              <path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z" />
            </svg>
          </span>
          <span>
            Salud<span className="text-gradient-accent">Guard</span>
          </span>
        </div>
        <span className="sg-sub">Validador forense de incapacidades</span>
        <div className="sg-top-right">
          <Badge tone="ok">🔒 Anonimización PII activa (Ley 1581)</Badge>
          <Badge tone="info">AI Engine activo</Badge>
          <button
            type="button"
            className="sg-theme"
            onClick={toggleTheme}
            aria-label={
              theme === "dark"
                ? "Cambiar a modo claro"
                : "Cambiar a modo oscuro"
            }
            title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>

      <nav className="sg-side" aria-label="Secciones">
        {NAV.map(([id, label, icon]) => (
          <button
            key={id}
            type="button"
            className="sg-nav"
            aria-current={view === id ? "page" : undefined}
            onClick={() => setView(id)}
          >
            <span aria-hidden="true">{icon}</span>
            {label}
            {id === "dictamen" && done && <small>listo</small>}
          </button>
        ))}
      </nav>

      <main className="sg-main">
        {view === "panel" && (
          <PanelView
            {...{
              file,
              validation,
              job,
              error,
              busy,
              onPick,
              onStart,
              onReset,
              onRetry,
              ackWarning,
            }}
            onContinue={() => setAckWarning(true)}
            goFicha={() => setView("ficha")}
          />
        )}
        {view === "ficha" && (
          <FichaView
            {...{ report, fileUrl, edits, setEdits }}
            onConfirm={() => setView("dictamen")}
            goPanel={() => setView("panel")}
          />
        )}
        {view === "dictamen" && (
          <DictamenView
            {...{
              report,
              rawReport,
              edits,
              validation,
              forense,
              manual,
              setManual,
              onRetry,
            }}
            goPanel={() => setView("panel")}
          />
        )}
        {view === "lab" && <LabView />}
      </main>
    </div>
  );
}
