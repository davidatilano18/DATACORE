"""Incidencias operativas derivadas de lo que realmente pasó en la simulación.

Las incidencias no son aleatorias: cada desabasto, retraso, merma o
diferencia de conteo reportado corresponde a un evento real de la
simulación. Solo una parte se reporta, como ocurre en la práctica.
"""

import numpy as np
import pandas as pd

from .config import GeneratorConfig


def generar(cfg: GeneratorConfig, rng: np.random.Generator, dias: pd.DatetimeIndex,
            sucursales: pd.DataFrame, productos: pd.DataFrame, proveedores: pd.DataFrame,
            fallas: pd.DataFrame, perdido: np.ndarray, entregas: pd.DataFrame,
            movimientos: pd.DataFrame) -> pd.DataFrame:
    partes = []
    sku = productos.set_index("id_producto")["sku"]

    if len(fallas):
        f = fallas.copy()
        f["tipo"] = "FALLA_SISTEMA"
        f["severidad"] = np.select([f["horas_fuera"] >= 6, f["horas_fuera"] >= 3], ["alta", "media"], "baja")
        f["descripcion"] = "Punto de venta fuera de servicio por " + f["horas_fuera"].astype(str) + " horas"
        f["id_producto"] = pd.NA
        partes.append(f.rename(columns={"fecha": "fecha_reporte"}))

    partes.append(_desabastos(rng, dias, sucursales, productos, sku, perdido))

    prov_por_prod = productos.set_index("id_producto")["id_proveedor"]
    lead = prov_por_prod.map(proveedores.set_index("id_proveedor")["dias_entrega"])
    tarde = entregas[(entregas["dias_retraso"] >= 5) & (rng.random(len(entregas)) < 0.25)].copy()
    tarde["fecha_reporte"] = tarde["fecha_orden"] + pd.to_timedelta(
        tarde["id_producto"].map(lead) + 1, unit="D")
    tarde["tipo"] = "RETRASO_PROVEEDOR"
    tarde["severidad"] = np.where(tarde["dias_retraso"] >= 6, "alta", "media")
    tarde["descripcion"] = ("Orden OC-" + tarde["id_orden"].astype(str).str.zfill(7) + " de "
                            + tarde["id_producto"].map(sku) + " no llegó en la fecha comprometida")
    partes.append(tarde)

    merma = movimientos[(movimientos["tipo"] == "MERMA") & (movimientos["cantidad"] <= -5)]
    merma = merma[rng.random(len(merma)) < 0.5].copy()
    merma["fecha_reporte"] = merma["fecha"]
    merma["tipo"] = "MERCANCIA_DANADA"
    merma["severidad"] = "baja"
    merma["descripcion"] = (merma["cantidad"].abs().astype(str) + " piezas de "
                            + merma["id_producto"].map(sku) + " dañadas o caducadas")
    partes.append(merma)

    ajuste = movimientos[(movimientos["tipo"] == "AJUSTE_CONTEO") & (movimientos["cantidad"].abs() >= 5)]
    ajuste = ajuste[rng.random(len(ajuste)) < 0.7].copy()
    ajuste["fecha_reporte"] = ajuste["fecha"]
    ajuste["tipo"] = "DIFERENCIA_INVENTARIO"
    ajuste["severidad"] = np.where(ajuste["cantidad"].abs() >= 8, "media", "baja")
    ajuste["descripcion"] = ("Conteo físico difiere del sistema en " + ajuste["cantidad"].astype(int).astype(str)
                             + " piezas de " + ajuste["id_producto"].map(sku))
    partes.append(ajuste)

    partes.append(_quejas(rng, dias, sucursales))

    cols = ["fecha_reporte", "id_sucursal", "id_producto", "tipo", "severidad", "descripcion"]
    inc = pd.concat([p[cols] for p in partes if len(p)], ignore_index=True)
    inc = inc[inc["fecha_reporte"] <= dias[-1]]
    inc = inc.sort_values(["fecha_reporte", "id_sucursal"]).reset_index(drop=True)
    inc.insert(0, "id_incidencia", np.arange(1, len(inc) + 1))
    return _estatus(rng, inc, dias[-1])


def _desabastos(rng, dias, sucursales, productos, sku, perdido) -> pd.DataFrame:
    ii, jj, dd = np.nonzero(perdido > 0)
    if len(ii) == 0:
        return pd.DataFrame()
    ev = pd.DataFrame({"i": ii, "j": jj, "d": dd, "u": perdido[ii, jj, dd]})
    ev = ev.sort_values(["i", "j", "d"])
    # Días con faltante separados por 3 días o menos forman un mismo episodio.
    nuevo = (ev["i"].diff() != 0) | (ev["j"].diff() != 0) | (ev["d"].diff() > 3)
    ev["episodio"] = nuevo.cumsum()
    ep = ev.groupby("episodio").agg(i=("i", "first"), j=("j", "first"), d=("d", "first"),
                                     unidades=("u", "sum"), dias=("d", "nunique"))
    ep = ep[(ep["unidades"] >= 5) & (rng.random(len(ep)) < 0.3)]
    out = pd.DataFrame({
        "fecha_reporte": dias[np.minimum(ep["d"].to_numpy() + rng.integers(0, 2, len(ep)), len(dias) - 1)],
        "id_sucursal": sucursales["id_sucursal"].to_numpy()[ep["i"]],
        "id_producto": productos["id_producto"].to_numpy()[ep["j"]],
    })
    out["tipo"] = "DESABASTO"
    out["severidad"] = np.select([ep["unidades"].to_numpy() >= 20, ep["unidades"].to_numpy() >= 6],
                                 ["alta", "media"], "baja")
    out["descripcion"] = "Sin existencia de " + out["id_producto"].map(sku) + "; clientes sin surtir"
    return out


def _quejas(rng, dias, sucursales) -> pd.DataFrame:
    filas = []
    motivos = ["Tiempo de espera en caja", "Producto con precio distinto al de anaquel",
               "Atención del personal", "Producto defectuoso", "Factura no recibida"]
    for suc in sucursales.itertuples():
        abiertos = dias[dias >= suc.fecha_apertura]
        for d in abiertos[rng.random(len(abiertos)) < 0.3 / 30.4]:
            filas.append({"fecha_reporte": d, "id_sucursal": suc.id_sucursal, "id_producto": pd.NA,
                          "tipo": "QUEJA_CLIENTE", "severidad": "baja",
                          "descripcion": f"Queja de cliente: {rng.choice(motivos).lower()}"})
    return pd.DataFrame(filas)


def _estatus(rng, inc: pd.DataFrame, fin: pd.Timestamp) -> pd.DataFrame:
    n = len(inc)
    dias_res = np.select([inc["severidad"] == "alta", inc["severidad"] == "media"],
                         [rng.integers(0, 3, n), rng.integers(1, 7, n)], rng.integers(2, 15, n))
    resolucion = inc["fecha_reporte"] + pd.to_timedelta(dias_res, unit="D")
    abierta = resolucion > fin
    inc["estatus"] = np.where(abierta, rng.choice(["abierta", "en_proceso"], n), "resuelta")
    inc["fecha_resolucion"] = resolucion.where(~abierta)
    inc["id_producto"] = inc["id_producto"].astype("Int64")
    return inc
