# AGENTS.md: guía para agentes de código (Codex, Claude)

DATACORE es el proyecto de estadía (UPQ, Ingeniería en Datos e IA) de David Atilano y Ricardo Ordaz:
una plataforma de datos completa para NexaTech Solutions, una distribuidora **ficticia**. Lee `docs/`
antes de cambiar algo importante; ahí están los requerimientos, la arquitectura, el modelo de datos
y las reglas de simulación.

## Entorno

- Windows 11, Python 3.15 en `.venv` (usa `.venv\Scripts\python`, no el Python del sistema).
- Instalación: `.venv\Scripts\python -m pip install -e .` (las dependencias están en `requirements.txt`).
- Con Python 3.15 instala con `--only-binary=:all:`: no hay compilador de C, así que paquetes como pyyaml fallan.
- Generar datos: `.venv\Scripts\python -m datacore.generator --salida data` (unos 15 s, semilla 42).
- Pruebas: `.venv\Scripts\python -m pytest -q`.
- En PowerShell 5.1 **no edites archivos con `Get-Content | Set-Content`**: rompe los acentos (UTF-8 → ANSI).

## Convenciones

- Código, comentarios, nombres de tablas y columnas, y documentación **en español**. Identificadores
  sin acentos (`tamano`, `descripcion`) y en `snake_case`.
- Las columnas que empiezan con `_` en el generador son parámetros ocultos: **nunca** se exportan a `data/raw`.
- Los archivos crudos usan códigos de negocio (`codigo_sucursal`, `sku`); el ETL los traduce a llaves (`id_*`).
- `data/` no se versiona. `data/ground_truth/` es la verdad de referencia contra la que se prueban el ETL y la calidad.
- Todo módulo nuevo lleva pruebas en `tests/`. No metas datos a mano en las pruebas si puedes generarlos
  con una configuración reducida (ver `tests/test_generator.py`).
- Los montos se redondean a 2 decimales; las cantidades de inventario son enteros con signo (+ entra, − sale).

## Estructura

```
src/datacore/generator/  listo: catálogos, demanda, inventario, incidencias, defectos
src/datacore/etl/        listo: extracción, limpieza, reglas de calidad, carga a PostgreSQL (python -m datacore.etl --evaluar)
src/datacore/eda/        listo: reporte exploratorio en reports/eda/
src/datacore/db.py       conexión (roles admin / app / lector desde .env; nunca imprimas .env)
src/datacore/ml/         pendiente: pronóstico semanal de demanda y alertas
src/datacore/api/        pendiente: FastAPI
src/datacore/dashboard/  pendiente: Streamlit
db/schema.sql            DDL de PostgreSQL (esquemas core y ops)
```

## Cómo trabajar una tarea

1. Lee la sección relevante de `docs/` y el código vecino; imita su estilo.
2. Cambios pequeños y enfocados en la tarea. No reformatees archivos que no tocas.
3. Corre `pytest -q` antes de terminar e informa el resultado real.
4. Si cambias el esquema o una regla de negocio, actualiza `db/schema.sql` y el documento de `docs/` correspondiente.
