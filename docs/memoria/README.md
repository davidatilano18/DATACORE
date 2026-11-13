# Memoria de estadía

Reporte de proyecto de estadía de DATACORE en el formato oficial de la Universidad Politécnica de Querétaro.

| Archivo | Contenido |
|---|---|
| [Memoria_Estadia_DATACORE.pdf](Memoria_Estadia_DATACORE.pdf) | Versión para leer e imprimir (85 páginas). |
| [Memoria_Estadia_DATACORE.docx](Memoria_Estadia_DATACORE.docx) | Versión editable en Word. |
| [fuente/](fuente/LEEME.md) | Texto por capítulo, figuras y el generador del documento. |
| [plantilla/](plantilla/) | Plantilla oficial de la UPQ, descomprimida, sobre la que se arma el documento. |

**Contenido:** antecedentes, marco teórico, definición del proyecto, desarrollo por etapas (incluidas las mejoras de
impacto en dinero, alertas, pedido sugerido y explicaciones), análisis de resultados, conclusiones, 17 referencias en
formato APA y tres anexos. Incluye 26 figuras y 44 tablas numeradas por capítulo.

## Cómo regenerarla

El contenido vive en `fuente/texto/*.txt`; no se edita el `.docx` a mano.

```bash
# Requisitos: LibreOffice y PyMuPDF en el entorno del proyecto
.venv/Scripts/python -m pip install pymupdf
.venv/Scripts/python docs/memoria/fuente/figs.py docs/memoria/fuente/figs reports/ml   # figuras propias
bash docs/memoria/fuente/ciclo.sh                                                       # .docx + PDF con índices numerados
cp docs/memoria/fuente/Memoria_Estadia_DATACORE.docx docs/memoria/
cp docs/memoria/fuente/pdf/Memoria_Estadia_DATACORE.pdf docs/memoria/
```

`ciclo.sh` arma el documento, lo convierte a PDF, lee en qué página quedó cada título, figura y tabla, y vuelve a
armarlo hasta que los números de los índices son estables.
