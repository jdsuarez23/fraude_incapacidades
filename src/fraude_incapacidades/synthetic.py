"""Generador de certificados sintéticos en PDF para el laboratorio Ground Truth (HU-09).

Produce SINT-001..SINT-030 (30 PDFs reales) + `manifest.json` (etiquetas Ground Truth) +
`registro_mock.json` (RETHUS/ADRES/entidades simulados) en `tests/synthetic/`.
Todo es ficticio: nombres, documentos y entidades. Generación determinista.

Composición: 15 íntegros (8 nativos digitales, 4 escaneados legibles, 3 ilegibles/manuscritos)
y 15 con alteraciones controladas (12 detectables por las reglas y 3 sutiles que no lo son).
"""
from __future__ import annotations

import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

SYNTH_DIR = Path(__file__).resolve().parents[2] / "tests" / "synthetic"
INTEGRO, ADULTERADO, ILEGIBLE = "Íntegro", "Adulterado", "Ilegible"

HIS = "his"
APLANADO = "aplanado"
PS = "editor:Adobe Photoshop 25.0"
CANVA = "editor:Canva"
AI = "editor:Adobe Illustrator 28.0"

# Campos por caso. Valores por defecto: documento limpio.
# cie/dias → CIE-10 y días; meta → metadatos; medico/adres → estado en el registro simulado;
# firma → bloque de firma dibujado; aritmetica=False → fecha fin no cuadra con los días.
_CASOS: list[dict] = [
    # ── 8 íntegros nativos digitales ───────────────────────────────
    *[{"tipo": "Nativo digital", "etiqueta": INTEGRO, "render": "nativo", "cie": c, "dias": d}
      for c, d in (("J069", 3), ("A09", 2), ("G44", 2), ("J06", 5), ("K29", 4), ("A083", 2), ("J069", 4), ("H10", 3))],
    # ── 4 íntegros escaneados legibles (2 con señales débiles → falsos positivos) ──
    {"tipo": "Escaneado", "etiqueta": INTEGRO, "render": "escaneado",
        "meta": APLANADO, "cie": "J069", "dias": 3},
    {"tipo": "Escaneado sin sello", "etiqueta": INTEGRO, "render": "escaneado",
        "meta": APLANADO, "firma": False, "cie": "K29", "dias": 3},
    {"tipo": "Escaneado (cambio de razón social EPS)", "etiqueta": INTEGRO, "render": "escaneado", "meta": APLANADO,
     "eps_afiliada": "EPS SANITAS", "cie": "J069", "dias": 4},
    {"tipo": "Escaneado (incapacidad prolongada legítima)", "etiqueta": INTEGRO,
     "render": "escaneado", "meta": APLANADO, "cie": "J069", "dias": 15},
    # ── 3 ilegibles / manuscritos → deben derivarse a Inconcluso ──
    {"tipo": "Manuscrito ilegible", "etiqueta": ILEGIBLE,
        "render": "manuscrito", "meta": APLANADO},
    {"tipo": "Escaneado baja calidad", "etiqueta": ILEGIBLE,
        "render": "ilegible", "meta": APLANADO},
    {"tipo": "Escaneado baja calidad", "etiqueta": ILEGIBLE,
        "render": "ilegible", "meta": APLANADO},
    # ── 12 adulterados detectables ────────────────────────────────
    {"tipo": "Fechas alteradas + Photoshop", "etiqueta": ADULTERADO,
        "render": "nativo", "meta": PS, "aritmetica": False, "cie": "J069", "dias": 4},
    {"tipo": "Metadatos Canva + días excesivos", "etiqueta": ADULTERADO,
        "render": "nativo", "meta": CANVA, "cie": "J069", "dias": 15},
    {"tipo": "Médico inexistente", "etiqueta": ADULTERADO, "render": "nativo",
        "medico": "no_encontrado", "cie": "A09", "dias": 3},
    {"tipo": "Médico inexistente + Canva", "etiqueta": ADULTERADO, "render": "nativo",
        "medico": "no_encontrado", "meta": CANVA, "cie": "K29", "dias": 3},
    {"tipo": "IPS apócrifa", "etiqueta": ADULTERADO, "render": "nativo",
        "entidad_registrada": False, "firma": False, "cie": "J069", "dias": 3},
    {"tipo": "Fechas alteradas", "etiqueta": ADULTERADO,
        "render": "nativo", "aritmetica": False, "cie": "G44", "dias": 2},
    {"tipo": "CIE-10 / días fuera de rango", "etiqueta": ADULTERADO,
        "render": "nativo", "cie": "J069", "dias": 21},
    {"tipo": "Error aritmético de fechas", "etiqueta": ADULTERADO,
        "render": "nativo", "aritmetica": False, "cie": "A09", "dias": 3},
    {"tipo": "Afiliación inactiva + días excesivos", "etiqueta": ADULTERADO,
        "render": "nativo", "adres": "inactivo", "cie": "J069", "dias": 16},
    {"tipo": "Metadatos Photoshop", "etiqueta": ADULTERADO,
        "render": "nativo", "meta": PS, "cie": "H10", "dias": 3},
    {"tipo": "Médico inhabilitado + EPS discordante", "etiqueta": ADULTERADO, "render": "nativo",
        "medico": "inhabilitado", "eps_afiliada": "EPS SANITAS", "cie": "J069", "dias": 4},
    {"tipo": "Modificado después de crearse + Illustrator, sin firma", "etiqueta": ADULTERADO,
        "render": "nativo", "meta": AI + "|mod", "firma": False, "cie": "K29", "dias": 3},
    # ── 3 adulterados sutiles que las reglas no pueden detectar (falsos negativos) ──
    {"tipo": "Fecha alterada y re-escaneada", "etiqueta": ADULTERADO,
        "render": "escaneado", "meta": APLANADO, "cie": "J069", "dias": 4},
    {"tipo": "Código CIE-10 cambiado (rango compatible)", "etiqueta": ADULTERADO,
     "render": "nativo", "cie": "J069", "dias": 3},
    {"tipo": "Registro médico ajeno (RETHUS caído)", "etiqueta": ADULTERADO,
     "render": "nativo", "medico": "no_disponible", "cie": "A09", "dias": 3},
]

