# DATACORE: una imagen para todos los servicios; SERVICIO elige qué arranca.
#   api        → FastAPI en $PORT
#   dashboard  → Streamlit en $PORT
#   diario     → respaldo → ETL → modelo → monitoreo (para una tarea programada)
#   monitoreo  → chequeo de componentes
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg \
    SERVICIO=api PORT=8000 DATACORE_ROOT=/app

# pg_dump/pg_restore para respaldos.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY pyproject.toml README.md ./
COPY src ./src
COPY db ./db
COPY .streamlit ./.streamlit
RUN pip install --no-deps . && useradd --create-home datacore && mkdir -p logs backups && chown -R datacore /app
USER datacore

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD curl -sf "http://127.0.0.1:${PORT}/salud" || curl -sf "http://127.0.0.1:${PORT}/_stcore/health" || exit 1

CMD ["sh", "-c", "case \"$SERVICIO\" in \
  api) exec uvicorn datacore.api.app:app --host 0.0.0.0 --port \"$PORT\" ;; \
  dashboard) exec streamlit run src/datacore/dashboard/Inicio.py --server.port \"$PORT\" --server.address 0.0.0.0 --server.headless true ;; \
  diario) exec python -m datacore.operacion diario ;; \
  monitoreo) exec python -m datacore.operacion monitoreo ;; \
  *) echo \"SERVICIO desconocido: $SERVICIO\" >&2; exit 2 ;; esac"]
