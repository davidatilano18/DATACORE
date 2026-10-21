"""Carga a PostgreSQL con COPY, en una sola transacción.

Es una recarga completa (TRUNCATE + COPY): correr el ETL dos veces sobre los
mismos archivos deja exactamente los mismos datos (idempotencia, RNF-04).
Cada tabla deja su renglón en ops.etl_ejecuciones y sus hallazgos en
ops.calidad_hallazgos.
"""

import io
from datetime import datetime

import pandas as pd
from sqlalchemy import Engine, text

ORDEN = ["sucursales", "categorias", "proveedores", "productos", "clientes", "ventas",
         "detalle_venta", "inventario", "movimientos_inventario", "incidencias"]


def _copy(cursor, tabla: str, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    columnas = ", ".join(df.columns)
    with cursor.copy(f"COPY {tabla} ({columnas}) FROM STDIN WITH (FORMAT csv)") as cp:
        while bloque := buf.read(1 << 20):
            cp.write(bloque)


def cargar(engine: Engine, tablas: dict[str, pd.DataFrame], hallazgos: pd.DataFrame,
           estadisticas: dict[str, dict], inicio: datetime) -> dict[str, int]:
    ids: dict[str, int] = {}
    try:
        with engine.begin() as c:
            cursor = c.connection.driver_connection.cursor()
            c.execute(text("TRUNCATE " + ", ".join(f"core.{t}" for t in ORDEN) + " CASCADE"))
            for tabla in ORDEN:
                _copy(cursor, f"core.{tabla}", tablas[tabla])
                e = estadisticas[tabla]
                ids[tabla] = c.execute(text(
                    "INSERT INTO ops.etl_ejecuciones (proceso, archivo_origen, inicio, fin, estatus, "
                    "filas_leidas, filas_cargadas, filas_rechazadas) "
                    "VALUES (:p, :a, :i, now(), 'exitosa', :l, :c, :r) RETURNING id_ejecucion"),
                    {"p": f"carga_{tabla}", "a": e["archivos"], "i": inicio, "l": e["leidas"],
                     "c": len(tablas[tabla]), "r": e["leidas"] - len(tablas[tabla])}).scalar()
            h = hallazgos.copy()
            h.insert(0, "id_ejecucion", h["tabla"].map(ids))
            _copy(cursor, "ops.calidad_hallazgos", h)
    except Exception as exc:
        with engine.begin() as c:
            c.execute(text("INSERT INTO ops.etl_ejecuciones (proceso, inicio, fin, estatus, mensaje_error) "
                           "VALUES ('etl_completo', :i, now(), 'fallida', :m)"), {"i": inicio, "m": str(exc)[:2000]})
        raise
    return ids
