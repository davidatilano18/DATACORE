"""¿Las alertas de desabasto anticipan faltantes reales?

Para cada semana de origen del backtest se toma la existencia al cierre de
esa semana y el pronóstico hecho en ese momento (horizonte 1), se aplica la
regla de RIESGO_DESABASTO y se revisa si en las dos semanas siguientes el par
tuvo al menos un día sin existencia. Se compara contra una regla sin modelo
(promedio de las últimas 4 semanas) con el mismo horizonte de reposición.
"""

import numpy as np
import pandas as pd
from scipy import stats

from .datos import Series

Z_90 = stats.norm.ppf(0.9)


def _clasificacion(alerta: np.ndarray, evento: np.ndarray) -> dict:
    vp = int((alerta & evento).sum())
    fp = int((alerta & ~evento).sum())
    fn = int((~alerta & evento).sum())
    precision = vp / (vp + fp) if vp + fp else np.nan
    exhaustividad = vp / (vp + fn) if vp + fn else np.nan
    f1 = 2 * precision * exhaustividad / (precision + exhaustividad) if vp else 0.0
    return {"alertas": vp + fp, "faltantes_reales": vp + fn, "aciertos": vp, "precision": precision,
            "exhaustividad": exhaustividad, "f1": f1}


def evaluar(series: Series, predicciones: pd.DataFrame, dispersion: float) -> tuple[pd.DataFrame, int]:
    """`predicciones`: salida del backtest (horizonte 1) con columnas semana, id_sucursal, id_producto, gbm, media_4."""
    p = predicciones[predicciones["horizonte"] == 1].copy()
    p["origen"] = p["semana"] - pd.Timedelta(weeks=1)
    clave = lambda df, col: pd.MultiIndex.from_arrays([df[col], df["id_sucursal"], df["id_producto"]])

    def apilado(ancho: pd.DataFrame) -> pd.Series:
        s = ancho.stack(level=[0, 1], future_stack=True)
        s.index.names = ["semana", "id_sucursal", "id_producto"]
        return s

    existencia = apilado(series.existencia)
    agotado = apilado(series.agotado)
    p["existencia"] = existencia.reindex(clave(p, "origen")).to_numpy()
    siguiente = agotado.reindex(clave(p.assign(s2=p["semana"] + pd.Timedelta(weeks=1)), "s2")).to_numpy()
    p["evento"] = (np.nan_to_num(agotado.reindex(clave(p, "semana")).to_numpy()) > 0) | (np.nan_to_num(siguiente) > 0)
    p = p.dropna(subset=["existencia"])
    p = p[p["existencia"] > 0]  # si ya está en cero el faltante es un hecho, no una predicción

    dias = p["id_producto"].map(series.productos.set_index("id_producto")["dias_entrega"]).to_numpy() + 7
    filas = []
    for nombre, col, con_intervalo in (("modelo (p90)", "gbm", True), ("modelo (media)", "gbm", False),
                                       ("promedio 4 semanas", "media_4", False)):
        mu = np.clip(p[col].to_numpy(), 0, None) * dias / 7
        umbral = mu + Z_90 * np.sqrt(mu + mu ** 2 / dispersion) if con_intervalo else mu
        alerta = p["existencia"].to_numpy() < umbral
        filas.append({"regla": nombre, **_clasificacion(alerta, p["evento"].to_numpy())})
    return pd.DataFrame(filas), len(p)


def reporte_markdown(tabla: pd.DataFrame, n_casos: int) -> str:
    filas = ["| regla | alertas | faltantes reales | aciertos | precisión | exhaustividad | F1 |",
             "|---|---|---|---|---|---|---|"]
    for r in tabla.itertuples(index=False):
        filas.append(f"| {r.regla} | {r.alertas:,} | {r.faltantes_reales:,} | {r.aciertos:,} | {r.precision:.1%} | "
                     f"{r.exhaustividad:.1%} | {r.f1:.3f} |")
    return ("## Evaluación de las alertas de desabasto\n\n"
            f"{n_casos:,} casos (par × semana de origen) en el periodo de prueba, con existencia positiva al cierre. "
            "Un *faltante real* es al menos un día sin existencia en las dos semanas siguientes. La alerta se dispara "
            "si la existencia es menor que la demanda esperada durante el tiempo de entrega + 7 días.\n\n"
            + "\n".join(filas) + "\n")
