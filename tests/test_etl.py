"""Pruebas del ETL contra un dataset reducido con defectos inyectados."""

from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from datacore.etl.evaluacion import deteccion, fidelidad
from datacore.etl.extraccion import extraer
from datacore.etl.pipeline import transformar
from datacore.generator.config import GeneratorConfig
from datacore.generator.run import generar

# Tasas de defecto altas para que cada tipo aparezca varias veces aun con pocos datos.
CFG = replace(GeneratorConfig(), seed=11, fecha_fin=date(2023, 12, 31), n_productos=120, n_clientes=1500)
CFG = replace(CFG, defectos={k: max(v, 0.02) for k, v in CFG.defectos.items()})


@pytest.fixture(scope="module")
def resultado(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("etl")
    generar(CFG, ruta)
    tablas, hallazgos = transformar(extraer(ruta / "raw"))
    bitacora = pd.read_csv(ruta / "ground_truth" / "defectos_inyectados.csv", dtype=str)
    return {"tablas": tablas, "hallazgos": hallazgos, "bitacora": bitacora, "gt": ruta / "ground_truth"}


def test_detecta_cada_tipo_de_defecto(resultado):
    det = deteccion(resultado["hallazgos"], resultado["bitacora"]).set_index("defecto")
    # Un correo sin "@" cuyo dueño también perdió el teléfono no siempre es recuperable.
    assert (det["exhaustividad"] >= 0.95).all(), det[det["exhaustividad"] < 0.95]
    assert (det["precision"] >= 0.99).all(), det[det["precision"] < 0.99]


def test_tablas_sin_duplicados_y_con_llaves_validas(resultado):
    t = resultado["tablas"]
    assert t["ventas"]["id_venta"].is_unique
    assert t["detalle_venta"]["id_detalle"].is_unique
    assert t["clientes"]["id_cliente"].is_unique
    assert t["detalle_venta"]["id_venta"].isin(t["ventas"]["id_venta"]).all()
    assert t["detalle_venta"]["id_producto"].isin(t["productos"]["id_producto"]).all()
    assert t["ventas"]["id_cliente"].dropna().isin(t["clientes"]["id_cliente"]).all()
    assert (t["detalle_venta"]["cantidad"] > 0).all()
    assert (t["productos"]["costo_unitario"] < t["productos"]["precio_unitario"]).all()
    assert (t["movimientos_inventario"]["cantidad"] != 0).all()


def test_total_cuadra_con_detalle(resultado):
    t = resultado["tablas"]
    suma = t["detalle_venta"].groupby("id_venta")["subtotal"].sum()
    total = t["ventas"].set_index("id_venta")["total"]
    assert (total.loc[suma.index] - suma).abs().max() < 0.011


def test_fidelidad_contra_referencia(resultado):
    fid = fidelidad(resultado["tablas"], resultado["gt"])
    # Solo se pierden los renglones con SKU inexistente y los tickets que quedaron vacíos por ello.
    assert fid.loc["detalle_venta", "faltantes"] == (resultado["bitacora"]["tipo_defecto"]
                                                       == "detalle_producto_inexistente").sum()
    assert fid.loc["detalle_venta", "precio_unitario"] == 1.0
    assert fid.loc["detalle_venta", "cantidad"] == 1.0
    assert fid.loc["ventas", "id_sucursal"] == 1.0
    assert fid.loc["ventas", "id_cliente"] == 1.0
    assert fid.loc["movimientos_inventario", "cantidad"] == 1.0
    assert fid.loc["clientes", "estado"] == 1.0
