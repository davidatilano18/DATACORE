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
| `diario` | proceso diario (para una tarea programada); genera los datos simulados si `data/raw` está vacío |
| `inicial` | carga única de un servidor nuevo: base, datos, ETL, modelo y anomalías |
| `monitoreo` | chequeo de componentes |

Variables necesarias: `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_APP_USER`, `PG_APP_PASSWORD`, `PG_LECTOR_USER`, `PG_LECTOR_PASSWORD` (y `PG_ADMIN_*` solo para `db_setup` y la verificación de respaldos). Opcionales: `DATACORE_API_KEY`, `DATACORE_CORS`, y en el dashboard `DATACORE_API_URL`.

## Despliegue en producción: Railway (13 de noviembre de 2026)

DATACORE está desplegado en su **propio proyecto de Railway** (`datacore`), separado del otro proyecto que tiene la
cuenta del equipo.

| Servicio | Qué corre | Liga |
|---|---|---|
| `datacore-dashboard` | `SERVICIO=dashboard` | https://datacore-dashboard-production.up.railway.app |
| `datacore-api` | `SERVICIO=api`, protegida con `X-API-Key` (salvo `/salud`) | https://datacore-api-production.up.railway.app |
| `datacore-diario` | `SERVICIO=diario`, tarea programada `0 8 * * 1` (lunes 2:00 en el Centro de México), sin reinicio | — |
| `Postgres` | PostgreSQL 18 administrado por Railway, con volumen persistente | red privada |

**Cómo se desplegó** (`deploy/railway/desplegar.sh`, repetible):

1. `railway init --name datacore` y `railway add --database postgres`.
2. `desplegar.sh servicios`: crea los tres servicios y sus variables. La conexión usa la red privada
   (`${{Postgres.PGHOST}}`); el administrador es el usuario del servicio Postgres. Las contraseñas de los roles
   `datacore_app` y `datacore_lector` y la clave de la API se generan en `deploy/railway/secretos.env`, que no se versiona.
3. `desplegar.sh inicial`: el servicio de operación corre una vez `SERVICIO=inicial` (roles, esquemas, datos
   simulados, ETL, modelo y anomalías). Tardó unos 7 minutos, 5.7 de ellos en el modelo.
4. `desplegar.sh apps`: sube la API y el dashboard y les asigna dominio público.
5. `desplegar.sh diario`: cambia la operación a `SERVICIO=diario` y la programa con la API de Railway
   (`serviceInstanceUpdate`). La primera corrida completa (respaldo y su verificación, datos, ETL, modelo, anomalías y
   monitoreo) se probó a mano antes de programarla.

**Resultados verificados en la nube:** las mismas cifras que en local (279 alertas de desabasto, 462 de exceso y 152
sin rotación; 13,334 unidades de pedido sugerido); la API responde 401 sin clave; las seis páginas del dashboard cargan.

**Decisiones y hallazgos del despliegue:**

- **Cliente de PostgreSQL 18 en la imagen.** Railway usa PostgreSQL 18 y `pg_dump` solo respalda servidores de su
  versión o anteriores; la imagen instala `postgresql-client-18` del repositorio oficial (también sirve para el 16 de la CI).
- **Datos del paquete.** El mapa de la red y las tipografías se declaran en `pyproject.toml`
  (`tool.setuptools.package-data`); sin eso la página de Inicio fallaba dentro de la imagen.
- **Logotipo.** `tema.py` resolvía la raíz desde su propia ubicación, que en la imagen es `site-packages`; ahora usa
  `DATACORE_ROOT` (`/app`), igual que `db.py`.
- **Sin disco persistente para la aplicación.** Los datos simulados se regeneran en ~10 s con la misma semilla y las
  bitácoras de operación viven en la base (`ops.corridas`, `ops.respaldos`, `ops.monitoreo`). El respaldo diario se
  crea y se verifica en cada corrida; la persistencia de la base la da el volumen de Railway.
- **Subidas desde una copia limpia.** En Windows, `railway up` desde la carpeta de trabajo falla con "Acceso denegado"
  si hay bitácoras abiertas; el script sube solo los archivos versionados. No se usa `railway service redeploy`:
  reconstruye sin el Dockerfile.
- **Costo (medido el 13/11/2026):** en reposo la base usa ~620 MB, el dashboard ~190 MB y la API ~75 MB de memoria, con
  CPU casi en cero; encendidos todo el mes serían ~US$9. Para bajarlo:
  - **Apagado automático** (`sleepApplication`) en el dashboard, la API y PostgreSQL: se duermen sin tráfico y despiertan
    con la primera visita o con la tarea programada; la primera carga tarda unos segundos más.
  - **Proceso semanal** (`0 8 * * 1`, lunes 2:00): los datos simulados no cambian, así que no hace falta a diario.
  - **Límite de gasto** de la cuenta: aviso a US$7 y tope a US$10 al mes (`railway usage limit`). El tope aplica a toda
    la cuenta y detiene los servicios al alcanzarlo.
  - Después de la evaluación conviene apagar o borrar el proyecto `datacore`.

