"""Entrenamiento final, pronóstico de las próximas semanas y alertas de inventario.

Escribe en ops.modelos (versión y métricas del backtest), ops.predicciones_demanda
(pronóstico con intervalo del 80 %) y ops.alertas_inventario.
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import Engine, text

from . import caracteristicas as car
from .datos import Series
from .modelos import entrenar

Z_90 = stats.norm.ppf(0.9)
DIAS_EXCESO = 180


def pronosticar(series: Series, horizontes=(1, 2, 3, 4), dispersion: dict[int, float] | None = None,
                excluir_censuradas: bool = False, log=print) -> pd.DataFrame:
    ultima = series.unidades.index.max()
    salida = []
    for h in horizontes:
        entreno = car.construir(series, h)
        if excluir_censuradas:
            entreno["agotado_objetivo"] = car._apilar(series.agotado, "a").reindex(
                pd.MultiIndex.from_frame(entreno[["semana", "id_sucursal", "id_producto"]])).to_numpy()
        modelo = entrenar(entreno, excluir_censuradas=excluir_censuradas)
        objetivo = pd.DatetimeIndex([ultima + pd.Timedelta(weeks=h)])
        futuro = car.construir(series, h, semanas_objetivo=objetivo)
        mu = np.clip(modelo.predict(futuro[car.COLUMNAS_MODELO]), 0, None)
        k = (dispersion or {}).get(h, 1.0)
        # Binomial negativa con media μ y dispersión k: intervalo del 10 % al 90 %.
        p = k / (k + np.maximum(mu, 1e-9))
        salida.append(pd.DataFrame({
            "id_sucursal": futuro["id_sucursal"].to_numpy(), "id_producto": futuro["id_producto"].to_numpy(),
            "semana_inicio": objetivo[0], "horizonte": h, "demanda_estimada": mu.round(2),
            "limite_inferior": stats.nbinom.ppf(0.1, k, p), "limite_superior": stats.nbinom.ppf(0.9, k, p),
            "_dispersion": k,
        }))
        log(f"pronóstico h={h} → semana {objetivo[0].date()}: {len(futuro):,} pares, "
            f"{mu.sum():,.0f} unidades estimadas")
    pron = pd.concat(salida, ignore_index=True)
    activos = series.productos.loc[series.productos["activo"], "id_producto"]
    return pron[pron["id_producto"].isin(activos)].reset_index(drop=True)


def alertas(series: Series, pron: pd.DataFrame) -> pd.DataFrame:
    """Compara la existencia actual contra la demanda esperada en el tiempo de reposición."""
    inv = series.inventario[["id_sucursal", "id_producto", "existencia"]]
    prod = series.productos.set_index("id_producto")
    semanal = pron.pivot_table(index=["id_sucursal", "id_producto"], columns="horizonte", values="demanda_estimada")
    k = pron.groupby(["id_sucursal", "id_producto"])["_dispersion"].first()
    df = inv.join(semanal, on=["id_sucursal", "id_producto"], how="inner")
    df["media_semanal"] = semanal.reindex(pd.MultiIndex.from_frame(df[["id_sucursal", "id_producto"]])).mean(axis=1).to_numpy()
    df["dias_entrega"] = df["id_producto"].map(prod["dias_entrega"])

    # Demanda durante entrega + una semana de revisión, prorrateando los pronósticos semanales.
    dias_horizonte = df["dias_entrega"] + 7
    mu_h = np.zeros(len(df))
    var_h = np.zeros(len(df))
    kk = k.reindex(pd.MultiIndex.from_frame(df[["id_sucursal", "id_producto"]])).to_numpy()
    for h in sorted(semanal.columns):
        fraccion = np.clip(dias_horizonte - 7 * (h - 1), 0, 7) / 7
        mu_w = df[h].fillna(0).to_numpy() * fraccion
        mu_h += mu_w
        var_h += mu_w + mu_w ** 2 / kk
    df["demanda_horizonte_p90"] = mu_h + Z_90 * np.sqrt(var_h)
    df["cobertura_dias"] = df["existencia"] / np.where(df["media_semanal"] > 0, df["media_semanal"] / 7, np.nan)

    ultimas_13 = series.unidades.iloc[-13:].sum()
    df["unidades_13_semanas"] = ultimas_13.reindex(pd.MultiIndex.from_frame(df[["id_sucursal", "id_producto"]])).to_numpy()

    sin_rotacion = (df["existencia"] > 0) & (df["unidades_13_semanas"] == 0) & (df["media_semanal"] < 0.25)
    riesgo = ~sin_rotacion & (df["existencia"] < df["demanda_horizonte_p90"])
    exceso = ~sin_rotacion & ~riesgo & (df["cobertura_dias"] > DIAS_EXCESO)
    df["tipo"] = np.select([riesgo, exceso, sin_rotacion], ["RIESGO_DESABASTO", "EXCESO_INVENTARIO", "SIN_ROTACION"], "")
    out = df[df["tipo"] != ""]
    return pd.DataFrame({
        "id_sucursal": out["id_sucursal"], "id_producto": out["id_producto"], "tipo": out["tipo"],
        "existencia": out["existencia"], "demanda_estimada": out["demanda_horizonte_p90"].round(2),
        "dias_cobertura": out["cobertura_dias"].round(1).clip(upper=9999),
    }).reset_index(drop=True)


def guardar(engine: Engine, metricas: dict, fecha_corte: pd.Timestamp, pron: pd.DataFrame,
            alertas_df: pd.DataFrame, algoritmo: str) -> int:
    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    with engine.begin() as c:
        c.execute(text("UPDATE ops.modelos SET activo = FALSE WHERE nombre = 'demanda_semanal'"))
        id_modelo = c.execute(text(
            "INSERT INTO ops.modelos (nombre, version, algoritmo, fecha_corte_datos, metricas, activo) "
            "VALUES ('demanda_semanal', :v, :a, :f, CAST(:m AS jsonb), TRUE) RETURNING id_modelo"),
            {"v": version, "a": algoritmo, "f": fecha_corte.date(), "m": json.dumps(metricas)}).scalar()
        filas = pron.assign(id_modelo=id_modelo)[["id_modelo", "id_sucursal", "id_producto", "semana_inicio",
                                                  "demanda_estimada", "limite_inferior", "limite_superior"]]
        filas.to_sql("predicciones_demanda", c, schema="ops", if_exists="append", index=False, chunksize=5000)
        c.execute(text("DELETE FROM ops.alertas_inventario WHERE NOT atendida"))
        alertas_df.to_sql("alertas_inventario", c, schema="ops", if_exists="append", index=False, chunksize=5000)
    return id_modelo