_DX = {"J069": "Infección aguda de las vías respiratorias superiores", "A09": "Gastroenteritis de presunto origen infeccioso",
       "G44": "Cefalea tensional", "J06": "Infección respiratoria aguda", "K29": "Gastritis", "A083": "Infección viral intestinal",
       "H10": "Conjuntivitis"}
_NOMBRES = ["Camila Rojas Prieto", "Andrés Mejía Salcedo", "Laura Gómez Duarte", "Julián Torres Ayala", "Natalia Pardo Vega",
            "Sergio Ramírez Lugo", "Paola Cifuentes Mora", "Daniel Ortiz Cañón", "Marcela Acosta Rey", "Iván Beltrán Suárez"]
_MEDICOS = ["Dr. Ricardo Salazar Pinto", "Dra. Elena Barrios Cruz",
            "Dr. Hernán Valdés Rico", "Dra. Sofía Londoño Páez"]


def _build_order() -> list[dict]:
    rng = random.Random(2026)
    idx = list(range(len(_CASOS)))
    rng.shuffle(idx)
    return [_CASOS[i] for i in idx]


def _fields(n: int, c: dict) -> dict:
    inicio = date(2026, 2, 2) + timedelta(days=n * 3)
    dias = c.get("dias", 3)
    fin = inicio + timedelta(days=dias -
                             1 if c.get("aritmetica", True) else dias + 1)
    cie = c.get("cie", "J069")
    cc_pac = str(1000200000 + n * 137)
    cc_med = str(79000000 + n * 911)
    entidad = "IPS Vida Total Express" if c.get(
        "entidad_registrada", True) is False else f"IPS Clínica Santa Marta {1 + n % 4}"
    return {
        "entidad": entidad, "consecutivo": f"INC-{90000 + n}", "paciente": _NOMBRES[n % len(_NOMBRES)],
        "cc_paciente": cc_pac, "eps_emisora": "EPS SURA", "eps_afiliada": c.get("eps_afiliada", "EPS SURA"),
        "cie": cie, "diagnostico": _DX.get(cie, "Diagnóstico general"), "inicio": inicio.isoformat(), "fin": fin.isoformat(),
        "dias": dias, "medico": _MEDICOS[n % len(_MEDICOS)], "cc_medico": cc_med, "rm": f"RM-{50000 + n}",
    }


def _draw(page, f: dict, firma: bool, visible: bool) -> None:
    # render_mode 3 = texto invisible (capa OCR de un escaneo)
    rm = 0 if visible else 3
    kw = {"fontname": "helv", "render_mode": rm}
    page.insert_text((50, 60), f["entidad"], fontsize=18, **kw)
    page.insert_text(
        (50, 95), "CERTIFICADO DE INCAPACIDAD MÉDICA", fontsize=13, **kw)
    lines = [
        ("Entidad emisora", f["entidad"]), ("Consecutivo",
                                            f["consecutivo"]), ("Paciente", f["paciente"]),
        ("Tipo de documento", "CC"), ("Número de documento",
                                      f["cc_paciente"]), ("EPS de afiliación", f["eps_emisora"]),
        ("Código CIE-10", f["cie"]), ("Diagnóstico",
                                      f["diagnostico"]), ("Fecha de inicio", f["inicio"]),
        ("Fecha de fin", f["fin"]), ("Días otorgados",
                                     str(f["dias"])), ("Médico", f["medico"]),
        ("Cédula del médico", f["cc_medico"]), ("Registro médico", f["rm"]),
    ]
    y = 150
    for k, v in lines:
        page.insert_text((50, y), f"{k}: {v}", fontsize=11, **kw)
        y += 30
    page.insert_text((50, 818), "Firma y sello del médico", fontsize=8, **kw)
    if firma and visible:  # el trazo de firma es parte de la imagen, no del texto
        _signature(page)


