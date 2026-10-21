"""Modelo global de demanda semanal, baselines y métricas."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .caracteristicas import COLUMNAS_MODELO

BASELINES = {
    "ingenuo": "lag_1",            # lo mismo que la última semana observada
    "media_movil_8": "media_8",
    "estacional": "lag_52",        # misma semana del año pasado (si no hay, media 8)
    "sba": "sba",                  # Syntetos-Boylan para demanda intermitente
}


def nuevo_modelo(semilla: int = 42) -> HistGradientBoostingRegressor:
    # Pérdida Poisson: la demanda son conteos, con muchos ceros y varianza que crece con la media.
    return HistGradientBoostingRegressor(loss="poisson", learning_rate=0.06, max_iter=500, max_leaf_nodes=63,
                                         min_samples_leaf=80, l2_regularization=1.0, early_stopping=True,
                                         validation_fraction=0.1, n_iter_no_change=25, random_state=semilla,
                                         categorical_features="from_dtype")


def entrenar(df: pd.DataFrame, excluir_censuradas: bool = True, semilla: int = 42) -> HistGradientBoostingRegressor:
    """`excluir_censuradas`: no aprender de semanas donde el par pasó 3 días o más sin existencia,
    porque ahí la venta observada subestima la demanda."""
    if excluir_censuradas and "agotado_objetivo" in df:
        df = df[~(df["agotado_objetivo"] >= 3 / 7)]
    modelo = nuevo_modelo(semilla)
    modelo.fit(df[COLUMNAS_MODELO], df["y"])
    return modelo


def predecir_baselines(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({nombre: df[col] for nombre, col in BASELINES.items()})
    out["estacional"] = out["estacional"].fillna(df["media_8"])
    return out.fillna(0.0)


def metricas(y: pd.Series, pred: pd.Series) -> dict:
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    total = y.sum()
    return {
        "wape": float(np.abs(y - pred).sum() / total) if total else np.nan,
        "sesgo": float((pred - y).sum() / total) if total else np.nan,
        "mae": float(np.abs(y - pred).mean()),
        "rmse": float(np.sqrt(((y - pred) ** 2).mean())),
    }


def dispersion_binomial_negativa(y: pd.Series, mu: pd.Series) -> float:
    """Estima k en Var = μ + μ²/k (método de momentos) para construir intervalos."""
    y, mu = np.asarray(y, float), np.clip(np.asarray(mu, float), 1e-6, None)
    exceso = ((y - mu) ** 2 - mu).sum()
    return float(np.clip((mu ** 2).sum() / exceso, 0.05, 1e3)) if exceso > 0 else 1e3
