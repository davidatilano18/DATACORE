"""Pruebas del detector causal y de su API."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from datacore.ml.anomalias import detectar, evaluar, festivos


def test_detector_causal_calendario_y_apertura():
    fechas = pd.date_range("2024-01-01", "2024-12-31")
    valores = 100 + fechas.dayofweek.to_numpy()*5 + np.random.default_rng(42).normal(0, 2, len(fechas))
    diaria = pd.DataFrame(dict(fecha=fechas, id_sucursal=1, ingreso=valores*10, tickets=valores))
    sucursales = pd.DataFrame(dict(id_sucursal=[1], fecha_apertura=[pd.Timestamp("2024-01-01")]))
    caidas = pd.to_datetime(["2024-06-11", "2024-08-13"])
    diaria.loc[diaria.fecha.isin(caidas), ["ingreso", "tickets"]] *= 0.1
    diaria.loc[diaria.fecha == "2024-09-12", ["ingreso", "tickets"]] *= 4
    diaria.loc[festivos(fechas), ["ingreso", "tickets"]] *= 0.01
    resultado = detectar(diaria, sucursales)
    assert set(caidas) <= set(resultado.loc[resultado.tipo == "caida", "fecha"])
    assert pd.Timestamp("2024-09-12") in set(resultado.loc[resultado.tipo == "pico", "fecha"])
    assert not festivos(resultado.fecha).any()
    assert resultado.fecha.min() >= pd.Timestamp("2024-03-01")
    corte = pd.Timestamp("2024-08-01")
    diaria.loc[diaria.fecha >= corte, ["ingreso", "tickets"]] *= 50
    posterior = detectar(diaria, sucursales)
    pd.testing.assert_frame_equal(resultado[resultado.fecha < corte].reset_index(drop=True),
                                  posterior[posterior.fecha < corte].reset_index(drop=True))
    sucursales.fecha_apertura = pd.Timestamp("2024-07-01")
    assert (detectar(diaria, sucursales).fecha >= pd.Timestamp("2024-08-12")).all()


def test_evaluacion_sin_duplicar_metricas():
    detectadas = pd.DataFrame(dict(id_sucursal=[1, 1, 1], fecha=["2024-06-01"]*2 + ["2024-06-02"],
                                   tipo=["caida"]*3))
    fallas = pd.DataFrame(dict(id_sucursal=[1, 1], fecha=["2024-06-01", "2024-06-04"], horas_fuera=[2, 8]))
    r = evaluar(detectadas, fallas).iloc[0]
    assert r.precision == r.exhaustividad == r.f1 == 0.5
    assert evaluar(detectadas.iloc[:0], fallas).iloc[0].f1 == 0


def test_ruta_anomalias(monkeypatch):
    from datacore.db import engine
    try:
        with engine("lector").connect() as c:
            c.execute(text("SELECT 1 FROM ops.anomalias LIMIT 1"))
    except Exception:
        pytest.skip("sin BD con esquema de anomalías")
    from datacore.api.app import app
    monkeypatch.setenv("DATACORE_API_KEY", "prueba")
    with TestClient(app) as cliente:
        assert cliente.get("/anomalias").status_code == 401
        cabecera = {"X-API-Key": "prueba"}
        r = cliente.get("/anomalias", params=dict(id_sucursal=1, desde="2024-01-01", hasta="2024-12-31", tipo="caida"), headers=cabecera)
        assert r.status_code == 200
        assert all(f["id_sucursal"] == 1 and f["tipo"] == "caida" and f["sucursal"]
                   and "2024-01-01" <= f["fecha"] <= "2024-12-31" for f in r.json())
        assert cliente.get("/anomalias?tipo=otro", headers=cabecera).status_code == 422