def _signature(page) -> None:
    import fitz
    rng = random.Random(7)
    x, y = 70.0, 740.0
    for _ in range(6):
        pts = [(x + i * 18 + rng.uniform(-3, 3), y + rng.uniform(-22, 22))
               for i in range(11)]
        for a, b in zip(pts, pts[1:]):
            page.draw_line(a, b, color=(0.05, 0.05, 0.3), width=1.6)
        y += rng.uniform(-4, 4)
    page.draw_circle(fitz.Point(240, 735), 28, color=(
        0.1, 0.1, 0.4), width=1.5)  # sello


def _scribbles(page, seed: int) -> None:
    rng = random.Random(seed)
    for row in range(14):
        y = 120 + row * 40
        pts = [(50 + i * 12, y + rng.uniform(-9, 9)) for i in range(40)]
        for a, b in zip(pts, pts[1:]):
            page.draw_line(a, b, color=(0.1, 0.1, 0.35), width=1.3)


def _to_scan(src_doc, blur: float, noise: bool) -> bytes:
    """Rasteriza la página y devuelve PNG/JPEG tipo escáner."""
    import fitz
    from PIL import Image, ImageFilter
    pix = src_doc[0].get_pixmap(
        matrix=fitz.Matrix(1.6, 1.6), colorspace=fitz.csGRAY)
    im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        rng = random.Random(3)
        px = im.load()
        for _ in range(pix.width * pix.height // 60):
            px[rng.randrange(pix.width), rng.randrange(
                pix.height)] = rng.randrange(120, 255)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=62 if blur >= 4 else 80)
    return buf.getvalue()


def _metadata(meta: str) -> dict:
    created = "D:20260210083000-05'00'"
    if meta == APLANADO:
        return {"creator": "", "producer": "", "creationDate": "", "modDate": "", "title": "", "author": ""}
    if meta.startswith("editor:"):
        name = meta.split(":", 1)[1].split("|")[0]
        mod = "D:20260216101500-05'00'" if meta.endswith("|mod") else created
        return {"creator": name, "producer": name, "creationDate": created, "modDate": mod, "title": "", "author": ""}
    return {"creator": "SaludSoft HIS 4.2", "producer": "SaludSoft PDF Engine", "creationDate": created, "modDate": created, "title": "", "author": ""}


def build_pdf(f: dict, case: dict) -> bytes:
    import fitz
    firma = case.get("firma", True)
    render = case["render"]
    base = fitz.open()
    bp = base.new_page(width=595, height=842)
    if render == "manuscrito":
        bp.insert_text((50, 60), "~", fontsize=1, render_mode=3)
        _scribbles(bp, seed=len(f["paciente"]))
    else:
        _draw(bp, f, firma, visible=True)

    if render == "nativo":
        out = base
    else:
        blur, noise = {"escaneado": (0.5, True), "ilegible": (
            5.5, True), "manuscrito": (1.2, True)}[render]
        img = _to_scan(base, blur, noise)
        out = fitz.open()
        pg = out.new_page(width=595, height=842)
        pg.insert_image(pg.rect, stream=img)
        if render == "escaneado":
            # capa de texto invisible (PDF escaneado con OCR)
            _draw(pg, f, firma, visible=False)
    out.set_metadata(_metadata(case.get("meta", HIS)))
    data = out.tobytes(garbage=3, deflate=True)
    return data


def generate(force: bool = False) -> list[dict]:
    """Crea (si faltan) los 30 PDFs, el manifest y el registro simulado. Devuelve el manifest."""
    manifest_path = SYNTH_DIR / "manifest.json"
    if manifest_path.exists() and not force:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    registro = {"rethus": {}, "adres": {}, "entidades": {}}
    manifest = []
    for n, case in enumerate(_build_order(), start=1):
        f = _fields(n, case)
        sid = f"SINT-{n:03d}"
        (SYNTH_DIR / f"{sid}.pdf").write_bytes(build_pdf(f, case))
        registro["rethus"][f["cc_medico"]] = {
            "estado": case.get("medico", "activo")}
        registro["adres"][f["cc_paciente"]] = {
            "estado": case.get("adres", "activo"), "eps": f["eps_afiliada"]}
        registro["entidades"][f["entidad"].upper()] = {
            "registrada": case.get("entidad_registrada", True)}
        manifest.append({"id": sid, "archivo": f"{sid}.pdf",
                        "tipo": case["tipo"], "etiqueta_real": case["etiqueta"]})
    (SYNTH_DIR / "registro_mock.json").write_text(json.dumps(registro,
                                                             ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(
        manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
