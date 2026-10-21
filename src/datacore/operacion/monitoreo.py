"""Monitoreo básico de la plataforma; cada chequeo queda en ops.monitoreo.

Componentes: base de datos, API, dashboard, espacio en disco y frescura del
último ETL, respaldo y modelo. Devuelve código de salida distinto de 0 si
algún componente falla, para que el programador de tareas lo detecte.
"""

import os
import shutil
import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy import text

from ..db import RAIZ, engine
from ..registro import obtener_logger

log = obtener_logger("monitoreo")

UMBRALES = {
    "etl_horas": float(os.getenv("DATACORE_ETL_MAX_HORAS", 26)),
    "respaldo_horas": float(os.getenv("DATACORE_RESPALDO_MAX_HORAS", 26)),
    "modelo_dias": float(os.getenv("DATACORE_MODELO_MAX_DIAS", 8)),
    "disco_gb": float(os.getenv("DATACORE_DISCO_MIN_GB", 5)),
}


def _http(componente: str, url: str | None) -> dict:
    if not url:
        return {"componente": componente, "estado": "alerta", "detalle": "URL no configurada"}
    t0 = time.perf_counter()
    try:
        r = httpx.get(url, timeout=10)
        estado = "ok" if r.status_code == 200 else "falla"
        detalle = f"HTTP {r.status_code}"
    except httpx.HTTPError as exc:
        estado, detalle = "falla", f"sin respuesta: {type(exc).__name__}"
    return {"componente": componente, "estado": estado, "latencia_ms": (time.perf_counter() - t0) * 1000,
            "detalle": f"{url} → {detalle}"}


def _antiguedad(c, sql: str, limite: timedelta, componente: str) -> dict:
    ultimo = c.execute(text(sql)).scalar()
    if ultimo is None:
        return {"componente": componente, "estado": "alerta", "detalle": "sin registros"}
    edad = datetime.now() - ultimo
    estado = "ok" if edad <= limite else "alerta"
    return {"componente": componente, "estado": estado, "detalle": f"último: {ultimo:%Y-%m-%d %H:%M} "
                                                                   f"(hace {edad.total_seconds() / 3600:.1f} h)"}


def revisar(api_url: str | None = None, dashboard_url: str | None = None) -> list[dict]:
    api_url = api_url or os.getenv("DATACORE_API_URL", "http://127.0.0.1:8000")
    dashboard_url = dashboard_url or os.getenv("DATACORE_DASHBOARD_URL")
    resultados = []

    t0 = time.perf_counter()
    try:
        eng = engine("app")
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
            resultados.append({"componente": "base_de_datos", "estado": "ok",
                               "latencia_ms": (time.perf_counter() - t0) * 1000,
                               "detalle": c.execute(text("SELECT version()")).scalar().split(",")[0]})
            resultados.append(_antiguedad(c, "SELECT max(fin) FROM ops.etl_ejecuciones WHERE estatus = 'exitosa'",
                                          timedelta(hours=UMBRALES["etl_horas"]), "etl"))
            resultados.append(_antiguedad(c, "SELECT max(fin) FROM ops.respaldos WHERE estatus = 'exitoso'",
                                          timedelta(hours=UMBRALES["respaldo_horas"]), "respaldo"))
            resultados.append(_antiguedad(c, "SELECT max(entrenado_en) FROM ops.modelos WHERE activo",
                                          timedelta(days=UMBRALES["modelo_dias"]), "modelo"))
    except Exception as exc:
        resultados.append({"componente": "base_de_datos", "estado": "falla", "detalle": str(exc)[:500]})
        eng = None

    resultados.append(_http("api", api_url.rstrip("/") + "/salud"))
    if dashboard_url:
        resultados.append(_http("dashboard", dashboard_url.rstrip("/") + "/_stcore/health"))

    libre = shutil.disk_usage(RAIZ).free / 1e9
    resultados.append({"componente": "disco", "estado": "ok" if libre >= UMBRALES["disco_gb"] else "alerta",
                       "detalle": f"{libre:.1f} GB libres"})

    for r in resultados:
        nivel = {"ok": log.info, "alerta": log.warning, "falla": log.error}[r["estado"]]
        nivel("%-13s %-6s %s", r["componente"], r["estado"], r.get("detalle", ""))
    if eng is not None:
        with eng.begin() as c:
            c.execute(text("INSERT INTO ops.monitoreo (componente, estado, latencia_ms, detalle) "
                           "VALUES (:componente, :estado, :latencia_ms, :detalle)"),
                      [{"latencia_ms": None, "detalle": None} | r for r in resultados])
    return resultados
