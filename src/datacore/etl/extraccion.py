"""Extracción: lee los archivos de cada área tal como llegan.

Todo se lee como texto (sin inferir tipos ni convertir vacíos en NaN): la
conversión y la validación son trabajo de la transformación, que así puede
registrar cada valor que no cumple.
"""

from pathlib import Path

import pandas as pd


def _csv(ruta: Path, **kwargs) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, **kwargs)
    df["_archivo"] = ruta.name
    df["_fila"] = range(2, len(df) + 2)  # fila 1 = encabezado
    return df


def _excel(ruta: Path) -> pd.DataFrame:
    df = pd.read_excel(ruta, dtype=str, keep_default_na=False)
    df["_archivo"] = ruta.name
    df["_fila"] = range(2, len(df) + 2)
    return df


def _por_anio(carpeta: Path, patron: str) -> pd.DataFrame:
    archivos = sorted(carpeta.glob(patron))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos {patron} en {carpeta}")
    return pd.concat([_csv(a) for a in archivos], ignore_index=True)


def extraer(raw: Path) -> dict[str, pd.DataFrame]:
    return {
        "sucursales": _csv(raw / "catalogos" / "sucursales.csv"),
        "proveedores": _excel(raw / "catalogos" / "proveedores.xlsx"),
        "productos": _excel(raw / "catalogos" / "productos.xlsx"),
        # El CRM exporta en Windows-1252 separado por punto y coma.
        "clientes": _csv(raw / "clientes" / "clientes.csv", sep=";", encoding="cp1252"),
        "ventas": _por_anio(raw / "ventas", "ventas_*.csv"),
        "detalle_venta": _por_anio(raw / "ventas", "detalle_venta_*.csv"),
        "movimientos_inventario": _por_anio(raw / "inventario", "movimientos_inventario_*.csv"),
        "inventario": _csv(raw / "inventario" / "inventario_actual.csv"),
        "incidencias": _csv(raw / "operacion" / "incidencias.csv"),
    }
