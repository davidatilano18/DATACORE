"""Proceso diario: respaldo → datos → ETL (incluye refresco de kpi) → modelo → anomalías → monitoreo.

El respaldo va primero porque el ETL recarga `core` por completo: si algo
sale mal, siempre existe la foto anterior. Cada paso queda en ops.corridas.
"""

import json
import time
from pathlib import Path

from sqlalchemy import text

from ..db import RAIZ, engine
from ..registro import obtener_logger

log = obtener_logger("diario")


def _paso(nombre: str, funcion, pasos: list) -> object:
    t0 = time.perf_counter()
    log.info("▶ %s", nombre)
    try:
        resultado = funcion()
    except Exception as exc:
        pasos.append({"paso": nombre, "estatus": "fallido", "segundos": round(time.perf_counter() - t0, 1),
                      "detalle": str(exc)[:500]})
        raise
    pasos.append({"paso": nombre, "estatus": "exitoso", "segundos": round(time.perf_counter() - t0, 1)})
    log.info("✔ %s (%.1fs)", nombre, time.perf_counter() - t0)
    return resultado


def ejecutar(raw: Path | None = None, con_modelo: bool = True, verificar_respaldo: bool = True) -> bool:
    from ..etl.pipeline import ejecutar as etl
    from . import datos, monitoreo, respaldo

    eng = engine("app")
    with eng.begin() as c:
        id_corrida = c.execute(text("INSERT INTO ops.corridas (proceso, estatus) VALUES ('diario', 'en_curso') "
                                    "RETURNING id_corrida")).scalar()
    pasos: list[dict] = []
    error = None
    try:
        archivo = _paso("respaldo", respaldo.respaldar, pasos)
        if verificar_respaldo:
            _paso("verificacion_respaldo", lambda: respaldo.verificar(archivo), pasos)
        if raw is None:
            # En un servidor nuevo no hay archivos de entrada: se generan los simulados (una sola vez).
            _paso("datos", datos.asegurar_datos_simulados, pasos)
        _paso("etl", lambda: etl(raw or RAIZ / "data" / "raw", cargar_bd=True), pasos)
        if con_modelo:
            _paso("modelo", _publicar_modelo, pasos)
            _paso("anomalias", _publicar_anomalias, pasos)
    except Exception as exc:
        error = exc
        log.exception("la corrida diaria falló")
    finally:
        try:
            _paso("monitoreo", monitoreo.revisar, pasos)
        except Exception:
            log.exception("el monitoreo falló")
        with eng.begin() as c:
            c.execute(text("UPDATE ops.corridas SET fin = now(), estatus = :e, pasos = CAST(:p AS jsonb), "
                           "mensaje_error = :m WHERE id_corrida = :i"),
                      {"e": "fallida" if error else "exitosa", "p": json.dumps(pasos),
                       "m": str(error)[:2000] if error else None, "i": id_corrida})
    return error is None


def inicial() -> bool:
    """Carga inicial en un servidor nuevo: base y esquema → datos → ETL → modelo → anomalías.
    Sin respaldo (todavía no hay nada que respaldar). Idempotente: se puede volver a correr."""
    from ..db_setup import aplicar_esquema, crear_roles_y_base
    from ..etl.pipeline import ejecutar as etl
    from . import datos

    pasos: list[dict] = []
    try:
        _paso("base", lambda: (crear_roles_y_base(), aplicar_esquema(reset=False)), pasos)
        _paso("datos", datos.asegurar_datos_simulados, pasos)
        _paso("etl", lambda: etl(RAIZ / "data" / "raw", cargar_bd=True), pasos)
        _paso("modelo", _publicar_modelo, pasos)
        _paso("anomalias", _publicar_anomalias, pasos)
    except Exception:
        log.exception("la carga inicial falló en el paso %s", len(pasos))
        return False
    return True


def _publicar_anomalias():
    from ..ml import anomalias
    anomalias.ejecutar(engine("app"), RAIZ / "data" / "ground_truth", RAIZ / "reports" / "ml")


def _publicar_modelo():
    import sys
    from ..ml import __main__ as ml
    argv = sys.argv
    sys.argv = ["datacore.ml", "publicar"]
    try:
        ml.main()
    finally:
        sys.argv = argv
