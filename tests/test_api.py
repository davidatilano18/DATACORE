"""Pruebas de la API contra la base local; se saltan si no hay base con datos."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

try:
    from datacore.db import engine

    with engine("lector").connect() as _c:
        _HAY_DATOS = _c.execute(text("SELECT count(*) FROM core.ventas")).scalar() > 0 and \
            _c.execute(text("SELECT count(*) FROM ops.modelos WHERE activo")).scalar() > 0
except Exception:
    _HAY_DATOS = False

pytestmark = pytest.mark.skipif(not _HAY_DATOS, reason="sin base de datos con datos y modelo publicado")


@pytest.fixture(scope="module")
def cliente(monkeypatch_module):
    from datacore.api.app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    mp.delenv("DATACORE_API_KEY", raising=False)
    yield mp
    mp.undo()


def test_salud(cliente):
    r = cliente.get("/salud").json()
    assert r["estado"] == "ok" and r["modelo_activo"]["id_modelo"] >= 1


@pytest.mark.parametrize("ruta", ["/kpi/resumen", "/catalogos/sucursales", "/catalogos/categorias",
                                  "/catalogos/productos?buscar=Arroz", "/ventas/sucursales", "/ventas/categorias",
                                  "/productos/abc?clase=A", "/inventario/cobertura?estado=exceso",
                                  "/inventario/estados", "/inventario/desabasto", "/alertas?tipo=RIESGO_DESABASTO",
                                  "/modelo", "/pronosticos", "/calidad/ultima-carga", "/etl/ejecuciones",
                                  "/incidencias/mensuales"])
def test_rutas_responden(cliente, ruta):
    r = cliente.get(ruta)
    assert r.status_code == 200, r.text
    assert r.json()


def test_ventas_diarias_cuadran_con_resumen(cliente):
    dias = cliente.get("/ventas/diarias").json()
    resumen = cliente.get("/kpi/resumen").json()
    assert abs(sum(d["ingreso"] for d in dias) - resumen["ingreso_total"]) < 1


def test_filtros_y_validacion(cliente):
    assert cliente.get("/alertas?tipo=NO_EXISTE").status_code == 422
    assert cliente.get("/productos/abc?clase=Z").status_code == 422
    assert cliente.get("/alertas?limite=0").status_code == 422
    una = cliente.get("/ventas/diarias?desde=2025-12-01&hasta=2025-12-31&id_sucursal=1").json()
    assert len(una) == 31


def test_pronostico_de_un_producto(cliente):
    prod = cliente.get("/alertas?tipo=RIESGO_DESABASTO&limite=1").json()[0]["id_producto"]
    serie = cliente.get(f"/pronosticos?id_producto={prod}").json()
    assert len(serie) == 4
    assert all(s["limite_inferior"] <= s["demanda_estimada"] + 1 for s in serie)


def test_clave_api(monkeypatch):
    from datacore.api.app import app
    monkeypatch.setenv("DATACORE_API_KEY", "secreta")
    with TestClient(app) as c:
        assert c.get("/kpi/resumen").status_code == 401
        assert c.get("/kpi/resumen", headers={"X-API-Key": "secreta"}).status_code == 200
        assert c.get("/salud").status_code == 200  # la salud no exige clave


def test_atender_alerta_inexistente(cliente):
    assert cliente.post("/alertas/999999999/atender").status_code == 404
