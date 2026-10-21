"""Lectura de `core` y construcción de las series semanales por sucursal-producto.

Las series se manejan en formato ancho (filas = semanas, columnas = pares
sucursal-producto) para calcular rezagos y ventanas de forma vectorizada.
Una celda es NaN cuando el par aún no existía (sucursal sin abrir o producto
sin lanzar); 0 significa que existía y no vendió.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import Engine

SQL_SEMANAL = """
SELECT date_trunc('week', v.fecha_hora)::date AS semana, v.id_sucursal, d.id_producto,
       sum(d.cantidad) AS unidades, sum(d.subtotal) AS ingreso
FROM core.detalle_venta d JOIN core.ventas v USING (id_venta)
WHERE v.estatus = 'completada'
GROUP BY 1, 2, 3
"""

# Existencia al cierre de cada día con movimiento (el último movimiento del día manda).
SQL_EXISTENCIA = """
SELECT DISTINCT ON (id_sucursal, id_producto, fecha) id_sucursal, id_producto, fecha, existencia_resultante
FROM core.movimientos_inventario
ORDER BY id_sucursal, id_producto, fecha, id_movimiento DESC
"""

SQL_PRODUCTOS = """
SELECT p.id_producto, p.sku, p.nombre, p.id_categoria, c.nombre AS categoria, p.fecha_alta, p.activo,
       p.precio_unitario, pr.dias_entrega
FROM core.productos p JOIN core.categorias c USING (id_categoria) JOIN core.proveedores pr USING (id_proveedor)
"""


@dataclass
class Series:
    unidades: pd.DataFrame        # (semanas × pares) unidades vendidas
    precio: pd.DataFrame          # precio promedio cobrado, arrastrado hacia adelante
    agotado: pd.DataFrame         # fracción de días de la semana con existencia 0
    existencia: pd.DataFrame      # existencia al cierre del domingo de cada semana
    inicio_par: pd.Series         # primera semana completa de vida de cada par
    sucursales: pd.DataFrame
    productos: pd.DataFrame
    inventario: pd.DataFrame
    fecha_corte: pd.Timestamp     # último día con datos


def cargar(engine: Engine) -> Series:
    with engine.connect() as c:
        semanal = pd.read_sql(SQL_SEMANAL, c, parse_dates=["semana"])
        existencia = pd.read_sql(SQL_EXISTENCIA, c, parse_dates=["fecha"])
        productos = pd.read_sql(SQL_PRODUCTOS, c, parse_dates=["fecha_alta"])
        sucursales = pd.read_sql("SELECT * FROM core.sucursales", c, parse_dates=["fecha_apertura"])
        inventario = pd.read_sql("SELECT * FROM core.inventario", c)
        fecha_corte = pd.Timestamp(pd.read_sql("SELECT max(fecha_hora)::date AS f FROM core.ventas", c)["f"].iat[0])
    return construir_series(semanal, existencia, productos, sucursales, inventario, fecha_corte)


def construir_series(semanal, existencia, productos, sucursales, inventario, fecha_corte) -> Series:
    inicio_datos = existencia["fecha"].min()
    # Solo semanas completas (lunes a domingo) dentro del periodo con datos.
    primera = inicio_datos + pd.offsets.Week(weekday=0) if inicio_datos.dayofweek else inicio_datos
    ultima = fecha_corte - pd.Timedelta(days=6) - pd.offsets.Week(weekday=0) if fecha_corte.dayofweek != 6 \
        else fecha_corte - pd.Timedelta(days=6)
    semanas = pd.date_range(primera, ultima, freq="W-MON")

    # Existencia diaria por par: se arrastra el último valor a los días sin movimiento.
    diaria = existencia.pivot_table(index="fecha", columns=["id_sucursal", "id_producto"],
                                    values="existencia_resultante", aggfunc="last")
    diaria = diaria.reindex(pd.date_range(inicio_datos, fecha_corte, freq="D")).ffill()
    pares = diaria.columns
    inicio_dia = diaria.notna().idxmax()
    agotado = (diaria == 0).astype(float).where(diaria.notna())
    agotado = agotado.resample("W-MON", label="left", closed="left").mean().reindex(semanas)
    cierre = diaria.resample("W-MON", label="left", closed="left").last().reindex(semanas)

    inicio_par = inicio_dia.map(lambda d: d if d.dayofweek == 0 else d + pd.offsets.Week(weekday=0))
    vivo = pd.DataFrame(semanas.to_numpy()[:, None] >= inicio_par.to_numpy()[None, :], index=semanas, columns=pares)

    unidades = semanal.pivot_table(index="semana", columns=["id_sucursal", "id_producto"], values="unidades",
                                   aggfunc="sum").reindex(index=semanas, columns=pares)
    ingreso = semanal.pivot_table(index="semana", columns=["id_sucursal", "id_producto"], values="ingreso",
                                  aggfunc="sum").reindex(index=semanas, columns=pares)
    precio = (ingreso / unidades).ffill()
    unidades = unidades.fillna(0).where(vivo)
    return Series(unidades=unidades, precio=precio, agotado=agotado.where(vivo), existencia=cierre.where(vivo),
                  inicio_par=inicio_par,
                  sucursales=sucursales, productos=productos, inventario=inventario, fecha_corte=fecha_corte)


def demanda_real(series: Series, demanda_perdida: pd.DataFrame) -> pd.DataFrame:
    """Ventas + demanda no surtida (solo existe en la simulación: ground_truth/demanda_perdida)."""
    perdida = demanda_perdida.assign(semana=demanda_perdida["fecha"].dt.to_period("W-SUN").dt.start_time)
    perdida = perdida.pivot_table(index="semana", columns=["id_sucursal", "id_producto"], values="unidades",
                                  aggfunc="sum").reindex(index=series.unidades.index, columns=series.unidades.columns)
    return series.unidades + perdida.fillna(0).where(series.unidades.notna())


def clases_abc(series: Series, hasta: pd.Timestamp) -> pd.Series:
    """Clase ABC por par según ingreso aproximado (unidades × precio) antes de `hasta`."""
    previo = series.unidades.index < hasta
    ingreso = (series.unidades[previo] * series.precio[previo].fillna(0)).sum()
    orden = ingreso.sort_values(ascending=False)
    acumulado = orden.cumsum() / max(orden.sum(), 1e-9)
    clase = pd.Series(np.select([acumulado.shift(fill_value=0) < 0.8, acumulado.shift(fill_value=0) < 0.95],
                                ["A", "B"], "C"), index=orden.index)
    return clase.reindex(series.unidades.columns)
