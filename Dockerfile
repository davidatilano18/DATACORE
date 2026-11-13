# DATACORE: una imagen para todos los servicios; SERVICIO elige qué arranca.
#   api        → FastAPI en $PORT
#   dashboard  → Streamlit en $PORT
#   diario     → respaldo → datos → ETL → modelo → monitoreo (para una tarea programada)
#   inicial    → carga única de un servidor nuevo: base, datos simulados, ETL, modelo
#   monitoreo  → chequeo de componentes
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg \
    SERVICIO=api PORT=8000 DATACORE_ROOT=/app

# pg_dump/pg_restore para respaldos, de la versión 18 (repositorio oficial de PostgreSQL): pg_dump solo respalda
# servidores de su versión o anteriores, y Railway usa PostgreSQL 18; también sirve para el 16 de la CI.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY pyproject.toml README.md ./
COPY src ./src
COPY db ./db
COPY .streamlit ./.streamlit
# Logotipo e ícono del dashboard (tema.py los busca en branding/png).
COPY branding/png ./branding/png
RUN pip install --no-deps . && useradd --create-home datacore && mkdir -p logs backups data reports/ml && chown -R datacore /app
USER datacore

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD curl -sf "http://127.0.0.1:${PORT}/salud" || curl -sf "http://127.0.0.1:${PORT}/_stcore/health" || exit 1

CMD ["sh", "-c", "case \"$SERVICIO\" in \
  api) exec uvicorn datacore.api.app:app --host 0.0.0.0 --port \"$PORT\" ;; \
  dashboard) exec streamlit run src/datacore/dashboard/Inicio.py --server.port \"$PORT\" --server.address 0.0.0.0 --server.headless true ;; \
  diario) exec python -m datacore.operacion diario ;; \
  inicial) exec python -m datacore.operacion inicial ;; \
  monitoreo) exec python -m datacore.operacion monitoreo ;; \
  *) echo \"SERVICIO desconocido: $SERVICIO\" >&2; exit 2 ;; esac"]
