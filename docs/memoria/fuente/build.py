"""Arma la memoria de estadía DATACORE sobre la plantilla oficial de la UPQ.

Uso: python build.py [paginas.json]
Si se pasa paginas.json (bookmark -> página), los índices se llenan con esos números.
"""
import json
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
PLANTILLA = BASE.parent / "plantilla"
BUILD = BASE / "build"
FIGS = BASE / "figs"
TEXTO = BASE / "texto"
REPO = BASE.parents[2]  # raíz del repositorio (docs/memoria/fuente → ../../..)
SALIDA = BASE / "Memoria_Estadia_DATACORE.docx"

TEXT_W = 12240 - 2 * 1701  # ancho útil en twips (8838)
EMU_CM = 360000
MAX_ALTO_CM = 19.0

IMAGENES_EXTRA = {
    "logotipo.png": REPO / "branding/png/logotipo.png",
    **{f"eda_{n}.png": REPO / f"reports/eda/{n}.png" for n in
       ["ventas_mensuales", "categorias_mes", "sucursales", "pareto_productos", "calendario", "mezcla", "inventario", "incidencias"]},
    **{f"dash_{n}.png": REPO / f"reports/dashboard/{n}.png" for n in
       ["inicio", "ventas", "inventario", "alertas", "pronostico", "calidad", "calidad_detalle_0", "pronostico_detalle_0"]},
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def run(texto, rpr=""):
    partes = texto.split("\t")
    out = []
    for i, p in enumerate(partes):
        if i:
            out.append(f"<w:r><w:rPr>{rpr}</w:rPr><w:tab/></w:r>")
        if p:
            out.append(f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(p)}</w:t></w:r>')
    return "".join(out)


TOKEN = re.compile(r"(\*\*.+?\*\*|\*[^*\s][^*]*?\*|\[PENDIENTE:[^\]]*\])")


def runs(texto, base=""):
    out = []
    for tok in TOKEN.split(texto):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            out.append(run(tok[2:-2], base + "<w:b/><w:bCs/>"))
        elif tok.startswith("[PENDIENTE"):
            out.append(run(tok, base + '<w:b/><w:highlight w:val="yellow"/>'))
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            out.append(run(tok[1:-1], base + "<w:i/><w:iCs/>"))
        else:
            out.append(run(tok, base))
    return "".join(out)


def par(contenido, estilo=None, ppr_extra=""):
    ps = f'<w:pStyle w:val="{estilo}"/>' if estilo else ""
    return f"<w:p><w:pPr>{ps}{ppr_extra}</w:pPr>{contenido}</w:p>"


def png_size(path: Path):
    with open(path, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    return w, h


ROMANOS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


class Memoria:
    def __init__(self, paginas):
        self.paginas = paginas
        self.body = []
        self.toc_h, self.toc_fig, self.toc_tab = [], [], []
        self.bm = 0
        self.cap = None
        self.n_fig = self.n_tab = 0
        self.imgs = []  # (rid, nombre_media, origen)
        self.num_listas = []
        self.captions = []  # para revisar referencias

    def bookmark(self, contenido):
        self.bm += 1
        nombre = f"_Toc9{self.bm:05d}"
        return nombre, f'<w:bookmarkStart w:id="{900 + self.bm}" w:name="{nombre}"/>{contenido}<w:bookmarkEnd w:id="{900 + self.bm}"/>'

    # --- encabezados -------------------------------------------------------------
    def h1(self, texto, centrado=False, espacio_antes=0):
        nombre, cont = self.bookmark(run(texto))
        extra = "<w:pageBreakBefore/>"
        if espacio_antes:
            extra += f'<w:spacing w:before="{espacio_antes}"/>'
        if centrado:
            extra += '<w:jc w:val="center"/>'
        self.body.append(par(cont, "Ttulo1", extra))
        self.toc_h.append((1, texto, nombre))

    def hn(self, nivel, texto):
        nombre, cont = self.bookmark(run(texto))
        self.body.append(par(cont, f"Ttulo{nivel}"))
        self.toc_h.append((nivel, texto, nombre))

    # --- bloques -------------------------------------------------------------------
    def parrafo(self, texto):
        self.body.append(par(runs(texto), "MemTexto"))

    def lista(self, items, numerada):
        if numerada:
            num_id = 100 + len(self.num_listas)
            self.num_listas.append(num_id)
        else:
            num_id = 90
        for it in items:
            self.body.append(par(runs(it), "MemLista", f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>'))

    def ecuacion(self, expr, numero):
        self.body.append(par(run("\t" + expr + "\t" + f"({numero})", "<w:i/><w:iCs/>") , "MemEcuacion"))

    def nota(self, texto):
        self.body.append(par(run("Nota. ", "<w:i/><w:iCs/>") + runs(texto), "MemNota"))

    def caption(self, tipo, titulo):
        if tipo == "Figura":
            self.n_fig += 1
            num = f"{self.cap}.{self.n_fig}"
            estilo, lista = "MemPieFigura", self.toc_fig
        else:
            self.n_tab += 1
            num = f"{self.cap}.{self.n_tab}"
            estilo, lista = "MemPieTabla", self.toc_tab
        etiqueta = f"{tipo} {num}."
        nombre, cont = self.bookmark(run(etiqueta + " ", "<w:b/><w:bCs/>") + run(titulo, "<w:i/><w:iCs/>"))
        lista.append((1, f"{etiqueta} {titulo}", nombre))
        self.captions.append(f"{etiqueta} {titulo}")
        return par(cont, estilo)

    def figura(self, archivo, ancho_cm, titulo):
        origen = FIGS / archivo if (FIGS / archivo).exists() else IMAGENES_EXTRA[archivo]
        w, h = png_size(origen)
        ancho = ancho_cm
        alto = ancho * h / w
        if alto > MAX_ALTO_CM:
            alto, ancho = MAX_ALTO_CM, MAX_ALTO_CM * w / h
        cx, cy = int(ancho * EMU_CM), int(alto * EMU_CM)
        n = len(self.imgs) + 1
        rid = f"rIdMem{n}"
        media = f"mem_{n:02d}.png"
        self.imgs.append((rid, media, origen))
        did = 2000 + n
        dibujo = (
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{did}" name="Imagen {did}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{did}" name="{media}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
        self.body.append(par(dibujo, "MemFigura"))
        self.body.append(self.caption("Figura", titulo))

    def tabla(self, titulo, filas):
        self.body.append(self.caption("Tabla", titulo))
        ncol = len(filas[0])
        largos, minimos = [], []
        for j in range(ncol):
            m = max(len(f[j]) if j < len(f) else 0 for f in filas)
            largos.append(min(max(m, 6), 60) ** 0.85)
            # La palabra más larga de la columna debe caber sin partirse (9 pt, encabezado en negritas).
            palabra = max(len(w) for f in filas if j < len(f) for w in (f[j].split() or [""]))
            minimos.append(min(palabra * 112 + 220, TEXT_W // 2))
        total = sum(largos)
        anchos = [max(minimos[j], int(TEXT_W * largos[j] / total)) for j in range(ncol)]
        # Reparte el exceso quitándolo a las columnas con más holgura sobre su mínimo.
        exceso = sum(anchos) - TEXT_W
        while exceso > 0:
            holgura = [anchos[j] - minimos[j] for j in range(ncol)]
            k = max(range(ncol), key=lambda j: holgura[j])
            if holgura[k] <= 0:
                break
            quita = min(exceso, holgura[k])
            anchos[k] -= quita
            exceso -= quita
        anchos[-1] += TEXT_W - sum(anchos)
        grid = "".join(f'<w:gridCol w:w="{a}"/>' for a in anchos)
        borde = ('<w:tblBorders><w:top w:val="single" w:sz="8" w:space="0" w:color="1B2A4A"/>'
                 '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="1B2A4A"/>'
                 '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="BFC5D0"/></w:tblBorders>')
        xml = [f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/><w:jc w:val="center"/>{borde}'
               '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
               '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
               '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
               f"<w:tblGrid>{grid}</w:tblGrid>"]
        for i, f in enumerate(filas):
            f = f + [""] * (ncol - len(f))
            trpr = "<w:cantSplit/>" + ("<w:tblHeader/>" if i == 0 else "")
            celdas = []
            for j, c in enumerate(f):
                shade = '<w:shd w:val="clear" w:color="auto" w:fill="E8ECF3"/>' if i == 0 else ""
                base = "<w:b/><w:bCs/>" if i == 0 else ""
                numerica = i > 0 and re.fullmatch(r"[−\-]?[\d.,]+\s?%?|[\d.,]+ \(.*\)", c.strip() or "x")
                jc = '<w:jc w:val="right"/>' if numerica else ""
                celdas.append(f'<w:tc><w:tcPr><w:tcW w:w="{anchos[j]}" w:type="dxa"/>{shade}</w:tcPr>'
                              + par(runs(c.strip(), base), "MemTablaTexto", jc) + "</w:tc>")
            xml.append(f"<w:tr><w:trPr>{trpr}</w:trPr>{''.join(celdas)}</w:tr>")
        xml.append("</w:tbl>")
        self.body.append("".join(xml))

    def referencia(self, texto):
        self.body.append(par(runs(texto), "MemReferencia"))

    def salto(self):
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    # --- índices ----------------------------------------------------------------------
    def indice(self, entradas, instr, estilo_por_nivel):
        if not entradas:
            return ""
        out = []
        tabs = f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W - 10}"/></w:tabs>'
        for k, (nivel, texto, bm) in enumerate(entradas):
            pag = str(self.paginas.get(bm, ""))
            inicio = ""
            if k == 0:
                inicio = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                          f'<w:r><w:instrText xml:space="preserve"> {esc(instr)} </w:instrText></w:r>'
                          '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
            link = (f'<w:hyperlink w:anchor="{bm}" w:history="1">{run(texto)}<w:r><w:tab/></w:r>'
                    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                    f'<w:r><w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
                    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                    f"<w:r><w:t>{pag}</w:t></w:r><w:r><w:fldChar w:fldCharType=\"end\"/></w:r></w:hyperlink>")
            fin = '<w:r><w:fldChar w:fldCharType="end"/></w:r>' if k == len(entradas) - 1 else ""
            out.append(par(inicio + link + fin, estilo_por_nivel(nivel), tabs))
        return "".join(out)


def leer_bloques():
    lineas = []
    for f in sorted(TEXTO.glob("*.txt")):
        lineas += f.read_text(encoding="utf8").splitlines() + [""]
    return lineas


def construir(paginas):
    m = Memoria(paginas)
    lineas = leer_bloques()
    i = 0
    marcador_indices = None
    while i < len(lineas):
        ln = lineas[i].rstrip()
        if not ln:
            i += 1
            continue
        if ln.startswith("#! "):
            titulo = ln[3:]
            m.cap = None
            m.h1(titulo, centrado=titulo.isupper())
            i += 1
        elif ln.startswith("#A "):
            m.cap, m.n_fig, m.n_tab = "A", 0, 0
            m.h1(ln[3:], centrado=True)
            i += 1
        elif ln.startswith("# "):
            titulo, sub = [s.strip() for s in ln[2:].split("|")]
            romano = titulo.split()[1]
            if marcador_indices is None:
                # Los índices van entre el Abstract y el primer capítulo.
                marcador_indices = len(m.body)
            m.cap, m.n_fig, m.n_tab = ROMANOS[romano], 0, 0
            m.h1(titulo, centrado=True, espacio_antes=3600)
            m.body.append(par(run(sub, '<w:color w:val="8A1538"/><w:sz w:val="32"/><w:szCs w:val="32"/>'), "MemSubCap"))
            m.salto()
            i += 1
        elif ln.startswith("### "):
            m.hn(3, ln[4:]); i += 1
        elif ln.startswith("## "):
            m.hn(2, ln[3:]); i += 1
        elif ln.startswith("[FIGURA "):
            meta, titulo = ln[len("[FIGURA "):].split("] ", 1)
            archivo, ancho = meta.split()
            m.figura(archivo, float(ancho), titulo)
            i += 1
        elif ln.startswith("[TABLA] "):
            titulo = ln[len("[TABLA] "):]
            filas = []
            i += 1
            while i < len(lineas) and lineas[i].startswith("|"):
                filas.append([c for c in lineas[i].strip().strip("|").split(" | ")])
                i += 1
            m.tabla(titulo, filas)
        elif ln.startswith("[NOTA] "):
            m.nota(ln[len("[NOTA] "):]); i += 1
        elif ln.startswith("[ECUACION] "):
            expr, num = ln[len("[ECUACION] "):].rsplit(" | ", 1)
            m.ecuacion(expr.strip(), num.strip()); i += 1
        elif ln.startswith("[REF] "):
            m.referencia(ln[len("[REF] "):]); i += 1
        elif ln.startswith("- "):
            items = []
            while i < len(lineas) and lineas[i].startswith("- "):
                items.append(lineas[i][2:]); i += 1
            m.lista(items, numerada=False)
        elif re.match(r"^\d+\. ", ln):
            items = []
            while i < len(lineas) and re.match(r"^\d+\. ", lineas[i]):
                items.append(re.sub(r"^\d+\. ", "", lineas[i])); i += 1
            m.lista(items, numerada=True)
        else:
            m.parrafo(ln); i += 1

    # Índices: contenido, figuras y tablas, después del Abstract.
    toc_pre = []
    nombre, cont = m.bookmark(run("ÍNDICE"))
    toc_h_completo = [(1, "ÍNDICE", nombre)]
    toc_pre.append(par(cont, "Ttulo1", '<w:pageBreakBefore/><w:jc w:val="center"/>'))
    nf, contf = m.bookmark(run("Índice de figuras"))
    nt, contt = m.bookmark(run("Índice de tablas"))
    # orden de títulos en el índice: Resumen, Abstract, ÍNDICE, figuras, tablas, capítulos...
    pre = m.toc_h[:2]
    post = m.toc_h[2:]
    toc_h = pre + toc_h_completo + [(1, "Índice de figuras", nf), (1, "Índice de tablas", nt)] + post
    toc_pre.append(m.indice(toc_h, 'TOC \\o "1-3" \\h \\z \\u', lambda n: f"TDC{n}"))
    toc_pre.append(par(contf, "Ttulo1", '<w:pageBreakBefore/><w:jc w:val="center"/>'))
    toc_pre.append(m.indice(m.toc_fig, 'TOC \\h \\z \\t "Pie de figura DATACORE,1"', lambda n: "Tabladeilustraciones"))
    toc_pre.append(par(contt, "Ttulo1", '<w:pageBreakBefore/><w:jc w:val="center"/>'))
    toc_pre.append(m.indice(m.toc_tab, 'TOC \\h \\z \\t "Pie de tabla DATACORE,1"', lambda n: "Tabladeilustraciones"))
    m.body[marcador_indices:marcador_indices] = toc_pre
    m.toc_h_full = toc_h
    return m


ESTILOS = """
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemTexto"><w:name w:val="Texto DATACORE"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="0" w:after="160" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemLista"><w:name w:val="Lista DATACORE"/><w:basedOn w:val="MemTexto"/><w:pPr><w:spacing w:after="80"/><w:ind w:left="720" w:hanging="360"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemFigura"><w:name w:val="Figura DATACORE"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="60" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemPieFigura"><w:name w:val="Pie de figura DATACORE"/><w:basedOn w:val="Normal"/><w:next w:val="MemNota"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="60" w:after="40" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemPieTabla"><w:name w:val="Pie de tabla DATACORE"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" w:after="80" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemNota"><w:name w:val="Nota DATACORE"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="40" w:after="240" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:rPr><w:color w:val="404040"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemTablaTexto"><w:name w:val="Texto de tabla DATACORE"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemEcuacion"><w:name w:val="Ecuacion DATACORE"/><w:basedOn w:val="Normal"/><w:pPr><w:tabs><w:tab w:val="center" w:pos="4419"/><w:tab w:val="right" w:pos="8828"/></w:tabs><w:spacing w:before="120" w:after="200"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemReferencia"><w:name w:val="Referencia DATACORE"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="0" w:after="160" w:line="360" w:lineRule="auto"/><w:ind w:left="720" w:hanging="720"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="MemSubCap"><w:name w:val="Subtitulo de capitulo DATACORE"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="240"/><w:jc w:val="center"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="TDC2"><w:name w:val="toc 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="60"/><w:ind w:left="240"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="TDC3"><w:name w:val="toc 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="60"/><w:ind w:left="480"/></w:pPr><w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Tabladeilustraciones"><w:name w:val="table of figures"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="99"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="80"/><w:ind w:left="1080" w:hanging="1080"/></w:pPr><w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Piedepgina"><w:name w:val="footer"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="99"/><w:unhideWhenUsed/><w:pPr><w:tabs><w:tab w:val="center" w:pos="4419"/><w:tab w:val="right" w:pos="8838"/></w:tabs><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:style>
"""

NUMERACION_ABS = """
<w:abstractNum w:abstractNumId="90"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="\u2022"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:hint="default"/></w:rPr></w:lvl></w:abstractNum>
<w:abstractNum w:abstractNumId="91"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
"""

FOOTER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<w:p><w:pPr><w:pStyle w:val="Piedepgina"/><w:jc w:val="center"/></w:pPr>'
          '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
          '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>')


def portada(xml):
    def rep(viejo, nuevo, veces=2):
        nonlocal xml
        assert xml.count(viejo) == veces, (viejo, xml.count(viejo))
        xml = xml.replace(viejo, nuevo)
    rep("<w:t>xx</w:t>", "<w:t>DATACORE: Plataforma Inteligente de Gestión, Monitoreo y Análisis de Datos Empresariales</w:t>")
    rep("<w:t>gg</w:t>", "<w:t>David Israel Atilano Quiroz</w:t><w:br/><w:t>Ricardo Leonel Ordaz Aguilar</w:t>")
    rep("<w:t>dff</w:t>", "<w:t>René Santana Cruz</w:t>")
    rep("<w:t>ff</w:t>", "<w:t>Adela Becerra Chávez</w:t>")
    # Asesor externo y mes de entrega (datos del usuario).
    xml = re.sub(r'(<w:r>)(<w:rPr>(?:(?!</w:rPr>).)*?)(</w:rPr><w:t>)dsd(</w:t>)',
                 r'\1\2\3Dra. Karina Anaya\4', xml)
    xml = re.sub(r'(<w:rPr>(?:(?!</w:rPr>).)*?)(</w:rPr><w:t>)Mayo(</w:t>)',
                 r'\1\2Noviembre\3', xml)
    assert "dsd" not in xml and ">Mayo<" not in xml
    # El título y los dos nombres ocupan tres renglones más: se quitan tres renglones vacíos
    # antes del lugar y la fecha para que no se salgan del recuadro.
    vacio = re.compile(r'<w:p [^>]*>(?:<w:pPr>(?:(?!</w:pPr>).)*</w:pPr>)?</w:p>', re.S)
    marcas = [mm.start() for mm in re.finditer(r"Dra\. Karina Anaya<", xml)]
    for ini in reversed(marcas):
        fin = xml.find("El Marqu", ini)
        seg = xml[ini:fin]
        vacios = list(vacio.finditer(seg))
        assert len(vacios) >= 3, len(vacios)
        for v in reversed(vacios[:3]):
            seg = seg[:v.start()] + seg[v.end():]
        xml = xml[:ini] + seg + xml[fin:]
    return xml


def main():
    paginas = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else {}
    if BUILD.exists():
        shutil.rmtree(BUILD)
    shutil.copytree(PLANTILLA, BUILD)
    m = construir(paginas)

    doc = (BUILD / "word/document.xml").read_text(encoding="utf8")
    corte = doc.find('<w:p w14:paraId="5D04C935"')
    cuerpo_ini = doc.find("<w:body>") + len("<w:body>")
    cabecera, portadas = doc[:cuerpo_ini], doc[cuerpo_ini:corte]
    sect_final = re.search(r"<w:sectPr[ >].*?</w:sectPr>", doc[corte:], re.S).group(0)
    portadas = portada(portadas)
    # Sección 1 (portadas) sin pie; sección 2 con número de página.
    sect1 = sect_final.replace("<w:cols", '<w:titlePg/><w:cols') if False else sect_final
    sect_portada = f"<w:p><w:pPr>{sect1}</w:pPr></w:p>"
    sect2 = sect_final.replace(">", '><w:footerReference w:type="default" r:id="rIdPie1"/>', 1)
    cuerpo = "".join(m.body)
    doc = cabecera + portadas + sect_portada + cuerpo + sect2 + "</w:body></w:document>"
    # El primer título del cuerpo ya inicia en página nueva por la sección.
    (BUILD / "word/document.xml").write_text(doc, encoding="utf8")

    # Estilos: Arial en todo el documento y estilos propios.
    st = (BUILD / "word/styles.xml").read_text(encoding="utf8")
    st = st.replace('<w:rFonts w:asciiTheme="minorHAnsi" w:eastAsiaTheme="minorHAnsi" w:hAnsiTheme="minorHAnsi" w:cstheme="minorBidi"/>',
                    '<w:rFonts w:ascii="Arial" w:eastAsia="Arial" w:hAnsi="Arial" w:cs="Arial"/>', 1)
    st = st.replace('w:asciiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi"',
                    'w:ascii="Arial" w:eastAsia="Arial" w:hAnsi="Arial" w:cs="Arial"')
    st = st.replace('<w:rFonts w:eastAsiaTheme="majorEastAsia" w:cstheme="majorBidi"/>', '<w:rFonts w:ascii="Arial" w:eastAsia="Arial" w:hAnsi="Arial" w:cs="Arial"/>')
    # Títulos en negritas y tamaños sobrios (16, 14 y 12 pt).
    for sid, sz in (("Ttulo1", 32), ("Ttulo2", 28), ("Ttulo3", 24)):
        st = re.sub(rf'(<w:style [^>]*w:styleId="{sid}".*?<w:sz w:val=")\d+("/><w:szCs w:val=")\d+(")',
                    rf"\g<1>{sz}\g<2>{sz}\g<3>", st, count=1, flags=re.S)
        st = re.sub(rf'(<w:style [^>]*w:styleId="{sid}".*?<w:rPr>)', r"\1<w:b/><w:bCs/>", st, count=1, flags=re.S)
    st = st.replace("</w:styles>", ESTILOS + "</w:styles>")
    (BUILD / "word/styles.xml").write_text(st, encoding="utf8")

    nu = (BUILD / "word/numbering.xml").read_text(encoding="utf8")
    p = nu.find("<w:num ")
    nu = nu[:p] + NUMERACION_ABS + nu[p:]
    nums = '<w:num w:numId="90"><w:abstractNumId w:val="90"/></w:num>' + "".join(
        f'<w:num w:numId="{n}"><w:abstractNumId w:val="91"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        for n in m.num_listas)
    nu = nu.replace("</w:numbering>", nums + "</w:numbering>")
    (BUILD / "word/numbering.xml").write_text(nu, encoding="utf8")

    # Imágenes, pie de página y relaciones.
    rels = (BUILD / "word/_rels/document.xml.rels").read_text(encoding="utf8")
    extra = []
    for rid, media, origen in m.imgs:
        shutil.copy(origen, BUILD / "word/media" / media)
        extra.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{media}"/>')
    extra.append('<Relationship Id="rIdPie1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>')
    rels = rels.replace("</Relationships>", "".join(extra) + "</Relationships>")
    (BUILD / "word/_rels/document.xml.rels").write_text(rels, encoding="utf8")
    (BUILD / "word/footer1.xml").write_text(FOOTER, encoding="utf8")
    ct = (BUILD / "[Content_Types].xml").read_text(encoding="utf8")
    ct = ct.replace("</Types>", '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>')
    (BUILD / "[Content_Types].xml").write_text(ct, encoding="utf8")

    # Pedir a Word que actualice los campos al abrir (los índices ya traen números).
    se = (BUILD / "word/settings.xml").read_text(encoding="utf8")
    if "w:updateFields" not in se:
        se = se.replace("<w:compat>", '<w:updateFields w:val="true"/><w:compat>', 1)
    (BUILD / "word/settings.xml").write_text(se, encoding="utf8")

    if SALIDA.exists():
        SALIDA.unlink()
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(BUILD.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(BUILD).as_posix())
    # Mapa de títulos y pies para localizar páginas en el PDF.
    mapa = {bm: t for _, t, bm in (m.toc_h_full + m.toc_fig + m.toc_tab)}
    (BASE / "mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=0), encoding="utf8")
    (BASE / "captions.txt").write_text("\n".join(m.captions), encoding="utf8")
    print("ok", SALIDA, "figuras", len(m.toc_fig), "tablas", len(m.toc_tab), "títulos", len(m.toc_h))


if __name__ == "__main__":
    main()
