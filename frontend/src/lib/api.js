export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function parse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(
      (d && (d.mensaje || (typeof d === "string" ? d : null))) ||
        `Error del servidor (${res.status})`,
    );
  }
  return data;
}

const form = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return fd;
};

export const startJob = async (file) =>
  parse(await fetch(`${API}/api/jobs`, { method: "POST", body: form(file) }));

export const validateRemote = async (file) =>
  parse(
    await fetch(`${API}/api/validate`, { method: "POST", body: form(file) }),
  );

export const getJob = async (id) => parse(await fetch(`${API}/api/jobs/${id}`));

export const retryJob = async (id) =>
  parse(await fetch(`${API}/api/jobs/${id}/retry`, { method: "POST" }));

export async function exportPdf(payload) {
  const res = await fetch(`${API}/api/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`No se pudo generar el PDF (${res.status})`);
  return res.blob();
}

export const runBenchmark = async ({ useCache, force }) =>
  parse(
    await fetch(
      `${API}/api/benchmark/run?use_cache=${useCache}&force=${force}`,
      { method: "POST" },
    ),
  );

export const getBenchmarkCache = async () =>
  parse(await fetch(`${API}/api/benchmark/cache`));

export const regenerateSynthetic = async () =>
  parse(await fetch(`${API}/api/benchmark/regenerate`, { method: "POST" }));

export const startAgentBatch = async ({ n, useCache }) =>
  parse(
    await fetch(`${API}/api/benchmark/agent?n=${n}&use_cache=${useCache}`, {
      method: "POST",
    }),
  );
  
export const getAgentBatch = async (id) =>
  parse(await fetch(`${API}/api/benchmark/agent/${id}`));

export const cancelAgentBatch = async (id) =>
  parse(
    await fetch(`${API}/api/benchmark/agent/${id}/cancel`, { method: "POST" }),
  );

export async function startCustomBatch(files, etiquetas) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  fd.append("etiquetas", JSON.stringify(etiquetas));
  return parse(
    await fetch(`${API}/api/benchmark/custom`, { method: "POST", body: fd }),
  );
}

export const syntheticPdfUrl = (id) => `${API}/api/benchmark/pdf/${id}`;

export function download(blob, name) {
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob),
    download: name,
  });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
