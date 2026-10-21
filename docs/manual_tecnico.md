# Manual técnico de DATACORE

Para quien instala, opera o modifica la plataforma. El diseño está en `docs/01` a `docs/06`; este manual cubre el *cómo*.

## 1. Requisitos

| Componente | Versión probada | Notas |
|---|---|---|
| Python | 3.15 (Windows) y 3.13 (CI, Docker) | Con 3.15 instala con `--only-binary=:all:` (no hay compilador de C). |
| PostgreSQL | 16 | Servidor local o administrado; `pg_dump` y `pg_restore` para los respaldos. |
| Git | cualquiera reciente | |
| Docker | opcional | Para correr la imagen; el CI la construye en cada push. |

## 2. Instalación desde cero

```powershell
git clone https://github.com/davidatilano18/DATACORE.git
cd DATACORE
python -m venv .venv
.venv\Scripts\python -m pip install --only-binary=:all: -r requirements.txt
.venv\Scripts\python -m pip install -e .
copy .env.example .env      # y llena las contraseñas (ver §3)
```

Carga inicial (unos 3 minutos sin contar el modelo):

```powershell
.venv\Scripts\python -m datacore.generator --salida data      # datos simulados (15 s)
.venv\Scripts\python -m datacore.db_setup                      # base, roles, tablas, vistas
.venv\Scripts\python -m datacore.etl --evaluar                 # data/raw → PostgreSQL (≈50 s)
.venv\Scripts\python -m datacore.ml publicar                   # modelo, pronósticos, alertas (≈8 min)
```

Servicios:

```powershell
.venv\Scripts\python -m uvicorn datacore.api.app:app --port 8000          # API → http://127.0.0.1:8000/docs
.venv\Scripts\python -m streamlit run src/datacore/dashboard/Inicio.py    # dashboard → http://localhost:8501
```

## 3. Configuración (`.env`)

| Variable | Uso |
|---|---|
| `PG_HOST`, `PG_PORT`, `PG_DB` | Conexión a PostgreSQL. |
| `PG_ADMIN_USER`, `PG_ADMIN_PASSWORD` | Superusuario: solo para `db_setup` y la verificación de respaldos. |
| `PG_APP_USER`, `PG_APP_PASSWORD` | Rol dueño de los esquemas: ETL, modelo, respaldos, escritura de la API. |
| `PG_LECTOR_USER`, `PG_LECTOR_PASSWORD` | Solo lectura: consultas de la API. |
| `DATACORE_API_KEY` | Si se define, la API exige el encabezado `X-API-Key` (excepto `/salud`). |
| `DATACORE_API_URL` | Dirección de la API para el dashboard y el monitoreo. |
| `DATACORE_CORS` | Orígenes permitidos, separados por coma (por defecto `*`). |
| `DATACORE_LOG_LEVEL` | `INFO` por defecto. |
| `DATACORE_ROOT` | Raíz del proyecto (en Docker es `/app`). |

`.env` nunca se versiona (`.gitignore`).

## 4. Mapa del código

```
src/datacore/
├── generator/   simulación de NexaTech (catálogos, demanda, inventario, incidencias, defectos)
├── etl/         extracción → transformación (reglas de calidad) → carga COPY → evaluación
├── eda/         reporte exploratorio
├── ml/          series semanales, variables, modelo, backtest, publicación, evaluación de alertas
├── api/         FastAPI (app.py: rutas; consultas.py: SQL parametrizado)
├── dashboard/   Streamlit (Inicio.py, pages/, interfaz.py, cliente.py)
├── operacion/   respaldo, monitoreo, proceso diario
├── db.py        conexión por rol desde .env
├── db_setup.py  creación de base, roles, esquemas y vistas; refresco de materializadas
└── registro.py  bitácoras en logs/
db/  schema.sql (core, ops) · operacion.sql (respaldos, monitoreo, corridas) · vistas.sql (kpi)
```

## 5. Tareas frecuentes

| Necesito… | Comando |
|---|---|
| Regenerar los datos con otra semilla | `python -m datacore.generator --seed 7 --salida data` |
| Recrear el esquema desde cero (**borra datos**) | `python -m datacore.db_setup --reset` |
| Refrescar las vistas materializadas | `python -m datacore.db_setup --refrescar` |
| Correr el ETL sin tocar la base | `python -m datacore.etl --sin-carga --evaluar` |
| Evaluar el modelo contra baselines | `python -m datacore.ml evaluar` |
| Respaldar y verificar | `python -m datacore.operacion respaldo --verificar` |
| Restaurar un respaldo en la base viva | `pg_restore -h localhost -U datacore_app -d datacore --clean --if-exists backups\<archivo>.dump` |
| Revisar el estado | `python -m datacore.operacion monitoreo` |
| Correr las pruebas | `python -m pytest -q` (las de base, API y dashboard se saltan si no hay servicios) |

## 6. Agregar una regla de calidad

1. En `src/datacore/etl/transformacion.py`, dentro de la función de la tabla, detecta los registros y llama a `h.agregar(tabla, "nombre_regla", claves, accion, originales, finales)` con `accion` ∈ `corregido`, `rechazado` o `marcado`.
2. Si la regla ataca un defecto del generador, usa el **mismo nombre** que el tipo de defecto: así la evaluación mide su precisión y exhaustividad automáticamente.
3. Agrega o ajusta la prueba en `tests/test_etl.py`.

## 7. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Falta PG_... en .env` | `.env` incompleto | Copia `.env.example` y llena los valores. |
| `la autentificación password falló` | Contraseña incorrecta en `.env` | Corrígela; para restablecer la de `postgres`, edita `pg_hba.conf` temporalmente a `trust`. |
| `pip` intenta compilar y falla | Paquete sin rueda (wheel) para Python 3.15 | Instala con `--only-binary=:all:` o usa Python 3.13. |
| El dashboard muestra "No se pudo conectar con la API" | La API no corre o `DATACORE_API_URL` es incorrecta | Levanta uvicorn; revisa la variable. |
| `401` en la API | `DATACORE_API_KEY` definida | Envía `X-API-Key` o quita la variable. |
| Los acentos se dañan al editar desde PowerShell 5.1 | `Get-Content`/`Set-Content` usan ANSI | Edita con un editor UTF-8 o con Python. |
