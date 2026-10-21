"""Acceso a datos de la API: consultas parametrizadas sobre core, kpi y ops."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Engine, text


def _fila(row) -> dict:
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row._mapping.items()}


def filas(engine: Engine, sql: str, **params) -> list[dict]:
    with engine.connect() as c:
        return [_fila(r) for r in c.execute(text(sql), params)]


def una(engine: Engine, sql: str, **params) -> dict | None:
    resultado = filas(engine, sql, **params)
    return resultado[0] if resultado else None


def filtros(**condiciones) -> tuple[str, dict]:
    """Construye un WHERE con las condiciones cuyo valor no es None.

    Las llaves son "columna operador" (p. ej. "fecha >=") y los valores van
    siempre como parámetros enlazados, nunca concatenados en el SQL.
    """
    partes, params = [], {}
    for i, (clave, valor) in enumerate(condiciones.items()):
        if valor is None:
            continue
        columna, operador = clave.rsplit(" ", 1) if " " in clave else (clave, "=")
        partes.append(f"{columna} {operador} :p{i}")
        params[f"p{i}"] = valor
    return ("WHERE " + " AND ".join(partes)) if partes else "", params


def rango_fechas(engine: Engine) -> tuple[date, date]:
    r = una(engine, "SELECT min(fecha_hora)::date AS desde, max(fecha_hora)::date AS hasta FROM core.ventas")
    return r["desde"], r["hasta"]
