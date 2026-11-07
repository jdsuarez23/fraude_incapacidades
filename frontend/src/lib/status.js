export const VERDICTS = {
  Válido: {
    tone: "ok",
    color: "var(--ok)",
    text: "DOCUMENTO VÁLIDO",
    hint: "Continúa al trámite normal de nómina.",
  },
  Sospechoso: {
    tone: "warn",
    color: "var(--warn)",
    text: "DOCUMENTO SOSPECHOSO",
    hint: "Priorizar revisión humana.",
  },
  "Potencialmente Fraudulento": {
    tone: "bad",
    color: "var(--bad)",
    text: "POTENCIALMENTE FRAUDULENTO",
    hint: "Auditoría prioritaria y revisión humana obligatoria.",
  },
  "Inconcluso / No Procesable": {
    tone: "info",
    color: "var(--info)",
    text: "INCONCLUSO / NO PROCESABLE",
    hint: "Revisión manual completa, sin puntaje.",
  },
};

export function scoreColor(score) {
  if (score == null) return "var(--info)";
  if (score >= 80) return "var(--ok)";
  if (score >= 41) return "var(--warn)";
  return "var(--bad)";
}

export const stageTone = {
  pendiente: "idle",
  en_curso: "info",
  completado: "ok",
  advertencia: "warn",
  error: "bad",
};
export const stageLabel = {
  pendiente: "Pendiente",
  en_curso: "En curso",
  completado: "Completado",
  advertencia: "Advertencia",
  error: "Error",
};
