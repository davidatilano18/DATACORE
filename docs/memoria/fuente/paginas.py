"""Localiza en el PDF la página de cada título y pie (bookmark) y escribe paginas.json."""
import json
import re
import sys
from pathlib import Path

import pymupdf

BASE = Path(__file__).resolve().parent
pdf = pymupdf.open(BASE / "pdf/Memoria_Estadia_DATACORE.pdf")
mapa = json.loads((BASE / "mapa.json").read_text(encoding="utf8"))
norm = lambda s: re.sub(r"\s+", " ", s).strip()
textos = [norm(p.get_text()) for p in pdf]

# Títulos: del índice de marcadores del PDF (en orden de aparición).
toc = pdf.get_toc(simple=True)
paginas, sin = {}, []
pendientes = [(bm, t) for bm, t in mapa.items() if not t.startswith(("Figura ", "Tabla "))]
j = 0
for bm, t in pendientes:
    while j < len(toc) and norm(toc[j][1]) != norm(t):
        j += 1
    if j < len(toc):
        paginas[bm] = toc[j][2]
        j += 1
    else:
        sin.append(t)
        j = 0

# Pies: primera página después de los índices donde aparece "Figura X.Y." al inicio de una línea del pie.
inicio = min(p for bm, p in paginas.items() if mapa[bm].startswith("CAPÍTULO I "))
for bm, t in mapa.items():
    if not t.startswith(("Figura ", "Tabla ")):
        continue
    etiqueta = t.split(". ", 1)[0] + "."
    titulo = t.split(". ", 1)[1][:30]
    hallada = None
    for k in range(inicio - 1, len(pdf)):
        if norm(etiqueta + " " + titulo) in textos[k]:
            hallada = k + 1
            break
    if hallada:
        paginas[bm] = hallada
    else:
        sin.append(t)

(BASE / "paginas.json").write_text(json.dumps(paginas, indent=0), encoding="utf8")
print("páginas del PDF:", len(pdf), "| localizados:", len(paginas), "de", len(mapa))
if sin:
    print("SIN LOCALIZAR:", *sin, sep="\n  ")
