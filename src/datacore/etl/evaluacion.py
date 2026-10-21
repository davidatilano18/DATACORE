"""Evaluación del ETL contra la verdad de referencia del generador (RNF-05).

1. Detección: por cada tipo de defecto inyectado, qué fracción encontró la
   regla del mismo nombre (exhaustividad) y qué fracción de lo que marcó la
   regla era realmente un defecto (precisión).
2. Fidelidad: qué tanto coinciden las tablas limpias con las originales.
"""

from pathlib import Path

import numpy as np
import pandas as pd


def deteccion(hallazgos: pd.DataFrame, bitacora: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for tipo, grupo in bitacora.groupby("tipo_defecto"):
        esperados = set(zip(grupo["tabla"], grupo["clave"].astype(str)))
        reglas = hallazgos[hallazgos["regla"] == tipo]
        encontrados = set(zip(reglas["tabla"], reglas["clave"].astype(str)))
        aciertos = len(esperados & encontrados)
        filas.append({"defecto": tipo, "inyectados": len(esperados), "detectados": len(encontrados),
                      "aciertos": aciertos,
                      "exhaustividad": aciertos / len(esperados) if esperados else np.nan,
                      "precision": aciertos / len(encontrados) if encontrados else np.nan})
    return pd.DataFrame(filas).sort_values("defecto").reset_index(drop=True)


def _comparar(limpio, referencia, llave, columnas) -> dict:
    m = referencia.merge(limpio, on=llave, how="left", suffixes=("_ref", ""), indicator=True)
    res = {"filas_referencia": len(referencia), "filas_limpias": len(limpio),
           "faltantes": int((m["_merge"] == "left_only").sum())}
    presentes = m[m["_merge"] == "both"]
    for col in columnas:
        a, b = presentes[f"{col}_ref"], presentes[col]
        if pd.api.types.is_float_dtype(a) or pd.api.types.is_float_dtype(b):
            iguales = np.isclose(pd.to_numeric(a), pd.to_numeric(b), atol=0.011) | (a.isna() & b.isna())
        else:
            iguales = (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())
        res[col] = float(np.mean(iguales)) if len(presentes) else np.nan
    return res


def fidelidad(tablas: dict[str, pd.DataFrame], gt: Path) -> pd.DataFrame:
    ref = {n: pd.read_parquet(gt / f"{n}.parquet") for n in
           ("ventas", "detalle_venta", "clientes", "productos", "movimientos_inventario")}
    ref["ventas"]["fecha_hora"] = ref["ventas"]["fecha_hora"].astype(str)
    ventas = tablas["ventas"].assign(fecha_hora=tablas["ventas"]["fecha_hora"].astype(str))
    for t in ("clientes", "productos"):
        for col in ref[t].columns:
            if col.startswith("fecha"):
                ref[t][col] = pd.to_datetime(ref[t][col]).dt.date
    resultados = {
        "ventas": _comparar(ventas, ref["ventas"], "id_venta",
                            ["fecha_hora", "id_sucursal", "id_cliente", "metodo_pago", "total"]),
        "detalle_venta": _comparar(tablas["detalle_venta"], ref["detalle_venta"], "id_detalle",
                                   ["id_producto", "cantidad", "precio_unitario", "subtotal"]),
        "clientes": _comparar(tablas["clientes"], ref["clientes"], "id_cliente", ["email", "telefono", "estado"]),
        "productos": _comparar(tablas["productos"], ref["productos"], "id_producto", ["costo_unitario"]),
        "movimientos_inventario": _comparar(tablas["movimientos_inventario"], ref["movimientos_inventario"],
                                            "id_movimiento", ["cantidad"]),
    }
    return pd.DataFrame(resultados).T


def reporte_markdown(det: pd.DataFrame, fid: pd.DataFrame, resumen: pd.DataFrame) -> str:
    def tabla(df: pd.DataFrame) -> str:
        df = df.copy()
        for col in df.columns:
            if pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].map(lambda x: "—" if pd.isna(x) else (f"{x:.1%}" if x <= 1 else f"{x:,.0f}"))
        encabezado = "| " + " | ".join(map(str, df.columns)) + " |"
        sep = "|" + "---|" * len(df.columns)
        filas = ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
        return "\n".join([encabezado, sep, *filas])

    fid = fid.reset_index(names="tabla")
    for col in ("filas_referencia", "filas_limpias", "faltantes"):
        fid[col] = fid[col].astype(int)
    return "\n\n".join([
        "# Reporte de calidad del ETL",
        "Generado por `python -m datacore.etl --evaluar`. Compara el resultado del ETL contra "
        "`data/ground_truth` (datos limpios y bitácora de defectos inyectados).",
        "## Carga por tabla", tabla(resumen.reset_index(names="tabla")),
        "## Detección de defectos inyectados",
        "*Exhaustividad* = defectos encontrados / inyectados. *Precisión* = aciertos / registros señalados por la regla.",
        tabla(det),
        "## Fidelidad contra la referencia",
        "Fracción de registros cuyo valor final coincide con el original. *faltantes* = registros de la referencia "
        "que no llegaron a la tabla limpia.",
        tabla(fid),
    ]) + "\n"
