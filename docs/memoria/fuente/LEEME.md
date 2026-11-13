# Fuente de la memoria de estadía

- `texto/*.txt`: contenido por capítulo (marcado simple: `#` capítulo, `##`/`###` subtítulos, `[TABLA]`, `[FIGURA archivo ancho_cm]`, `[NOTA]`, `[ECUACION] … | n`, `[REF]`, `[PENDIENTE: …]` sale resaltado en amarillo).
- `figs.py`: genera las figuras propias en `figs/` (`.venv\Scripts\python figs.py figs`).
- `build.py`: arma el .docx sobre la plantilla oficial (`../plantilla`, ya descomprimida).
- `ciclo.sh`: build → PDF con LibreOffice → números de página de los índices → build final. Usa el Python del proyecto (`.venv`) con PyMuPDF instalado; las variables de entorno `PY` y `SO` cambian el Python y la ruta de LibreOffice.
- `paginas.py` y `render.py`: leen el PDF para numerar los índices y generar las hojas de revisión en `hojas/`.

Los archivos intermedios (`build/`, `pdf/`, `hojas/`, `*.json`) no se versionan; la versión final se copia a `docs/memoria/`.
