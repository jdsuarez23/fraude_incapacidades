"""Exportación del dictamen a PDF (reporte estructurado y exportable, Entregable 1)."""
from __future__ import annotations

import io
from datetime import datetime
from html import escape as e

_CSS = """
body { font-family: sans-serif; font-size: 9.5pt; color: #111; }
h1 { font-size: 17pt; color: #3730a3; margin-bottom: 2pt; }
h2 { font-size: 11.5pt; color: #3730a3; margin-top: 12pt; margin-bottom: 3pt; border-bottom: 1px solid #c7d2fe; }
.v { font-size: 15pt; font-weight: bold; }
.muted { color: #555; font-size: 8.5pt; }
table { width: 100%; border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 3pt; text-align: left; vertical-align: top; }
th { background-color: #eef2ff; }
.bad { color: #b91c1c; } .warn { color: #b45309; } .ok { color: #047857; }
"""

_VCOLOR = {"Válido": "ok", "Sospechoso": "warn",
           "Potencialmente Fraudulento": "bad"}


def _rows(pairs) -> str:
    return "".join(f"<tr><th width='32%'>{e(str(k))}</th><td>{e(str(v if v not in (None, '') else '—'))}</td></tr>" for k, v in pairs)


def build_html(payload: dict) -> str:
    rep = payload.get("informe") or {}
    val = payload.get("validacion") or {}
    fz = rep.get("forense") or payload.get("forense") or {}
    ctrl = rep.get("control_reglas") or {}
    datos = rep.get("datos_extraidos") or {}
    edits = payload.get("correcciones_analista") or {}
    ver = rep.get("veredicto", "—")
    score = rep.get("puntaje_veracidad")

    h = [f"<h1>SaludGuard · Dictamen forense de incapacidad</h1>",
         f"<p class='muted'>Generado {datetime.now():%Y-%m-%d %H:%M} · Archivo: {e(str(val.get('nombre', '—')))} · SHA-256: {e(str(val.get('sha256', '—')))}</p>",
         f"<p><span class='v {_VCOLOR.get(ver, '')}'>{e(ver)}</span> &nbsp; Puntaje de veracidad: <b>{'sin puntaje' if score is None else f'{score}/100'}</b></p>",
         f"<p class='muted'>{e(rep.get('aviso_legal', 'Orientación técnica preliminar: no constituye decisión administrativa definitiva.'))}</p>"]
    if payload.get("validacion_manual"):
        h.append(
            "<p class='warn'><b>Marcado para validación manual por el analista.</b></p>")

    h.append(
        "<h2>Desglose del puntaje (base 100)</h2><table><tr><th>Regla</th><th>Puntos</th></tr>")
    for d in rep.get("desglose") or []:
        h.append(
            f"<tr><td>{e(str(d.get('regla')))}</td><td>{e(str(d.get('puntos')))}</td></tr>")
    for p in rep.get("verificacion_externa_pendiente") or []:
        h.append(
            f"<tr><td>{e(p)}: verificación externa pendiente</td><td>0 (no penaliza)</td></tr>")
    h.append("</table>")

    if ctrl:
        h.append("<h2>Control con las reglas del Entregable 1</h2><table>" + _rows([
            ("Puntaje por reglas", ctrl.get("puntaje")
             ), ("Veredicto por reglas", ctrl.get("veredicto")),
            ("Diferencia con el agente", ctrl.get("diferencia")), ("Mismo veredicto", "Sí" if ctrl.get("coincide_veredicto") else "No")]) + "</table>")

    h.append("<h2>Estado por fuente de verificación</h2><table><tr><th>Fuente</th><th>Estado</th><th>Detalle</th></tr>")
    for v in rep.get("verificadores") or []:
        h.append(
            f"<tr><td>{e(str(v.get('fuente')))}</td><td>{e(str(v.get('estado')))}</td><td>{e(str(v.get('detalle', '')))}</td></tr>")
    h.append("</table>")

    h.append("<h2>Análisis forense de metadatos del PDF</h2><table>" + _rows([
        ("Estado", fz.get("estado")), ("Creador", fz.get(
            "creador")), ("Productor", fz.get("productor")),
        ("Fecha de creación", fz.get("fecha_creacion")
         ), ("Fecha de modificación", fz.get("fecha_modificacion")),
        ("Días entre creación y modificación", fz.get("dias_entre_creacion_y_modificacion"))]) + "</table>")
    for a in fz.get("alertas") or []:
        h.append(
            f"<p class='{'bad' if a.get('nivel') == 'alta' else 'warn' if a.get('nivel') == 'media' else 'muted'}'>[{e(a.get('nivel', ''))}] {e(a.get('texto', ''))}</p>")

    for title, key in (("Hallazgos médicos", "hallazgos_medicos"), ("Análisis forense (agente)", "analisis_forense"), ("Verificación de entidades", "verificacion_entidades")):
        h.append(
            f"<h2>{title}</h2><p>{e(rep.get(key) or 'No disponible')}</p>")
    h.append("<h2>Alertas de riesgo</h2>" + ("<ul>" + "".join(f"<li>{e(a)}</li>" for a in rep.get(
        "alertas") or []) + "</ul>" if rep.get("alertas") else "<p>Sin alertas de riesgo real.</p>"))

    h.append("<h2>Datos extraídos (paciente anonimizado)</h2>")
    for sec, fields in datos.items():
        if isinstance(fields, dict):
            h.append(f"<p><b>{e(sec.capitalize())}</b></p><table>" + _rows(
                [(k, edits.get(f"{sec}.{k}", v)) for k, v in fields.items()]) + "</table>")
    if edits:
        h.append("<p class='muted'>Los valores corregidos por el analista se muestran ya aplicados; el puntaje no se recalculó con ellos.</p>")
    return f"<html><body>{''.join(h)}</body></html>"


def build_pdf(payload: dict) -> bytes:
    import fitz

    story = fitz.Story(html=build_html(payload), user_css=_CSS)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    media = fitz.paper_rect("a4")
    where = media + (40, 40, -40, -40)
    more = 1
    while more:
        dev = writer.begin_page(media)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()
