"""Pruebas de la mejora de alertas con casos sintéticos (no requieren base)."""

import numpy as np
import pandas as pd

from datacore.ml import alertas_segmentadas as al


def _casos(n_por_bloque=400, bloques=("2024-07-01", "2024-09-30", "2024-12-30", "2025-03-31"), semilla=1):
    rng = np.random.default_rng(semilla)
    filas = []
    for b in bloques:
        mu = rng.uniform(2, 20, n_por_bloque)
        existencia = rng.uniform(1, 30, n_por_bloque)
        agotado = rng.uniform(0, 0.6, n_por_bloque)
        # Faltante si la existencia no alcanza la demanda real, que es mayor cuanto más se agotó el par.
        demanda_real = rng.poisson(mu / (1 - agotado))
        filas.append(pd.DataFrame({
            "origen": pd.Timestamp(b), "semana": pd.Timestamp(b), "id_sucursal": 1, "id_producto": np.arange(n_por_bloque),
            "clase_abc": rng.choice(["A", "B", "C"], n_por_bloque), "entrega": "media",
            "existencia": existencia, "mu": mu, "var": mu + mu ** 2 / 2.3, "mu_promedio_4": mu * 0.9,
            "factor_censura": al.factor_censura(agotado), "evento": existencia < demanda_real}))
    c = pd.concat(filas, ignore_index=True)
    c["segmento"] = c["clase_abc"] + "·" + c["entrega"]
    return c


def test_grupos_de_entrega():
    assert list(al.grupo_entrega([2, 4, 5, 7, 8, 10])) == ["corta", "corta", "media", "media", "larga", "larga"]


def test_factor_de_censura_acotado():
    f = al.factor_censura(np.array([0.0, 0.5, 0.9, np.nan]), tope=2.0)
    assert list(f) == [1.0, 2.0, 2.0, 1.0]


def test_umbral_mas_alto_alerta_mas_seguido():
    c = _casos()
    assert al.alerta(c, 0.9).sum() >= al.alerta(c, "media").sum()
    assert al.alerta(c, "media", censura=True).sum() >= al.alerta(c, "media").sum()


def test_evaluacion_anidada_no_usa_el_bloque_evaluado():
    c = _casos()
    total, por_bloque, elegidas = al.evaluar_anidado(c, inicio=pd.Timestamp("2024-12-30"))
    assert set(por_bloque["bloque"]) == {pd.Timestamp("2024-12-30"), pd.Timestamp("2025-03-31")}
    assert set(total["regla"]) == set(al.REGLAS)
    # Si se cambian los eventos del bloque evaluado, las reglas elegidas para ese bloque no cambian.
    alterado = c.copy()
    ultimo = alterado["origen"] == pd.Timestamp("2025-03-31")
    alterado.loc[ultimo, "evento"] = ~alterado.loc[ultimo, "evento"]
    _, _, elegidas_alt = al.evaluar_anidado(alterado, inicio=pd.Timestamp("2024-12-30"))
    assert elegidas_alt[pd.Timestamp("2025-03-31")] == elegidas[pd.Timestamp("2025-03-31")]


def test_decision_con_bloques_previos_prefiere_la_correccion_cuando_hay_censura():
    regla, tabla = al.decidir(_casos(), hasta=pd.Timestamp("2024-12-30"))
    assert regla in al.FIJAS
    assert tabla.set_index("regla").loc["modelo, media + censura", "f1"] >= \
        tabla.set_index("regla").loc["modelo, media", "f1"]


def test_seccion_se_reemplaza_sin_tocar_el_resto(tmp_path):
    ruta = tmp_path / "backtest.md"
    ruta.write_text("# Reporte\n\ntexto previo\n", encoding="utf-8")
    seccion = "<!-- inicio: alertas segmentadas -->\nv1\n<!-- fin: alertas segmentadas -->"
    al.insertar_en_reporte(ruta, seccion)
    al.insertar_en_reporte(ruta, seccion.replace("v1", "v2"))
    texto = ruta.read_text(encoding="utf-8")
    assert "texto previo" in texto and "v2" in texto and "v1" not in texto
    assert texto.count("inicio: alertas segmentadas") == 1
