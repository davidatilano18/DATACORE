"""Pruebas del módulo de pronóstico sin base de datos (series construidas desde el generador)."""

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from datacore.generator.config import GeneratorConfig
from datacore.generator.run import generar
from datacore.ml import backtest, caracteristicas as car, publicacion
from datacore.ml.datos import construir_series

CFG = replace(GeneratorConfig(), seed=5, fecha_fin=date(2024, 6, 30), n_productos=60, n_clientes=800)


@pytest.fixture(scope="module")
def series(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("ml")
    t = generar(CFG, ruta)
    v = t["ventas"][t["ventas"]["estatus"] == "completada"]
    d = t["detalle_venta"].merge(v[["id_venta", "fecha_hora", "id_sucursal"]])
    semanal = (d.assign(semana=d["fecha_hora"].dt.to_period("W-SUN").dt.start_time)
                .groupby(["semana", "id_sucursal", "id_producto"], as_index=False)
                .agg(unidades=("cantidad", "sum"), ingreso=("subtotal", "sum")))
    m = t["movimientos_inventario"]
    existencia = m.groupby(["id_sucursal", "id_producto", "fecha"], as_index=False)["existencia_resultante"].last()
    prod = t["productos"].merge(t["categorias"].rename(columns={"nombre": "categoria"}))
    prod["dias_entrega"] = prod["id_proveedor"].map(t["proveedores"].set_index("id_proveedor")["dias_entrega"])
    return construir_series(semanal, existencia, prod, t["sucursales"], t["inventario"],
                            pd.Timestamp(CFG.fecha_fin))


def test_sin_fuga_de_informacion(series):
    """Alterar el futuro no debe cambiar las variables de semanas anteriores."""
    h = 2
    corte = series.unidades.index[40]
    original = car.construir(series, h)
    alterada = replace(series, unidades=series.unidades.copy())
    alterada.unidades.loc[alterada.unidades.index >= corte] *= 7
    modificada = car.construir(alterada, h)
    cols = [c for c in car.COLUMNAS_MODELO if not c.endswith("_cat")]
    # Una semana t usa datos hasta t − h; las semanas < corte + h no pueden ver lo alterado.
    sin_cambio = original["semana"] < corte + pd.Timedelta(weeks=h)
    a = original.loc[sin_cambio, cols].reset_index(drop=True)
    b = modificada.loc[modificada["semana"] < corte + pd.Timedelta(weeks=h), cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_modelo_supera_al_ingenuo(series):
    r = backtest.ejecutar(series, horizontes=(1,), semanas_prueba=8, variantes={"gbm": False}, log=lambda _: None)
    m = r["metricas"].set_index(["metodo", "segmento"])
    assert m.loc[("gbm", "todos"), "wape"] < m.loc[("ingenuo", "todos"), "wape"]
    assert abs(m.loc[("gbm", "todos"), "sesgo"]) < 0.25


def test_origen_movil_y_evaluacion_de_alertas(series):
    from datacore.ml import evaluacion_alertas
    r = backtest.ejecutar(series, horizontes=(1,), semanas_prueba=4, origenes=2, variantes={"gbm": False},
                          log=lambda _: None)
    assert len(r["origenes"]) == 2 and r["origenes"][1] - r["origenes"][0] == pd.Timedelta(weeks=4)
    pred = r["predicciones"]
    # Cada bloque solo se predice con un modelo entrenado antes de su inicio.
    assert set(pred["origen"]) == set(r["origenes"])
    assert (pred["semana"] >= pred["origen"]).all()
    assert set(r["metricas_por_origen"]["origen"]) == set(r["origenes"])
    tabla, casos = evaluacion_alertas.evaluar(series, pred, r["dispersion"][1])
    assert casos > 0 and len(tabla) == 3
    assert tabla["precision"].dropna().between(0, 1).all()
    # El umbral p90 es más alto que la media: alerta al menos igual de seguido.
    t = tabla.set_index("regla")
    assert t.loc["modelo (p90)", "alertas"] >= t.loc["modelo (media)", "alertas"]
    assert "Evaluación de las alertas" in evaluacion_alertas.reporte_markdown(tabla, casos)
    assert "por bloque" in backtest.reporte_markdown(r)


def test_pronostico_y_alertas(series):
    pron = publicacion.pronosticar(series, horizontes=(1, 2), dispersion={1: 2.0, 2: 2.0}, log=lambda _: None)
    assert (pron["demanda_estimada"] >= 0).all()
    assert (pron["limite_inferior"] <= pron["demanda_estimada"] + 1e-9).all()
    assert (pron["limite_superior"] >= pron["demanda_estimada"] - 1).all()
    assert set(pron["semana_inicio"]) == {series.unidades.index.max() + pd.Timedelta(weeks=h) for h in (1, 2)}
    al = publicacion.alertas(series, pron)
    assert set(al["tipo"]) <= {"RIESGO_DESABASTO", "EXCESO_INVENTARIO", "SIN_ROTACION"}
    assert not al.duplicated(["id_sucursal", "id_producto"]).any()


def test_sba_en_serie_intermitente():
    s = pd.DataFrame({("a", 1): [0, 0, 4, 0, 0, 0, 4, 0, 0, 0, 4.0]})
    f = car.sba(s, alfa=0.1).iloc[-1, 0]
    # Tamaño 4 cada 4 semanas → cerca de 1 por semana (el primer intervalo observado fue de 3).
    assert 0.9 < f < 1.3