## Alternativa documentada: Azure for Students (no utilizada)

> El equipo la eligió primero, pero la verificación de estudiante de Azure falló repetidamente (el enlace de
> verificación respondía "El cliente no tiene derechos de acceso al contenido"). Se conserva el plan y el script
> `deploy/azure/desplegar.sh` como alternativa. Los precios y créditos se consultaron en fuentes de terceros.

**Por qué Azure for Students:** US$100 de crédito sin tarjeta con el correo de la UPQ; PostgreSQL Flexible Server
B1ms incluido 750 h al mes durante 12 meses (alcanza para una base encendida todo el mes); la imagen Docker del
proyecto corre sin cambios en Azure Container Apps. Se descartaron Render (US$35–45 al mes) y un servidor virtual
propio (más barato, pero el equipo tendría que administrar seguridad y respaldos).

**Tamaños medidos:** el reentrenamiento del modelo llega a ~1.2 GB de memoria (medido en noviembre de 2026), por lo
que la tarea diaria necesita 2 GB. La API y el dashboard son ligeros (0.5 vCPU, 1 GB). La base ocupa ~280 MB y los
datos simulados ~80 MB.

| recurso de Azure | uso | tamaño |
|---|---|---|
| Azure Database for PostgreSQL Flexible Server | base `datacore` (core, ops, kpi) | Burstable B1ms, 32 GB |
| Azure Container Registry | imagen `datacore` | Basic |
| Container App `datacore-api` | `SERVICIO=api` | 0.5 vCPU, 1 GB, 1 réplica |
| Container App `datacore-dashboard` | `SERVICIO=dashboard`, ingreso público | 0.5 vCPU, 1 GB, 1 réplica |
| Container Apps Job `datacore-inicial` | `SERVICIO=inicial`, una sola vez | 1 vCPU, 2 GB |
| Container Apps Job `datacore-diario` | `SERVICIO=diario`, cron `0 8 * * *` (2:00 en el Centro de México) | 1 vCPU, 2 GB |
| Azure Files montado en `/app/data`, `/app/backups` y `/app/logs` | datos simulados, respaldos y bitácoras persistentes | 5 GB |

### Pasos

1. Activar Azure for Students con el correo institucional y crear un grupo de recursos `datacore`.
2. Crear el PostgreSQL Flexible Server B1ms y permitir el acceso desde los servicios de Azure. El usuario
   administrador se usa como `PG_ADMIN_*`.
3. Crear el registro de contenedores y subir la imagen (`docker build` y `docker push`, o desde GitHub Actions).
4. Crear el entorno de Container Apps, la cuenta de Azure Files y sus montajes.
5. Definir los secretos del entorno: `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_ADMIN_*`, `PG_APP_*`, `PG_LECTOR_*` y
   `DATACORE_API_KEY`. Nunca van en el repositorio.
6. Ejecutar una vez el Job `datacore-inicial` (`python -m datacore.operacion inicial`): crea roles, esquemas y vistas;
   genera los datos simulados en el disco persistente; corre el ETL y publica el modelo y las anomalías (~15 min).
7. Crear `datacore-api` (ingreso interno) y `datacore-dashboard` (ingreso público) con
   `DATACORE_API_URL=<URL interna de la API>` y la misma `DATACORE_API_KEY`.
8. Programar el Job `datacore-diario` y verificar `/salud`, el dashboard y `python -m datacore.operacion monitoreo`.

### Riesgos

- **El crédito y la base incluida vencen** (12 meses o antes, según los términos vigentes). Conviene una alerta de
  presupuesto en el portal y apagar los recursos después de la evaluación.
- **El consumo de las Container Apps encendidas todo el mes** sale del crédito si supera la cuota gratuita; con
  0.5 vCPU por servicio se estima bajo, pero hay que revisarlo en la primera semana.
- **Los datos son simulados y estáticos:** la tarea diaria vuelve a cargar los mismos archivos. Sirve para demostrar la
  operación (respaldo, ETL, modelo, monitoreo), no para recibir datos nuevos.
- **La configuración es más compleja que en un servidor único** (registro, red, montajes, secretos). Se recomienda
  documentar cada recurso creado.

Alternativa si se agota el crédito: un servidor virtual con Docker Compose y `deploy/linux/datacore.cron`.

El dashboard expone las bitácoras mediante las rutas protegidas `/operacion/monitoreo`,
`/operacion/respaldos`, `/operacion/corridas` e `/incidencias/abiertas`, con límite de filas validado.
La mezcla de categorías admite sucursal y fechas exactas. `/pronosticos/resumen` publica el total
esperado de cuatro semanas y un intervalo normal aproximado del 80 %, sumando las varianzas
binomiales negativas bajo independencia entre pares y semanas. Esta hipótesis puede subestimar
la incertidumbre si los errores temporales están correlacionados; no sustituye una calibración
conjunta de los cuatro horizontes.
