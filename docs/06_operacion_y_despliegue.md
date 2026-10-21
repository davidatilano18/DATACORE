# 06 · Operación y despliegue

## Comandos de operación

| Comando | Qué hace | Dónde deja evidencia |
|---|---|---|
| `python -m datacore.operacion respaldo --verificar` | `pg_dump` de `core`, `ops` y `kpi` (formato comprimido); restaura en una base temporal y compara las filas de cada tabla. Conserva los 7 respaldos más recientes. | `backups/`, `ops.respaldos` (columna `verificado`), `logs/respaldo.log` |
| `python -m datacore.operacion verificar [archivo]` | Solo la prueba de recuperación de un respaldo existente. | igual |
| `python -m datacore.operacion monitoreo` | Revisa la base (latencia y versión), la API (`/salud`), el dashboard (`/_stcore/health`), el espacio en disco y la antigüedad del último ETL, respaldo y modelo. Devuelve código 1 si algo falla. | `ops.monitoreo`, `logs/monitoreo.log` |
| `python -m datacore.operacion diario` | Respaldo y verificación → ETL (refresca `kpi`) → publicación del modelo → detección de anomalías → monitoreo. | `ops.corridas` (pasos, duración, error), `logs/diario.log` |

El respaldo va **antes** del ETL porque el ETL recarga `core` por completo: siempre hay una foto previa.

**Decisión de diseño:** las tablas de salida de `ops` (pronósticos, alertas, anomalías) no tienen llave foránea hacia `core`. El ETL recarga `core` con `TRUNCATE … CASCADE`, y con llaves foráneas cada recarga vaciaba también el historial de pronósticos y las alertas ya atendidas. El error se detectó en la revisión nocturna del 21/10/2026; `db/operacion.sql` incluye la migración que quita esas llaves en bases existentes, y una prueba evita que vuelvan.

**Resultado medido (20/10/2026):** respaldo de 16 MB en 3 s; la restauración de 15 tablas con 1,525,992 filas cuadró al 100 % en 12 s.

### Umbrales del monitoreo (variables de entorno)

| Variable | Por defecto | Significado |
|---|---|---|
| `DATACORE_ETL_MAX_HORAS` | 26 | Alerta si el último ETL exitoso es más antiguo. |
| `DATACORE_RESPALDO_MAX_HORAS` | 26 | Lo mismo para el último respaldo. |
| `DATACORE_MODELO_MAX_DIAS` | 8 | Antigüedad máxima del modelo activo. |
| `DATACORE_DISCO_MIN_GB` | 5 | Espacio libre mínimo. |
| `DATACORE_API_URL`, `DATACORE_DASHBOARD_URL` | `http://127.0.0.1:8000`, sin valor | Servicios que se revisan. |

### Programación automática

- **Windows:** `scripts/programar_tareas_windows.ps1` registra la tarea diaria (02:00) y el monitoreo cada 30 min. **No se ha ejecutado**: queda a decisión del equipo.
- **Linux:** `deploy/linux/datacore.cron`.

## Bitácoras

`src/datacore/registro.py` escribe en la consola y en `logs/<componente>.log`, con rotación a 5 MB y 5 copias: `api`, `respaldo`, `monitoreo`, `diario`. Cada petición a la API queda registrada con su método, ruta, código y latencia.

## Integración continua

`.github/workflows/ci.yml` corre en cada push a `main`:

1. PostgreSQL 16 como servicio y Python 3.13.
2. Datos simulados reducidos (120 productos, 1,500 clientes, 3 años) → `db_setup` → ETL con evaluación → publicación del modelo.
3. Levanta la API y corre **todas** las pruebas: incluidas API, dashboard, KPI y operación, que localmente se saltan si no hay base.
4. Respaldo con prueba de recuperación y monitoreo.
5. Construye la imagen Docker, la arranca contra la misma base y consulta `/salud` y `/kpi/resumen`.
6. Publica como artefacto el reporte de calidad y las bitácoras.

## Contenedor

Un solo `Dockerfile`; la variable `SERVICIO` elige qué arranca:

| `SERVICIO` | Proceso |
|---|---|
| `api` (por defecto) | `uvicorn datacore.api.app:app` en `$PORT` |
| `dashboard` | `streamlit run src/datacore/dashboard/Inicio.py` en `$PORT` |
| `diario` | proceso diario (para una tarea programada) |
| `monitoreo` | chequeo de componentes |

Variables necesarias: `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_APP_USER`, `PG_APP_PASSWORD`, `PG_LECTOR_USER`, `PG_LECTOR_PASSWORD` (y `PG_ADMIN_*` solo para `db_setup` y la verificación de respaldos). Opcionales: `DATACORE_API_KEY`, `DATACORE_CORS`, y en el dashboard `DATACORE_API_URL`.

## Plan de despliegue en Railway (pendiente, no ejecutado)

> **No se ha desplegado nada.** El equipo tiene otro proyecto en Railway con presentación el 22/10/2026. El despliegue se hará después y en un **proyecto de Railway separado**.

1. Crear un proyecto nuevo en Railway, solo para DATACORE.
2. Agregar el servicio **PostgreSQL** de Railway.
3. Agregar el servicio **api** desde el repo de GitHub (usa el `Dockerfile`), con `SERVICIO=api` y las variables `PG_*` tomadas del servicio PostgreSQL. Definir `DATACORE_API_KEY`.
4. Agregar el servicio **dashboard** desde el mismo repo, con `SERVICIO=dashboard`, `DATACORE_API_URL=<url interna de api>` y la misma `DATACORE_API_KEY`.
5. Carga inicial desde una máquina con el repo: crear roles, esquema y datos apuntando las variables `PG_*` a Railway (`db_setup`, `generator`, `etl`, `ml publicar`), o restaurar un respaldo con `pg_restore`.
6. Tarea programada (cron de Railway) con `SERVICIO=diario`.
7. Probar `/salud` y el dashboard; correr `monitoreo` contra las URL públicas.

Alternativa: un VPS (por ejemplo Contabo) con Docker o con systemd, usando `deploy/linux/datacore.cron`.

El dashboard expone las bitácoras mediante las rutas protegidas `/operacion/monitoreo`,
`/operacion/respaldos`, `/operacion/corridas` e `/incidencias/abiertas`, con límite de filas validado.
La mezcla de categorías admite sucursal y fechas exactas. `/pronosticos/resumen` publica el total
esperado de cuatro semanas y un intervalo normal aproximado del 80 %, sumando las varianzas
binomiales negativas bajo independencia entre pares y semanas. Esta hipótesis puede subestimar
la incertidumbre si los errores temporales están correlacionados; no sustituye una calibración
conjunta de los cuatro horizontes.
