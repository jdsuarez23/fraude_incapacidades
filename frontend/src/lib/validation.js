// Validación técnica en el navegador, antes del envío (HU-01).
// Límites del Entregable 1: PDF, máx. 5 MB, hasta 2 páginas. Mantener igual a src/fraude_incapacidades/validation.py
export const MAX_SIZE_BYTES = 5 * 1024 * 1024;
export const MAX_PAGES = 2;
export const ALLOWED_EXT = [".pdf"];

export async function sha256Hex(buffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function countPdfPages(bytes) {
  const text = new TextDecoder("latin1").decode(bytes);
  const m = text.match(/\/Type\s*\/Page(?![s\w])/g);
  return m ? m.length : null;
}

export async function validateFile(file) {
  const errores = [];
  const name = file.name || "";
  const ext = name.includes(".")
    ? "." + name.split(".").pop().toLowerCase()
    : "";
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const sha256 = await sha256Hex(buffer);
  let paginas = null;

  if (!ALLOWED_EXT.includes(ext))
    errores.push(
      `Formato no soportado (${ext || "sin extensión"}). Solo se admite PDF.`,
    );
  if (file.size === 0) errores.push("El archivo está vacío.");
  if (file.size > MAX_SIZE_BYTES)
    errores.push(
      `Pesa ${(file.size / 1048576).toFixed(1)} MB y supera el máximo de 5 MB.`,
    );
  const magic = String.fromCharCode(...bytes.slice(0, 5));
  if (ext === ".pdf" && file.size > 0) {
    if (magic !== "%PDF-")
      errores.push("El contenido no corresponde a un PDF real.");
    else {
      paginas = countPdfPages(bytes);
      if (paginas && paginas > MAX_PAGES)
        errores.push(`Tiene ${paginas} páginas; el máximo es ${MAX_PAGES}.`);
    }
  }
  return {
    valido: errores.length === 0,
    errores,
    sha256,
    paginas,
    paginasProcesadas: paginas ? Math.min(paginas, MAX_PAGES) : null,
    formato: ext.replace(".", "").toUpperCase() || "?",
    tamano: file.size,
    nombre: name,
  };
}

export const fmtMB = (b) =>
  b < 1048576
    ? `${(b / 1024).toFixed(0)} KB`
    : `${(b / 1048576).toFixed(1)} MB`;
