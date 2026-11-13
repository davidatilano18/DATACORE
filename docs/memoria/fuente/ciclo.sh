#!/bin/bash
# build -> pdf -> paginas -> build con páginas -> pdf -> verificar estabilidad -> hojas
set -e
cd "$(dirname "$0")"
# Python con PyMuPDF (por defecto, el del proyecto) y LibreOffice; ambos se pueden cambiar con variables de entorno.
PY="${PY:-../../../.venv/Scripts/python}"
SO="${SO:-/c/Program Files/LibreOffice/program/soffice.exe}"
"$PY" -I build.py >/dev/null
"$SO" --headless --convert-to pdf --outdir pdf Memoria_Estadia_DATACORE.docx >/dev/null 2>&1
"$PY" -I paginas.py
for n in 1 2; do
  cp paginas.json paginas_prev.json
  "$PY" -I build.py paginas.json >/dev/null
  "$SO" --headless --convert-to pdf --outdir pdf Memoria_Estadia_DATACORE.docx >/dev/null 2>&1
  "$PY" -I paginas.py
  if cmp -s paginas.json paginas_prev.json; then echo "estable"; break; fi
done
rm -rf hojas; "$PY" -I render.py pdf/Memoria_Estadia_DATACORE.pdf hojas
