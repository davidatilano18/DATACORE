"""Recomendación de pedido de las alertas de desabasto (función pura, no requiere base)."""

import numpy as np
import pandas as pd

from datacore.ml.publicacion import recomendacion


def test_cantidad_lleva_al_nivel_objetivo_y_fecha_respeta_la_entrega():
    corte = pd.Timestamp("2025-12-31")
    r = recomendacion(existencia=np.array([10.0, 0.0, 40.0]), mu=np.array([20.0, 20.0, 20.0]),
                      var=np.array([60.0, 60.0, 60.0]), dias_horizonte=np.array([10, 10, 10]),
                      dias_entrega=np.array([3, 3, 3]), fecha_corte=corte)
    assert (r["nivel_objetivo"] > 20).all()                       # demanda esperada + stock de seguridad
    assert (np.array([10, 0, 40]) + r["cantidad_sugerida"] >= r["nivel_objetivo"]).all()
    assert r["cantidad_sugerida"].min() >= 1
    # 10 unidades a 2 por día duran 5 días; con 3 de entrega hay que pedir a más tardar 2 días después del corte.
    assert r.loc[0, "fecha_limite"] == (corte + pd.Timedelta(days=2)).date()
    # Sin existencia ya no da tiempo: el día siguiente al corte.
    assert r.loc[1, "fecha_limite"] == (corte + pd.Timedelta(days=1)).date()
    assert r.loc[2, "fecha_limite"] > r.loc[0, "fecha_limite"]


def test_mas_incertidumbre_pide_mas():
    corte = pd.Timestamp("2025-12-31")
    base = dict(existencia=np.array([5.0]), mu=np.array([20.0]), dias_horizonte=np.array([10]),
                dias_entrega=np.array([3]), fecha_corte=corte)
    poca = recomendacion(var=np.array([25.0]), **base)
    mucha = recomendacion(var=np.array([200.0]), **base)
    assert mucha.loc[0, "cantidad_sugerida"] > poca.loc[0, "cantidad_sugerida"]
