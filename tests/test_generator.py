"""Pruebas de consistencia del dataset generado (sobre una versión reducida)."""

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from datacore.generator.config import GeneratorConfig
from datacore.generator.run import generar

CFG = replace(GeneratorConfig(), seed=7, fecha_fin=date(2023, 12, 31), n_productos=120, n_clientes=1500)


@pytest.fixture(scope="session")
def salida(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("data")
    generar(CFG, ruta)
    return ruta


@pytest.fixture(scope="session")
def gt(salida):
    return {p.stem: pd.read_parquet(p) for p in (salida / "ground_truth").glob("*.parquet")}


def test_llaves_foraneas(gt):
    assert gt["ventas"]["id_sucursal"].isin(gt["sucursales"]["id_sucursal"]).all()
    clientes = gt["ventas"]["id_cliente"].dropna()
    assert clientes.isin(gt["clientes"]["id_cliente"]).all()
    assert gt["detalle_venta"]["id_venta"].isin(gt["ventas"]["id_venta"]).all()
    assert gt["detalle_venta"]["id_producto"].isin(gt["productos"]["id_producto"]).all()
    assert gt["productos"]["id_proveedor"].isin(gt["proveedores"]["id_proveedor"]).all()
    assert gt["ventas"]["id_venta"].isin(gt["detalle_venta"]["id_venta"]).all(), "ticket sin renglones"


def test_total_igual_a_suma_de_renglones(gt):
    suma = gt["detalle_venta"].groupby("id_venta")["subtotal"].sum()
    total = gt["ventas"].set_index("id_venta")["total"]
    assert np.allclose(total.loc[suma.index], suma, atol=0.01)


def test_cliente_registrado_antes_de_comprar(gt):
    v = gt["ventas"].dropna(subset=["id_cliente"])
    registro = v["id_cliente"].map(gt["clientes"].set_index("id_cliente")["fecha_registro"])
    # Se asignan clientes registrados al inicio del mes de la compra.
    assert (registro <= v["fecha_hora"]).all()


def test_ventas_dentro_de_vigencia(gt):
    d = gt["detalle_venta"].merge(gt["ventas"][["id_venta", "fecha_hora", "id_sucursal"]])
    alta = d["id_producto"].map(gt["productos"].set_index("id_producto")["fecha_alta"])
    baja = d["id_producto"].map(gt["parametros_productos"].set_index("id_producto")["_fecha_baja"])
    apertura = d["id_sucursal"].map(gt["sucursales"].set_index("id_sucursal")["fecha_apertura"])
    assert (d["fecha_hora"] >= alta).all()
    assert (baja.isna() | (d["fecha_hora"] < baja)).all()
    assert (d["fecha_hora"] >= apertura).all()


def test_inventario_cuadra_con_movimientos(gt):
    m = gt["movimientos_inventario"]
    assert (m["existencia_resultante"] >= 0).all()
    acumulado = m.groupby(["id_sucursal", "id_producto"])["cantidad"].cumsum()
    assert (acumulado == m["existencia_resultante"]).all()
    final = m.groupby(["id_sucursal", "id_producto"])["existencia_resultante"].last()
    inv = gt["inventario"].set_index(["id_sucursal", "id_producto"])["existencia"]
    assert (inv.loc[final.index] == final).all()


def test_salidas_de_inventario_igual_a_ventas(gt):
    d = gt["detalle_venta"].merge(gt["ventas"][["id_venta", "fecha_hora", "id_sucursal", "estatus"]])
    d = d[d["estatus"] == "completada"]
    vendido = d.groupby([d["fecha_hora"].dt.normalize(), "id_sucursal", "id_producto"])["cantidad"].sum()
    m = gt["movimientos_inventario"]
    salidas = -m[m["tipo"] == "SALIDA_VENTA"].groupby(["fecha", "id_sucursal", "id_producto"])["cantidad"].sum()
    vendido.index.names = salidas.index.names
    pd.testing.assert_series_equal(vendido.sort_index(), salidas.sort_index(), check_names=False)


def test_archivos_crudos_y_defectos(salida):
    raw = salida / "raw"
    for archivo in ("ventas/ventas_2023.csv", "ventas/detalle_venta_2023.csv", "catalogos/productos.xlsx",
                    "catalogos/proveedores.xlsx", "catalogos/sucursales.csv", "clientes/clientes.csv",
                    "inventario/inventario_actual.csv", "operacion/incidencias.csv"):
        assert (raw / archivo).exists(), archivo
    clientes = pd.read_csv(raw / "clientes" / "clientes.csv", sep=";", encoding="cp1252")
    assert len(clientes) > CFG.n_clientes  # incluye casi-duplicados
    bitacora = pd.read_csv(salida / "ground_truth" / "defectos_inyectados.csv")
    faltantes = set(CFG.defectos) - set(bitacora["tipo_defecto"])
    assert not faltantes, f"defectos sin inyectar: {faltantes}"


def test_reproducible(tmp_path, gt):
    cfg = replace(CFG, fecha_fin=date(2023, 3, 31))
    a = generar(cfg, tmp_path / "a")
    b = generar(cfg, tmp_path / "b")
    pd.testing.assert_frame_equal(a["detalle_venta"], b["detalle_venta"])
    pd.testing.assert_frame_equal(a["clientes"], b["clientes"])
